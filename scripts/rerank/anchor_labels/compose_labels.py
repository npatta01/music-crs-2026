"""Compose the final cleaned label set from the two cheap judges + the Opus arbiter.

Per turn:
  - each judge -> a label via the deterministic rule (anchoring = asked_diff AND same_artist).
  - judges AGREE  -> take it           (source=both_agree,     weight 1.0 ; HOLD -> 0.3)
  - judges DISAGREE -> Opus arbitrates  (source=opus_arbitrated, weight 0.6)  [covers ALL conflict types]

Emits four files into <out-dir>:
  judge1_<m>.jsonl, judge2_<m>.jsonl  — per-model per-turn judgments
  opus_arbiter.jsonl                  — Opus's call on every disagreement
  final_labels.jsonl                  — the clean, human-readable combined file (no raw data needed)
"""
from __future__ import annotations
import argparse, json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, REPO)
from scripts.rerank.anchor_labels.convo_context import load_index, load_docmap, prev_artist  # noqa: E402

# Artifacts dir: defaults to the local repo's exp/analysis/retrieval_exploration.
# Set ANCHOR_DATA_DIR to point elsewhere (e.g. a shared cache; see scripts/setup_worktree_cache.py).
DD = os.environ.get("ANCHOR_DATA_DIR", os.path.join(REPO, "exp/analysis/retrieval_exploration"))


def label_and_reason(asked_diff, same_artist, content, reaction):
    anchoring = bool(asked_diff) and bool(same_artist)
    if anchoring:
        return "NEGATIVE", "artist_anchoring", anchoring
    if content == "invalid":
        return "NEGATIVE", "content_violation", anchoring
    if content == "valid":
        if reaction == "MOVES":
            return "POSITIVE", "fits_and_liked", anchoring
        return "DROP", "fit_but_disliked", anchoring
    return "HOLD", "unverifiable", anchoring


def short_track(meta):
    return meta.replace("Music track: ", "").split(" | ")[0].strip()


def current_ask(request):
    if "USER (current request):" in request:
        return request.split("USER (current request):")[-1].split("\n")[0].strip()
    return request.split("USER:")[-1].split("\n")[0].strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", default=f"{DD}/judge_bakeoff/gold_judge_sheet.jsonl")
    ap.add_argument("--judge1", default=f"{DD}/judge_bakeoff/records_gold_gemma_final.jsonl")
    ap.add_argument("--judge2", default=f"{DD}/judge_bakeoff/records_gold_dsv4flash_final.jsonl")
    ap.add_argument("--j1-name", default="gemma")
    ap.add_argument("--j2-name", default="deepseek_v4_flash")
    ap.add_argument("--arbiter", default=None,
                    help="Opus AXIS-LEVEL arbiter for the conflicts: a {'sid|tn':{asked_diff,content}} "
                         ".json OR a .jsonl of judge records. Conflicts with no entry -> UNRESOLVED.")
    ap.add_argument("--split", required=True, help="train | test — MUST match the sheet's split")
    ap.add_argument("--out-dir", default=f"{DD}/labels_demo")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    sheet = {(r["sid"], r["tn"]): r for r in (json.loads(l) for l in open(a.sheet))}
    J1 = {(r["sid"], r["tn"]): r for r in (json.loads(l) for l in open(a.judge1))}
    J2 = {(r["sid"], r["tn"]): r for r in (json.loads(l) for l in open(a.judge2))}
    # arbiter accepted as axis-level json {sid|tn:{asked_diff,content}} OR jsonl judge-records.
    ARB = {}
    if a.arbiter and os.path.exists(a.arbiter):
        if a.arbiter.endswith(".jsonl"):
            for line in open(a.arbiter):
                r = json.loads(line)
                # an errored arbiter call has a fabricated asked_diff=False -> force BOTH axes None so
                # the conflict goes UNRESOLVED instead of consuming a fake verdict.
                if r.get("err"):
                    ARB[(r["sid"], r["tn"])] = {"asked_diff": None, "content": None}
                else:
                    ARB[(r["sid"], r["tn"])] = {"asked_diff": r.get("asked_diff"), "content": r.get("content")}
        else:
            for kk, v in json.load(open(a.arbiter)).items():
                sid, tn = kk.rsplit("|", 1); ARB[(sid, int(tn))] = v
    print("loading conversation index for just-played artist ...", flush=True)
    sid2row = load_index(a.split)
    doc = load_docmap(f"{DD}/doc_corpus.jsonl")
    bad = [k for k in (set(J1) | set(J2)) if k[0] not in sid2row]
    if bad:
        raise SystemExit(f"{len(bad)} sids absent from '{a.split}' index — wrong --split? e.g. {bad[:3]}")

    keys = sorted(set(J1) & set(J2) & set(sheet))
    j1_out, j2_out, arb_out, final_out, conflict_keys, dropped = [], [], [], [], [], []
    n_agree = n_arb = n_unres = 0

    for k in keys:
        sid, tn = k
        s = sheet[k]
        same = bool(s["same_artist"]); react = s["gt_label"]
        r1, r2 = J1[k], J2[k]
        if r1.get("err") or r2.get("err"):         # a judge failed -> not labelable; surface, never guess
            dropped.append(k); continue
        l1, why1, anc1 = label_and_reason(r1["asked_diff"], same, r1["content"], react)
        l2, why2, anc2 = label_and_reason(r2["asked_diff"], same, r2["content"], react)
        j1_out.append({"sid": sid, "tn": tn, "asked_diff": r1["asked_diff"], "same_artist": same,
                       "anchoring": anc1, "content": r1["content"], "label": l1})
        j2_out.append({"sid": sid, "tn": tn, "asked_diff": r2["asked_diff"], "same_artist": same,
                       "anchoring": anc2, "content": r2["content"], "label": l2})

        if l1 == l2:                               # judges agree
            n_agree += 1
            ad, ct, lab, why = r1["asked_diff"], r1["content"], l1, why1
            source, weight = "both_agree", (0.3 if lab == "HOLD" else 1.0)
        else:                                       # disagree -> needs the Opus arbiter
            conflict_keys.append(k)
            o = ARB.get(k)
            if not o or (o.get("asked_diff") is None and o.get("content") is None):
                n_unres += 1                        # no arbiter entry -> surface loudly, NEVER silent-HOLD
                ad, ct, lab, why = None, None, "UNRESOLVED", "needs_arbiter"
                source, weight = "unarbitrated", 0.0
            else:
                n_arb += 1
                ad, ct = o.get("asked_diff"), o.get("content")
                lab, why, _ = label_and_reason(ad, same, ct, react)
                source, weight = "opus_arbitrated", 0.6
                arb_out.append({"sid": sid, "tn": tn, "judge1_said": l1, "judge2_said": l2,
                                "opus_asked_diff": ad, "opus_content": ct, "opus_label": lab})

        final_out.append({
            "sid": sid, "tn": tn,
            "current_ask": current_ask(s["request"])[:240],
            "just_played": prev_artist(sid, tn, sid2row, doc),
            "candidate_track": short_track(s["track_meta"]),
            "listener_reaction": react,
            "same_artist": same,
            "asked_for_different_artist": (None if ad is None else bool(ad)),
            "anchoring": ((bool(ad) and same) if ad is not None else None),
            "content_fit": ct,
            "label": lab,
            "label_reason": why,
            "confidence_weight": weight,
            "decided_by": source,
        })

    def dump(name, rows):
        p = os.path.join(a.out_dir, name)
        with open(p, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        return p

    dump(f"judge1_{a.j1_name}.jsonl", j1_out)
    dump(f"judge2_{a.j2_name}.jsonl", j2_out)
    dump("opus_arbiter.jsonl", arb_out)
    # the EXACT arbiter input, derived from THIS judge pair (fixes the build_seeboth pair-mismatch):
    dump("conflicts_sheet.jsonl", [sheet[k] for k in conflict_keys])
    fp = dump("final_labels.jsonl", final_out)

    from collections import Counter
    print(f"\ncomposed {len(final_out)} turns from {len(keys)} ({len(dropped)} dropped — a judge errored)")
    print(f"  {n_agree} agreed | {n_arb} arbiter-resolved | {n_unres} UNRESOLVED (conflicts with no arbiter entry)")
    if n_unres:
        print(f"  ACTION: run the Opus arbiter on conflicts_sheet.jsonl ({len(conflict_keys)} rows), "
              f"then re-run with --arbiter <its output>")
    print("final label distribution:", dict(Counter(r["label"] for r in final_out)))
    print("by reason:", dict(Counter(r["label_reason"] for r in final_out)))
    print(f"-> {a.out_dir}/  [judge1, judge2, opus_arbiter, conflicts_sheet, final_labels]")


if __name__ == "__main__":
    main()
