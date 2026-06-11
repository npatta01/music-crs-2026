"""Score devset pool candidates with a trained next-play model (reproducible
version of the previously-inline script; audit required it checked in).

Output: parquet (session_id, turn_number, track_id, stage1_score) for the
stage-2 stacker (`train_lgbm.py --stage1-scores`).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as pds
import torch
import torch.nn.functional as F

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "rerank"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "nextplay"))

from build_features import Catalog, NpzEmbedStore  # noqa: E402
from build_train_features import load_split, load_user_cf  # noqa: E402
from train_two_tower import CAT_FIELDS, NextPlayModel  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="exp/analysis/nextplay_v2/model.pt")
    ap.add_argument("--db-uri", required=True)
    ap.add_argument("--pools", default="exp/analysis/rerank/features_v2",
                    help="Parquet dir defining (session_id, turn_number, track_id) to score.")
    ap.add_argument("--msg-store", default="exp/analysis/rerank/raw_msg_store")
    ap.add_argument("--out", default="exp/analysis/nextplay_v2/devset_pool_scores.parquet")
    args = ap.parse_args()

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    cat = Catalog(args.db_uri, "music_track_catalog")
    user_cf = load_user_cf()
    cf_idx = cat.vec_idx["cf_bpr"]
    cf_ids = sorted(cf_idx, key=cf_idx.get)
    n_tracks = len(cf_ids)
    priors = torch.tensor(np.stack([
        np.array([cat.pop_pct.get(t, 0.0) for t in cf_ids]),
        np.array([cat.era_pop_pct.get(t, cat.pop_pct.get(t, 0.0)) for t in cf_ids]),
        np.array([cat.within_artist_pop.get(t, 0.0) for t in cf_ids]),
    ], axis=1), dtype=torch.float32)
    meta_rows = np.zeros((n_tracks, 1024), dtype=np.float32)
    midx = cat.vec_idx["metadata_qwen3_embedding_0_6b"]
    for i, t in enumerate(cf_ids):
        j = midx.get(t)
        if j is not None:
            meta_rows[i] = cat.vec["metadata_qwen3_embedding_0_6b"][j]
    trk_in = torch.cat([torch.tensor(cat.vec["cf_bpr"], dtype=torch.float32),
                        priors, torch.tensor(meta_rows)], dim=1).to(device)

    train_sessions = load_split("train")
    cat_vocab = []
    for f in CAT_FIELDS:
        vals = sorted({s[f] for s in train_sessions} | {""})
        cat_vocab.append({v: i for i, v in enumerate(vals)})
    model = NextPlayModel([len(v) + 1 for v in cat_vocab]).to(device)
    model.load_state_dict(torch.load(args.model, map_location=device))
    model.eval()

    dev_sessions = {s["session_id"]: s for s in load_split("test")}
    store = NpzEmbedStore(args.msg_store)
    zero = np.zeros(128, dtype=np.float32)
    zero_msg = np.zeros(1024, dtype=np.float32)

    tbl = pds.dataset(args.pools).to_table(
        columns=["session_id", "turn_number", "track_id"]).to_pydict()
    by_turn: dict[tuple[str, int], list[str]] = {}
    for sid, tn, tid in zip(tbl["session_id"], tbl["turn_number"], tbl["track_id"]):
        by_turn.setdefault((str(sid), int(tn)), []).append(str(tid))
    print(f"{len(by_turn)} turns to score", flush=True)

    out_rows = []
    with torch.no_grad():
        trk_vec_all = F.normalize(model.trk(trk_in), dim=-1)
        fw = model.flag_w.detach().cpu().numpy()
        for n_done, ((sid, tn), tids) in enumerate(sorted(by_turn.items())):
            sess = dev_sessions.get(sid)
            if sess is None:
                continue
            played = [t for k in sorted(sess["played_by_turn"]) if k < tn
                      for t in sess["played_by_turn"][k]]
            last = played[-1] if played else None
            prev = played[-2] if len(played) > 1 else None
            lastv = cat.vec["cf_bpr"][cf_idx[last]] if last in cf_idx else zero
            vs = [cat.vec["cf_bpr"][cf_idx[p]] for p in played if p in cf_idx]
            centv = np.mean(vs, axis=0) if vs else zero
            driftv = zero
            if last in cf_idx and prev in cf_idx:
                d = 2 * cat.vec["cf_bpr"][cf_idx[last]] - cat.vec["cf_bpr"][cf_idx[prev]]
                n = np.linalg.norm(d)
                driftv = d / n if n > 0 else zero
            uvec = user_cf.get(sess["user_id"])
            uv = uvec if uvec is not None else zero
            msg = sess["user_text_by_turn"].get(tn, "")
            mv = store.get_many([msg], offline=True).get(msg) if msg else None
            cf_feats = torch.tensor(np.concatenate(
                [uv, lastv, centv, driftv, mv if mv is not None else zero_msg]),
                dtype=torch.float32).unsqueeze(0)
            cat_ids = torch.tensor(
                [[cat_vocab[i].get(sess[f], len(cat_vocab[i]))
                  for i, f in enumerate(CAT_FIELDS)]], dtype=torch.long)
            turn_onehot = np.zeros(8, dtype=np.float32)
            turn_onehot[min(tn, 8) - 1] = 1.0
            scalars = torch.tensor(np.concatenate(
                [turn_onehot, [float(bool(played)), float(uvec is not None)]]),
                dtype=torch.float32).unsqueeze(0)
            ctx = F.normalize(model.ctx(cf_feats.to(device), cat_ids.to(device),
                                        scalars.to(device)), dim=-1)
            rows = [cf_idx[t] for t in tids if t in cf_idx]
            tid_ok = [t for t in tids if t in cf_idx]
            scores = (model.scale * (ctx @ trk_vec_all[rows].T)).squeeze(0).cpu().numpy()
            sess_art = {a for p in played for a in cat.meta.get(p, {}).get("artists", ())}
            sess_alb = {al for p in played for al in cat.meta.get(p, {}).get("albums", ())}
            played_idx = {cf_idx[p] for p in played if p in cf_idx}
            for t, r, sc in zip(tid_ok, rows, scores):
                m = cat.meta[t]
                sc2 = float(sc)
                if set(m["artists"]) & sess_art:
                    sc2 += float(fw[0])
                if set(m["albums"]) & sess_alb:
                    sc2 += float(fw[1])
                if r in played_idx:
                    sc2 += float(fw[2])
                out_rows.append((sid, tn, t, sc2))
            if n_done % 1000 == 0:
                print(f"  {n_done} turns", flush=True)

    df = pd.DataFrame(out_rows, columns=["session_id", "turn_number", "track_id", "stage1_score"])
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out)
    print(f"wrote {len(df)} scores -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
