from __future__ import annotations

import base64
import html
import json
import re
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from scripts import build_approach_report, validate_approach_report


PNG_DATA = "data:image/png;base64," + base64.b64encode(
    validate_approach_report.PNG_SIGNATURE + b"fixture"
).decode("ascii")
REPORT_SOURCE = Path(__file__).resolve().parents[1] / "docs" / "approach" / "source.html"
EVIDENCE_LEDGER = REPORT_SOURCE.parent / "evidence.json"


def report_opening() -> str:
    source = REPORT_SOURCE.read_text(encoding="utf-8")
    return source[source.index('<header class="hero">') : source.index(
        '<div class="deep-dive-boundary"'
    )]


class SourceStructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.directory_links: list[tuple[str, str]] = []
        self.response_payloads: list[tuple[str, bool]] = []
        self._directory_depth = 0
        self._response_depth = 0
        self._details_depth = 0
        self._link_href: str | None = None
        self._link_text: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        classes = set(attributes.get("class", "").split())
        if tag == "nav" and "directory" in classes:
            self._directory_depth = 1
        elif self._directory_depth:
            self._directory_depth += 1
        if tag == "section" and attributes.get("id") == "response":
            self._response_depth = 1
        elif self._response_depth:
            self._response_depth += 1
        if self._response_depth and tag == "details":
            self._details_depth += 1
        if self._directory_depth and tag == "a":
            self._link_href = attributes.get("href")
            self._link_text = []
        if self._response_depth and tag == "pre":
            label = attributes.get("aria-label", "")
            if label.startswith("Exact "):
                self.response_payloads.append((label, self._details_depth > 0))

    def handle_data(self, data: str) -> None:
        if self._link_href is not None:
            self._link_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._directory_depth and tag == "a" and self._link_href is not None:
            self.directory_links.append(
                (self._link_href, " ".join("".join(self._link_text).split()))
            )
            self._link_href = None
            self._link_text = []
        if self._response_depth and tag == "details":
            self._details_depth -= 1
        if self._directory_depth:
            self._directory_depth -= 1
        if self._response_depth:
            self._response_depth -= 1


def valid_report(extra_head: str = "", extra_body: str = "") -> str:
    section_ids = (
        "overview",
        "walkthrough",
        "state",
        "compile",
        "ranking",
        "response",
        "evaluation",
        "infrastructure",
        "reproduce",
    )
    sections = "".join(
        f'<section id="{section}"><details><summary>x</summary>x</details></section>'
        for section in section_ids
    )
    return f"""<!doctype html>
<html><head><style>body {{ color: black; }}</style>{extra_head}</head><body>
<a href="#overview">Overview</a>
<img src="{PNG_DATA}" alt="one"><img src="{PNG_DATA}" alt="two">
<span class="evidence-badge">Verified</span>
<span class="evidence-badge">Inferred</span>
<span class="evidence-badge">Illustrative</span>
{sections}{extra_body}</body></html>"""


class ApproachReportBuildTests(unittest.TestCase):
    def test_build_supports_a_report_without_decorative_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "docs" / "approach" / "source.html"
            output = root / "docs" / "approach.html"
            source.parent.mkdir(parents=True)
            source.write_text("<main>No decorative images</main>", encoding="utf-8")

            build_approach_report.build(source, output)

            self.assertEqual(
                output.read_text(encoding="utf-8"),
                "<main>No decorative images</main>",
            )

    def test_opening_contains_complete_submitted_architecture(self) -> None:
        opening = report_opening()
        for label in (
            "Conversation",
            "LLM state",
            "V1 → V0Plus projection",
            "Entity resolution",
            "Query compiler",
            "Retrieval mesh",
            "Candidate pool assembly",
            "LightGBM LambdaMART",
            "Exact-track pin",
            "Final artist guard",
            "Top 20",
            "Top-1 explanation",
        ):
            self.assertIn(label, opening)
        self.assertIn('class="offline-loop"', opening)
        self.assertIn("LLM-as-judge", opening)

    def test_opening_does_not_present_rrf_as_the_final_ranker(self) -> None:
        opening = report_opening()
        self.assertNotIn("Weighted RRF", opening)
        self.assertIn("LightGBM determines the learned base order", opening)

    def test_opening_has_no_decorative_image(self) -> None:
        self.assertNotIn("<img", report_opening())

    def test_obsolete_walkthrough_styles_and_classes_are_absent(self) -> None:
        source = REPORT_SOURCE.read_text(encoding="utf-8")
        for selector in ("badge", "turn", "turn.listener", "speaker"):
            self.assertNotRegex(source, rf"(?m)^\s*\.{re.escape(selector)}\s*\{{")
        class_values = re.findall(r'class=["\']([^"\']*)["\']', source)
        class_tokens = {token for value in class_values for token in value.split()}
        self.assertTrue({"badge", "turn", "listener", "speaker"}.isdisjoint(class_tokens))

    def test_executive_example_exposes_meaningful_state(self) -> None:
        opening = report_opening()
        for label in (
            "Intent mode",
            "Exploration policy",
            "Routing",
            "Resolved entities",
            "Positive facets",
            "Negative facets",
            "Hard constraints",
            "History treatment",
        ):
            self.assertIn(label, opening)
        self.assertIn("Pumped Up Kicks", opening)
        self.assertIn("BM25 rank 1", opening)
        self.assertIn("reference conversation text", opening)

    def test_executive_example_scopes_frozen_baseline_ranks(self) -> None:
        opening = report_opening()
        self.assertIn("Verified frozen 2026-06-06 devset baseline", opening)
        self.assertIn(
            "BM25 rank 1 → fused rank 1 → recorded final rank 1.", opening
        )
        self.assertNotIn("LightGBM final rank 1", opening)

    def test_tablet_architecture_reflows_without_minimum_track_widths(self) -> None:
        source = REPORT_SOURCE.read_text(encoding="utf-8")
        tablet_marker = "@media (min-width: 720px) and (max-width: 1063px) {"
        self.assertIn(tablet_marker, source)
        tablet_start = source.index(tablet_marker)
        tablet_end = source.index("@media (max-width: 719px) {", tablet_start)
        tablet_css = source[tablet_start:tablet_end]

        self.assertIn(
            ".online-path { grid-template-columns: repeat(4, minmax(0, 1fr)); }",
            tablet_css,
        )
        self.assertIn(
            ".architecture-node:nth-child(4) { grid-column: 3 / span 2;",
            tablet_css,
        )

    def test_quick_opening_stays_under_250_visible_words(self) -> None:
        source = REPORT_SOURCE.read_text(encoding="utf-8")
        opening = source[source.index('<header class="hero">') : source.index(
            '<div class="deep-dive-boundary"'
        )]
        visible = re.sub(r"<(style|script).*?</\1>", " ", opening, flags=re.S)
        visible = re.sub(r"<[^>]+>", " ", visible)
        words = re.findall(r"\b[\w’'-]+\b", html.unescape(visible))
        self.assertLessEqual(len(words), 250)

    def test_directory_begins_after_the_deep_dive_boundary(self) -> None:
        source = REPORT_SOURCE.read_text(encoding="utf-8")
        self.assertLess(
            source.index('<div class="deep-dive-boundary"'),
            source.index('<div class="directory-shell">'),
        )

    def test_source_is_an_approach_only_deck(self) -> None:
        source = REPORT_SOURCE.read_text(encoding="utf-8")
        required = [
            "overview", "walkthrough", "state", "compile", "ranking",
            "response", "evaluation", "infrastructure", "reproduce",
        ]
        positions = [source.index(f'id="{section_id}"') for section_id in required]
        self.assertEqual(positions, sorted(positions))
        for removed in ("examples", "gaps", "lessons"):
            self.assertNotIn(f'id="{removed}"', source)
        for forbidden in (
            "Submitted failure spine",
            "completion-handling failure",
            "first broken boundary",
            "Primary bad trace",
            "failure-trace",
        ):
            self.assertNotIn(forbidden, source)

        walkthrough = source[
            source.index('<section class="chapter" id="walkthrough"') :
            source.index('<section class="chapter" id="state"')
        ]
        self.assertIn("Pumped Up Kicks", walkthrough)
        self.assertNotIn("Blind-B", walkthrough)

    def test_ranking_chapter_names_the_final_submitted_orderer(self) -> None:
        source = REPORT_SOURCE.read_text(encoding="utf-8")
        ranking = source[source.index('<section class="chapter" id="ranking"') : source.index(
            '<section class="chapter" id="response"'
        )]
        self.assertIn("ranking.mode: lgbm", ranking)
        self.assertIn("learned base order", ranking)
        self.assertIn("Exact-track pin", ranking)
        self.assertIn("confidence ≥90", ranking)
        self.assertIn("same-turn artist guard", ranking)
        self.assertIn("visual/lyric rescue stages are disabled", ranking)
        self.assertIn("candidate pool assembly", ranking)

    def test_evaluation_separates_ranking_metrics_from_llm_judging(self) -> None:
        source = REPORT_SOURCE.read_text(encoding="utf-8")
        evaluation = source[source.index('<section class="chapter" id="evaluation"') : source.index(
            '<section class="chapter" id="infrastructure"'
        )]
        self.assertIn("Ranking relevance", evaluation)
        self.assertIn("Response quality", evaluation)
        self.assertIn("LLM-as-judge", evaluation)
        self.assertIn("does not rank tracks", evaluation)

    def test_ignored_artifact_provenance_is_visible_but_not_linked(self) -> None:
        source = REPORT_SOURCE.read_text(encoding="utf-8")
        local_hrefs = re.findall(r'<a\b[^>]*\bhref=["\']([^"\']+)', source)
        self.assertFalse(
            any("../../exp/" in href for href in local_hrefs),
            local_hrefs,
        )
        provenance_paths = (
            "exp/inference/blindset_B/"
            "state_ranker_v10_lgbm_blindset_B_trace.jsonl",
            "exp/inference/blindset_B/state_ranker_v10_lgbm_blindset_B.json",
        )
        for path in provenance_paths:
            self.assertIn(f"<code>{path}</code>", source)
        self.assertEqual(source.count(f"<code>{provenance_paths[1]}</code>"), 1)

    def test_evidence_ledger_contains_only_approach_contracts(self) -> None:
        evidence = json.loads(EVIDENCE_LEDGER.read_text(encoding="utf-8"))
        for removed in ("failureExamples", "gaps", "goodExamples"):
            self.assertNotIn(removed, evidence)
        self.assertIn("submittedMechanics", evidence["primaryTrace"])
        self.assertNotIn("submittedFailure", evidence["primaryTrace"])

    def test_directory_contains_only_approach_slides(self) -> None:
        source = REPORT_SOURCE.read_text(encoding="utf-8")
        parser = SourceStructureParser()
        parser.feed(source)
        expected = [
            ("#overview", "Architecture"),
            ("#walkthrough", "Worked example"),
            ("#state", "State"),
            ("#compile", "Retrieval"),
            ("#ranking", "Ranking"),
            ("#response", "Response"),
            ("#evaluation", "Evaluation"),
            ("#infrastructure", "Compute"),
            ("#reproduce", "Reproduce"),
        ]
        self.assertEqual(parser.directory_links, expected)

    def test_exact_response_payloads_are_progressively_disclosed(self) -> None:
        parser = SourceStructureParser()
        parser.feed(REPORT_SOURCE.read_text(encoding="utf-8"))
        self.assertEqual(
            parser.response_payloads,
            [
                ("Exact reconstructed listener context and style message", True),
                ("Exact final response-model user wrapper", True),
            ],
        )

    def test_small_screen_directory_scrolls_inside_navigation(self) -> None:
        source = REPORT_SOURCE.read_text(encoding="utf-8")
        mobile_marker = "@media (max-width: 55.999rem) {"
        self.assertIn(mobile_marker, source)
        mobile_start = source.index(mobile_marker)
        mobile_end = source.index("}", mobile_start)
        mobile_css = source[mobile_start:mobile_end]
        self.assertIn(".directory ul", mobile_css)
        self.assertIn("overflow-x: auto", mobile_css)
        self.assertIn("flex-wrap: nowrap", mobile_css)

    def test_rebases_relative_local_hrefs_from_source_to_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "docs" / "approach" / "source.html"
            output = root / "docs" / "approach.html"
            target = root / "configs" / "active.yaml"
            source.parent.mkdir(parents=True)
            target.parent.mkdir(parents=True)
            target.write_text("active: true\n", encoding="utf-8")
            source.write_text(
                '<a href="../../configs/active.yaml#ranking">config</a>'
                '<a href="#overview">fragment</a>'
                '<a href="https://example.test/citation">citation</a>'
                '<a href="data:text/plain,source">data</a>',
                encoding="utf-8",
            )

            build_approach_report.build(source, output)

            packaged = output.read_text(encoding="utf-8")
            self.assertIn('href="../configs/active.yaml#ranking"', packaged)
            self.assertIn('href="#overview"', packaged)
            self.assertIn('href="https://example.test/citation"', packaged)
            self.assertIn('href="data:text/plain,source"', packaged)

    def test_rebased_href_preserves_query_and_fragment_and_validates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "docs" / "approach" / "source.html"
            output = root / "docs" / "approach.html"
            target = root / "configs" / "active.yaml"
            source.parent.mkdir(parents=True)
            target.parent.mkdir(parents=True)
            target.write_text("active: true\n", encoding="utf-8")
            fixture = valid_report(
                extra_body=(
                    '<a href="../../configs/active.yaml?mode=full&amp;stage=ranking#ranking">'
                    "config</a>"
                )
            )
            source.write_text(fixture, encoding="utf-8")

            build_approach_report.build(source, output)

            packaged = output.read_text(encoding="utf-8")
            self.assertIn(
                'href="../configs/active.yaml?mode=full&amp;stage=ranking#ranking"',
                packaged,
            )
            self.assertEqual(validate_approach_report.validate(output), [])

    def test_build_rejects_malformed_template_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.html"
            output = root / "approach.html"
            source.write_text("<main>{{BROKEN</main>", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "malformed template token"):
                build_approach_report.build(source, output)


class ApproachReportValidationTests(unittest.TestCase):
    def validate_fixture(self, html: str) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.html"
            report.write_text(html, encoding="utf-8")
            return validate_approach_report.validate(report)

    def test_approach_only_fixture_does_not_require_gap_statuses(self) -> None:
        self.assertEqual(self.validate_fixture(valid_report()), [])

    def test_status_pills_do_not_count_as_evidence_statuses(self) -> None:
        parser = validate_approach_report.ReportParser()
        parser.feed(
            '<span class="status-pill">Verified</span>'
            '<span class="status-pill">Inferred</span>'
            '<span class="status-pill">Illustrative</span>'
        )
        self.assertEqual(parser.evidence_statuses, set())

    def test_missing_packaged_local_href_fails(self) -> None:
        errors = self.validate_fixture(
            valid_report(extra_body='<a href="missing/source.md">missing</a>')
        )
        self.assertTrue(
            any("missing local href target" in error for error in errors), errors
        )

    def test_local_href_outside_report_repository_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "repository" / "docs" / "approach.html"
            report.parent.mkdir(parents=True)
            (root / "outside.json").write_text("{}", encoding="utf-8")
            report.write_text(
                valid_report(extra_body='<a href="../../outside.json">outside</a>'),
                encoding="utf-8",
            )

            errors = validate_approach_report.validate(report)

            self.assertTrue(
                any("outside report repository" in error for error in errors), errors
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

    def test_zero_embedded_pngs_are_allowed(self) -> None:
        report = valid_report().replace(f'<img src="{PNG_DATA}" alt="one">', "")
        report = report.replace(f'<img src="{PNG_DATA}" alt="two">', "")
        self.assertEqual(self.validate_fixture(report), [])


if __name__ == "__main__":
    unittest.main()
