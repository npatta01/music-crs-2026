from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

import pytest
from playwright.sync_api import Locator, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "retrospective.html"
ENHANCER = ROOT / "scripts/report/retrospective_deck.mjs"


@pytest.fixture(scope="session")
def enhanced_report(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("retrospective-deck") / "retrospective.html"
    subprocess.run(
        ["node", str(ENHANCER), "--input", str(REPORT), "--output", str(output)],
        cwd=ROOT,
        check=True,
        text=True,
    )
    return output


@pytest.fixture()
def page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path="/usr/bin/google-chrome",
            args=["--no-sandbox"],
        )
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        yield page, errors
        context.close()
        browser.close()


def open_deck(page: Page, report: Path, suffix: str = "") -> None:
    page.goto(f"{report.as_uri()}{suffix}")
    page.locator("html[data-deck-ready='true']").wait_for()


def _slide_overflow_audit(slide: Locator, tolerance: int = 2) -> dict:
    return slide.evaluate(
        """(node, tolerance) => {
          const rect = node.getBoundingClientRect();
          const viewportWidth = document.documentElement.clientWidth;
          const owner = node.closest('.deck-vertical');
          const visible = element => {
            const style = getComputedStyle(element);
            const box = element.getBoundingClientRect();
            return style.display !== 'none'
              && style.visibility !== 'hidden'
              && box.width > 0
              && box.height > 0;
          };
          const nestedVerticalOverflow = [node, ...node.querySelectorAll('*')]
            .filter(element => element !== owner && visible(element))
            .filter(element => ['auto', 'scroll'].includes(getComputedStyle(element).overflowY))
            .filter(element => element.scrollHeight > element.clientHeight + tolerance)
            .map(element => ({
              tag: element.tagName.toLowerCase(),
              id: element.id,
              classes: element.className,
              overflowY: getComputedStyle(element).overflowY,
              clientHeight: element.clientHeight,
              scrollHeight: element.scrollHeight,
            }));
          return {
            rect: {left: rect.left, right: rect.right},
            viewportWidth,
            clientWidth: node.clientWidth,
            scrollWidth: node.scrollWidth,
            chapterScrollerCount: (owner ? 1 : 0) + node.querySelectorAll('.deck-vertical').length,
            chapterScrollerOverflowY: owner ? getComputedStyle(owner).overflowY : null,
            nestedVerticalOverflow,
          };
        }""",
        tolerance,
    )


def _assert_slide_has_no_unintended_overflow(slide: Locator, tolerance: int = 2) -> None:
    audit = _slide_overflow_audit(slide, tolerance)
    assert audit["rect"]["left"] >= -tolerance, audit
    assert audit["rect"]["right"] <= audit["viewportWidth"] + tolerance, audit
    assert audit["scrollWidth"] <= audit["clientWidth"] + tolerance, audit
    assert audit["chapterScrollerCount"] == 1, audit
    assert audit["chapterScrollerOverflowY"] in {"auto", "scroll"}, audit
    assert audit["nestedVerticalOverflow"] == [], audit


def test_groups_every_block_once(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report)
    assert browser_page.locator(".deck-chapter").count() == 8
    assert browser_page.locator(".deck-slide").count() == 56
    assert browser_page.locator(".deck-chapter").evaluate_all(
        "nodes => nodes.map(node => node.querySelectorAll('.deck-slide').length)"
    ) == [6, 6, 7, 7, 7, 5, 13, 5]
    assert browser_page.locator(".deck-vertical-rail").count() == 8
    assert browser_page.locator(".deck-rail-button").count() == 56
    assigned = browser_page.locator(".deck-slide [data-artifact-block-id]")
    assert assigned.count() == 74
    ids = assigned.evaluate_all("nodes => nodes.map(node => node.dataset.artifactBlockId)")
    assert len(ids) == len(set(ids)) == 74
    assert errors == []


def test_content_aware_archetypes_and_visual_canvas(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report)
    for archetype in ("cover", "story", "visual", "matrix", "audit"):
        assert browser_page.locator(f".deck-slide--{archetype}").count() > 0
    covers = browser_page.locator(".deck-slide--cover")
    assert covers.count() == 7
    assert covers.locator(".deck-chapter-map").count() == 7
    assert browser_page.locator(".deck-flow-lane, .deck-diagnosis").count() >= 6
    assert browser_page.locator(".deck-mechanism").count() >= 4
    assert browser_page.locator(".deck-flow-step, .deck-mechanism-stage").count() >= 20
    assert browser_page.locator("figure.deck-visual img").count() == 0
    cover_box = covers.first.locator(".deck-slide-inner").bounding_box()
    assert cover_box is not None and cover_box["width"] > 1180
    assert browser_page.locator(".deck-slide--story .portable-markdown").first.evaluate(
        "node => getComputedStyle(node).maxWidth"
    ) != "none"
    assert errors == []


def test_diagnosis_is_visual_evidence_not_paragraph_prose(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report, "#diagnosis/information-loss")
    assert browser_page.locator("[data-chapter='diagnosis'] .deck-slide").count() == 6
    assert browser_page.locator("#diagnosis\\/information-loss .deck-bottleneck-stage").count() == 10
    assert browser_page.locator("#diagnosis\\/constraint-wiring .deck-wiring-link").count() >= 8
    assert browser_page.locator("#diagnosis\\/features-seen .deck-feature-family").count() == 6
    assert browser_page.locator("#diagnosis\\/evidence-missed .deck-boundary-column").count() == 3
    assert browser_page.locator("#diagnosis\\/confidence .deck-confidence-column").count() == 3
    for slug in ("score-location", "information-loss", "constraint-wiring", "features-seen", "evidence-missed", "confidence"):
        words = browser_page.locator(f"#diagnosis\\/{slug}").evaluate(
            "node => [...node.querySelectorAll('p')].filter(p => p.offsetParent !== null).map(p => p.textContent).join(' ').split(/\\s+/).filter(Boolean).length"
        )
        assert words <= 120
    assert errors == []


def test_diagnosis_confidence_and_unknown_boundaries_are_explicit(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report, "#diagnosis/confidence")
    text = browser_page.locator("#diagnosis\\/confidence").inner_text()
    for phrase in ("Verified", "Likely contributor", "Unknown", "candidate recall", "echo_retries=0"):
        assert phrase in text
    assert "sole cause" not in text.lower()


def test_curated_and_canonical_submitted_copy_share_candidate_boundary(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report, "?path=curated#ours/inference-rail")
    curated = browser_page.locator("[id='ours/inference-rail']").inner_text()
    assert "Up to 500 hits from each traced branch" in curated
    assert "LightGBM LambdaMART reorders the union" in curated
    browser_page.evaluate("window.__retrospectiveDeck.goTo('ours/offline-rail', {behavior: 'auto'})")
    canonical = browser_page.locator("[id='ours/offline-rail'] .deck-embedded-document").evaluate(
        "node => node.shadowRoot.textContent"
    )
    browser_page.evaluate("window.__retrospectiveDeck.goTo('ours/walkthrough', {behavior: 'auto'})")
    walkthrough = browser_page.locator("[id='ours/walkthrough']").inner_text()
    submitted = f"{canonical}\n{walkthrough}"
    assert "up to 500 hits from each traced branch" in submitted.lower()
    assert "LightGBM" in submitted
    assert not re.search(r"up to 500 candidates from (?:that|the|a|each)? ?union", submitted, re.I)
    assert "top-500 fused pool" not in submitted.lower()
    assert "fused top 500" not in submitted.lower()


def test_reusable_visual_grammars_compare_all_five_teams(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    expected_teams = ["npatta01", "volart", "niwatori", "swyoo", "team2_s2"]
    valid_statuses = {"present", "partial", "not-documented"}
    for slug, selector, row_selector, cell_selector, expected_cells in (
        (
            "query/provenance-stacks",
            ".deck-provenance-stack",
            ".deck-provenance-team",
            ".deck-provenance-layer[data-status]",
            5,
        ),
        ("retrieval/evidence-heatmap", ".deck-evidence-heatmap", "tr[data-team]", "td[data-status]", 11),
        ("response/control-heatmap", ".deck-control-lanes", "tr[data-team]", "td[data-status]", 6),
    ):
        open_deck(browser_page, enhanced_report, f"#{slug}")
        escaped_slug = slug.replace("/", r"\/")
        visual = browser_page.locator(f"#{escaped_slug} {selector}")
        assert visual.count() == 1
        rows = visual.locator(row_selector)
        assert rows.evaluate_all("nodes => nodes.map(node => node.dataset.team)") == expected_teams
        assert rows.evaluate_all(
            "(nodes, cellSelector) => nodes.map(node => node.querySelectorAll(cellSelector).length)",
            cell_selector,
        ) == [expected_cells] * len(expected_teams)
        assert set(visual.locator("[data-status]").evaluate_all("nodes => nodes.map(node => node.dataset.status)")) <= valid_statuses
    assert errors == []


def test_mobile_evidence_heatmap_shows_status_and_short_qualifier(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    browser_page.set_viewport_size({"width": 390, "height": 844})
    open_deck(browser_page, enhanced_report, "#retrieval/evidence-heatmap")
    labels = browser_page.locator("#retrieval\\/evidence-heatmap td[data-status] .deck-grid-cell-label")
    assert labels.count() == 55
    audit = labels.evaluate_all(
        """nodes => nodes.map(node => ({
          text: node.textContent.trim(),
          display: getComputedStyle(node).display,
          visibility: getComputedStyle(node).visibility,
          width: node.getBoundingClientRect().width,
          height: node.getBoundingClientRect().height,
        }))"""
    )
    assert all(item["display"] != "none" and item["visibility"] != "hidden" for item in audit)
    assert all(item["width"] > 0 and item["height"] > 0 for item in audit)
    assert all(re.match(r"^(Present|Partial|Not documented) · .+", item["text"]) for item in audit)
    assert {item["text"].split(" · ", 1)[0] for item in audit} == {"Present", "Partial", "Not documented"}
    assert errors == []


@pytest.mark.parametrize("viewport", [(1533, 903), (1280, 800), (1024, 768), (390, 844)])
def test_answer_first_slides_have_no_overflow(viewport, enhanced_report: Path) -> None:
    width, height = viewport
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": width, "height": height})
        for slug in (
            "diagnosis/score-location", "diagnosis/information-loss", "diagnosis/constraint-wiring",
            "diagnosis/features-seen", "diagnosis/evidence-missed", "diagnosis/confidence",
            "query/provenance-stacks", "retrieval/evidence-heatmap", "response/control-heatmap",
        ):
            open_deck(page, enhanced_report, f"#{slug}")
            slide = page.locator(f"#{slug.replace('/', r'\/')}")
            _assert_slide_has_no_unintended_overflow(slide)
        browser.close()


def test_slide_overflow_assertion_detects_synthetic_regressions(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report, "#diagnosis/score-location")
    slide = browser_page.locator("#diagnosis\\/score-location")

    for translation in ("translateX(-12px)", "translateX(12px)"):
        original_transform = slide.evaluate("node => node.style.transform")
        try:
            slide.evaluate("(node, value) => node.style.transform = value", translation)
            with pytest.raises(AssertionError):
                _assert_slide_has_no_unintended_overflow(slide)
        finally:
            slide.evaluate("(node, value) => node.style.transform = value", original_transform)

    for overflow_y in ("auto", "scroll"):
        try:
            slide.evaluate(
                """(node, overflowY) => {
                  const scroller = document.createElement('div');
                  scroller.dataset.syntheticNestedScroller = overflowY;
                  scroller.style.cssText = `height: 1px; overflow-y: ${overflowY}`;
                  const content = document.createElement('div');
                  content.style.height = '24px';
                  scroller.append(content);
                  node.append(scroller);
                }""",
                overflow_y,
            )
            with pytest.raises(AssertionError):
                _assert_slide_has_no_unintended_overflow(slide)
        finally:
            slide.locator(f"[data-synthetic-nested-scroller='{overflow_y}']").evaluate("node => node.remove()")

    _assert_slide_has_no_unintended_overflow(slide)
    assert errors == []


def test_reusable_visual_grammars_keep_primary_copy_bounded(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    for slug in ("query/provenance-stacks", "retrieval/evidence-heatmap", "response/control-heatmap"):
        open_deck(browser_page, enhanced_report, f"#{slug}")
        words = browser_page.locator(f"[id='{slug}']").evaluate(
            """node => {
              const isHidden = element => {
                for (let current = element; current && current !== node.parentElement; current = current.parentElement) {
                  const style = getComputedStyle(current);
                  if (style.display === 'none' || style.visibility === 'hidden') return true;
                  const rect = current.getBoundingClientRect();
                  const clipped = style.overflow === 'hidden'
                    && rect.width <= 1 && rect.height <= 1
                    && (style.clip !== 'auto' || style.clipPath !== 'none');
                  if (clipped) return true;
                }
                return false;
              };
              const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
              const visibleText = [];
              while (walker.nextNode()) {
                if (!isHidden(walker.currentNode.parentElement)) visibleText.push(walker.currentNode.nodeValue);
              }
              return visibleText.join(' ').split(/\\s+/).filter(Boolean).length;
            }"""
        )
        assert words <= 120
    assert errors == []


def test_every_diagnosis_claim_has_a_visible_explicit_confidence(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report, "#diagnosis/score-location")
    audit = browser_page.locator("[data-chapter='diagnosis']").evaluate(
        """root => {
          const selectors = [
            '.deck-score-finding',
            '.deck-bottleneck-stage',
            '.deck-loss',
            '.deck-wiring-source li',
            '.deck-wiring-link',
            '.deck-wiring-target li',
            '.deck-feature-family',
            '.deck-boundary-column > ul > li',
            '.deck-response-control > li',
            '.deck-confidence-column > ul > li',
            '.deck-belief-timeline > ol > li',
            '.deck-failure-taxonomy > ol > li',
            '.deck-takeaway',
          ];
          const expected = [...root.querySelectorAll(selectors.join(','))];
          const declared = [...root.querySelectorAll('[data-diagnosis-claim]')];
          const valid = new Set(['verified', 'likely', 'unknown']);
          const labels = {
            verified: 'Verified',
            likely: 'Likely contributor',
            unknown: 'Unknown',
          };
          return {
            expectedCount: expected.length,
            declaredCount: declared.length,
            missingDeclarations: expected
              .filter(node => !node.hasAttribute('data-diagnosis-claim'))
              .map(node => node.textContent.trim()),
            invalidConfidence: declared
              .filter(node => !valid.has(node.dataset.confidence))
              .map(node => node.textContent.trim()),
            missingVisibleLabels: declared.filter(node => {
              const badge = node.querySelector(':scope > .deck-confidence-label');
              return !badge
                || badge.textContent.trim() !== labels[node.dataset.confidence]
                || getComputedStyle(badge).display === 'none'
                || getComputedStyle(badge).visibility === 'hidden'
                || badge.offsetParent === null;
            }).map(node => node.textContent.trim()),
          };
        }"""
    )
    assert audit["expectedCount"] >= 70
    assert audit["declaredCount"] == audit["expectedCount"]
    assert audit["missingDeclarations"] == []
    assert audit["invalidConfidence"] == []
    assert audit["missingVisibleLabels"] == []
    assert errors == []


def test_constraint_wiring_keeps_played_track_feedback_distinctions(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report, "#diagnosis/constraint-wiring")
    extracted = browser_page.locator(
        "#diagnosis\\/constraint-wiring .deck-wiring-source li"
    )
    for distinction in (
        "Played-track acceptance",
        "Played-track rejection",
        "Played-track contrast",
        "Played-track sentiment",
        "Pinned played-track references",
    ):
        assert extracted.filter(has_text=distinction).count() == 1
    assert errors == []


def test_dense_topics_teach_then_compare(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report, "#query/lifecycle")
    for mechanism, comparison in (
        ("query/lifecycle", "query/query-matrix"),
        ("query/data-glossary", "query/data-matrix"),
        ("retrieval/retriever-mechanism", "retrieval/retriever-matrix"),
        ("response/overview", "response/grounding-heatmap"),
    ):
        assert browser_page.locator(f"[id='{mechanism}'] .deck-mechanism").count() == 1
        assert browser_page.locator(f"[id='{comparison}'] .deck-comparison").count() == 1
        assert browser_page.locator(f"[id='{comparison}'] .deck-team-row").count() >= 4
        assert browser_page.locator(f"[id='{comparison}'] .deck-common-different").count() == 1
    assert errors == []


def test_exact_dense_evidence_is_progressively_disclosed(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report, "#query/query-matrix")
    details = browser_page.locator(
        "[id='query/query-matrix'] details[data-disclosure-for='query_matrix']"
    )
    assert details.count() == 1
    assert details.get_attribute("open") is None
    evidence = details.locator("[data-artifact-block-id='query_matrix']")
    assert not evidence.is_visible()
    details.locator("summary").click()
    assert evidence.is_visible()


def test_wide_short_chapter_covers_do_not_collide(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    browser_page.set_viewport_size({"width": 1828, "height": 536})
    open_deck(browser_page, enhanced_report, "#query/cover")
    for cover in browser_page.locator(".deck-slide--cover").all():
        copy_box = cover.locator(".deck-page-copy").bounding_box()
        map_box = cover.locator(".deck-chapter-map").bounding_box()
        assert copy_box is not None and map_box is not None
        assert copy_box["x"] + copy_box["width"] <= map_box["x"] - 12
        heading = cover.locator(".deck-slide-heading")
        assert heading.evaluate("node => node.scrollWidth <= node.clientWidth + 1")
    assert errors == []


def test_supplied_failure_pages_promote_embeds_without_nested_scroll(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report)
    failure_pages = (
        "outcome/gap-chart",
        "query/query-matrix",
        "query/data-matrix",
        "query/prompt-audit",
    )
    for slug in failure_pages:
        browser_page.evaluate("slug => window.__retrospectiveDeck.goTo(slug, {behavior: 'auto'})", slug)
        target = browser_page.locator(f"[id='{slug}']")
        if target.locator("iframe").count():
            assert target.locator(".deck-embedded-document").count() > 0
            disclosure = target.locator("details.deck-disclosure")
            if disclosure.count():
                disclosure.first.evaluate("node => node.open = true")
            assert target.locator(".deck-embedded-document").first.is_visible()
        assert target.locator("iframe:visible").count() == 0
        overflow = target.evaluate(
            "node => ({client: node.clientWidth, scroll: node.scrollWidth, embeds: [...node.querySelectorAll('.deck-embedded-document')].map(embed => ({client: embed.clientWidth, scroll: embed.scrollWidth}))})"
        )
        assert overflow["scroll"] <= overflow["client"] + 2
        assert all(embed["scroll"] <= embed["client"] + 2 for embed in overflow["embeds"])
    audit = browser_page.locator("[id='query/prompt-audit'] .deck-embedded-document").first
    assert audit.evaluate("node => [...node.shadowRoot.querySelectorAll('details')].every(item => item.open)")
    assert errors == []


def test_promoted_embeds_are_allowlist_sanitized_and_make_no_requests(enhanced_report: Path) -> None:
    malicious = """<!doctype html><html><head>
      <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data: blob:; style-src 'unsafe-inline'; font-src data:; connect-src 'none'; script-src 'none'; media-src data: blob:; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'">
      <style>
      @import 'https://attacker.invalid/import.css';
      .bad{background:url(https://attacker.invalid/css.png);behavior:url(x);-moz-binding:url(x);}
      .ok{color:rgb(1,2,3)}
    </style></head><body>
      <section class="ok" onclick="fetch('https://attacker.invalid/click')"><p>Evidence survives</p></section>
      <script>fetch('https://attacker.invalid/script')</script>
      <iframe src="https://attacker.invalid/frame"></iframe><object data="https://attacker.invalid/object"></object>
      <embed src="https://attacker.invalid/embed"><form action="https://attacker.invalid/form"><button formaction="javascript:alert(1)">x</button></form>
      <video poster="https://attacker.invalid/poster"><source src="https://attacker.invalid/media"></video>
      <img src="https://attacker.invalid/image" srcset="https://attacker.invalid/2x 2x" onerror="alert(1)">
      <a href="javascript:alert(1)" ping="https://attacker.invalid/ping">unsafe</a>
      <a href="https://example.com/safe">safe</a>
      <svg><a xlink:href="javascript:alert(1)"><animate attributeName="href" values="javascript:alert(1)"/></a></svg>
      <math><annotation-xml encoding="text/html"><script>alert(1)</script></annotation-xml></math>
      <div style="background:url(https://attacker.invalid/inline);color:red">inline</div>
    </body></html>"""
    requests: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 1024, "height": 768})
        page = context.new_page()
        page.on("request", lambda request: requests.append(request.url) if request.url.startswith(("http://", "https://")) else None)
        open_deck(page, enhanced_report)
        requests.clear()
        page.evaluate("""source => {
          const host = window.__retrospectiveDeck.promoteEmbeddedDocument(source);
          host.classList.add('deck-adversarial-host');
          document.body.append(host);
        }""", malicious)
        host = page.locator(".deck-adversarial-host")
        assert host.is_visible()
        audit = host.evaluate(r"""node => {
          const root = node.shadowRoot;
          const elements = [...root.querySelectorAll('*')];
          const attrs = elements.flatMap(element => [...element.attributes].map(attr => `${attr.name}=${attr.value}`));
          return {
            text: root.textContent,
            forbidden: root.querySelectorAll('script,iframe,object,embed,form,input,button,video,audio,source,track,svg,math').length,
            handlers: attrs.filter(value => /^on/i.test(value)),
            fetchAttrs: attrs.filter(value => /^(?:srcset|xlink:href|action|formaction|ping|poster|background)=/i.test(value)),
            executable: attrs.filter(value => /(?:javascript:|vbscript:|data:text\/html)/i.test(value)),
            externalFetch: attrs.filter(value => /^(?:src|srcset|data|action|formaction|ping|poster|background)=.*https?:\/\//i.test(value)),
            inlineStyle: elements.filter(element => element.hasAttribute('style')).length,
            css: [...root.querySelectorAll('style')].map(style => style.textContent).join('\n'),
            links: [...root.querySelectorAll('a')].map(link => link.href),
          };
        }""")
        assert "Evidence survives" in audit["text"]
        assert audit["forbidden"] == 0
        assert audit["handlers"] == []
        assert audit["fetchAttrs"] == []
        assert audit["executable"] == []
        assert audit["externalFetch"] == []
        assert audit["inlineStyle"] == 0
        assert "@import" not in audit["css"].lower()
        assert "url(" not in audit["css"].lower()
        assert "behavior" not in audit["css"].lower()
        assert "binding" not in audit["css"].lower()
        assert audit["links"] == ["https://example.com/safe"]
        assert requests == []
        context.close()
        browser.close()


def test_long_prose_matrices_render_as_readable_team_cards(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report)
    for slug in ("query/query-matrix", "query/data-matrix"):
        browser_page.evaluate("slug => window.__retrospectiveDeck.goTo(slug, {behavior: 'auto'})", slug)
        table = browser_page.locator(f"[id='{slug}'] table.deck-prose-matrix")
        assert table.count() == 1
        assert table.locator("tbody").evaluate("node => getComputedStyle(node).display") == "grid"
        assert table.locator("tbody tr").count() == 5
        labels = table.locator("tbody tr").first.locator("td").evaluate_all(
            "nodes => nodes.map(node => node.dataset.columnLabel)"
        )
        assert all(labels)
        assert float(table.locator("tbody td").first.evaluate("node => parseFloat(getComputedStyle(node).fontSize)")) >= 13


def test_dense_walkthroughs_use_progressive_visual_cards(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report, "#ours/walkthrough")
    for slug, minimum in (("ours/walkthrough", 5), ("leaders/volart-response", 5)):
        browser_page.evaluate("slug => window.__retrospectiveDeck.goTo(slug, {behavior: 'auto'})", slug)
        cards = browser_page.locator(f"[id='{slug}'] .deck-insight-card")
        assert cards.count() >= minimum
        assert browser_page.locator(f"[id='{slug}'] details.deck-insight-card:not([open])").count() >= 1
        cards.first.evaluate("node => node.open = true")
        assert cards.first.locator(".deck-insight-detail").is_visible()
    assert errors == []


def test_leader_introductions_are_compact_system_cards(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    expected = {
        "volart-outcome": {
            "result": "0.5866 composite · 0.3965 nDCG@20 · 4.90/5 judge",
            "query": "GPT-4o-mini produced one cached retrieval rewrite plus positive entity and era JSON.",
            "knowledge": "Official records, train co-occurrence and frequency/MOVES priors, plus generated track descriptions.",
            "retrieval": "Five lanes fed a top-500 LambdaMART boundary with direct co-occurrence features.",
            "response": "Three drafts, independent critique, selective rewrite, hardening, and lexical control.",
            "limit": "Structured musical-fact verification was not documented.",
        },
        "niwatori-outcome": {
            "result": "0.5859 composite · 0.4934 nDCG@20 · 4.45/5 judge",
            "query": "Source-specific safe text, full played history, and last-track transition keys; no LLM retrieval rewrite documented.",
            "knowledge": "Official records plus mapped TalkPlayData-1 co-occurrence and transition statistics.",
            "retrieval": "Fourteen-source union, direct co-occurrence, Markov transition, and 176 documented features with OOF artifacts.",
            "response": "Ten seeded drafts selected for lexical diversity.",
            "limit": "The selector was not a factual critic; response fact checking was not documented.",
        },
        "swyoo-outcome": {
            "result": "0.5784 composite · 0.3829 nDCG@20 · 4.85/5 judge",
            "query": "Separate BM25, QEmb, and two-tower representations with an optional cached session summary.",
            "knowledge": "LRCLIB, Genius, and MusicBrainz enriched lyrics, identifiers, tags, labels, countries, and dates.",
            "retrieval": "Three independently rendered pools with group-aware OOF routing for learned sources.",
            "response": "PAS generation with theme/citation validation and repair.",
            "limit": "One PAS prediction was used; no best-of-N independent critic was documented.",
        },
        "team2-outcome": {
            "result": "0.5759 composite · 0.4452 nDCG@20 · 4.65/5 judge",
            "query": "Conversation BM25, live text, recent item vectors, ALS history, and cached structured lists.",
            "knowledge": "Official catalog, conversations, users, labels, and embeddings; no external music dataset documented.",
            "retrieval": "Live and structured sources fed routed rankers with covariate-shift weighting and 37 documented features.",
            "response": "Verified catalog facts grounded a first draft followed by Gemini Pro refinement.",
            "limit": "No independent structured fact or recommendation-ID integrity check was documented.",
        },
    }
    visible_copy = {}
    for slug, fields in expected.items():
        open_deck(browser_page, enhanced_report, f"#leaders/{slug}")
        card = browser_page.locator(f"#leaders\\/{slug} .deck-system-card")
        assert card.count() == 1
        assert card.locator("[data-system-field]").evaluate_all(
            "nodes => nodes.map(node => node.dataset.systemField)"
        ) == ["result", "query", "knowledge", "retrieval", "response", "limit"]
        visible_copy[slug] = {
            field: card.locator(f"[data-system-field='{field}'] dd").inner_text()
            for field in fields
        }
        assert visible_copy[slug] == fields

    # Preserve evidence boundaries instead of flattening every leader into the
    # same external-data and multi-draft template.
    assert "external" not in visible_copy["volart-outcome"]["knowledge"].lower()
    assert "external" not in visible_copy["niwatori-outcome"]["knowledge"].lower()
    assert "no external music dataset documented" in visible_copy["team2-outcome"]["knowledge"].lower()
    assert "independent critique" not in visible_copy["niwatori-outcome"]["response"].lower()
    assert "independent critique" not in visible_copy["swyoo-outcome"]["response"].lower()
    assert "independent critique" not in visible_copy["team2-outcome"]["response"].lower()
    assert "drafts" not in visible_copy["swyoo-outcome"]["response"].lower()
    assert "drafts" not in visible_copy["team2-outcome"]["response"].lower()
    assert "selector was not a factual critic" in visible_copy["niwatori-outcome"]["limit"].lower()
    assert "one pas prediction" in visible_copy["swyoo-outcome"]["limit"].lower()
    assert "no best-of-n independent critic" in visible_copy["swyoo-outcome"]["limit"].lower()
    assert errors == []


def test_leader_canonical_blocks_share_one_closed_named_disclosure(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    canonical_blocks = {
        "volart-outcome": ("volart_heading", "volart_outcome"),
        "niwatori-outcome": ("niwatori_heading", "niwatori_outcome"),
        "swyoo-outcome": ("swyoo_heading", "swyoo_outcome"),
        "team2-outcome": ("team2_s2_heading", "team2_s2_outcome"),
    }
    for slug, block_ids in canonical_blocks.items():
        open_deck(browser_page, enhanced_report, f"#leaders/{slug}")
        slide = browser_page.locator(f"#leaders\\/{slug}")
        disclosure = slide.locator(f"details[data-disclosure-for='{block_ids[-1]}']")
        assert disclosure.count() == 1
        assert disclosure.get_attribute("open") is None
        assert disclosure.locator("[data-artifact-block-id]").evaluate_all(
            "nodes => nodes.map(node => node.dataset.artifactBlockId)"
        ) == list(block_ids)
        for block_id in block_ids:
            block = disclosure.locator(f"[data-artifact-block-id='{block_id}']")
            assert block.count() == 1
            assert block.is_hidden()
        disclosure.locator("summary").click()
        assert disclosure.get_attribute("open") == ""
        for block_id in block_ids:
            assert disclosure.locator(f"[data-artifact-block-id='{block_id}']").is_visible()
    assert errors == []


def test_score_interpretation_is_three_findings_with_exact_math_disclosed(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report, "#outcome/gap-interpretation")
    assert browser_page.locator("#outcome\\/gap-interpretation .deck-score-finding").count() == 3
    text = browser_page.locator("#outcome\\/gap-interpretation").inner_text()
    assert "arithmetic, not causal" in text.lower()
    assert browser_page.locator(
        "#outcome\\/gap-interpretation details[data-disclosure-for='gap_interpretation']"
    ).count() == 1
    details = browser_page.locator(
        "#outcome\\/gap-interpretation details[data-disclosure-for='gap_interpretation']"
    )
    details.evaluate("node => node.open = true")
    exact_text = details.inner_text()
    assert "0.000000001" in exact_text
    assert "arithmetic decomposition, not a causal decomposition" in exact_text.lower()


def test_diagnosis_slides_show_pinned_submission_and_documentation_boundary(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    for slug in ("score-location", "information-loss", "constraint-wiring", "features-seen", "evidence-missed", "confidence"):
        open_deck(browser_page, enhanced_report, f"#diagnosis/{slug}")
        boundary = browser_page.locator(f"#diagnosis\\/{slug} .deck-evidence-boundary")
        assert boundary.is_visible()
        assert boundary.locator(".deck-pinned-badge").inner_text() == "Blind-B deployed evidence · 2ecc45a7"
        assert "documentation depth can bias" in boundary.inner_text().lower()
        assert "absence from reviewed sources is not proof of absence" in boundary.inner_text().lower()
    assert errors == []


def test_synthesis_matrix_fills_canvas_and_encodes_status(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report, "#synthesis/matrix")
    slide = browser_page.locator("[id='synthesis/matrix'] .deck-slide-inner")
    table = browser_page.locator("[id='synthesis/matrix'] table")
    slide_box = slide.bounding_box()
    table_box = table.bounding_box()
    assert slide_box is not None and table_box is not None
    assert table_box["width"] >= min(1120, slide_box["width"] * .82)
    assert browser_page.locator("[id='synthesis/matrix'] td.deck-status--yes").count() > 0
    assert browser_page.locator("[id='synthesis/matrix'] td.deck-status--partial").count() > 0
    assert browser_page.locator("[id='synthesis/matrix'] td.deck-status--missing").count() > 0
    assert errors == []


def test_prompt_audit_names_the_active_state_contract(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report, "#query/prompt-audit")
    audit = browser_page.locator("[id='query/prompt-audit'] .deck-embedded-document").first
    text = audit.evaluate("node => node.shadowRoot.textContent")
    for phrase in ("Current request", "Facts", "Played-track feedback", "Explicit played-track references", "After extraction", "V0Plus"):
        assert phrase in text
    assert audit.evaluate(
        "node => getComputedStyle(node.shadowRoot.querySelector('.state-contract ul')).display"
    ) == "grid"
    assert errors == []


def test_lane_only_diagrams_use_the_vertical_canvas(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report, "#ours/inference-rail")
    slide = browser_page.locator("[id='ours/inference-rail']")
    assert slide.get_attribute("class") and "deck-flow-only" in slide.get_attribute("class")
    step_box = slide.locator(".deck-flow-step").first.bounding_box()
    assert step_box is not None and step_box["height"] >= 120
    assert float(slide.locator(".deck-flow-step").first.evaluate("node => parseFloat(getComputedStyle(node).fontSize)")) >= 15
    assert errors == []


def test_story_pages_use_presentation_scale_and_canvas(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report, "#outcome/gap-interpretation")
    findings = browser_page.locator("[id='outcome/gap-interpretation'] .deck-score-findings")
    exact_narrative = browser_page.locator(
        "[id='outcome/gap-interpretation'] [data-artifact-block-id='gap_interpretation'] .portable-markdown"
    )
    assert not exact_narrative.is_visible()
    assert float(findings.locator(".deck-score-finding h3").first.evaluate(
        "node => parseFloat(getComputedStyle(node).fontSize)"
    )) >= 18
    box = findings.bounding_box()
    assert box is not None and box["width"] >= 1000

    browser_page.set_viewport_size({"width": 1202, "height": 659})
    browser_page.reload()
    browser_page.wait_for_function("document.documentElement.dataset.deckReady === 'true'")
    findings_box = findings.bounding_box()
    rail_box = browser_page.locator("[data-chapter='outcome'] .deck-vertical-rail").bounding_box()
    assert findings_box is not None and rail_box is not None
    assert findings_box["x"] + findings_box["width"] <= rail_box["x"] - 12


def test_progressive_disclosure_and_sources(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report)
    exact_table = browser_page.locator('#outcome\\/leaderboard-table [data-artifact-block-id="leaderboard_table"]')
    assert not exact_table.is_visible()
    exact_details = browser_page.locator(
        '#outcome\\/leaderboard-table details[data-disclosure-for="leaderboard_table"]'
    )
    assert exact_details.count() == 1
    exact_details.locator("summary").click()
    assert exact_table.is_visible()
    assert browser_page.locator(".deck-source-list .portable-sources").count() == 1
    assert browser_page.locator(".deck-source-list .portable-sources > ol > li").count() == 10
    assert browser_page.locator(".retrospective-deck a[href^='https://']").count() >= 27
    browser_page.goto(f"{enhanced_report.as_uri()}#synthesis/evidence")
    browser_page.wait_for_function("document.documentElement.dataset.deckReady === 'true'")
    source_details = browser_page.locator(".deck-source-list")
    source_details.evaluate("node => node.open = true")
    assert source_details.locator(".portable-sources").is_visible()


def test_leaderboard_uses_compact_ranked_rows(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report, "#outcome/leaderboard-table")
    rows = browser_page.locator("[id='outcome/leaderboard-table'] .deck-score-row")
    assert rows.count() == 5
    scoreboard = browser_page.locator("[id='outcome/leaderboard-table'] .deck-scoreboard")
    assert scoreboard.count() == 1
    box = scoreboard.bounding_box()
    assert box is not None and box["height"] < 430
    assert browser_page.locator(
        "[id='outcome/leaderboard-table'] details[data-disclosure-for='leaderboard_table']"
    ).count() == 1
    assert errors == []


def test_visual_first_default_has_bounded_visible_prose(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report)
    for slug in (
        "query/lifecycle",
        "query/data-matrix",
        "retrieval/retriever-matrix",
        "response/grounding-heatmap",
    ):
        text = browser_page.locator(f"[id='{slug}']").evaluate(
            "node => [...node.querySelectorAll('p')].filter(p => p.offsetParent !== null).map(p => p.textContent).join(' ')"
        )
        assert len(text.split()) <= 120


def test_linear_and_print_modes(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report, "?view=linear")
    assert browser_page.locator("html").get_attribute("data-deck-view") == "linear"
    assert browser_page.locator(".deck-chapter").first.is_visible()
    assert browser_page.locator("details.deck-disclosure:not([open])").count() == 0
    expected = ["title", *re.findall(r'data-artifact-block-id="([^"]+)"', REPORT.read_text())]
    actual = browser_page.locator(".deck-slide [data-artifact-block-id]").evaluate_all(
        "nodes => nodes.map(node => node.dataset.artifactBlockId)"
    )
    assert actual == expected
    assert browser_page.locator(".deck-source-list .portable-sources").is_visible()
    linear_card = browser_page.locator("details.deck-insight-card").first
    assert linear_card.locator("summary").evaluate("node => getComputedStyle(node).display") == "none"
    assert linear_card.locator(".deck-insight-detail strong").first.evaluate("node => getComputedStyle(node).display") != "none"
    browser_page.get_by_role("button", name="Deck view").click()
    assert browser_page.locator(".deck-chapter").evaluate_all("nodes => nodes.map(node => node.dataset.chapter)") == [
        "outcome", "diagnosis", "ours", "query", "retrieval", "response", "leaders", "synthesis"
    ]
    browser_page.get_by_role("button", name="Linear view").click()
    assert browser_page.locator(".deck-slide [data-artifact-block-id]").evaluate_all(
        "nodes => nodes.map(node => node.dataset.artifactBlockId)"
    ) == expected
    browser_page.goto(enhanced_report.as_uri())
    browser_page.wait_for_function("document.documentElement.dataset.deckReady === 'true'")
    assert browser_page.locator(".deck-source-list").count() == 1
    browser_page.emulate_media(media="print")
    browser_page.evaluate("dispatchEvent(new Event('beforeprint'))")
    assert browser_page.locator("details.deck-disclosure:not([open])").count() == 0
    assert browser_page.locator(".deck-chrome").first.evaluate("node => getComputedStyle(node).display") == "none"
    assert browser_page.locator(".deck-slide").nth(49).is_visible()
    assert browser_page.locator(".deck-source-list .portable-sources").is_visible()
    print_card = browser_page.locator("details.deck-insight-card").first
    assert print_card.locator("summary").evaluate("node => getComputedStyle(node).display") == "none"
    assert print_card.locator(".deck-insight-detail strong").first.evaluate("node => getComputedStyle(node).display") != "none"
    browser_page.evaluate("dispatchEvent(new Event('afterprint'))")
    assert browser_page.locator(".deck-source-list").count() == 1


def test_mobile_has_bounded_content_and_touch_targets(enhanced_report: Path) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 390, "height": 844})
        open_deck(page, enhanced_report)
        assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        sizes = page.locator(".deck-chrome button").evaluate_all(
            "nodes => nodes.filter(node => node.offsetParent !== null).map(node => ({width: node.getBoundingClientRect().width, height: node.getBoundingClientRect().height}))"
        )
        assert all(size["width"] >= 44 and size["height"] >= 44 for size in sizes)
        browser.close()


def test_tablet_coarse_pointer_navigation_has_44px_targets_and_no_overflow(enhanced_report: Path) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 1024, "height": 768}, has_touch=True)
        page = context.new_page()
        open_deck(page, enhanced_report)
        controls = page.locator(".deck-chapter-button:visible, .deck-rail-button:visible")
        assert controls.count() > 8
        sizes = controls.evaluate_all(
            "nodes => nodes.map(node => ({label: node.getAttribute('aria-label'), width: node.getBoundingClientRect().width, height: node.getBoundingClientRect().height}))"
        )
        assert all(size["width"] >= 44 and size["height"] >= 44 for size in sizes), sizes
        assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        context.close()
        browser.close()


def test_enhancer_does_not_change_embedded_payload(enhanced_report: Path) -> None:
    source = REPORT.read_text()
    enhanced = enhanced_report.read_text()
    marker = 'id="data-analytics-portable-artifact-payload-source"'
    source_payload = source[source.index(marker):source.index("</template>", source.index(marker))]
    enhanced_payload = enhanced[enhanced.index(marker):enhanced.index("</template>", enhanced.index(marker))]
    assert hashlib.sha256(source_payload.encode()).digest() == hashlib.sha256(enhanced_payload.encode()).digest()


def test_buttons_keys_hash_and_history(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report)
    previous_button = browser_page.locator('[data-action="previous"]')
    next_button = browser_page.locator('[data-action="next"]')
    assert previous_button.is_disabled()
    assert next_button.inner_text() == "Executive answer →"
    next_button.click()
    browser_page.wait_for_url("**#outcome/executive-answer")
    browser_page.keyboard.press("ArrowRight")
    browser_page.wait_for_url("**#diagnosis/score-location")
    browser_page.keyboard.press("ArrowRight")
    browser_page.wait_for_url("**#ours/cover")
    browser_page.keyboard.press("ArrowRight")
    browser_page.wait_for_url("**#query/cover")
    browser_page.keyboard.press("ArrowRight")
    browser_page.wait_for_url("**#retrieval/cover")
    browser_page.keyboard.press("ArrowDown")
    browser_page.wait_for_url("**#retrieval/retriever-mechanism")
    browser_page.go_back()
    browser_page.wait_for_url("**#retrieval/cover")
    assert errors == []


def test_curated_path_is_explicit_and_can_open_full_audit(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report, "?path=curated#outcome/executive-answer")
    assert browser_page.locator("html").get_attribute("data-reading-path") == "curated"
    assert browser_page.get_by_role("button", name="Explore evidence audit").is_visible()
    browser_page.get_by_role("button", name="Next").click()
    browser_page.wait_for_url("**#outcome/gap-chart")
    browser_page.get_by_role("button", name="Explore evidence audit").click()
    assert browser_page.locator("html").get_attribute("data-reading-path") == "audit"
    assert browser_page.get_by_role("button", name="Read retrospective").is_visible()
    assert errors == []


def test_curated_path_does_not_hide_audit_from_jump_or_direct_links(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report, "?path=curated#diagnosis/features-seen")
    browser_page.get_by_role("button", name="Jump").click()
    palette = browser_page.get_by_role("dialog", name="Jump anywhere")
    palette.get_by_role("searchbox").fill("prompt and file audit")
    palette.get_by_role("button", name=re.compile("Prompt and file audit", re.I)).click()
    browser_page.wait_for_url("**#query/prompt-audit")
    assert browser_page.locator("html").get_attribute("data-reading-path") == "audit"


def test_jump_palette_filters_and_restores_focus(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report)
    opener = browser_page.get_by_role("button", name="Jump")
    opener.focus()
    browser_page.keyboard.press("Control+K")
    palette = browser_page.get_by_role("dialog", name="Jump anywhere")
    assert palette.is_visible()
    palette.get_by_role("searchbox").fill("volart")
    palette.get_by_role("button", name="Leading teams — volart · outcome, query, and data").click()
    browser_page.wait_for_url("**#leaders/volart-outcome")
    opener.focus()
    browser_page.keyboard.press("Control+K")
    browser_page.keyboard.press("Escape")
    assert opener.evaluate("node => document.activeElement === node")


def test_direct_and_invalid_hashes(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report, "#response/matrix")
    target = browser_page.locator('#response\\/grounding-heatmap')
    assert target.get_attribute("aria-current") == "true"
    box = target.bounding_box()
    assert box is not None and abs(box["x"]) < 1
    browser_page.goto(f"{enhanced_report.as_uri()}#not/a-slide")
    browser_page.wait_for_url("**#outcome/cover")


def test_direct_hash_opens_disclosure(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report, "#retrieval/feature-matrix?open=feature_matrix")
    assert browser_page.locator('.retrospective-deck [data-artifact-block-id="feature_matrix"]').is_visible()


def test_reduced_motion_and_passive_scroll_do_not_steal_focus(enhanced_report: Path) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1280, "height": 800}, reduced_motion="reduce")
        open_deck(page, enhanced_report)
        assert page.locator(".deck-track").evaluate("node => getComputedStyle(node).scrollBehavior") == "auto"
        page.get_by_role("button", name="Jump").focus()
        page.locator(".deck-track").evaluate("node => node.scrollLeft = node.clientWidth")
        page.wait_for_timeout(120)
        assert page.get_by_role("button", name="Jump").evaluate("node => document.activeElement === node")
        browser.close()


def test_no_external_requests_or_browser_errors(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    requests: list[str] = []
    browser_page.on("request", lambda request: requests.append(request.url))
    open_deck(browser_page, enhanced_report)
    external = [url for url in requests if not url.startswith(("file:", "data:", "blob:"))]
    assert external == []
    assert errors == []


def test_gesture_navigation_creates_history_entry(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report)
    initial_length = browser_page.evaluate("history.length")
    browser_page.locator(".deck-track").evaluate(
        "node => { node.style.scrollBehavior = 'auto'; node.scrollLeft = node.clientWidth; node.style.scrollBehavior = ''; }"
    )
    browser_page.wait_for_url("**#diagnosis/score-location")
    assert browser_page.evaluate("history.length") == initial_length + 1
    browser_page.go_back()
    browser_page.wait_for_url("**#outcome/cover")
    box = browser_page.locator('#outcome\\/cover').bounding_box()
    assert box is not None and abs(box["x"]) < 1


def test_interrupted_programmatic_scroll_reconciles_and_unblocks_gestures(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report)
    browser_page.evaluate(
        "() => { window.__deckPushCalls = 0; const push = history.pushState.bind(history); history.pushState = (...args) => { window.__deckPushCalls += 1; return push(...args); }; }"
    )
    browser_page.evaluate("window.__retrospectiveDeck.goTo('synthesis/cover').slug")
    assert browser_page.evaluate("window.__deckPushCalls") == 1
    browser_page.locator(".deck-track").evaluate(
        "node => { node.style.scrollBehavior = 'auto'; node.scrollLeft = node.clientWidth; node.style.scrollBehavior = ''; }"
    )
    browser_page.wait_for_timeout(150)
    assert browser_page.evaluate("window.__retrospectiveDeck.currentSlug()") == "diagnosis/score-location"
    assert browser_page.evaluate("location.hash") == "#diagnosis/score-location"
    assert browser_page.evaluate("window.__deckPushCalls") == 1

    browser_page.locator(".deck-track").evaluate(
        "node => { node.style.scrollBehavior = 'auto'; node.scrollLeft = node.clientWidth * 2; node.style.scrollBehavior = ''; }"
    )
    browser_page.wait_for_url("**#ours/cover")
    assert browser_page.evaluate("window.__deckPushCalls") == 2


def test_orientation_controls_and_topic_search(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report, "#leaders/volart-outcome")
    assert browser_page.locator(".deck-chapter-button").count() == 8
    current_chapter = browser_page.locator('.deck-chapter-button[aria-current="true"]')
    assert current_chapter.get_attribute("aria-label") == "Leading teams"
    rail_button = browser_page.locator('.deck-rail-button[aria-current="true"]')
    rail_button.focus()
    browser_page.wait_for_timeout(150)
    assert rail_button.evaluate("node => getComputedStyle(node, '::after').opacity") == "1"
    browser_page.keyboard.press("Control+K")
    palette = browser_page.get_by_role("dialog", name="Jump anywhere")
    palette.get_by_role("searchbox").fill("BM25")
    assert palette.locator(".deck-jump-item").count() > 0

    browser_page.set_viewport_size({"width": 390, "height": 844})
    browser_page.reload()
    browser_page.wait_for_function("document.documentElement.dataset.deckReady === 'true'")
    assert "Leading teams" in browser_page.locator(".deck-mobile-orientation").inner_text()


def test_javascript_disabled_keeps_complete_linear_fallback(enhanced_report: Path) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 1280, "height": 800}, java_script_enabled=False)
        page = context.new_page()
        page.goto(enhanced_report.as_uri())
        assert page.locator("#data-analytics-portable-fallback").is_visible()
        assert page.locator(".portable-block-stack > [data-artifact-block-id]").count() == 73
        assert page.locator("#data-analytics-portable-fallback > .portable-sources").is_visible()
        context.close()
        browser.close()
