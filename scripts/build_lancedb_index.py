from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from mcrs.lancedb.indexing import build_track_lancedb_table


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the Music CRS LanceDB track index locally.")
    parser.add_argument("--out-dir", default="cache/lancedb", help="Local LanceDB directory to create.")
    parser.add_argument("--table-name", default="music_track_catalog", help="LanceDB table name.")
    parser.add_argument("--drop-existing", action="store_true", help="Delete the existing DB directory first.")
    embedding_group = parser.add_mutually_exclusive_group()
    embedding_group.add_argument(
        "--include-embeddings",
        dest="include_embeddings",
        action="store_true",
        help="Store precomputed track embedding vectors. This is the default.",
    )
    embedding_group.add_argument(
        "--metadata-only",
        dest="include_embeddings",
        action="store_false",
        help="Skip precomputed track embedding vectors and build only metadata/FTS fields.",
    )
    parser.set_defaults(include_embeddings=True)
    parser.add_argument("--batch-size", type=int, default=1024, help="Rows per LanceDB insert batch.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = build_track_lancedb_table(
        db_uri=args.out_dir,
        table_name=args.table_name,
        include_embeddings=args.include_embeddings,
        drop_existing=args.drop_existing,
        batch_size=args.batch_size,
    )
    print(json.dumps(asdict(summary), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
