"""Next-play prediction over the FULL catalog — the architecture-class pivot.

Instead of reranking retrieval pools, directly predict which track the
generator played next, trained on all 121k train-split turns:

  score(context, track) = g(context) . h(track) + w . flags(context, track)

- context: user cf_bpr, last-played cf_bpr, session-centroid cf_bpr, drift,
  turn number, goal/profile categoricals
- track tower: cf_bpr + popularity priors (h precomputed for all 47k -> one
  matmul scores the catalog)
- flags: same-artist-as-session / same-album / already-played-artist counts,
  computed vectorized per turn for all 47k
- loss: sampled softmax (GT vs uniform+popularity negatives drawn from the
  full catalog — matches the inference distribution, unlike pool sampling)

Eval: full-catalog scoring on the user-grouped devset TEST sessions (same
seed-13 split as the reranker work). Baseline to beat: production RRF
hit@20 0.293 / ndcg@20 0.1374.

Local: torch + MPS.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "rerank"))

from build_features import Catalog  # noqa: E402
from build_train_features import load_split, load_user_cf  # noqa: E402

CAT_FIELDS = ["goal_category", "goal_specificity", "age_group", "gender"]


def build_examples(sessions, cat, user_cf, cf_idx):
    """One example per turn: context arrays + GT row index in catalog order."""
    examples = []
    for sess in sessions:
        uvec = user_cf.get(sess["user_id"])
        for tn in sorted(sess["played_by_turn"]):
            gt = sess["played_by_turn"][tn][0]
            if gt not in cf_idx:
                continue
            played = [t for k in sorted(sess["played_by_turn"]) if k < tn
                      for t in sess["played_by_turn"][k]]
            examples.append({
                "session_id": sess["session_id"],
                "turn": tn, "gt": gt, "played": played,
                "uvec": uvec,
                "cats": tuple(sess[f] for f in CAT_FIELDS),
            })
    return examples


class ContextEncoder(nn.Module):
    def __init__(self, cat_sizes, cf_dim=128, out_dim=128, hidden=512):
        super().__init__()
        self.embs = nn.ModuleList([nn.Embedding(n, 16) for n in cat_sizes])
        in_dim = cf_dim * 4 + 16 * len(cat_sizes) + 10  # turn onehot(8)+has_hist+has_user
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
            nn.Linear(hidden, out_dim),
        )

    def forward(self, cf_feats, cat_ids, scalars):
        cats = [emb(cat_ids[:, i]) for i, emb in enumerate(self.embs)]
        x = torch.cat([cf_feats] + cats + [scalars], dim=1)
        return self.net(x)


class TrackTower(nn.Module):
    def __init__(self, cf_dim=128, prior_dim=3, out_dim=128, hidden=256):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(cf_dim + prior_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, out_dim),
        )

    def forward(self, x):
        return self.net(x)


class NextPlayModel(nn.Module):
    def __init__(self, cat_sizes):
        super().__init__()
        self.ctx = ContextEncoder(cat_sizes)
        self.trk = TrackTower()
        self.flag_w = nn.Parameter(torch.zeros(3))
        self.scale = nn.Parameter(torch.tensor(10.0))

    def score(self, ctx_vec, trk_vec, flags):
        dot = (ctx_vec.unsqueeze(1) * trk_vec).sum(-1)
        return self.scale * dot / (
            ctx_vec.norm(dim=-1, keepdim=True) * trk_vec.norm(dim=-1).clamp(min=1e-6)
        ) + (flags * self.flag_w).sum(-1)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db-uri", required=True)
    ap.add_argument("--out-dir", default="exp/analysis/nextplay")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--negatives", type=int, default=512)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--devset-gt", default="exp/ground_truth/devset.json")
    ap.add_argument("--max-train-sessions", type=int, default=0)
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(args.seed)
    rng = random.Random(args.seed)
    device = "mps" if torch.backends.mps.is_available() else "cpu"

    print("loading catalog + embeddings ...", flush=True)
    cat = Catalog(args.db_uri, "music_track_catalog")
    user_cf = load_user_cf()
    cf_idx = cat.vec_idx["cf_bpr"]
    cf_ids = sorted(cf_idx, key=cf_idx.get)
    cf = torch.tensor(cat.vec["cf_bpr"], dtype=torch.float32)
    n_tracks = cf.shape[0]
    priors = torch.tensor(np.stack([
        np.array([cat.pop_pct.get(t, 0.0) for t in cf_ids]),
        np.array([cat.era_pop_pct.get(t, cat.pop_pct.get(t, 0.0)) for t in cf_ids]),
        np.array([cat.within_artist_pop.get(t, 0.0) for t in cf_ids]),
    ], axis=1), dtype=torch.float32)
    trk_in = torch.cat([cf, priors], dim=1).to(device)
    # popularity^0.75 negative-sampling distribution
    pop = np.array([cat.pop_pct.get(t, 0.0) for t in cf_ids]) + 0.01
    neg_p = pop ** 0.75
    neg_p /= neg_p.sum()

    # artist/album membership for flags
    artist_of = [cat.meta[t]["artists"] for t in cf_ids]
    artist_index: dict[str, list[int]] = defaultdict(list)
    for i, arts in enumerate(artist_of):
        for a in arts:
            artist_index[a].append(i)
    album_index: dict[str, list[int]] = defaultdict(list)
    for i, t in enumerate(cf_ids):
        for al in cat.meta[t]["albums"]:
            album_index[al].append(i)

    print("loading sessions ...", flush=True)
    train_sessions = load_split("train")
    if args.max_train_sessions:
        train_sessions = train_sessions[: args.max_train_sessions]
    dev_sessions = load_split("test")

    # categorical vocabularies from train
    cat_vocab = []
    for f in CAT_FIELDS:
        vals = sorted({s[f] for s in train_sessions} | {""})
        cat_vocab.append({v: i for i, v in enumerate(vals)})
    cat_sizes = [len(v) + 1 for v in cat_vocab]  # +1 OOV

    train_ex = build_examples(train_sessions, cat, user_cf, cf_idx)
    rng.shuffle(train_ex)
    print(f"  train examples: {len(train_ex)}", flush=True)

    # user-grouped devset split (same as reranker, seed 13)
    sess_user = {str(r["session_id"]): str(r["user_id"]) for r in json.load(open(args.devset_gt))}
    dsids = sorted({s["session_id"] for s in dev_sessions})
    dusers = sorted({sess_user.get(s, s) for s in dsids})
    rng2 = random.Random(13)
    rng2.shuffle(dusers)
    n_u = len(dusers)
    test_u = set(dusers[int(0.85 * n_u):])
    test_sessions = [s for s in dev_sessions if sess_user.get(s["session_id"]) in test_u]
    test_ex = build_examples(test_sessions, cat, user_cf, cf_idx)
    print(f"  devset test examples: {len(test_ex)} ({len(test_sessions)} sessions)", flush=True)

    zero = np.zeros(128, dtype=np.float32)

    def ctx_arrays(batch):
        cf_feats, cat_ids, scalars = [], [], []
        flag_rows = []
        for ex in batch:
            played = ex["played"]
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
            uv = ex["uvec"] if ex["uvec"] is not None else zero
            cf_feats.append(np.concatenate([uv, lastv, centv, driftv]))
            cat_ids.append([cat_vocab[i].get(v, len(cat_vocab[i])) for i, v in enumerate(ex["cats"])])
            turn_onehot = np.zeros(8, dtype=np.float32)
            turn_onehot[min(ex["turn"], 8) - 1] = 1.0
            scalars.append(np.concatenate([
                turn_onehot,
                [float(bool(played)), float(ex["uvec"] is not None)]]))
            # flag candidate index sets, resolved later
            sess_art = {a for p in played for a in cat.meta.get(p, {}).get("artists", ())}
            sess_alb = {al for p in played for al in cat.meta.get(p, {}).get("albums", ())}
            played_idx = {cf_idx[p] for p in played if p in cf_idx}
            flag_rows.append((sess_art, sess_alb, played_idx))
        return (torch.tensor(np.stack(cf_feats), dtype=torch.float32),
                torch.tensor(cat_ids, dtype=torch.long),
                torch.tensor(np.stack(scalars), dtype=torch.float32),
                flag_rows)

    def flags_for(flag_rows, cand_idx: torch.Tensor):
        B, K = cand_idx.shape
        out = np.zeros((B, K, 3), dtype=np.float32)
        ci = cand_idx.cpu().numpy()
        for b, (sess_art, sess_alb, played_idx) in enumerate(flag_rows):
            art_rows = set()
            for a in sess_art:
                art_rows.update(artist_index.get(a, ()))
            alb_rows = set()
            for al in sess_alb:
                alb_rows.update(album_index.get(al, ()))
            for k in range(K):
                j = int(ci[b, k])
                out[b, k, 0] = 1.0 if j in art_rows else 0.0
                out[b, k, 1] = 1.0 if j in alb_rows else 0.0
                out[b, k, 2] = 1.0 if j in played_idx else 0.0
        return torch.tensor(out)

    model = NextPlayModel(cat_sizes).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)

    def evaluate():
        model.eval()
        hits20 = ndcgs = hits1 = 0.0
        n = 0
        with torch.no_grad():
            trk_vec_all = model.trk(trk_in)  # (N,128)
            for start in range(0, len(test_ex), 64):
                batch = test_ex[start:start + 64]
                cf_b, cat_b, sc_b, fr = ctx_arrays(batch)
                ctx_vec = model.ctx(cf_b.to(device), cat_b.to(device), sc_b.to(device))
                dots = model.scale * (F.normalize(ctx_vec, dim=-1) @
                                      F.normalize(trk_vec_all, dim=-1).T)
                # flags over full catalog, sparse add
                dots = dots.cpu()
                for b, (sess_art, sess_alb, played_idx) in enumerate(fr):
                    art_rows = [i for a in sess_art for i in artist_index.get(a, ())]
                    alb_rows = [i for al in sess_alb for i in album_index.get(al, ())]
                    if art_rows:
                        dots[b, art_rows] += model.flag_w[0].item()
                    if alb_rows:
                        dots[b, alb_rows] += model.flag_w[1].item()
                    if played_idx:
                        dots[b, list(played_idx)] += model.flag_w[2].item()
                for b, ex in enumerate(batch):
                    gt_row = cf_idx[ex["gt"]]
                    rank = int((dots[b] > dots[b, gt_row]).sum().item()) + 1
                    n += 1
                    hits20 += rank <= 20
                    hits1 += rank <= 1
                    ndcgs += 1 / math.log2(rank + 1) if rank <= 20 else 0.0
        model.train()
        return {"ndcg20": ndcgs / n, "hit20": hits20 / n, "hit1": hits1 / n, "n": n}

    print("training ...", flush=True)
    step = 0
    for epoch in range(args.epochs):
        rng.shuffle(train_ex)
        for start in range(0, len(train_ex), args.batch):
            batch = train_ex[start:start + args.batch]
            cf_b, cat_b, sc_b, fr = ctx_arrays(batch)
            B = len(batch)
            gt_rows = torch.tensor([cf_idx[ex["gt"]] for ex in batch])
            neg = torch.tensor(np.random.choice(n_tracks, size=(B, args.negatives), p=neg_p))
            cand = torch.cat([gt_rows.unsqueeze(1), neg], dim=1)  # (B, 1+K)
            flags = flags_for(fr, cand).to(device)
            ctx_vec = model.ctx(cf_b.to(device), cat_b.to(device), sc_b.to(device))
            trk_vec = model.trk(trk_in[cand.to(device)])
            logits = model.score(ctx_vec, trk_vec, flags)
            loss = F.cross_entropy(logits, torch.zeros(B, dtype=torch.long, device=device))
            opt.zero_grad()
            loss.backward()
            opt.step()
            step += 1
            if step % 100 == 0:
                print(f"  epoch {epoch} step {step} loss {loss.item():.4f}", flush=True)
        metrics = evaluate()
        print(f"epoch {epoch}: devset-test {metrics}", flush=True)
        torch.save(model.state_dict(), out / "model.pt")
        (out / "metrics.json").write_text(json.dumps(metrics, indent=2))

    print("done", flush=True)


if __name__ == "__main__":
    main()
