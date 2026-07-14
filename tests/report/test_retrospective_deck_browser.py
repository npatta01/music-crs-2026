from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright

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
    page.wait_for_function("document.documentElement.dataset.deckReady === 'true'")


def test_groups_every_block_once(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report)
    assert browser_page.locator(".deck-chapter").count() == 7
    assert browser_page.locator(".deck-slide").count() == 51
    assert browser_page.locator(".deck-chapter").evaluate_all(
        "nodes => nodes.map(node => node.querySelectorAll('.deck-slide').length)"
    ) == [6, 7, 6, 7, 7, 13, 5]
    assert browser_page.locator(".deck-vertical-rail").count() == 7
    assert browser_page.locator(".deck-rail-button").count() == 51
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
    assert browser_page.locator(".deck-flow-lane").count() >= 6
    assert browser_page.locator(".deck-mechanism").count() >= 4
    assert browser_page.locator(".deck-flow-step, .deck-mechanism-stage").count() >= 20
    assert browser_page.locator("figure.deck-visual img").count() == 0
    cover_box = covers.first.locator(".deck-slide-inner").bounding_box()
    assert cover_box is not None and cover_box["width"] > 1180
    assert browser_page.locator(".deck-slide--story .portable-markdown").first.evaluate(
        "node => getComputedStyle(node).maxWidth"
    ) != "none"
    assert errors == []


def test_dense_topics_teach_then_compare(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report, "#query/lifecycle")
    for mechanism, comparison in (
        ("query/lifecycle", "query/query-matrix"),
        ("query/data-glossary", "query/data-matrix"),
        ("retrieval/retriever-mechanism", "retrieval/retriever-matrix"),
        ("response/overview", "response/matrix"),
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
    narrative = browser_page.locator(
        "[id='outcome/gap-interpretation'] [data-artifact-block-id='gap_interpretation'] .portable-markdown"
    )
    assert float(narrative.evaluate("node => parseFloat(getComputedStyle(node).fontSize)")) >= 18
    box = narrative.bounding_box()
    assert box is not None and box["width"] >= 1000
    paragraphs = narrative.locator("p")
    assert float(paragraphs.first.evaluate("node => parseFloat(getComputedStyle(node).lineHeight)")) >= 28

    browser_page.set_viewport_size({"width": 1202, "height": 659})
    browser_page.reload()
    browser_page.wait_for_function("document.documentElement.dataset.deckReady === 'true'")
    narrative_box = narrative.bounding_box()
    rail_box = browser_page.locator("[data-chapter='outcome'] .deck-vertical-rail").bounding_box()
    assert narrative_box is not None and rail_box is not None
    assert narrative_box["x"] + narrative_box["width"] <= rail_box["x"] - 12


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
        "query/query-glossary",
        "query/data-matrix",
        "retrieval/retriever-matrix",
        "response/matrix",
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
    browser_page.wait_for_url("**#query/cover")
    browser_page.keyboard.press("ArrowRight")
    browser_page.wait_for_url("**#retrieval/cover")
    browser_page.keyboard.press("ArrowDown")
    browser_page.wait_for_url("**#retrieval/retriever-mechanism")
    browser_page.go_back()
    browser_page.wait_for_url("**#retrieval/cover")
    assert errors == []


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
    target = browser_page.locator('#response\\/matrix')
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
    browser_page.wait_for_url("**#query/cover")
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
    assert browser_page.evaluate("window.__retrospectiveDeck.currentSlug()") == "query/cover"
    assert browser_page.evaluate("location.hash") == "#query/cover"
    assert browser_page.evaluate("window.__deckPushCalls") == 1

    browser_page.locator(".deck-track").evaluate(
        "node => { node.style.scrollBehavior = 'auto'; node.scrollLeft = node.clientWidth * 2; node.style.scrollBehavior = ''; }"
    )
    browser_page.wait_for_url("**#retrieval/cover")
    assert browser_page.evaluate("window.__deckPushCalls") == 2


def test_orientation_controls_and_topic_search(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report, "#leaders/volart-outcome")
    assert browser_page.locator(".deck-chapter-button").count() == 7
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
