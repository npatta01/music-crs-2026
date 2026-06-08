"""Feature engineering for the v0+ LambdaMART reranker.

Pure transform: ``candidates.parquet`` + ``groups.jsonl`` (from ``build_dataset.py``) plus a
``LanceDbCatalog`` -> a dense feature matrix. Implements the blocks from issue #93 / the
design doc, with the first-cut decisions locked 2026-06-03:

* A   per-branch rank / norm_rank / score / hit  (absent => NaN; ``_hit`` carries presence)
* A'  cross-branch aggregates + within-group z-scored scores
* C   item-side catalog join (popularity, year, decade, n_tags, embedding flags) -- **no raw IDs**
* D   query-side scalars (group-constant; help only via interactions)
* E   query x item match (the learned routing-multiplier replacement)
* F   cheap structural signals (score gap/ratio to top, within-union artist concentration,
      conversation position, query specificity, tag jaccard/novelty)
* P   abandoned-direction match (negative-pivot mirror of E's anchor features): does the
      candidate resemble (artist/album/track/tags) the carried-forward positive tracks the user
      is pivoting away from? Lets the tree learn ``pivot AND resembles-abandoned => demote``.
* U   Tier-A user-profile + conversation-goal context (organizer session metadata joined by
      session_id): goal category/specificity, user age/gender, session_date×release_year era
      interactions, and a Tier-B ``preferred_musical_culture`` × candidate-tags genre-token
      match. Group-constant categoricals + per-candidate interactions; neutral (NaN) when the
      session-meta join is absent (serving path / pre-join datasets).

artist_id / album_id are used internally for match features but are **never emitted** as
model columns (memorisation/leakage guard).

Block G (sentiment-split embedding relevance) was prototyped and dropped: on devset it added
only +0.001 NDCG@20 over this set (redundant with the ``centroid.{cf_bpr,audio_clap,user.cf_bpr}``
branches, which already encode anchor similarity) at ~5x the feature-build cost. See git history.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from mcrs.rerank.branches import (
    BRANCH_BY_KEY,
    BRANCH_KEYS,
    GROUPS,
    hit_col,
    norm_rank_col,
    rank_col,
    raw_rank_col,
    raw_score_col,
    score_col,
    score_gap_col,
    score_ratio_col,
)

GROUP_KEYS = ["session_id", "turn_number"]


# ----------------------------------------------------------------- catalog metadata frame

def catalog_metadata_frame(catalog: Any) -> pd.DataFrame:
    """One row per catalog track with the metadata used by blocks C/E/F (vectorised join)."""
    track_ids = catalog.all_track_ids()
    records = []
    for tid in track_ids:
        row = getattr(catalog, "_per_track", {}).get(tid, {})
        pop = row.get("popularity")
        records.append({
            "track_id": tid,
            "artist_id": catalog.artist_id_of(tid),
            "album_id": catalog.album_id_of(tid),
            "popularity": float(pop) if pop is not None else np.nan,
            "release_year": catalog.release_year_of(tid),
            "tags": tuple(catalog.tag_list(tid)),
        })
    meta = pd.DataFrame.from_records(records)
    meta["n_tags"] = meta["tags"].map(len)
    meta["log_popularity"] = np.log1p(meta["popularity"].fillna(0.0))
    meta["release_decade"] = (meta["release_year"] // 10 * 10).astype("Float64")
    return meta


# ----------------------------------------------------------------------------- group state

def load_groups(dataset_dir: str | Path) -> pd.DataFrame:
    recs = [json.loads(l) for l in open(Path(dataset_dir) / "groups.jsonl")]
    return pd.DataFrame.from_records(recs)


def _resolved_sets(targets: list[dict[str, Any]]) -> tuple[set[str], set[str], float, float]:
    """(artist_entity_ids, track_entity_ids, max_artist_conf, max_track_conf) from resolved_targets."""
    a_ids, t_ids = set(), set()
    a_conf, t_conf = np.nan, np.nan
    for tgt in targets or []:
        eid, conf = tgt.get("entity_id"), tgt.get("confidence")
        if tgt.get("kind") == "artist" and eid:
            a_ids.add(eid)
            a_conf = conf if (isinstance(a_conf, float) and math.isnan(a_conf)) else max(a_conf, conf)
        elif tgt.get("kind") == "track" and eid:
            t_ids.add(eid)
            t_conf = conf if (isinstance(t_conf, float) and math.isnan(t_conf)) else max(t_conf, conf)
    return a_ids, t_ids, float(a_conf), float(t_conf)


# ------------------------------------------------------------------------ block builders

def _block_a_and_f_branch(df: pd.DataFrame, groups: pd.DataFrame) -> pd.DataFrame:
    """A (rank/norm_rank/score/hit) + per-branch F (score gap/ratio to top) + within-group z."""
    pool_depth = pd.json_normalize(groups["pool_depth"]).add_prefix("pd__")
    top_score = pd.json_normalize(groups["top_score"]).add_prefix("ts__")
    gmeta = pd.concat([groups[GROUP_KEYS].reset_index(drop=True),
                       pool_depth.reset_index(drop=True),
                       top_score.reset_index(drop=True)], axis=1)
    df = df.merge(gmeta, on=GROUP_KEYS, how="left")

    out = {}
    for key in BRANCH_KEYS:
        rank = df[raw_rank_col(key)].astype("Float64")
        score = df[raw_score_col(key)].astype("Float64")
        depth = df.get(f"pd__{key}")
        top = df.get(f"ts__{key}")
        out[rank_col(key)] = rank
        out[score_col(key)] = score
        out[hit_col(key)] = rank.notna().astype("int8")
        out[norm_rank_col(key)] = (rank / depth) if depth is not None else np.nan
        if top is not None:
            out[score_gap_col(key)] = top - score
            out[score_ratio_col(key)] = score / top.replace(0, np.nan)
        else:
            out[score_gap_col(key)] = np.nan
            out[score_ratio_col(key)] = np.nan
    feats = pd.DataFrame(out, index=df.index)

    # within-group z-score of each branch's raw score (cross-branch-comparable magnitude).
    gb = df.groupby(GROUP_KEYS, sort=False)
    for key in BRANCH_KEYS:
        s = df[raw_score_col(key)].astype(float)
        mean = gb[raw_score_col(key)].transform("mean")
        std = gb[raw_score_col(key)].transform("std")
        feats[f"{key}__score_z"] = (s - mean) / std.replace(0, np.nan)
    return feats


def _block_a_aggregates(feats: pd.DataFrame) -> pd.DataFrame:
    hit_cols = [hit_col(k) for k in BRANCH_KEYS]
    rank_cols = [rank_col(k) for k in BRANCH_KEYS]
    nr_cols = [norm_rank_col(k) for k in BRANCH_KEYS]
    z_cols = [f"{k}__score_z" for k in BRANCH_KEYS]
    agg = pd.DataFrame(index=feats.index)
    agg["agg__n_branches_hit"] = feats[hit_cols].sum(axis=1).astype("int16")
    for grp in GROUPS:
        cols = [hit_col(k) for k in BRANCH_KEYS if BRANCH_BY_KEY[k].group == grp]
        agg[f"agg__n_{grp}_hit"] = feats[cols].sum(axis=1).astype("int16")
    agg["agg__min_rank"] = feats[rank_cols].min(axis=1)
    agg["agg__mean_norm_rank"] = feats[nr_cols].mean(axis=1)
    agg["agg__max_score_z"] = feats[z_cols].max(axis=1)
    agg["agg__mean_score_z"] = feats[z_cols].mean(axis=1)
    return agg


def _block_c(df: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    cols = ["track_id", "log_popularity", "release_year", "release_decade", "n_tags"]
    c = df[["track_id"]].merge(meta[cols], on="track_id", how="left").drop(columns="track_id")
    return c.add_prefix("c__")


def _block_d(df: pd.DataFrame, groups: pd.DataFrame) -> pd.DataFrame:
    g = groups.copy()
    routing = pd.json_normalize(g["routing_tags"])
    ryr = pd.json_normalize(g["release_year_range"]).reindex(columns=["start", "end"])
    g = g.reset_index(drop=True)
    d = pd.DataFrame({"session_id": g["session_id"], "turn_number": g["turn_number"]})
    d["intent_mode"] = g["intent_mode"].astype("category")
    d["exploration_policy"] = g["exploration_policy"].astype("category")
    for rk in ["exact_entity_probe", "lyric_search", "feature_articulation",
               "image_or_visual_search", "hidden_target_search"]:
        d[f"q__routing_{rk}"] = routing[rk].astype("int8")
    # Excluded by design (serving constraints):
    #  - n_turns / frac_through_session / is_last_turn: total session length is future info.
    #  - turn_number: group-constant, low-importance, and plumbing the true turn index through
    #    the live inference path isn't worth it; the reranker stays a pure fn of (state, pools).
    d["q__n_anchors"] = g["n_anchors"].astype("int16")
    d["q__has_seed"] = g["has_seed"].astype("int8")
    d["q__n_rejections"] = g["n_rejections"].astype("int16")
    for kind in ["artists", "albums", "tracks", "tags"]:
        d[f"q__n_mentioned_{kind}"] = g[f"n_mentioned_{kind}"].astype("int16")
    d["q__has_lyrical_theme"] = g["has_lyrical_theme"].astype("int8")
    d["q__has_release_year_range"] = ryr.notna().any(axis=1).astype("int8")
    d["q__year_range_width"] = (ryr["end"] - ryr["start"]).astype("Float64")
    d["q__intent_n_tokens"] = g["turn_intent"].fillna("").map(lambda s: len(s.split())).astype("int16")
    a_conf, t_conf = [], []
    for tgts in g["resolved_targets"]:
        _, _, ac, tc = _resolved_sets(tgts)
        a_conf.append(ac)
        t_conf.append(tc)
    d["q__resolved_artist_confidence"] = a_conf
    d["q__resolved_track_confidence"] = t_conf
    out = df[GROUP_KEYS].merge(d, on=GROUP_KEYS, how="left").drop(columns=GROUP_KEYS)
    return out


def _block_e_and_f_union(df: pd.DataFrame, groups: pd.DataFrame, meta: pd.DataFrame,
                         agg_min_rank: pd.Series) -> pd.DataFrame:
    """Per-group set-membership match features (E) + within-union artist concentration (F)."""
    artist_of = dict(zip(meta["track_id"], meta["artist_id"]))
    tags_of = dict(zip(meta["track_id"], meta["tags"]))
    year_of = dict(zip(meta["track_id"], meta["release_year"]))
    grp_state = groups.set_index([groups["session_id"], groups["turn_number"]])

    n = len(df)
    cols = {
        "e__is_anchor_track": np.zeros(n, "int8"),
        "e__artist_match_anchor": np.zeros(n, "int8"),
        "e__artist_match_resolved_target": np.zeros(n, "int8"),
        "e__is_resolved_target_track": np.zeros(n, "int8"),
        "e__same_artist_as_rejected": np.zeros(n, "int8"),
        "e__is_rejected_track": np.zeros(n, "int8"),
        "e__is_played_already": np.zeros(n, "int8"),
        "e__tag_overlap_positive": np.zeros(n, "int16"),
        "e__tag_overlap_rejected": np.zeros(n, "int16"),
        "e__in_release_year_range": np.full(n, np.nan),
        "e__years_outside_range": np.full(n, np.nan),
        "f__n_same_artist_in_union": np.ones(n, "int32"),
        "f__artist_best_rank_in_union": np.full(n, np.nan),
        "f__jaccard_tag_overlap": np.full(n, np.nan),
        "f__n_candidate_tags_not_in_positive": np.zeros(n, "int16"),
    }
    df = df.reset_index(drop=True)
    min_rank = agg_min_rank.to_numpy()

    for (sid, turn), sub in df.groupby(GROUP_KEYS, sort=False):
        gs = grp_state.loc[(sid, turn)]
        if isinstance(gs, pd.DataFrame):
            gs = gs.iloc[0]
        anchor_tracks = set(gs["anchor_track_ids"])
        played = set(gs["played_track_ids"])
        rej_tracks = set(gs["rejected_track_ids"])
        rej_artists = set(gs["rejected_artist_ids"])
        pos_tags = set(gs["positive_tags"])
        rej_tags = set(gs["rejected_tags"])
        a_ids, t_ids, _, _ = _resolved_sets(gs["resolved_targets"])
        anchor_artists = {artist_of.get(t) for t in anchor_tracks} | a_ids
        anchor_artists.discard(None)
        ryr = gs["release_year_range"] or {}
        y0, y1 = ryr.get("start"), ryr.get("end")

        idx = sub.index.to_numpy()
        tids = sub["track_id"].to_numpy()
        artists = np.array([artist_of.get(t) for t in tids], dtype=object)

        cols["e__is_anchor_track"][idx] = [t in anchor_tracks for t in tids]
        cols["e__is_played_already"][idx] = [t in played for t in tids]
        cols["e__is_rejected_track"][idx] = [t in rej_tracks for t in tids]
        cols["e__is_resolved_target_track"][idx] = [t in t_ids for t in tids]
        cols["e__artist_match_anchor"][idx] = [a in anchor_artists for a in artists]
        cols["e__artist_match_resolved_target"][idx] = [a in a_ids for a in artists]
        cols["e__same_artist_as_rejected"][idx] = [a in rej_artists for a in artists]

        cand_tags = [set(tags_of.get(t, ())) for t in tids]
        cols["e__tag_overlap_positive"][idx] = [len(ct & pos_tags) for ct in cand_tags]
        cols["e__tag_overlap_rejected"][idx] = [len(ct & rej_tags) for ct in cand_tags]
        cols["f__n_candidate_tags_not_in_positive"][idx] = [len(ct - pos_tags) for ct in cand_tags]
        if pos_tags:
            cols["f__jaccard_tag_overlap"][idx] = [
                (len(ct & pos_tags) / len(ct | pos_tags)) if (ct or pos_tags) else 0.0
                for ct in cand_tags]

        years = np.array([year_of.get(t) for t in tids], dtype=object)
        if y0 is not None or y1 is not None:
            in_rng, outside = [], []
            for y in years:
                if y is None or (isinstance(y, float) and math.isnan(y)):
                    in_rng.append(np.nan)
                    outside.append(np.nan)
                    continue
                below = (y0 is not None and y < y0)
                above = (y1 is not None and y > y1)
                in_rng.append(0.0 if (below or above) else 1.0)
                outside.append((y - y0) if below else (y - y1) if above else 0.0)
            cols["e__in_release_year_range"][idx] = in_rng
            cols["e__years_outside_range"][idx] = outside

        # within-union artist concentration
        sub_min = min_rank[idx]
        by_artist_count: dict[Any, int] = {}
        by_artist_best: dict[Any, float] = {}
        for a, mr in zip(artists, sub_min):
            by_artist_count[a] = by_artist_count.get(a, 0) + 1
            if not (isinstance(mr, float) and math.isnan(mr)):
                cur = by_artist_best.get(a, math.inf)
                by_artist_best[a] = min(cur, mr)
        cols["f__n_same_artist_in_union"][idx] = [by_artist_count[a] for a in artists]
        cols["f__artist_best_rank_in_union"][idx] = [
            by_artist_best.get(a, np.nan) for a in artists]

    return pd.DataFrame(cols, index=df.index)


# ----------------------------------------------------- block P: abandoned-direction (pivot)

def _abandoned_anchor_track_ids(track_feedback: list[dict[str, Any]] | None) -> set[str]:
    """Carried-forward positive (accepted/seed, sentiment>0) tracks = the "abandoned direction".

    Mirrors the non-pivot branch of ``compiler_v0plus._positive_anchor_track_ids`` but
    INTENTIONALLY omits the pivot guard: on a pivot turn this is exactly the direction the user
    just left, which the reranker needs in order to learn to demote it. On a non-pivot turn it
    equals the anchor set (harmlessly redundant with the ``e__*`` anchor-match features).
    """
    ids: set[str] = set()
    for tf in track_feedback or []:
        if tf.get("role") in ("accepted", "seed") and (tf.get("overall_sentiment") or 0) > 0:
            tid = tf.get("track_id")
            if tid:
                ids.add(tid)
    return ids


def _block_p_pivot_away(df: pd.DataFrame, groups: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    """Per-candidate resemblance to the ABANDONED direction + pivot scalars.

    The negative-pivot mirror of E's anchor-match features. For every candidate, flag whether it
    matches the artist / album / track / tags of the carried-forward positive ("abandoned")
    tracks (``_abandoned_anchor_track_ids``), so a LambdaMART tree can learn the interaction
    ``intent_mode==pivot AND resembles-abandoned => demote``. Derived purely from ``track_feedback``
    already in the group record, so no trace regeneration is needed.

    All columns are deliberately left monotone-UNCONSTRAINED (see ``monotone_constraints``): the
    correct direction flips with intent (demote on pivot; the same similarity is mildly positive
    off-pivot), so the tree decides.

    Limitation: the abandoned set comes from positively-rated *played* tracks only; a pivot away
    from an artist that was merely *mentioned* (never played) is not captured by this tier.
    """
    artist_of = dict(zip(meta["track_id"], meta["artist_id"]))
    album_of = dict(zip(meta["track_id"], meta["album_id"]))
    tags_of = dict(zip(meta["track_id"], meta["tags"]))
    grp_state = groups.set_index([groups["session_id"], groups["turn_number"]])

    n = len(df)
    cols = {
        "p__is_abandoned_track": np.zeros(n, "int8"),
        "p__artist_match_abandoned": np.zeros(n, "int8"),
        "p__album_match_abandoned": np.zeros(n, "int8"),
        "p__tag_overlap_abandoned": np.zeros(n, "int16"),
        "p__jaccard_tag_abandoned": np.full(n, np.nan),
        "q__is_pivot": np.zeros(n, "int8"),
        "q__n_abandoned_anchors": np.zeros(n, "int16"),
    }
    df = df.reset_index(drop=True)

    for (sid, turn), sub in df.groupby(GROUP_KEYS, sort=False):
        gs = grp_state.loc[(sid, turn)]
        if isinstance(gs, pd.DataFrame):
            gs = gs.iloc[0]
        abandoned_tracks = _abandoned_anchor_track_ids(gs.get("track_feedback"))
        intent = gs.get("intent_mode")
        idx = sub.index.to_numpy()
        cols["q__is_pivot"][idx] = 1 if intent == "pivot" else 0
        cols["q__n_abandoned_anchors"][idx] = len(abandoned_tracks)
        if not abandoned_tracks:
            continue  # nothing abandoned -> matches stay 0, jaccard stays NaN

        abandoned_artists = {artist_of.get(t) for t in abandoned_tracks}
        abandoned_artists.discard(None)
        abandoned_albums = {album_of.get(t) for t in abandoned_tracks}
        abandoned_albums.discard(None)
        abandoned_tags: set[str] = set()
        for t in abandoned_tracks:
            abandoned_tags.update(tags_of.get(t, ()))

        tids = sub["track_id"].to_numpy()
        artists = np.array([artist_of.get(t) for t in tids], dtype=object)
        albums = np.array([album_of.get(t) for t in tids], dtype=object)
        cols["p__is_abandoned_track"][idx] = [t in abandoned_tracks for t in tids]
        cols["p__artist_match_abandoned"][idx] = [a in abandoned_artists for a in artists]
        cols["p__album_match_abandoned"][idx] = [a in abandoned_albums for a in albums]
        cand_tags = [set(tags_of.get(t, ())) for t in tids]
        cols["p__tag_overlap_abandoned"][idx] = [len(ct & abandoned_tags) for ct in cand_tags]
        if abandoned_tags:
            cols["p__jaccard_tag_abandoned"][idx] = [
                (len(ct & abandoned_tags) / len(ct | abandoned_tags)) if (ct or abandoned_tags) else 0.0
                for ct in cand_tags]

    return pd.DataFrame(cols, index=df.index)


# ------------------------------------------------- block U: user-profile + conversation-goal

USER_GOAL_CATEGORICALS = ["q__goal_category", "q__goal_specificity", "q__user_gender"]
_FORMATIVE_MIN, _FORMATIVE_MAX = 12, 25  # nostalgia band: track released when user was ~12-25

# Geographic / filler tokens stripped from a free-text ``preferred_musical_culture`` so only
# genre tokens remain to match against catalog tags. (Geo words like "american" are themselves
# common tags, so they must be removed or they'd add noise; pure-genre tokens like "rock" stay.)
_CULTURE_STOP = frozenset({
    "culture", "cultures", "music", "musical", "scene", "style", "sound", "sounds", "subculture",
    "and", "of", "the", "a", "an",
    "western", "eastern", "northern", "southern", "north", "south", "east", "west",
    "american", "america", "anglo", "anglophone", "angloamerican", "british", "britain", "uk",
    "european", "europe", "brazilian", "brazil", "nordic", "scandinavian", "german", "germany",
    "french", "france", "francophone", "japanese", "japan", "korean", "korea", "irish", "ireland",
    "spanish", "spain", "hispanic", "canadian", "canada", "australian", "australia", "jamaican",
    "caribbean", "polynesian", "indonesian", "asian", "african", "africa", "diaspora", "black",
    "international", "global", "worldwide", "domestic", "national", "anglophone",
    "contemporary", "modern", "vintage", "retro", "classic", "old", "new", "school", "golden",
    "age", "mainstream", "early", "late", "mid", "era",
})


def _genre_tokens(text: str) -> set[str]:
    """Split free text into lowercased word-tokens (keeping intra-word hyphens like 'hip-hop').

    Drops era tokens ('90s') and single chars. Shared by the culture phrase and candidate tags
    so a single-word culture token ('rock') matches a multi-word tag ('alternative rock')."""
    out: set[str] = set()
    for p in re.split(r"[^\w-]+", text.lower()):
        p = p.strip("-")
        if len(p) < 2 or re.fullmatch(r"\d+s?", p):
            continue
        out.add(p)
    return out


def _culture_tokens(culture: Any) -> set[str]:
    """Genre tokens from a ``preferred_musical_culture`` phrase (geo/filler stripped).

    A token is dropped if it (or, for a hyphenated compound like 'anglo-american', all of its
    hyphen-parts) is geo/filler — so 'hip-hop' survives but 'anglo-american' does not."""
    out: set[str] = set()
    if not culture or not isinstance(culture, str):
        return out
    for t in _genre_tokens(culture):
        if t in _CULTURE_STOP:
            continue
        if all(p in _CULTURE_STOP for p in t.split("-") if p):
            continue
        out.add(t)
    return out


def _session_year(session_date: Any) -> float:
    """Year from a 'YYYY-MM-DD' session_date string; NaN if missing/malformed."""
    if not session_date or not isinstance(session_date, str) or len(session_date) < 4:
        return np.nan
    try:
        return float(int(session_date[:4]))
    except ValueError:
        return np.nan


def _block_u_user_goal(df: pd.DataFrame, groups: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    """Tier-A session-context features + a Tier-B preferred-musical-culture × tags match.

    Group-constant: goal category (A-K) / specificity (LL/LH/HL/HH) / user gender as pinned
    categoricals, plus user age and session year as numerics. Per-candidate: how the candidate's
    release year relates to the session date and user age (track age at session, after-session
    anomaly, user age at release, nostalgia/formative-years flag), and how many genre tokens of
    the user's ``preferred_musical_culture`` appear in the candidate's tags (overlap + binary).
    All monotone-unconstrained.

    Reads fields from the group record (joined by ``session_meta`` in ``build_dataset``). When
    those columns are absent (serving path / pre-join datasets) every feature is neutral
    (NaN / NaN-category), so the column set stays stable and train/serve parity holds.
    """
    year_of = dict(zip(meta["track_id"], meta["release_year"]))
    tags_of = dict(zip(meta["track_id"], meta["tags"]))
    grp_state = groups.set_index([groups["session_id"], groups["turn_number"]])
    cols_present = {c: (c in groups.columns) for c in
                    ("goal_category", "goal_specificity", "user_gender", "user_age",
                     "session_date", "user_preferred_musical_culture")}

    n = len(df)
    cols: dict[str, Any] = {
        "q__goal_category": np.array([None] * n, dtype=object),
        "q__goal_specificity": np.array([None] * n, dtype=object),
        "q__user_gender": np.array([None] * n, dtype=object),
        "q__user_age": np.full(n, np.nan),
        "q__session_year": np.full(n, np.nan),
        "u__track_age_at_session": np.full(n, np.nan),
        "u__released_after_session": np.full(n, np.nan),
        "u__user_age_at_release": np.full(n, np.nan),
        "u__release_in_formative_window": np.full(n, np.nan),
        "u__culture_tag_overlap": np.full(n, np.nan),
        "u__culture_tag_match": np.full(n, np.nan),
    }
    df = df.reset_index(drop=True)
    _tag_tokens_cache: dict[str, set[str]] = {}

    def _tag_tokens(tid):
        toks = _tag_tokens_cache.get(tid)
        if toks is None:
            toks = set()
            for tag in tags_of.get(tid, ()):
                toks |= _genre_tokens(tag)
            _tag_tokens_cache[tid] = toks
        return toks

    def _get(gs, key):
        return gs.get(key) if cols_present[key] else None

    for (sid, turn), sub in df.groupby(GROUP_KEYS, sort=False):
        gs = grp_state.loc[(sid, turn)]
        if isinstance(gs, pd.DataFrame):
            gs = gs.iloc[0]
        idx = sub.index.to_numpy()
        cols["q__goal_category"][idx] = _get(gs, "goal_category")
        cols["q__goal_specificity"][idx] = _get(gs, "goal_specificity")
        cols["q__user_gender"][idx] = _get(gs, "user_gender")

        age = _get(gs, "user_age")
        age = float(age) if (age is not None and not (isinstance(age, float) and math.isnan(age))) else None
        if age is not None:
            cols["q__user_age"][idx] = age
        syear = _session_year(_get(gs, "session_date"))
        if not math.isnan(syear):
            cols["q__session_year"][idx] = syear

        tids = sub["track_id"].to_numpy()

        # Tier-B: preferred_musical_culture genre tokens vs candidate tag tokens.
        culture_toks = _culture_tokens(_get(gs, "user_preferred_musical_culture"))
        if culture_toks:
            ov = [len(culture_toks & _tag_tokens(t)) for t in tids]
            cols["u__culture_tag_overlap"][idx] = ov
            cols["u__culture_tag_match"][idx] = [1.0 if o > 0 else 0.0 for o in ov]

        if math.isnan(syear):
            continue  # no session year -> era interactions stay NaN
        track_age, after, age_at_rel, formative = [], [], [], []
        for t in tids:
            y = year_of.get(t)
            if y is None or (isinstance(y, float) and math.isnan(y)):
                track_age.append(np.nan); after.append(np.nan)
                age_at_rel.append(np.nan); formative.append(np.nan)
                continue
            ta = syear - float(y)
            track_age.append(ta)
            after.append(1.0 if float(y) > syear else 0.0)
            if age is not None:
                ua = age - ta
                age_at_rel.append(ua)
                formative.append(1.0 if _FORMATIVE_MIN <= ua <= _FORMATIVE_MAX else 0.0)
            else:
                age_at_rel.append(np.nan); formative.append(np.nan)
        cols["u__track_age_at_session"][idx] = track_age
        cols["u__released_after_session"][idx] = after
        cols["u__user_age_at_release"][idx] = age_at_rel
        cols["u__release_in_formative_window"][idx] = formative

    out = pd.DataFrame(cols, index=df.index)
    for c in USER_GOAL_CATEGORICALS:
        levels = CATEGORICAL_LEVELS[c]
        vals = pd.Series(out[c], index=out.index)
        # Map any value outside the pinned levels to NA up front (pandas 4 rejects
        # constructing a Categorical from non-null values not in `categories`).
        vals = vals.where(vals.isin(levels))
        out[c] = pd.Categorical(vals, categories=levels)
    return out



# ------------------------------------------------------------------------------- assembly

def features_from_frames(
    candidates: pd.DataFrame,
    groups: pd.DataFrame,
    catalog: Any,
    meta: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Assemble the feature frame from in-memory candidate + group frames.

    Shared by the offline batch builder (``build_features``) and the **online** compiler
    reranker (``mcrs.rerank.online``) so training and serving features are byte-identical.
    Pass a precomputed ``meta`` (``catalog_metadata_frame``) to avoid rebuilding the 47k-row
    catalog frame per call in the online path.
    """
    df = candidates
    if meta is None:
        meta = catalog_metadata_frame(catalog)

    a_f = _block_a_and_f_branch(df, groups)
    a_agg = _block_a_aggregates(a_f)
    c = _block_c(df, meta)
    d = _block_d(df, groups)
    e_f = _block_e_and_f_union(df, groups, meta, a_agg["agg__min_rank"])
    p = _block_p_pivot_away(df, groups, meta)
    u = _block_u_user_goal(df, groups, meta)

    key_cols = GROUP_KEYS + ["track_id"] + (["label"] if "label" in df.columns else [])
    out = pd.concat(
        [df[key_cols].reset_index(drop=True),
         a_f.reset_index(drop=True), a_agg.reset_index(drop=True),
         c.reset_index(drop=True), d.reset_index(drop=True),
         e_f.reset_index(drop=True), p.reset_index(drop=True),
         u.reset_index(drop=True)],
        axis=1,
    )
    return out


def build_features(dataset_dir: str | Path, catalog: Any) -> pd.DataFrame:
    """Assemble the full feature frame (keys + label + features) for one dataset dir."""
    ddir = Path(dataset_dir)
    df = pd.read_parquet(ddir / "candidates.parquet")
    groups = load_groups(ddir)
    return features_from_frames(df, groups, catalog)


NON_FEATURE_COLS = set(GROUP_KEYS + ["track_id", "label"])
CATEGORICAL_FEATURES = ["intent_mode", "exploration_policy",
                        "q__goal_category", "q__goal_specificity", "q__user_gender"]
# Fixed category levels (from the schema enums). pandas categoricals encode by *code* (the
# position in the categories list), so train and serve MUST share the same ordered levels --
# otherwise a single-turn serving frame (one intent_mode) assigns different codes than the
# multi-category training frame and the model reads the wrong category. Pin them here.
CATEGORICAL_LEVELS: dict[str, list[str]] = {
    "intent_mode": ["open_explore", "refinement", "pivot", "playlist_build"],
    "exploration_policy": ["exploit", "diversify_artists", "diversify_albums", "balanced"],
    # Tier-A (block U). Levels pinned from the challenge dataset; unseen values -> NaN code.
    "q__goal_category": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"],
    "q__goal_specificity": ["LL", "LH", "HL", "HH"],
    "q__user_gender": ["female", "male"],
}


def feature_columns(frame: pd.DataFrame) -> list[str]:
    return [c for c in frame.columns if c not in NON_FEATURE_COLS]


def monotone_constraints(feature_cols: list[str]) -> list[int]:
    """+1 on the trustworthy raw branch scores (per registry); 0 elsewhere."""
    cons = []
    for col in feature_cols:
        c = 0
        if col.endswith("__score"):
            key = col[: -len("__score")]
            if key in BRANCH_BY_KEY:
                c = BRANCH_BY_KEY[key].score_monotone
        cons.append(c)
    return cons


def feature_meta(frame: pd.DataFrame) -> dict[str, Any]:
    cols = feature_columns(frame)
    return {
        "feature_columns": cols,
        "categorical_features": [c for c in CATEGORICAL_FEATURES if c in cols],
        "monotone_constraints": monotone_constraints(cols),
        "n_features": len(cols),
    }


def main(argv: list[str] | None = None) -> int:
    from mcrs.qu_modules.v0plus_catalog_lance import LanceDbCatalog

    p = argparse.ArgumentParser(description="Build the rerank feature matrix.")
    p.add_argument("--dataset-dir", default="exp/rerank/dataset")
    p.add_argument("--out", default=None, help="Parquet output path (default: <dataset-dir>/features.parquet)")
    p.add_argument("--db-uri", default="cache/lancedb")
    p.add_argument("--table-name", default="music_track_catalog")
    args = p.parse_args(argv)

    catalog = LanceDbCatalog(db_uri=args.db_uri, table_name=args.table_name)
    frame = build_features(args.dataset_dir, catalog)
    out = Path(args.out) if args.out else Path(args.dataset_dir) / "features.parquet"
    frame.to_parquet(out, index=False)
    meta = feature_meta(frame)
    with open(out.with_suffix(".meta.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
    print(json.dumps({
        "rows": len(frame),
        "n_features": meta["n_features"],
        "categorical": meta["categorical_features"],
        "n_monotone": sum(1 for x in meta["monotone_constraints"] if x != 0),
        "out": str(out),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
