"""
Music CRS — Interactive Prediction Explorer

A Streamlit app for browsing and evaluating predictions from the
Music Conversational Recommender System challenge.

Supports:
  - Dev set predictions (with ground truth comparison + metrics)
  - Blind set predictions (no ground truth, just browse)

Run:
    streamlit run streamlit_app.py
"""

import os
import json
import glob
import math
import numpy as np
import pandas as pd
import streamlit as st
from datasets import load_dataset

st.set_page_config(
    page_title="Music CRS Explorer",
    page_icon="🎵",
    layout="wide",
)

# Let inline HTML blocks inherit Streamlit's theme text colour (light + dark)
st.markdown("""
<style>
  div[data-testid="stMarkdownContainer"] div,
  div[data-testid="stMarkdownContainer"] small,
  div[data-testid="stMarkdownContainer"] span,
  div[data-testid="stMarkdownContainer"] i,
  div[data-testid="stMarkdownContainer"] b { color: inherit; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Data loading (cached so we only fetch once)
# ─────────────────────────────────────────────

@st.cache_data(show_spinner="Loading track catalog from Hugging Face...")
def load_track_catalog():
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Track-Metadata", split="all_tracks")
    return {item["track_id"]: item for item in ds}


@st.cache_data(show_spinner="Loading dev set ground truth...")
def load_ground_truth():
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")
    sessions = {s["session_id"]: s for s in ds}
    gt = {
        (s["session_id"], t["turn_number"]): t["content"]
        for s in ds
        for t in s["conversations"]
        if t["role"] == "music"
    }
    return sessions, gt


@st.cache_data(show_spinner="Loading blind set conversations...")
def load_blind_sessions():
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="blind_a")
    return {s["session_id"]: s for s in ds}


@st.cache_data(show_spinner="Loading predictions...")
def load_predictions(filepath: str):
    with open(filepath) as f:
        raw = json.load(f)
    return {(p["session_id"], p["turn_number"]): p for p in raw}


# ─────────────────────────────────────────────
# Metric helpers
# ─────────────────────────────────────────────

def ndcg_at_k(predicted_ids, gt_id, k):
    if not gt_id or not predicted_ids:
        return 0.0
    for rank, tid in enumerate(predicted_ids[:k], start=1):
        if tid == gt_id:
            return 1.0 / math.log2(rank + 1)
    return 0.0


def hit_at_k(predicted_ids, gt_id, k):
    if not gt_id or not predicted_ids:
        return 0
    return int(gt_id in predicted_ids[:k])


# ─────────────────────────────────────────────
# Display helpers
# ─────────────────────────────────────────────

def track_info(tid, track_meta):
    meta = track_meta.get(tid, {})
    return {
        "name":   (meta.get("track_name")  or ["?"])[0],
        "artist": (meta.get("artist_name") or ["?"])[0],
        "album":  (meta.get("album_name")  or ["?"])[0],
        "tags":   ", ".join((meta.get("tag_list") or [])[:5]),
        "pop":    meta.get("popularity", "?"),
        "year":   str(meta.get("release_date", ""))[:4],
    }


def render_track_card(tid, track_meta, rank=None, highlight=False):
    info = track_info(tid, track_meta)
    # Use higher opacity so the card is visible in both light and dark mode
    bg = "rgba(202,138,4,0.28)" if highlight else "rgba(128,128,128,0.18)"
    border = "1px solid rgba(202,138,4,0.8)" if highlight else "1px solid rgba(128,128,128,0.35)"
    rank_str = f"**#{rank}** " if rank else ""
    star = " ⭐ (Ground Truth)" if highlight else ""
    st.markdown(
        f"""<div style="border:{border};border-radius:8px;padding:10px;background:{bg};margin-bottom:6px">
        {rank_str}<b>{info['name']}</b>{star}<br>
        <i>{info['artist']}</i><br>
        <span style="font-size:0.85em;opacity:0.8">{info['album']}</span><br>
        <span style="font-size:0.8em;opacity:0.65">{info['tags']}</span><br>
        <span style="font-size:0.8em">Popularity: {info['pop']} · {info['year']}</span>
        </div>""",
        unsafe_allow_html=True,
    )


def render_conversation(session, target_turn=None, track_meta=None):
    for turn in session.get("conversations", []):
        role = turn["role"]
        content = turn["content"]
        tnum = turn["turn_number"]
        is_target = tnum == target_turn

        if role == "user":
            # Higher opacity: visible on dark AND light backgrounds
            opacity = "0.35" if is_target else "0.22"
            border_w = "3px" if is_target else "2px"
            label = f"Turn {tnum} · User" + (" ← selected turn" if is_target else "")
            st.markdown(
                f'<div style="background:rgba(59,130,246,{opacity});border-left:{border_w} solid #3b82f6;'
                f'text-align:right;padding:8px 12px;border-radius:0 8px 8px 0;margin:3px 0">'
                f'<small><b>{label}</b></small><br>{content}</div>',
                unsafe_allow_html=True,
            )
        elif role == "assistant":
            st.markdown(
                f'<div style="background:rgba(34,197,94,0.22);border-left:2px solid #22c55e;'
                f'text-align:left;padding:8px 12px;border-radius:0 8px 8px 0;margin:3px 0">'
                f'<small><b>Turn {tnum} · Assistant</b></small><br>{content}</div>',
                unsafe_allow_html=True,
            )
        # music turns are shown in the right panel


# ─────────────────────────────────────────────
# Aggregate metrics (cached on predictions dict)
# ─────────────────────────────────────────────

def compute_aggregate_metrics(predictions, ground_truth, track_meta):
    ndcg1, ndcg10, ndcg20 = [], [], []
    hit1, hit10, hit20 = [], [], []
    all_ids = set()
    for (sid, turn), pred in predictions.items():
        gt = ground_truth.get((sid, turn))
        ptids = pred.get("predicted_track_ids", [])
        ndcg1.append(ndcg_at_k(ptids, gt, 1))
        ndcg10.append(ndcg_at_k(ptids, gt, 10))
        ndcg20.append(ndcg_at_k(ptids, gt, 20))
        hit1.append(hit_at_k(ptids, gt, 1))
        hit10.append(hit_at_k(ptids, gt, 10))
        hit20.append(hit_at_k(ptids, gt, 20))
        all_ids.update(ptids)
    return {
        "NDCG@1": np.mean(ndcg1),
        "NDCG@10": np.mean(ndcg10),
        "NDCG@20": np.mean(ndcg20),
        "Hit@1": np.mean(hit1),
        "Hit@10": np.mean(hit10),
        "Hit@20": np.mean(hit20),
        "Catalog Diversity": len(all_ids) / len(track_meta),
        "_ndcg10_list": ndcg10,
        "_hit20_list": hit20,
    }


# ─────────────────────────────────────────────
# App layout
# ─────────────────────────────────────────────

st.title("🎵 Music CRS — Prediction Explorer")
st.caption("Browse predictions from the Music Conversational Recommender System challenge.")

# Sidebar controls
with st.sidebar:
    st.header("Controls")

    split_mode = st.radio(
        "Dataset split",
        ["Dev Set (with ground truth)", "Blind Set A (no ground truth)"],
        index=0,
    )
    is_devset = split_mode.startswith("Dev")

    # Discover prediction files for the selected split
    search_dir = "exp/inference/devset" if is_devset else "exp/inference/blindset"
    pred_files = sorted(glob.glob(f"{search_dir}/*.json"))

    if not pred_files:
        st.warning(
            f"No prediction files found in `{search_dir}/`.\n\n"
            + ("Run `python run_inference_devset.py --tid llama1b_bm25_devset`" if is_devset
               else "Run `python run_inference_blindset.py --tid llama1b_bm25_blindset_A`")
        )
        st.stop()

    selected_file = st.selectbox(
        "Prediction file",
        pred_files,
        format_func=lambda p: os.path.basename(p),
    )

    show_agg = st.toggle("Show aggregate metrics", value=True) if is_devset else False

    st.divider()
    st.markdown(
        "**Legend**\n"
        "- 🔵 User message\n"
        "- 🟢 Assistant reply\n"
        "- ⭐ Ground truth song\n"
        "- 🟡 Highlighted = ground truth in predictions"
    )

# ── Load data ──
track_meta = load_track_catalog()
predictions = load_predictions(selected_file)
pred_session_ids = sorted({sid for (sid, _) in predictions})

if is_devset:
    sessions_dict, ground_truth = load_ground_truth()
else:
    sessions_dict = load_blind_sessions()
    ground_truth = {}

# Filter to sessions that exist in our conversation dataset
pred_session_ids = [sid for sid in pred_session_ids if sid in sessions_dict]

if not pred_session_ids:
    st.error("No matching sessions found between predictions and conversation dataset.")
    st.stop()

# Session and turn selectors (in sidebar)
with st.sidebar:
    selected_sid = st.selectbox(
        "Session",
        pred_session_ids,
        format_func=lambda s: s[:16] + "...",
    )

    if is_devset:
        # Show all turns that have predictions
        available_turns = sorted({turn for (sid, turn) in predictions if sid == selected_sid})
        selected_turn = st.select_slider(
            "Turn",
            options=available_turns if available_turns else [1],
            value=available_turns[0] if available_turns else 1,
        )
    else:
        # Blind set: only one turn
        available_turns = sorted({turn for (sid, turn) in predictions if sid == selected_sid})
        selected_turn = available_turns[0] if available_turns else 1
        st.info(f"Blind set: showing turn {selected_turn}")

# ── Aggregate metrics (dev set only) ──
if is_devset and show_agg:
    st.subheader("📊 Aggregate Metrics")
    metrics = compute_aggregate_metrics(predictions, ground_truth, track_meta)

    cols = st.columns(7)
    for col, key in zip(cols, ["NDCG@1", "NDCG@10", "NDCG@20", "Hit@1", "Hit@10", "Hit@20", "Catalog Diversity"]):
        col.metric(key, f"{metrics[key]:.4f}")

    with st.expander("NDCG@10 distribution across all turns"):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.hist(metrics["_ndcg10_list"], bins=40, color="steelblue", edgecolor="white")
        ax.axvline(metrics["NDCG@10"], color="red", linestyle="--",
                   label=f"Mean: {metrics['NDCG@10']:.4f}")
        ax.set_xlabel("NDCG@10")
        ax.set_ylabel("Count (log scale)")
        ax.set_yscale("log")
        ax.legend()
        ax.set_title("NDCG@10 Distribution")
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()
        hit20_pct = np.mean(metrics["_hit20_list"])
        st.caption(f"Correct track is in the top-20 for **{hit20_pct:.1%}** of turns.")

    st.divider()

# ── Session detail ──
session = sessions_dict.get(selected_sid, {})
profile = session.get("user_profile", {})
goal = session.get("conversation_goal", {})
pred = predictions.get((selected_sid, selected_turn), {})
ptids = pred.get("predicted_track_ids", [])
response = pred.get("predicted_response", "")
gt_id = ground_truth.get((selected_sid, selected_turn)) if is_devset else None

# Session info banner
st.markdown(
    f"""<div style="border:1px solid rgba(99,102,241,0.3);border-left:4px solid #6366f1;padding:10px;border-radius:8px;margin-bottom:12px;font-size:0.9em">
    <b>Session:</b> {selected_sid[:8]}... &nbsp;|&nbsp;
    <b>User:</b> {profile.get('age_group','?')} {profile.get('gender','?')} from {profile.get('country_name','?')} &nbsp;|&nbsp;
    <b>Culture:</b> {profile.get('preferred_musical_culture','?')}<br>
    <b>Goal:</b> <i>{goal.get('listener_goal','?')[:180]}</i>
    </div>""",
    unsafe_allow_html=True,
)

left_col, right_col = st.columns([4, 6])

# ── Left: Conversation ──
with left_col:
    st.subheader("💬 Conversation")
    render_conversation(session, target_turn=selected_turn, track_meta=track_meta)

# ── Right: Predictions ──
with right_col:
    # Dev set: metrics + ground truth
    if is_devset:
        if gt_id and ptids:
            n1  = ndcg_at_k(ptids, gt_id, 1)
            n10 = ndcg_at_k(ptids, gt_id, 10)
            n20 = ndcg_at_k(ptids, gt_id, 20)
            h1  = hit_at_k(ptids, gt_id, 1)
            h10 = hit_at_k(ptids, gt_id, 10)
            h20 = hit_at_k(ptids, gt_id, 20)
            rank_in_pred = ptids.index(gt_id) + 1 if gt_id in ptids else None

            st.subheader(f"📈 Turn {selected_turn} Metrics")
            mc = st.columns(6)
            mc[0].metric("NDCG@1",  f"{n1:.4f}")
            mc[1].metric("NDCG@10", f"{n10:.4f}")
            mc[2].metric("NDCG@20", f"{n20:.4f}")
            mc[3].metric("Hit@1",   str(h1))
            mc[4].metric("Hit@10",  str(h10))
            mc[5].metric("Hit@20",  str(h20))

            st.subheader("⭐ Ground Truth Song")
            if rank_in_pred:
                st.success(f"Found at rank {rank_in_pred} in the top-20!")
            else:
                st.error("Not found in the top-20 predictions.")
            render_track_card(gt_id, track_meta, highlight=True)

        elif not ptids:
            st.warning("No predictions for this turn.")
        else:
            st.info("No ground truth for this turn.")

    # LLM response
    if response:
        st.subheader("🤖 LLM Response")
        st.markdown(
            f'<div style="background:rgba(34,197,94,0.22);padding:12px;border-radius:0 8px 8px 0;border-left:4px solid #22c55e">{response}</div>',
            unsafe_allow_html=True,
        )

    # Top-20 predicted tracks
    st.subheader(f"🎶 Top-20 Predicted Tracks")
    if not ptids:
        st.info("No predictions found for this turn.")
    else:
        # Build a DataFrame for display
        rows = []
        for rank, tid in enumerate(ptids, 1):
            info = track_info(tid, track_meta)
            is_gt = (tid == gt_id)
            rows.append({
                "Rank": rank,
                "Track Name": info["name"],
                "Artist": info["artist"],
                "Album": info["album"],
                "Tags": info["tags"],
                "Popularity": info["pop"],
                "Year": info["year"],
                "✓ GT": "⭐" if is_gt else "",
            })

        df = pd.DataFrame(rows)

        def highlight_gt_row(row):
            if row["✓ GT"] == "⭐":
                return ["background-color: #fef9c3; color: #1a1a1a"] * len(row)
            return [""] * len(row)

        st.dataframe(
            df.style.apply(highlight_gt_row, axis=1),
            use_container_width=True,
            hide_index=True,
            height=min(600, 40 + 35 * len(df)),
        )

        if is_devset and gt_id:
            st.caption("⭐ Yellow row = ground truth song (if found in top-20)")
