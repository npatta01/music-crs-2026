from __future__ import annotations

import argparse

from mcrs.lancedb.modal_client import LanceDbModalClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke-test the deployed Modal LanceDB query function.")
    parser.add_argument("--app-name", default="music-crs", help="Modal app deployment name.")
    parser.add_argument("--class-name", default="ModalRetrievalService", help="Modal service class name.")
    parser.add_argument("--query", default="dark atmospheric synthwave", help="Text query to search.")
    parser.add_argument("--topk", type=int, default=20, help="Number of track IDs to return.")
    parser.add_argument("--remote-db-uri", default="/root/models/lancedb", help="Remote LanceDB path in Modal.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = LanceDbModalClient(app_name=args.app_name, class_name=args.class_name)
    track_ids = client.query(
        args.query,
        topk=args.topk,
        retrieval_config=None,
    )
    for track_id in track_ids:
        print(track_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
