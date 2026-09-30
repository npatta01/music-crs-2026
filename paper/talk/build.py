#!/usr/bin/env python3
"""Inline every figure into a single self-contained talk.html.

deck.html references figures/*.svg on disk, which is convenient to edit but
fragile to carry to a conference laptop. This emits one file with the figures
base64-embedded as data URIs, so the deck works from a USB stick with no
network and no sibling directory.

Embedding each SVG inside an <img> (rather than splicing the markup inline)
keeps every figure in its own document, so the glyph ids that pdftocairo emits
cannot collide between figures.

Usage: python3 paper/talk/build.py
"""

import base64
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
SRC = HERE / "deck.html"
OUT = HERE / "talk.html"


def data_uri(path: pathlib.Path) -> str:
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{payload}"


def main() -> int:
    html = SRC.read_text(encoding="utf-8")
    missing, inlined = [], []

    def sub(match: re.Match) -> str:
        rel = match.group(1)
        path = HERE / rel
        if not path.exists():
            missing.append(rel)
            return match.group(0)
        if rel not in inlined:
            inlined.append(rel)
        return f'src="{data_uri(path)}"'

    html = re.sub(r'src="(figures/[^"]+)"', sub, html)

    if missing:
        print(f"missing figures: {', '.join(sorted(set(missing)))}", file=sys.stderr)
        return 1

    OUT.write_text(html, encoding="utf-8")
    print(f"{OUT.relative_to(HERE.parent.parent)}  {OUT.stat().st_size / 1024:.0f} KB")
    for rel in inlined:
        print(f"  inlined {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
