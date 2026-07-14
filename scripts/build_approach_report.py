#!/usr/bin/env python3
"""Package the canonical approach report as deterministic self-contained HTML."""

from __future__ import annotations

import argparse
import base64
import html
import os
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ASSETS = (
    ("{{HERO_DATA_URI}}", Path("docs/approach/assets/hero.png")),
    ("{{ALIGNMENT_DATA_URI}}", Path("docs/approach/assets/alignment-vs-distortion.png")),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("docs/approach/source.html"),
        help="canonical HTML source",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/approach.html"),
        help="packaged HTML output",
    )
    return parser.parse_args()


def png_data_uri(path: Path) -> str:
    payload = path.read_bytes()
    if not payload.startswith(PNG_SIGNATURE):
        raise ValueError(f"invalid PNG signature: {path}")
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:image/png;base64,{encoded}"


HREF_ATTRIBUTE = re.compile(
    r"(?P<prefix>\bhref\s*=\s*)(?P<quote>['\"])(?P<value>.*?)(?P=quote)",
    flags=re.IGNORECASE,
)


def rebase_local_hrefs(source: str, source_path: Path, output_path: Path) -> str:
    """Preserve local link targets when source and packaged HTML live apart."""

    def replace(match: re.Match[str]) -> str:
        raw_value = html.unescape(match.group("value"))
        parsed = urlsplit(raw_value)
        if parsed.scheme or parsed.netloc or not parsed.path or raw_value.startswith("#"):
            return match.group(0)
        target = (source_path.parent / parsed.path).resolve()
        rebased_path = Path(os.path.relpath(target, output_path.parent.resolve())).as_posix()
        rebased = urlunsplit(("", "", rebased_path, parsed.query, parsed.fragment))
        quote = match.group("quote")
        escaped = html.escape(rebased, quote=True)
        if quote == "'":
            escaped = escaped.replace("&#x27;", "&#39;")
        return f'{match.group("prefix")}{quote}{escaped}{quote}'

    return HREF_ATTRIBUTE.sub(replace, source)


def build(source_path: Path, output_path: Path) -> int:
    source = source_path.read_text(encoding="utf-8")
    packaged = source
    for placeholder, asset_path in ASSETS:
        count = packaged.count(placeholder)
        if count != 1:
            raise ValueError(
                f"expected placeholder exactly once: {placeholder}; found {count}"
            )
        packaged = packaged.replace(placeholder, png_data_uri(asset_path))

    remaining = sorted(set(re.findall(r"\{\{[^{}]*\}\}", packaged)))
    if remaining or "{{" in packaged or "}}" in packaged:
        detail = ", ".join(remaining) if remaining else "malformed template token"
        raise ValueError(f"unreplaced template token: {detail}")

    packaged = rebase_local_hrefs(packaged, source_path, output_path)
    output = packaged.encode("utf-8")
    output_path.write_bytes(output)
    print(f"source: {source_path}")
    print(f"output: {output_path}")
    print(f"bytes: {len(output)}")
    return len(output)


def main() -> int:
    args = parse_args()
    try:
        build(args.source, args.output)
    except (OSError, UnicodeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
