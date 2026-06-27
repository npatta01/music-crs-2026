"""M0a — build the unified per-track text-doc corpus for the bi-encoder retriever.

Doc template (byte-identical at train/index/serve — see plan):
    "Music track: <artist> — <title> (<year>) | tags: <<=5 cleaned> | known for: <line>"

Two variants are written per track so the GATE-0 collapse gate can A/B them:
    doc      = with the LLM "known for" line  (omitted when the LLM abstains)
    doc_nokf = without the known-for line

Tag cleaning (tags are very noisy: median ~17, max ~105, full of personal/listmaker junk):
  - case-fold + dedup, drop an explicit junk blacklist + username/year-ish tokens,
  - keep only tags that are common across the catalog (genres are frequent, personal junk
    is rare), then rank a track's surviving tags by global frequency and cap to 5.

Known-for is generated ONCE per unique artist (dedup; ~9k artists), concurrently, cached to
disk and resumable. The prompt is instructed to abstain ("UNKNOWN") for artists it doesn't
recognize, so tail artists get NO hallucinated line (field-dropout in training also trains
for a missing known-for).

Run from the main checkout (paths are relative). Examples:
    python scripts/rerank/build_doc_corpus.py --skip-known-for      # fast base pass, no network
    python scripts/rerank/build_doc_corpus.py --workers 24          # full, with known-for
"""
from __future__ import annotations
import argparse, json, os, re, sys, threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import lancedb

OUT_DIR = "exp/analysis/retrieval_exploration"
DOC_OUT = f"{OUT_DIR}/doc_corpus.jsonl"  # derived (23M), gitignored — rebuilt from KF_CACHE + catalog
# Committed source-of-truth (~1.5M): the LLM-generated per-artist "known for" lines. Versioned in
# data/ (NOT the ignored exp/ tree) so doc_corpus.jsonl can be rebuilt WITHOUT re-running ~9k LLM
# calls. This script reads it on start and writes new artists back into the same file.
KF_CACHE = "data/artist_knownfor.json"

# Clearly-personal / non-genre tags to drop even when frequent.
JUNK_TAGS = {
    "favorites", "favourites", "favorite", "favourite", "favs", "fav", "loved", "love",
    "awesome", "beautiful", "cool", "nice", "good", "great", "amazing", "best", "perfect",
    "seen live", "want to see live", "owned", "albums i own", "my music", "my favorites",
    "spotify", "soundcloud", "youtube", "checked", "to listen", "listen", "music",
    "favorite songs", "favorite tracks", "all", "other", "misc", "various", "untagged",
    "male vocalists", "female vocalists", "male vocalist", "female vocalist",
}
# allow decade tokens like "90s", "00s", "2010s"; drop bare 4-digit years and username-ish tokens.
_DECADE = re.compile(r"^(19|20)?\d0s$")
_HAS_DIGIT = re.compile(r"\d")


def clean_tag(tag: str) -> str | None:
    t = (tag or "").strip().lower()
    if not t or len(t) < 2 or len(t) > 30:
        return None
    if t in JUNK_TAGS:
        return None
    if _HAS_DIGIT.search(t) and not _DECADE.match(t):
        return None  # drops bare years (1996), usernames (boa12, lizvelrene2010)
    return t


def load_catalog():
    db = lancedb.connect("cache/lancedb")
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
                     "yr": yr, "tags_raw": list(dict.fromkeys(raw_tags))})  # dedup, keep order
    return info


def select_tags(info, min_freq: int, cap: int):
    """Keep catalog-common tags, rank each track's by global frequency, cap."""
    freq = Counter()
    for d in info:
        for tg in d["tags_raw"]:
            freq[tg] += 1
    for d in info:
        kept = [tg for tg in d["tags_raw"] if freq[tg] >= min_freq]
        kept.sort(key=lambda tg: -freq[tg])
        d["tags"] = kept[:cap]
    return freq


KF_PROMPT = (
    "In ONE concise sentence, what is the musical artist '{artist}' best known for "
    "— their genre, style, sound, and era? "
    "If you do not recognize this specific artist, reply with exactly: UNKNOWN"
)


def gen_known_for(artists, model, workers, max_tokens, cache):
    import litellm
    todo = [a for a in artists if a and a not in cache]
    print(f"known-for: {len(artists)} artists, {len(todo)} to fetch ({len(cache)} cached)", flush=True)
    lock = threading.Lock(); done = [0]

    def one(a):
        try:
            r = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": KF_PROMPT.format(artist=a)}],
                temperature=0, max_tokens=max_tokens,
            )
            txt = (r.choices[0].message.content or "").strip()
        except Exception as e:
            txt = ""  # leave uncached on hard error so a rerun retries
            with lock:
                if done[0] < 5:
                    print(f"  err {a!r}: {repr(e)[:120]}", flush=True)
            return a, None
        if txt.upper().startswith("UNKNOWN") or len(txt) < 3:
            txt = ""  # abstain -> no line
        return a, txt

    if todo:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for a, txt in ex.map(one, todo):
                if txt is None:
                    continue
                with lock:
                    cache[a] = txt; done[0] += 1
                    if done[0] % 500 == 0:
                        print(f"  {done[0]}/{len(todo)}", flush=True)
                        json.dump(cache, open(KF_CACHE, "w"))
    json.dump(cache, open(KF_CACHE, "w"))
    have = sum(1 for a in artists if cache.get(a))
    print(f"known-for: coverage {have}/{len(artists)} = {100*have/max(1,len(artists)):.1f}% "
          f"(abstentions excluded)", flush=True)
    return cache


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DOC_OUT)
    ap.add_argument("--min-tag-freq", type=int, default=20)
    ap.add_argument("--cap-tags", type=int, default=5)
    ap.add_argument("--skip-known-for", action="store_true", help="base pass only, no network")
    ap.add_argument("--model", default="openrouter/deepseek/deepseek-chat")
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--max-tokens", type=int, default=120)
    a = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)

    info = load_catalog()
    freq = select_tags(info, a.min_tag_freq, a.cap_tags)
    n_with_tags = sum(1 for d in info if d["tags"])
    print(f"catalog: {len(info)} tracks; kept-tag coverage {n_with_tags}/{len(info)} "
          f"({100*n_with_tags/len(info):.1f}%); {sum(v>=a.min_tag_freq for v in freq.values())} "
          f"tags above freq>={a.min_tag_freq}", flush=True)

    cache = {}
    if not a.skip_known_for:
        if os.path.exists(KF_CACHE):
            cache = json.load(open(KF_CACHE))
        artists = sorted({d["ar"] for d in info if d["ar"]})
        cache = gen_known_for(artists, a.model, a.workers, a.max_tokens, cache)

    n = 0
    with open(a.out, "w") as f:
        for d in info:
            head = f"Music track: {d['ar']} — {d['nm']}"
            if d["yr"]:
                head += f" ({d['yr']})"
            tagstr = ", ".join(d["tags"])
            base = head + (f" | tags: {tagstr}" if tagstr else "")
            kf = cache.get(d["ar"], "")
            doc = base + (f" | known for: {kf}" if kf else "")
            f.write(json.dumps({"track_id": d["tid"], "artist": d["ar"],
                                "doc": doc, "doc_nokf": base}) + "\n")
            n += 1
    print(f"DONE wrote {n} docs -> {a.out}", flush=True)
    # show a few examples
    for d in info[:3]:
        kf = cache.get(d["ar"], "")
        head = f"Music track: {d['ar']} — {d['nm']}" + (f" ({d['yr']})" if d["yr"] else "")
        base = head + (f" | tags: {', '.join(d['tags'])}" if d["tags"] else "")
        print("  e.g.:", (base + (f" | known for: {kf}" if kf else ""))[:200], flush=True)


if __name__ == "__main__":
    main()
