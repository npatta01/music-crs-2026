"""Build the offline tag-embedding index for the tiered tag resolver.

Enumerates the catalog tag vocabulary from LanceDB, frequency-filters it
(dropping singleton/junk tags), embeds the surviving tags with the same
Qwen3 encoder the dense branches use (litellm -> DeepInfra, disk-cached),
and stores a compressed .npz + .meta.json sidecar.

Usage:
    python scripts/build_tag_embedding_index.py \
        --db-uri ./cache/lancedb \
        --out cache/tag_embedding_index/qwen_0_6b.npz \
        --min-track-count 5
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mcrs.qu_modules.tag_resolver import TagEmbeddingIndex, catalog_tag_key  # noqa: E402


def enumerate_tag_frequencies(db_uri: str, table_name: str) -> Counter:
    from mcrs.qu_modules.catalog_lance import LanceDbCatalog

    catalog = LanceDbCatalog(db_uri=db_uri, table_name=table_name)
    counts: Counter = Counter()
    for track_id in catalog.all_track_ids():
        seen_for_track = set()
        for tag in catalog.tag_list(track_id):
            key = catalog_tag_key(str(tag))
            if key and key not in seen_for_track:
                seen_for_track.add(key)
                counts[key] += 1
    return counts


def build_embed_fn(model_name: str, api_base: str, batch_size: int):
    import os

    from mcrs.embeddings.litellm_client import LiteLLMEmbeddingClient

    client = LiteLLMEmbeddingClient(
        model_name=model_name,
        api_base=api_base,
        api_key=os.environ.get("DEEPINFRA_API_KEY"),
        batch_size=batch_size,
        encoding_format="float",
    )
    return client


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-uri", default="./cache/lancedb")
    parser.add_argument("--table-name", default="music_track_catalog")
    parser.add_argument(
        "--out", default="cache/tag_embedding_index/qwen_0_6b.npz"
    )
    parser.add_argument("--min-track-count", type=int, default=5)
    parser.add_argument(
        "--model-name", default="openai/Qwen/Qwen3-Embedding-0.6B"
    )
    parser.add_argument(
        "--api-base", default="https://api.deepinfra.com/v1/openai"
    )
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument(
        "--limit", type=int, default=0, help="Debug: cap tag count (0 = all)."
    )
    args = parser.parse_args()

    t0 = time.time()
    print(f"Enumerating tag vocabulary from {args.db_uri}/{args.table_name} ...")
    counts = enumerate_tag_frequencies(args.db_uri, args.table_name)
    total = len(counts)
    kept = sorted(
        (tag for tag, c in counts.items() if c >= args.min_track_count),
        key=lambda t: (-counts[t], t),
    )
    if args.limit > 0:
        kept = kept[: args.limit]
    print(
        f"vocab: {total} distinct normalized tags, "
        f"{len(kept)} kept at min_track_count>={args.min_track_count} "
        f"({total - len(kept)} dropped)"
    )

    client = build_embed_fn(args.model_name, args.api_base, args.batch_size)
    vectors: list[list[float]] = []
    for start in range(0, len(kept), args.batch_size):
        chunk = kept[start : start + args.batch_size]
        vectors.extend(client.embed_batch(chunk))
        done = start + len(chunk)
        if done % (args.batch_size * 20) < args.batch_size or done == len(kept):
            print(f"  embedded {done}/{len(kept)} ({time.time() - t0:.0f}s)")

    index = TagEmbeddingIndex(tags=kept, vectors=vectors)
    out_path = Path(args.out)
    index.save(out_path)
    meta = {
        "model_name": args.model_name,
        "api_base": args.api_base,
        "min_track_count": args.min_track_count,
        "total_vocab": total,
        "kept_vocab": len(kept),
        "dim": len(vectors[0]) if vectors else 0,
        "built_unix": int(time.time()),
        "db_uri": args.db_uri,
        "table_name": args.table_name,
    }
    meta_path = out_path.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"wrote {out_path} + {meta_path} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
