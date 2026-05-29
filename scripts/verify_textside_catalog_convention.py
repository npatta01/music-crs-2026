"""Sanity-check that our text-side encoders share the catalog's
embedding convention.

For each modality we:

1. Load N catalog tracks at random.
2. Construct a short text description of each track (artist + tags).
3. Encode that text with the text-side encoder (SigLIP-2 / CLAP-text).
4. Compute cosine(text_emb, catalog_emb) per track.
5. Verify the mean cosine is in a plausible band (> 0.2 typically — they
   describe the same item, not identical to image/audio).

If the cosines look implausibly low (e.g. near 0), the convention is
likely wrong (normalization, pooling, or model variant mismatch). Fix
before any retrieval evaluation.

This is NOT a quality benchmark — it's a smoke test that the text and
catalog vectors live in the same space.

Usage:
    python scripts/verify_textside_catalog_convention.py --modality siglip2 --n 200
    python scripts/verify_textside_catalog_convention.py --modality clap --n 200 --clap-ckpt /path/to/music_audioset_epoch_15_esc_90.14.pt
"""

from __future__ import annotations

import argparse
import random
import statistics

import numpy as np
import pyarrow.parquet as pq


CATALOG_META = (
    "/Users/npatta01/.cache/huggingface/hub/"
    "datasets--talkpl-ai--TalkPlayData-Challenge-Track-Metadata/"
    "snapshots/91ddb944e1b0f5d13f18a2672214f69022c09d10/"
    "data/all_tracks-00000-of-00001.parquet"
)
CATALOG_EMB = (
    "/Users/npatta01/.cache/huggingface/hub/"
    "datasets--talkpl-ai--TalkPlayData-Challenge-Track-Embeddings/"
    "snapshots/e946dc86e6b245cddd2c6ebf74929176682919ef/"
    "data/all_tracks-00000-of-00001.parquet"
)


def build_text(row: dict) -> str:
    """A short, intent-style description of a track."""
    parts = []
    artist = row.get("artist_name") or []
    if artist:
        parts.append(", ".join(artist))
    tags = row.get("tag_list") or []
    if tags:
        parts.append(", ".join(tags[:6]))
    return " - ".join(parts) if parts else (row.get("track_name", [""])[0] if row.get("track_name") else "")


def cosine_matrix(text_vecs: np.ndarray, item_vecs: np.ndarray) -> np.ndarray:
    text_n = text_vecs / (np.linalg.norm(text_vecs, axis=1, keepdims=True) + 1e-12)
    item_n = item_vecs / (np.linalg.norm(item_vecs, axis=1, keepdims=True) + 1e-12)
    return np.einsum("ij,ij->i", text_n, item_n)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modality", choices=["siglip2", "clap"], required=True)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--clap-ckpt", type=str, default=None)
    ap.add_argument("--normalize", action="store_true",
                    help="L2-normalize the text-side output before scoring.")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    meta_cols = ["track_id", "track_name", "artist_name", "tag_list"]
    meta = pq.read_table(CATALOG_META, columns=meta_cols).to_pylist()

    emb_col = "image-siglip2" if args.modality == "siglip2" else "audio-laion_clap"
    emb_tbl = pq.read_table(CATALOG_EMB, columns=["track_id", emb_col])
    emb_by_id = dict(zip(emb_tbl["track_id"].to_pylist(), emb_tbl[emb_col].to_pylist()))

    rng = random.Random(args.seed)
    rng.shuffle(meta)
    sample = meta[: args.n]

    texts: list[str] = []
    item_vecs: list[list[float]] = []
    for row in sample:
        v = emb_by_id.get(row["track_id"])
        if not v:
            continue
        item_vecs.append(v)
        texts.append(build_text(row))
    n_use = len(item_vecs)
    print(f"using {n_use} sampled tracks")

    if args.modality == "siglip2":
        from mcrs.embeddings.siglip2_text_embedding import SigLIP2TextEmbeddingClient

        client = SigLIP2TextEmbeddingClient(device=args.device, l2_normalize=args.normalize)
    else:
        if not args.clap_ckpt:
            raise SystemExit("--clap-ckpt required for clap modality")
        from mcrs.embeddings.clap_text_embedding import ClapTextEmbeddingClient

        client = ClapTextEmbeddingClient(
            ckpt_path=args.clap_ckpt, device=args.device, l2_normalize=args.normalize
        )

    print("encoding text…")
    text_vecs = np.asarray(client.embed_batch(texts), dtype=np.float32)
    item_arr = np.asarray(item_vecs, dtype=np.float32)
    print(f"text shape: {text_vecs.shape}, catalog shape: {item_arr.shape}")
    assert text_vecs.shape == item_arr.shape, "dim mismatch between text encoder and catalog column"

    cos = cosine_matrix(text_vecs, item_arr)
    print(f"\ncosine(text_for_track, catalog_for_same_track):")
    print(f"  n      : {n_use}")
    print(f"  mean   : {cos.mean():.4f}")
    print(f"  stdev  : {cos.std():.4f}")
    print(f"  min/max: {cos.min():.4f} / {cos.max():.4f}")
    print(f"  p05/p95: {np.percentile(cos,5):.4f} / {np.percentile(cos,95):.4f}")

    # Also: cosine(text_for_track_A, catalog_for_track_B) — should be lower
    # on average than same-track cosines. If not, the encoders are not aligned.
    perm = list(range(n_use))
    rng.shuffle(perm)
    text_shuffled = text_vecs[perm]
    cos_random = cosine_matrix(text_shuffled, item_arr)
    print(f"\ncosine(text_for_random_track, catalog_for_track):")
    print(f"  mean   : {cos_random.mean():.4f}")
    print(f"  lift over random: {(cos.mean() - cos_random.mean()):+.4f}")
    print()
    if cos.mean() < 0.05:
        print("WARNING: mean cosine very low — likely convention mismatch.")
    if cos.mean() - cos_random.mean() < 0.02:
        print("WARNING: no detectable lift over random pairings — encoders may be misaligned.")


if __name__ == "__main__":
    main()
