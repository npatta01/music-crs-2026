"""
Download inference results or scores from the Modal volume to the local exp/ directory.

Usage:
    # Download inference predictions
    python modal/download_results.py --tid llama1b_bm25_devset

    # Download evaluation scores
    python modal/download_results.py --tid llama1b_bm25_devset --type scores
"""

import argparse
import os


def main():
    parser = argparse.ArgumentParser(description="Download results from music-crs-results Modal volume.")
    parser.add_argument("--tid", required=True, help="Task ID (e.g. llama1b_bm25_devset)")
    parser.add_argument("--split", default="devset", help="Dataset split (devset, blindset_A, ...)")
    parser.add_argument("--type", choices=["inference", "scores"], default="inference",
                        help="What to download: inference predictions or evaluation scores")
    parser.add_argument("--out_dir", default="exp", help="Local output base directory")
    args = parser.parse_args()

    import modal

    vol = modal.Volume.from_name("music-crs-results")

    if args.type == "inference":
        remote_path = f"inference/{args.split}/{args.tid}.json"
        local_path = os.path.join(args.out_dir, "inference", args.split, f"{args.tid}.json")
    else:
        remote_path = f"scores/{args.split}/{args.tid}.json"
        local_path = os.path.join(args.out_dir, "scores", args.split, f"{args.tid}.json")

    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    print(f"Downloading {remote_path} → {local_path} ...")
    with open(local_path, "wb") as f:
        for chunk in vol.read_file(remote_path):
            f.write(chunk)
    print("Done.")


if __name__ == "__main__":
    main()
