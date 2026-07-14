#!/usr/bin/env python3
"""Validate the packaged, self-contained system approach report."""

from __future__ import annotations

import argparse
import base64
import binascii
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


SECTION_IDS = (
    "overview",
    "infrastructure",
    "walkthrough",
    "state",
    "compile",
    "ranking",
    "response",
    "evaluation",
    "examples",
    "gaps",
    "lessons",
    "reproduce",
)
EVIDENCE_STATUSES = ("Verified", "Inferred", "Illustrative")
GAP_STATUSES = (
    "Observed failure",
    "Architectural limitation",
    "Measurement gap",
    "Unknown impact",
)
PNG_PREFIX = "data:image/png;base64,"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class ReportParser(HTMLParser):
    """Collect structural facts without executing or loading report content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.section_ids: list[str] = []
        self.internal_links: list[str] = []
        self.details_count = 0
        self.png_data_uris: list[str] = []
        self.evidence_statuses: set[str] = set()
        self.gap_statuses: set[str] = set()
        self.style_parts: list[str] = []
        self.errors: list[str] = []
        self._status_markers: list[tuple[str, str, list[str]]] = []
        self._style_depth = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        classes = set(attributes.get("class", "").split())
        if inline_style := attributes.get("style"):
            self.style_parts.append(inline_style)
        element_id = attributes.get("id")
        if element_id:
            self.ids.append(element_id)
            if tag == "section":
                self.section_ids.append(element_id)

        if tag == "a" and (href := attributes.get("href", "")).startswith("#"):
            self.internal_links.append(href[1:])
        if tag == "details":
            self.details_count += 1
        if tag == "img" and (src := attributes.get("src", "")).startswith(PNG_PREFIX):
            self.png_data_uris.append(src)

        src = attributes.get("src")
        if src and not src.startswith("data:"):
            self.errors.append(f"runtime-loaded src on <{tag}>: {src}")
        if tag == "link" and "stylesheet" in attributes.get("rel", "").lower().split():
            self.errors.append("runtime-loaded stylesheet is not allowed")
        if tag == "script":
            self.errors.append("script is not allowed")

        if tag == "style":
            self._style_depth += 1
        if tag == "dt":
            self._status_markers.append((tag, "definition", []))
        elif tag == "span" and "status-pill" in classes:
            self._status_markers.append((tag, "status-pill", []))
        elif tag == "span" and "evidence-badge" in classes:
            self._status_markers.append((tag, "evidence-badge", []))

    def handle_data(self, data: str) -> None:
        if self._style_depth:
            self.style_parts.append(data)
        for _, _, parts in self._status_markers:
            parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "style" and self._style_depth:
            self._style_depth -= 1
        for index in range(len(self._status_markers) - 1, -1, -1):
            marker_tag, marker_kind, parts = self._status_markers[index]
            if marker_tag != tag:
                continue
            del self._status_markers[index]
            text = " ".join("".join(parts).split())
            if marker_kind in {"definition", "evidence-badge", "status-pill"}:
                self.evidence_statuses.update(
                    status
                    for status in EVIDENCE_STATUSES
                    if text == status or text.startswith(f"{status} ·")
                )
            if marker_kind == "status-pill":
                self.gap_statuses.update(
                    status
                    for status in GAP_STATUSES
                    if text == status or text.startswith(f"{status} ·")
                )
            break


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="packaged HTML report")
    return parser.parse_args()


def validate(report: Path) -> list[str]:
    if not report.is_file():
        return [f"missing report: {report}"]

    try:
        source = report.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"cannot read report as UTF-8: {exc}"]

    parser = ReportParser()
    try:
        parser.feed(source)
        parser.close()
    except Exception as exc:  # HTMLParser can surface malformed entity errors.
        return [f"cannot parse report: {exc}"]

    errors = list(parser.errors)
    if parser.section_ids != list(SECTION_IDS):
        errors.append(
            "required sections missing, duplicated, or out of order: "
            + ", ".join(SECTION_IDS)
        )
    duplicate_ids = sorted({item for item in parser.ids if parser.ids.count(item) > 1})
    if duplicate_ids:
        errors.append("duplicate ids: " + ", ".join(duplicate_ids))
    invalid_anchors = sorted(
        {target for target in parser.internal_links if not target or target not in parser.ids}
    )
    if invalid_anchors:
        errors.append("invalid internal anchors: " + ", ".join(invalid_anchors))
    if parser.details_count < 8:
        errors.append(f"expected at least 8 disclosures; found {parser.details_count}")
    if len(parser.png_data_uris) != 2:
        errors.append(
            f"expected exactly 2 embedded PNG data URIs; found {len(parser.png_data_uris)}"
        )
    for index, uri in enumerate(parser.png_data_uris, 1):
        try:
            payload = base64.b64decode(uri.removeprefix(PNG_PREFIX), validate=True)
        except (binascii.Error, ValueError):
            errors.append(f"embedded PNG {index} is not valid base64")
            continue
        if not payload.startswith(PNG_SIGNATURE):
            errors.append(f"embedded PNG {index} has an invalid PNG signature")

    for status in EVIDENCE_STATUSES:
        if status not in parser.evidence_statuses:
            errors.append(f"missing evidence status: {status}")
    for status in GAP_STATUSES:
        if status not in parser.gap_statuses:
            errors.append(f"missing gap status: {status}")

    css = re.sub(r"/\*.*?\*/", "", "".join(parser.style_parts), flags=re.DOTALL)
    if re.search(r"@import\b", css, flags=re.IGNORECASE):
        errors.append("CSS @import is not allowed")
    for match in re.finditer(
        r"url\(\s*(['\"]?)(.*?)\1\s*\)", css, flags=re.IGNORECASE | re.DOTALL
    ):
        target = match.group(2).strip()
        if target and not target.lower().startswith("data:") and not target.startswith("#"):
            errors.append(f"external CSS url is not allowed: {target}")
    if "{{" in source or "}}" in source:
        errors.append("unreplaced template token found")
    return errors


def main() -> int:
    args = parse_args()
    errors = validate(args.report)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("approach report valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
