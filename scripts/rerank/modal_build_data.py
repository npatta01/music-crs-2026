"""Round 0 (Issue #153) — rebuild the bi-encoder data ON MODAL, GOAL-FREE.

Why: Blind Dataset B removes `conversation_goal` (and makes half the users cold-start), so the
retriever input must be goal-free / profile-free to generalize. We also do NOT trust whatever is
currently on the `biencoder-data` volume — so we rebuild the doc corpus from the authoritative
catalog (the LanceDB on the `music-crs-models` volume) and rebuild the per-variant query data from
the HF conversations, then verify, all on Modal (no local compute).

What it does (one CPU function):
  1. doc_corpus.jsonl  — rebuilt from /catalog/lancedb (music_track_catalog) + the cached, uploaded
     artist_knownfor.json (no LLM calls). Byte-identical template to build_doc_corpus.py. We read
     the OLD on-volume corpus first and report how many docs changed (verify, don't blind-trust).
  2. retriever_pairs.jsonl — REUSED as-is from the volume (validated labels + mined negatives;
     goal-agnostic). Not rebuilt (re-mining risks non-determinism).
  3. input_variants/{pairs,eval}_<v>.jsonl — rebuilt GOAL-FREE for the in-scope variants
     (baseline, v_tok, v_struct, v_struct_pt). Rows whose query body is empty (no prev AND no now
     user turn — e.g. cold-start first turn) are DROPPED and counted (a content-free query is a
     degenerate MNRL positive / meaningless eval row).

Setup (one-time small uploads to the volume), then run:
    modal volume put --force biencoder-data \
        exp/analysis/retrieval_exploration/artist_knownfor.json /artist_knownfor.json
    modal volume put --force biencoder-data \
        exp/analysis/rerank/devset_lanes_v10.jsonl /devset_lanes_v10.jsonl
    modal run scripts/rerank/modal_build_data.py
"""
import modal

image = (modal.Image.debian_slim(python_version="3.12")
    .pip_install("lancedb", "datasets", "numpy", "huggingface_hub", "hf_transfer")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"}))
app = modal.App("scout-build-data", image=image)
catalog_vol = modal.Volume.from_name("music-crs-models")          # holds /lancedb/music_track_catalog.lance
data_vol = modal.Volume.from_name("biencoder-data", create_if_missing=True)
hf_vol = modal.Volume.from_name("hf-cache", create_if_missing=True)

DATASET = "talkpl-ai/TalkPlayData-Challenge-Dataset"
MOVES = "MOVES_TOWARD_GOAL"
# GOAL-FREE, profile-free variants only (user variants dropped for Blind-B generalization).
VARIANTS = ["baseline", "v_tok", "v_struct", "v_struct_pt"]


# ----------------------------- doc corpus (from build_doc_corpus.py, verbatim logic) -----------
import re
_DECADE = re.compile(r"^(19|20)?\d0s$")
_HAS_DIGIT = re.compile(r"\d")
JUNK_TAGS = {
    "favorites", "favourites", "favorite", "favourite", "favs", "fav", "loved", "love",
    "awesome", "beautiful", "cool", "nice", "good", "great", "amazing", "best", "perfect",
    "seen live", "want to see live", "owned", "albums i own", "my music", "my favorites",
    "spotify", "soundcloud", "youtube", "checked", "to listen", "listen", "music",
    "favorite songs", "favorite tracks", "all", "other", "misc", "various", "untagged",
    "male vocalists", "female vocalists", "male vocalist", "female vocalist",
}


def clean_tag(tag):
    t = (tag or "").strip().lower()
    if not t or len(t) < 2 or len(t) > 30:
        return None
    if t in JUNK_TAGS:
        return None
    if _HAS_DIGIT.search(t) and not _DECADE.match(t):
        return None
    return t


def load_catalog(lancedb_dir):
    import lancedb
    db = lancedb.connect(lancedb_dir)
    t = db.open_table("music_track_catalog")
    rows = t.search().select(
        ["track_id", "track_name", "artist_name", "release_date", "tag_list"]
    ).limit(60000).to_list()
    info = []
    for r in rows:
        nm = r.get("track_name"); nm = (nm[0] if isinstance(nm, list) and nm else nm) or ""
        ar = r.get("artist_name"); ar = (ar[0] if isinstance(ar, list) and ar else ar) or ""
        yr = str(r.get("release_date") or "")[:4]
        raw_tags = [c for c in (clean_tag(x) for x in (r.get("tag_list") or [])) if c]
        info.append({"tid": str(r["track_id"]), "ar": str(ar), "nm": str(nm),
                     "yr": yr, "tags_raw": list(dict.fromkeys(raw_tags))})
    return info


def select_tags(info, min_freq=20, cap=5):
    from collections import Counter
    freq = Counter()
    for d in info:
        for tg in d["tags_raw"]:
            freq[tg] += 1
    for d in info:
        kept = [tg for tg in d["tags_raw"] if freq[tg] >= min_freq]
        kept.sort(key=lambda tg: -freq[tg])
        d["tags"] = kept[:cap]
    return freq


def build_doc_corpus(lancedb_dir, kf_path):
    import json
    info = load_catalog(lancedb_dir)
    select_tags(info, 20, 5)
    kf = json.load(open(kf_path)) if __import__("os").path.exists(kf_path) else {}
    docs = {}
    for d in info:
        head = f"Music track: {d['ar']} — {d['nm']}" + (f" ({d['yr']})" if d["yr"] else "")
        base = head + (f" | tags: {', '.join(d['tags'])}" if d["tags"] else "")
        cache_kf = kf.get(d["ar"], "")
        doc = base + (f" | known for: {cache_kf}" if cache_kf else "")
        docs[d["tid"]] = {"track_id": d["tid"], "artist": d["ar"], "doc": doc, "doc_nokf": base}
    return docs, len(kf)


# ----------------------------- query variants (GOAL-FREE) --------------------------------------
def short_track(doc):
    # "artist — title" from "Music track: artist — title (year) | tags...": drop tags/known-for
    # and a TRAILING (YYYY) only, so titles containing "(...)" are preserved (advisor fix).
    if not doc:
        return ""
    s = doc.split(" | ")[0].replace("Music track: ", "", 1)
    return re.sub(r"\s*\(\d{4}\)\s*$", "", s).strip()


def prev_track_str(played_sid, tn, doc_by_tid):
    for k in range(tn - 1, 0, -1):
        if played_sid.get(k):
            return short_track(doc_by_tid.get(played_sid[k][-1], ""))
    return ""


def build_q(variant, prev, now, pt):
    """GOAL-FREE query renderer (no [goal]/<|goal|> anywhere). Returns '' iff body is empty."""
    turns = " / ".join(t for t in (prev, now) if t)
    if variant == "baseline":
        return ("[msg] " + turns).strip() if turns else ""
    if variant in ("v_struct", "v_struct_pt"):
        s = ""
        if prev: s += f"[prev] {prev}"
        if now: s += (" " if s else "") + f"[now] {now}"
        if variant == "v_struct_pt" and pt: s += (" " if s else "") + f"[prev_track] {pt}"
        return s.strip()
    if variant == "v_tok":
        s = ""
        if prev: s += f"<|prev|> {prev}"
        if now: s += (" " if s else "") + f"<|now|> {now}"
        return s.strip()
    raise ValueError(f"unknown variant {variant!r}")


def load_split(split):
    """-> per sid: um{tn:user_text}, gpa{(sid,tn):assessment}, played{tn:[tids]}. Goal/profile dropped."""
    import ast
    from datasets import load_dataset
    ds = load_dataset(DATASET, split=split)
    um, gpa, played = {}, {}, {}
    for r in ds:
        conv = r.get("conversations")
        if isinstance(conv, str): conv = ast.literal_eval(conv)
        sid = str(r["session_id"]); u, p = {}, {}
        for m in conv:
            tn = int(m["turn_number"])
            if m["role"] == "user": u[tn] = str(m["content"])
            elif m["role"] == "music": p.setdefault(tn, []).append(str(m["content"]))
        um[sid] = u; played[sid] = p
        g = r.get("goal_progress_assessments")
        if isinstance(g, str): g = ast.literal_eval(g)
        for a in (g or []):
            gpa[(sid, int(a["turn_number"]))] = a.get("goal_progress_assessment")
    return um, gpa, played


@app.function(volumes={"/catalog": catalog_vol, "/data": data_vol,
              "/root/.cache/huggingface": hf_vol},
              secrets=[modal.Secret.from_name("huggingface")],
              cpu=4.0, memory=32768, timeout=7200)
def build():
    import json, os
    print("[1/3] rebuilding doc_corpus from /catalog/lancedb ...", flush=True)
    docs, n_kf = build_doc_corpus("/catalog/lancedb", "/data/artist_knownfor.json")
    print(f"  catalog tracks={len(docs)} | known-for cached artists={n_kf}", flush=True)

    # verify vs the OLD on-volume corpus before overwriting
    old_path = "/data/doc_corpus.jsonl"
    if os.path.exists(old_path):
        old = {}
        for line in open(old_path):
            d = json.loads(line); old[d["track_id"]] = d["doc"]
        changed = sum(1 for t, d in docs.items() if old.get(t) != d["doc"])
        added = len(set(docs) - set(old)); removed = len(set(old) - set(docs))
        print(f"  VERIFY vs old corpus: {len(old)} old -> {len(docs)} new | "
              f"docs changed={changed} added={added} removed={removed}", flush=True)
    else:
        print("  (no old corpus on volume to compare)", flush=True)

    with open(old_path, "w") as f:
        for t in docs:
            f.write(json.dumps(docs[t]) + "\n")
    doc_by_tid = {t: docs[t]["doc"] for t in docs}
    valid_docs = set(docs)
    print(f"  wrote {len(docs)} docs -> {old_path}", flush=True)

    print("[2/3] loading conversations (train + test) from HF ...", flush=True)
    um_tr, gpa_tr, played_tr = load_split("train")
    um_te, gpa_te, played_te = load_split("test")
    print(f"  train sessions={len(um_tr)} | test sessions={len(um_te)}", flush=True)

    pairs = [json.loads(l) for l in open("/data/retriever_pairs.jsonl")]
    print(f"  reusing {len(pairs)} validated retriever_pairs (labels + negs)", flush=True)

    print("[3/3] building GOAL-FREE input_variants ...", flush=True)
    out_dir = "/data/input_variants"; os.makedirs(out_dir, exist_ok=True)
    writers = {v: (open(f"{out_dir}/pairs_{v}.jsonl", "w"),
                   open(f"{out_dir}/eval_{v}.jsonl", "w")) for v in VARIANTS}
    samples = {}

    # TRAIN pairs: rebuild q goal-free; keep pos_id/negs/gpa; drop empty-body + missing-session rows
    n_pair = miss = empty_pair = n_moves = n_flip = 0
    for r in pairs:
        sid, tn = r["sid"], int(r["tn"])
        if sid not in um_tr:
            miss += 1; continue
        prev, now = um_tr[sid].get(tn - 1, ""), um_tr[sid].get(tn, "")
        if not (prev or now):
            empty_pair += 1; continue
        pt = prev_track_str(played_tr.get(sid, {}), tn, doc_by_tid)
        # OFF-BY-ONE FIX (memory goal-progress-label-offbyone): assessment[tn] grades track[tn-1];
        # the positive pos_id=track[tn] is graded by assessment[tn+1]. The last played track of a
        # session is unlabeled (gpa None -> the trainer's gpa!=MOVES filter drops it).
        corr_gpa = gpa_tr.get((sid, tn + 1))
        if corr_gpa == MOVES: n_moves += 1
        if (r["gpa"] == MOVES) != (corr_gpa == MOVES): n_flip += 1
        for v in VARIANTS:
            q = build_q(v, prev, now, pt)
            writers[v][0].write(json.dumps({"sid": sid, "tn": tn, "gpa": corr_gpa, "q": q,
                                            "pos_id": r["pos_id"], "negs_filt": r["negs_filt"],
                                            "negs_raw": r["negs_raw"]}) + "\n")
            samples.setdefault(v, q)
        n_pair += 1

    # DEVSET eval: test MOVES turns with a GT played track; drop empty-body
    n_eval = empty_eval = no_gt = 0
    for sid in um_te:
        for tn in sorted(um_te[sid]):
            if gpa_te.get((sid, tn + 1)) != MOVES:   # OFF-BY-ONE FIX: track[tn] graded by assessment[tn+1]
                continue
            gt_list = played_te.get(sid, {}).get(tn, [])
            if not gt_list or gt_list[0] not in valid_docs:
                no_gt += 1; continue
            prev, now = um_te[sid].get(tn - 1, ""), um_te[sid].get(tn, "")
            if not (prev or now):
                empty_eval += 1; continue
            pt = prev_track_str(played_te.get(sid, {}), tn, doc_by_tid)
            for v in VARIANTS:
                q = build_q(v, prev, now, pt)
                writers[v][1].write(json.dumps({"sid": sid, "tn": tn, "q": q, "gt": gt_list[0]}) + "\n")
            n_eval += 1

    for v in VARIANTS:
        writers[v][0].close(); writers[v][1].close()
    data_vol.commit()

    print(f"\nDONE. train pairs kept={n_pair} (skipped: missing-session={miss}, empty-body={empty_pair}); "
          f"corrected MOVES positives={n_moves} (label flips vs buggy={n_flip}); "
          f"devset eval turns={n_eval} (skipped: empty-body={empty_eval}, no/oos GT={no_gt})", flush=True)
    for v in VARIANTS:
        q = samples.get(v, "")
        assert "[goal]" not in q and "<|goal|>" not in q, f"GOAL LEAKED into {v}: {q!r}"
        print(f"  [{v}] sample query: {q[:160]}", flush=True)
    print("  (asserted no [goal]/<|goal|> in any sample) — verify with: modal volume ls biencoder-data /input_variants",
          flush=True)


@app.local_entrypoint()
def main():
    build.remote()
