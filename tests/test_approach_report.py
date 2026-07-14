from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build_approach_report, validate_approach_report


PNG_DATA = "data:image/png;base64," + base64.b64encode(
    validate_approach_report.PNG_SIGNATURE + b"fixture"
).decode("ascii")


def valid_report(extra_head: str = "", extra_body: str = "") -> str:
    sections = "".join(
        f'<section id="{section}"><details><summary>x</summary>x</details></section>'
        for section in validate_approach_report.SECTION_IDS
    )
    return f"""<!doctype html>
<html><head><style>body {{ color: black; }}</style>{extra_head}</head><body>
<a href="#overview">Overview</a>
<img src="{PNG_DATA}" alt="one"><img src="{PNG_DATA}" alt="two">
<span class="evidence-badge">Verified</span>
<span class="evidence-badge">Inferred</span>
<span class="evidence-badge">Illustrative</span>
<span class="status-pill">Observed failure</span>
<span class="status-pill">Architectural limitation</span>
<span class="status-pill">Measurement gap</span>
<span class="status-pill">Unknown impact</span>
{sections}{extra_body}</body></html>"""


class ApproachReportBuildTests(unittest.TestCase):
    def test_rebases_relative_local_hrefs_from_source_to_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "docs" / "approach" / "source.html"
            output = root / "docs" / "approach.html"
            target = root / "configs" / "active.yaml"
            source.parent.mkdir(parents=True)
            target.parent.mkdir(parents=True)
            target.write_text("active: true\n", encoding="utf-8")
            hero = root / "hero.png"
            alignment = root / "alignment.png"
            hero.write_bytes(validate_approach_report.PNG_SIGNATURE + b"hero")
            alignment.write_bytes(validate_approach_report.PNG_SIGNATURE + b"alignment")
            source.write_text(
                '<a href="../../configs/active.yaml#ranking">config</a>'
                '<a href="#overview">fragment</a>'
                '<a href="https://example.test/citation">citation</a>'
                '<a href="data:text/plain,source">data</a>'
                '<img src="{{HERO_DATA_URI}}"><img src="{{ALIGNMENT_DATA_URI}}">',
                encoding="utf-8",
            )

            with patch.object(
                build_approach_report,
                "ASSETS",
                (
                    ("{{HERO_DATA_URI}}", hero),
                    ("{{ALIGNMENT_DATA_URI}}", alignment),
                ),
            ):
                build_approach_report.build(source, output)

            packaged = output.read_text(encoding="utf-8")
            self.assertIn('href="../configs/active.yaml#ranking"', packaged)
            self.assertIn('href="#overview"', packaged)
            self.assertIn('href="https://example.test/citation"', packaged)
            self.assertIn('href="data:text/plain,source"', packaged)


class ApproachReportValidationTests(unittest.TestCase):
    def validate_fixture(self, html: str) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.html"
            report.write_text(html, encoding="utf-8")
            return validate_approach_report.validate(report)

    def test_missing_packaged_local_href_fails(self) -> None:
        errors = self.validate_fixture(
            valid_report(extra_body='<a href="missing/source.md">missing</a>')
        )
        self.assertTrue(
            any("missing local href target" in error for error in errors), errors
        )

    def test_existing_local_href_and_citation_data_and_fragment_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "source.md"
            target.write_text("source", encoding="utf-8")
            report = root / "report.html"
            report.write_text(
                valid_report(
                    extra_body=(
                        '<a href="source.md#evidence">local</a>'
                        '<a href="https://example.test/citation">citation</a>'
                        '<a href="data:text/plain,evidence">data</a>'
                    )
                ),
                encoding="utf-8",
            )
            self.assertEqual(validate_approach_report.validate(report), [])

    def test_resource_bearing_attributes_reject_external_and_sibling_dependencies(self) -> None:
        cases = {
            "srcset": '<source srcset="https://example.test/a.png 1x">',
            "mixed srcset": f'<source srcset="{PNG_DATA} 1x,sibling.png 2x">',
            "poster": '<video poster="sibling.png"></video>',
            "object data": '<object data="sibling.svg"></object>',
            "iframe": '<iframe src="https://example.test/embed"></iframe>',
        }
        for name, markup in cases.items():
            with self.subTest(name=name):
                errors = self.validate_fixture(valid_report(extra_body=markup))
                self.assertTrue(
                    any("runtime-loaded" in error for error in errors), errors
                )

    def test_data_resources_are_allowed_for_all_covered_attributes(self) -> None:
        markup = (
            f'<source srcset="{PNG_DATA} 1x, {PNG_DATA} 2x">'
            f'<video poster="{PNG_DATA}"></video>'
            '<object data="data:image/svg+xml,%3Csvg%3E%3C/svg%3E"></object>'
            '<iframe src="data:text/html,%3Cp%3Eembedded%3C/p%3E"></iframe>'
        )
        self.assertEqual(self.validate_fixture(valid_report(extra_body=markup)), [])


if __name__ == "__main__":
    unittest.main()
