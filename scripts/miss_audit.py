"""Miss audit: feature-rescue analysis over ALL in-pool misses.

Population: devset turns where the GT track is inside the union@K of branch
pools but NOT in the final top-20 — the reranker's addressable set. For every
candidate feature we ask, per miss: would this feature alone have ranked the
GT above the median (or max) of the tracks currently occupying the top-20?

Outputs (exp/analysis/miss_audit/):
  aggregates.json   per-feature rescue rates, overall + by stratum
  report.md         human-readable summary
  sample.csv        stratified sample for the LLM/hand judgment pass

Usage:
  python scripts/miss_audit.py \
      --trace exp/inference/devset/<tid>_trace.jsonl \
      --ground-truth exp/ground_truth/devset.json \
      --db-uri <repo>/cache/lancedb \
      --tag-index <repo>/cache/tag_embedding_index/qwen_0_6b.npz \
      --union-k 200 --sample-size 120
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mcrs.qu_modules.tag_resolver import (  # noqa: E402
    TagEmbeddingIndex,
    TieredTagResolver,
    catalog_tag_key,
)

FEATURES = [
    "same_artist_session",
    "same_album_last",
    "same_album_any",
    "cf_last",
    "cf_centroid",
    "user_cf",
    "pop_pct",
    "era_pop_pct",
    "year_in_constraint",
    "recent_at_session",
    "tag_overlap",
    "tag_overlap_idf",
    "culture_match",
    "age_era_affinity",
]


def load_catalog(db_uri: str, table_name: str):
    import lancedb

    db = lancedb.connect(db_uri)
    table = db.open_table(table_name)
    cols = ["track_id", "popularity", "release_date", "artist_id", "album_id", "tag_list", "cf_bpr"]
    df = table.to_pandas()[[c for c in cols if c in table.schema.names]]
    cat: dict[str, dict] = {}
    cf_rows, cf_ids = [], []
    pops, years = {}, {}
    for row in df.itertuples(index=False):
        tid = str(row.track_id)
        artist_ids = [str(a) for a in (row.artist_id if isinstance(row.artist_id, (list, np.ndarray)) else [row.artist_id]) if a]
        album_ids = [str(a) for a in (row.album_id if isinstance(row.album_id, (list, np.ndarray)) else [row.album_id]) if a]
        rd = row.release_date
        year = None
        rdate = None
        if rd is not None:
            try:
                rdate = rd if isinstance(rd, date) else date.fromisoformat(str(rd)[:10])
                year = rdate.year
            except Exception:
                pass
        raw_tags = row.tag_list
        if raw_tags is None:
            raw_tags = []
        tags = [str(t) for t in raw_tags]
        cat[tid] = {
            "artists": set(artist_ids),
            "albums": set(album_ids),
            "year": year,
            "rdate": rdate,
            "pop": float(row.popularity) if row.popularity is not None else 0.0,
            "tag_keys": {catalog_tag_key(t) for t in tags} - {""},
        }
        pops[tid] = cat[tid]["pop"]
        if year is not None:
            years[tid] = year
        if row.cf_bpr is not None and len(row.cf_bpr):
            cf_ids.append(tid)
            cf_rows.append(np.asarray(row.cf_bpr, dtype=np.float32))
    cf = np.vstack(cf_rows)
    cf /= np.maximum(np.linalg.norm(cf, axis=1, keepdims=True), 1e-9)
    cf_index = {tid: i for i, tid in enumerate(cf_ids)}

    # global + per-year popularity percentiles
    all_pop = np.sort(np.array(list(pops.values())))
    def pct(p: float) -> float:
        return float(np.searchsorted(all_pop, p) / max(len(all_pop), 1))
    pop_pct = {tid: pct(p) for tid, p in pops.items()}
    by_year: dict[int, list] = defaultdict(list)
    for tid, y in years.items():
        by_year[y].append(pops[tid])
    year_sorted = {y: np.sort(np.array(v)) for y, v in by_year.items()}
    era_pop_pct = {}
    for tid, y in years.items():
        arr = year_sorted[y]
        era_pop_pct[tid] = float(np.searchsorted(arr, pops[tid]) / max(len(arr), 1))

    # tag document frequency for IDF weighting
    df_counter: Counter = Counter()
    for tid, c in cat.items():
        df_counter.update(c["tag_keys"])
    n_tracks = len(cat)
    tag_idf = {t: math.log((n_tracks + 1) / (c + 1)) for t, c in df_counter.items()}

    return cat, cf, cf_index, pop_pct, era_pop_pct, tag_idf


def load_sessions():
    from datasets import load_dataset

    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")
    sessions = {}
    for row in ds:
        sid = str(row["session_id"])
        played_by_turn: dict[int, list[str]] = {}
        user_text_by_turn: dict[int, str] = {}
        seq: list[str] = []
        for msg in row["conversations"]:
            tn = int(msg["turn_number"])
            if msg["role"] == "music":
                played_by_turn.setdefault(tn, []).append(str(msg["content"]))
            elif msg["role"] == "user":
                user_text_by_turn[tn] = str(msg["content"])
        profile = row.get("user_profile") or {}
        goal = row.get("conversation_goal") or {}
        sessions[sid] = {
            "played_by_turn": played_by_turn,
            "user_text_by_turn": user_text_by_turn,
            "session_date": str(row.get("session_date") or ""),
            "age": profile.get("age"),
            "culture": str(profile.get("preferred_musical_culture") or ""),
            "goal_category": str(goal.get("category") or ""),
            "goal_specificity": str(goal.get("specificity") or ""),
        }
    return sessions


def load_user_cf():
    from mcrs.qu_modules.user_embeddings import UserEmbeddings

    ue = UserEmbeddings()
    fields = tuple(ue.available_fields)
    field = "cf_bpr" if "cf_bpr" in fields else (fields[0] if fields else None)
    if field is None:
        return {}
    out = {}
    for uid, vec in ue._vectors.get(field, {}).items():
        v = np.asarray(vec, dtype=np.float32)
        n = np.linalg.norm(v)
        if n > 0:
            out[str(uid)] = v / n
    return out


def state_tag_keys(trace_row: dict, resolver: TieredTagResolver) -> set[str]:
    keys: set[str] = set()
    res = trace_row["trace"].get("resolver") or {}
    for tag in res.get("positive_tags") or []:
        r = resolver.resolve(str(tag))
        keys.update(m.tag for m in r.matches)
        keys.add(catalog_tag_key(str(tag)))
    state = trace_row["trace"].get("state") or {}
    for fact in state.get("facts") or []:
        if fact.get("type") == "attribute" and fact.get("value"):
            r = resolver.resolve(str(fact["value"]))
            keys.update(m.tag for m in r.matches)
    return keys - {""}


def candidate_features(tid, cat, cf, cf_index, pop_pct, era_pop_pct, tag_idf,
                       sess, played, last_played, centroid_vec, user_vec,
                       q_tag_keys, constraint, session_year):
    c = cat.get(tid)
    if c is None:
        return None
    played_artists = set().union(*(cat[p]["artists"] for p in played if p in cat)) if played else set()
    played_albums = set().union(*(cat[p]["albums"] for p in played if p in cat)) if played else set()
    last_albums = cat[last_played]["albums"] if last_played in cat else set()

    def cf_cos(vec):
        i = cf_index.get(tid)
        if i is None or vec is None:
            return 0.0
        return float(cf[i] @ vec)

    overlap = c["tag_keys"] & q_tag_keys
    year = c["year"]
    in_constraint = 0.0
    if constraint and year is not None:
        s, e = constraint.get("start_year"), constraint.get("end_year")
        if s is not None or e is not None:
            in_constraint = float((s is None or year >= s) and (e is None or year <= e))
    recent = 0.0
    if session_year and year is not None:
        recent = float(abs(session_year - year) <= 1)
    age = sess.get("age")
    age_era = 0.0
    if age and year and sess.get("session_date"):
        try:
            birth = int(sess["session_date"][:4]) - int(age)
            age_era = float(birth + 12 <= year <= birth + 25)
        except Exception:
            pass
    culture_keys = {catalog_tag_key(w) for w in sess.get("culture", "").split()} - {""}
    return {
        "same_artist_session": float(bool(c["artists"] & played_artists)),
        "same_album_last": float(bool(c["albums"] & last_albums)),
        "same_album_any": float(bool(c["albums"] & played_albums)),
        "cf_last": cf_cos(cf[cf_index[last_played]] if last_played in cf_index else None),
        "cf_centroid": cf_cos(centroid_vec),
        "user_cf": cf_cos(user_vec),
        "pop_pct": pop_pct.get(tid, 0.0),
        "era_pop_pct": era_pop_pct.get(tid, 0.0),
        "year_in_constraint": in_constraint,
        "recent_at_session": recent,
        "tag_overlap": float(len(overlap)),
        "tag_overlap_idf": float(sum(tag_idf.get(t, 0.0) for t in overlap)),
        "culture_match": float(len(c["tag_keys"] & culture_keys)),
        "age_era_affinity": age_era,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trace", required=True)
    ap.add_argument("--ground-truth", default="exp/ground_truth/devset.json")
    ap.add_argument("--db-uri", required=True)
    ap.add_argument("--table-name", default="music_track_catalog")
    ap.add_argument("--tag-index", required=True)
    ap.add_argument("--union-k", type=int, default=200)
    ap.add_argument("--sample-size", type=int, default=120)
    ap.add_argument("--out-dir", default="exp/analysis/miss_audit")
    args = ap.parse_args()

    print("loading catalog ...", flush=True)
    cat, cf, cf_index, pop_pct, era_pop_pct, tag_idf = load_catalog(args.db_uri, args.table_name)
    print(f"  {len(cat)} tracks, cf matrix {cf.shape}", flush=True)
    print("loading sessions + user embeddings ...", flush=True)
    sessions = load_sessions()
    user_cf = load_user_cf()
    print(f"  {len(sessions)} sessions, {len(user_cf)} user vectors", flush=True)

    index = TagEmbeddingIndex.load(args.tag_index)
    vocab = frozenset(index.tags)
    resolver = TieredTagResolver(catalog_tag_keys=vocab, substring_vocab=vocab)

    gt_map = {
        (r["session_id"], int(r["turn_number"])): r["ground_truth_track_id"]
        for r in json.load(open(args.ground_truth))
    }

    misses = []
    n_turns = n_hit20 = n_unreachable = 0
    print("streaming trace ...", flush=True)
    with open(args.trace) as f:
        for line_no, line in enumerate(f):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                print(f"  skipping malformed line {line_no}", flush=True)
                continue
            sid, tn = str(row["session_id"]), int(row["turn_number"])
            gt = gt_map.get((sid, tn))
            if gt is None:
                continue
            n_turns += 1
            br = row["trace"]["branches"]
            final20 = [str(t) for t in br["final"]["track_ids"][:20]]
            if gt in final20:
                n_hit20 += 1
                continue
            best_branch, best_rank = None, None
            for pool in br["pools"]:
                for rank, hit in enumerate(pool["hits"], 1):
                    if str(hit[0]) == gt:
                        if best_rank is None or rank < best_rank:
                            best_branch, best_rank = pool["name"], rank
                        break
            if best_rank is None or best_rank > args.union_k:
                n_unreachable += 1
                continue
            fused_rank = None
            for rank, hit in enumerate(br["fused"], 1):
                if str(hit[0]) == gt:
                    fused_rank = rank
                    break

            sess = sessions.get(sid, {})
            played = [t for k in sorted(sess.get("played_by_turn", {})) if k < tn
                      for t in sess["played_by_turn"][k]]
            last_played = played[-1] if played else None
            centroid = None
            idxs = [cf_index[p] for p in played if p in cf_index]
            if idxs:
                centroid = cf[idxs].mean(axis=0)
                n = np.linalg.norm(centroid)
                centroid = centroid / n if n > 0 else None
            user_vec = user_cf.get(str(row.get("user_id") or ""))
            q_keys = state_tag_keys(row, resolver)
            constraint = (row["trace"].get("state") or {}).get("temporal_constraint")
            session_year = None
            if sess.get("session_date"):
                try:
                    session_year = int(sess["session_date"][:4])
                except Exception:
                    pass

            def feats(tid):
                return candidate_features(
                    tid, cat, cf, cf_index, pop_pct, era_pop_pct, tag_idf,
                    sess, played, last_played, centroid, user_vec,
                    q_keys, constraint, session_year)

            gt_f = feats(gt)
            if gt_f is None:
                continue
            top_f = [f for f in (feats(t) for t in final20) if f is not None]
            if not top_f:
                continue
            beat = {}
            for name in FEATURES:
                vals = sorted(f[name] for f in top_f)
                med = vals[len(vals) // 2]
                mx = vals[-1]
                beat[name] = {
                    "beat_median": gt_f[name] > med,
                    "beat_max": gt_f[name] > mx,
                }
            state = row["trace"].get("state") or {}
            misses.append({
                "session_id": sid,
                "turn_number": tn,
                "gt": gt,
                "best_branch": best_branch,
                "best_rank": best_rank,
                "fused_rank": fused_rank,
                "request_type": (state.get("current_request") or {}).get("request_type"),
                "goal_category": sess.get("goal_category"),
                "goal_specificity": sess.get("goal_specificity"),
                "beat": beat,
                "gt_feats": gt_f,
            })
            if line_no % 1000 == 0:
                print(f"  {line_no} lines, {len(misses)} misses", flush=True)

    print(f"turns={n_turns} hit20={n_hit20} unreachable@{args.union_k}={n_unreachable} "
          f"in-pool misses={len(misses)}", flush=True)

    def agg(rows):
        out = {}
        for name in FEATURES:
            out[name] = {
                "beat_median": sum(r["beat"][name]["beat_median"] for r in rows) / max(len(rows), 1),
                "beat_max": sum(r["beat"][name]["beat_max"] for r in rows) / max(len(rows), 1),
            }
        return out

    strata = {
        "ALL": misses,
        **{f"rank_{b}": [m for m in misses if lo < m["best_rank"] <= hi]
           for b, (lo, hi) in {"21_50": (0, 50), "51_100": (50, 100), "101_200": (100, 200)}.items()},
        **{f"cat_{c}": [m for m in misses if m["goal_category"] == c]
           for c in sorted({m["goal_category"] for m in misses})},
    }
    aggregates = {
        "population": {
            "n_turns": n_turns, "n_hit20": n_hit20,
            "n_unreachable": n_unreachable, "n_misses": len(misses),
            "union_k": args.union_k,
        },
        "strata": {k: {"n": len(v), "features": agg(v)} for k, v in strata.items()},
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "aggregates.json").write_text(json.dumps(aggregates, indent=2))
    (out_dir / "misses_full.json").write_text(json.dumps(misses))

    # stratified sample for LLM/hand judgment
    rng = random.Random(13)
    by_cat = defaultdict(list)
    for m in misses:
        by_cat[(m["goal_category"], m["best_rank"] > 50)].append(m)
    sample = []
    quota = max(1, args.sample_size // max(len(by_cat), 1))
    for _, rows in sorted(by_cat.items()):
        sample.extend(rng.sample(rows, min(quota, len(rows))))
    sample = sample[: args.sample_size]
    with open(out_dir / "sample.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["session_id", "turn_number", "user_text", "gt_label", "best_branch",
                    "best_rank", "fused_rank", "request_type", "goal_category",
                    "goal_specificity", "winning_features"])
        for m in sample:
            sess = sessions.get(m["session_id"], {})
            wins = [n for n in FEATURES if m["beat"][n]["beat_max"]]
            gt_c = cat.get(m["gt"], {})
            w.writerow([m["session_id"], m["turn_number"],
                        sess.get("user_text_by_turn", {}).get(m["turn_number"], "")[:400],
                        f"{'/'.join(sorted(gt_c.get('artists', [])))} y{gt_c.get('year')}",
                        m["best_branch"], m["best_rank"], m["fused_rank"],
                        m["request_type"], m["goal_category"], m["goal_specificity"],
                        ";".join(wins)])

    lines = ["# Miss Audit\n",
             f"Population: {len(misses)} in-pool misses (GT in union@{args.union_k}, not in final top-20) "
             f"out of {n_turns} turns. hit@20={n_hit20}, unreachable@{args.union_k}={n_unreachable}.\n",
             "## Feature rescue rates (ALL misses)\n",
             "| feature | beats median of top-20 | beats max |", "|---|---:|---:|"]
    for name in FEATURES:
        a = aggregates["strata"]["ALL"]["features"][name]
        lines.append(f"| {name} | {a['beat_median']:.1%} | {a['beat_max']:.1%} |")
    (out_dir / "report.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {out_dir}/aggregates.json, report.md, sample.csv ({len(sample)} rows)", flush=True)


if __name__ == "__main__":
    main()
