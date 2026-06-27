"""Build a self-contained 3-tower data file for Modal training: per turn, the query, positive,
negatives, AND the recently-played track ids (history tower). Resolves history from the train
split locally so the Modal job needs only this file + doc_corpus.jsonl (no HF dataset).

    python scripts/rerank/build_3tower_data.py
"""
import json, sys
sys.path.insert(0, "scripts/rerank")
from train_3tower import load_docs, load_played

PAIRS = "exp/analysis/retrieval_exploration/retriever_pairs.jsonl"
DOCS = "exp/analysis/retrieval_exploration/doc_corpus.jsonl"
OUT = "exp/analysis/retrieval_exploration/3tower_data.jsonl"
KMAX = 8  # store up to 8 recent plays; the trainer caps to --k-hist

doc = load_docs(DOCS); valid = set(doc)
print(f"docs {len(valid)}; loading played history...", flush=True)
played = load_played("train")
n = 0; nh = 0
with open(OUT, "w") as f:
    for line in open(PAIRS):
        r = json.loads(line)
        if r["pos_id"] not in valid:
            continue
        hist = [x for tn in range(1, r["tn"]) for x in played.get(r["sid"], {}).get(tn, []) if x in valid][-KMAX:]
        nh += 1 if hist else 0
        f.write(json.dumps({"q": r["q"], "gpa": r["gpa"], "pos": r["pos_id"],
                            "negs_filt": r["negs_filt"], "negs_raw": r["negs_raw"], "hist": hist}) + "\n")
        n += 1
print(f"DONE wrote {n} turns ({100*nh/max(1,n):.0f}% with history) -> {OUT}", flush=True)
