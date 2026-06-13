"""Online LightGBM (v9) reranker — serves the trained LambdaMART in-pipeline.

Consumes the SAME trace payload the offline feature builder reads and computes
features via the SAME `compute_turn_features` (scripts/rerank/features_v9.py),
so train/serve drift is structurally impossible. Hooked by V0PlusCompilerQU
right after trace assembly; replaces the RRF order over the branch-pool union.

Config (qu_kwargs.reranker):
  enabled: true
  model_path:    .../model_v9.txt          (LightGBM booster)
  meta_path:     .../model_v9.meta.json    ({cols, cat_idx}; trainer output)
  cat_maps:      .../cat_maps_v9.json      (categorical value->code, training)
  branch_names:  .../branch_names.json     (canonical 11)
  tag_index:     .../tag_embedding_index/qwen_0_6b.npz
  embed_memo:    .../q06_memo.json         (query-text embedding cache; live
                                            DeepInfra fill for unseen strings)
  msg_store:     .../raw_msg_store         (message-embedding store; live fill)
  pool_k: 500
  top_k_out: 1000

`session_meta` (threaded from run_inference) must carry the RAW conversation
(music entries = catalog track ids) + profile/goal — the dataset-equivalent
session context. Without it the session-history block would silently zero
(the round-2 blind bug class).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
for p in (_PROJECT_ROOT, _PROJECT_ROOT / "scripts" / "rerank"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

CATEGORICALS = ["age_group", "gender", "goal_category", "goal_specificity",
                "request_type", "intent_mode", "target_artist_mode",
                "temporal_strength"]


def session_entry_from_meta(meta: dict) -> dict:
    """Build the load_sessions()-shaped entry from a raw dataset row (parity
    with scripts/rerank/build_features.load_sessions)."""
    import ast
    from collections import defaultdict

    meta = dict(meta)
    for k in ("conversations", "user_profile", "conversation_goal"):
        if isinstance(meta.get(k), str):  # some HF caches store literals
            try:
                meta[k] = ast.literal_eval(meta[k])
            except Exception:
                meta[k] = [] if k == "conversations" else {}

    played, user_text = defaultdict(list), {}
    for msg in meta.get("conversations") or []:
        role = msg.get("role")
        tn = int(msg.get("turn_number") or 0)
        if role == "music":
            played[tn].append(str(msg.get("content")))
        elif role == "user":
            user_text[tn] = str(msg.get("content"))
    p = meta.get("user_profile") or {}
    g = meta.get("conversation_goal") or {}
    return {
        "played_by_turn": dict(played),
        "user_text_by_turn": user_text,
        "session_date": str(meta.get("session_date") or ""),
        "age": p.get("age"), "age_group": str(p.get("age_group") or ""),
        "gender": str(p.get("gender") or ""),
        "culture": str(p.get("preferred_musical_culture") or ""),
        "goal_category": str(g.get("category") or ""),
        "goal_specificity": str(g.get("specificity") or ""),
        "listener_goal": str(g.get("listener_goal") or ""),
    }


class LgbmOnlineReranker:
    def __init__(self, cfg: dict, db_uri: str, table_name: str = "music_track_catalog"):
        import lightgbm as lgb

        from mcrs.qu_modules.tag_resolver import TagEmbeddingIndex, TieredTagResolver

        from build_features import Catalog, EmbedMemo, NpzEmbedStore, load_user_cf
        from features_v9 import TurnContext

        self.booster = lgb.Booster(model_file=str(cfg["model_path"]))
        meta = json.load(open(cfg["meta_path"]))
        self.cols: list[str] = meta["cols"]
        self.cat_maps: dict = json.load(open(cfg["cat_maps"]))
        branch_names = json.load(open(cfg["branch_names"]))
        n_model = self.booster.num_feature()
        assert n_model == len(self.cols), (
            f"model expects {n_model} features, meta has {len(self.cols)}")

        cat = Catalog(db_uri, table_name)
        tag_index = TagEmbeddingIndex.load(str(cfg["tag_index"]))
        tag_vec = {t: tag_index.matrix[i] for i, t in enumerate(tag_index.tags)}
        vocab = frozenset(tag_index.tags)
        resolver = TieredTagResolver(catalog_tag_keys=vocab, substring_vocab=vocab)
        memo = EmbedMemo(Path(cfg["embed_memo"]))
        msg_store = NpzEmbedStore(cfg["msg_store"])
        self.ctx = TurnContext(
            cat, sessions={}, user_cf=load_user_cf(), resolver=resolver,
            tag_vec=tag_vec, memo=memo, msg_store=msg_store,
            branch_names=branch_names, pool_k=int(cfg.get("pool_k", 500)),
            offline=False)  # live-embed unseen query/message strings
        self.top_k_out = int(cfg.get("top_k_out", 1000))

    def _assemble(self, rows: list[dict]) -> np.ndarray:
        X = np.empty((len(rows), len(self.cols)), dtype=np.float32)
        for j, c in enumerate(self.cols):
            if c in CATEGORICALS:
                m = self.cat_maps[c]
                X[:, j] = [float(m.get(str(r.get(c, "")), -1)) for r in rows]
            else:
                X[:, j] = [float(r[c]) if (c in r and r[c] == r[c]) else np.nan
                           for r in rows]
        return X

    def rerank(self, trace: dict, session_meta: dict | None,
               user_id: str | None, hard_drop: set[str],
               fallback: list[str]) -> list[str]:
        """Re-order the branch-pool union; returns top_k_out ids (backfilled
        from `fallback` to preserve depth). Any failure -> fallback unchanged."""
        from features_v9 import compute_turn_features

        try:
            if not (trace.get("branches") or {}).get("pools"):
                return fallback
            sid = str((session_meta or {}).get("session_id") or "")
            tn = int((session_meta or {}).get("turn_number") or 0)
            if session_meta:
                self.ctx.sessions[sid] = session_entry_from_meta(session_meta)
            row = {"session_id": sid, "turn_number": tn,
                   "user_id": user_id, "trace": trace}
            rows, _ = compute_turn_features(row, self.ctx, gt=None)
            if not rows:
                return fallback
            # sidecar constraint features — exact replica of
            # scripts/rerank/build_constraint_features.py (resolver-based)
            res = trace.get("resolver") or {}
            played = frozenset(str(x) for x in res.get("played_track_ids") or [])
            rej_tracks = frozenset(str(x) for x in res.get("rejected_track_ids") or [])
            rej_artists = frozenset(str(x) for x in res.get("rejected_artist_ids") or [])
            for r in rows:
                tid = r["track_id"]
                arts = self.ctx.cat.meta.get(tid, {}).get("artists", ())
                r["is_played_track"] = float(tid in played)
                r["rejected_track_exact"] = float(tid in rej_tracks)
                r["rejected_artist_exact"] = float(
                    bool(rej_artists) and any(a in rej_artists for a in arts))
                mode = str(r.get("target_artist_mode") or "")
                r["violates_new_artist"] = float(
                    ("new" in mode or "different" in mode)
                    and float(r.get("same_artist_session") or 0.0) > 0)
            X = self._assemble(rows)
            scores = self.booster.predict(X)
            order = np.argsort(-scores)
            ranked = [rows[i]["track_id"] for i in order
                      if rows[i]["track_id"] not in hard_drop]
            seen = set(ranked)
            for t in fallback:  # preserve depth for downstream consumers
                if t not in seen and t not in hard_drop:
                    ranked.append(t)
                    seen.add(t)
            return ranked[: self.top_k_out]
        except Exception as e:  # serving must never hard-fail a turn
            print(f"[lgbm_reranker] fallback (turn {session_meta}): {e!r}",
                  flush=True)
            return fallback
