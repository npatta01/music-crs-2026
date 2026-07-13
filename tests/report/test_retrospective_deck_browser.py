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
    assert browser_page.locator(".deck-slide").count() == 50
    assert browser_page.locator(".deck-chapter").evaluate_all(
        "nodes => nodes.map(node => node.querySelectorAll('.deck-slide').length)"
    ) == [6, 7, 5, 7, 7, 13, 5]
    assert browser_page.locator(".deck-vertical-rail").count() == 7
    assert browser_page.locator(".deck-rail-button").count() == 50
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
    assert browser_page.locator(".deck-flow-lane").count() >= 7
    assert browser_page.locator(".deck-flow-step").count() >= 20
    assert browser_page.locator("figure.deck-visual img").count() == 0
    cover_box = covers.first.locator(".deck-slide-inner").bounding_box()
    assert cover_box is not None and cover_box["width"] > 1180
    assert browser_page.locator(".deck-slide--story .portable-markdown").first.evaluate(
        "node => getComputedStyle(node).maxWidth"
    ) != "none"
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


def test_progressive_disclosure_and_sources(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report)
    exact_table = browser_page.locator('#outcome\\/leaderboard-table [data-artifact-block-id="leaderboard_table"]')
    assert exact_table.is_visible()
    assert browser_page.locator(".deck-source-list .portable-sources").count() == 1
    assert browser_page.locator(".deck-source-list .portable-sources > ol > li").count() == 10
    assert browser_page.locator(".retrospective-deck a[href^='https://']").count() >= 27
    browser_page.goto(f"{enhanced_report.as_uri()}#synthesis/evidence")
    browser_page.wait_for_function("document.documentElement.dataset.deckReady === 'true'")
    source_details = browser_page.locator(".deck-source-list")
    source_details.evaluate("node => node.open = true")
    assert source_details.locator(".portable-sources").is_visible()


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
    browser_page.goto(enhanced_report.as_uri())
    browser_page.wait_for_function("document.documentElement.dataset.deckReady === 'true'")
    assert browser_page.locator(".deck-source-list").count() == 1
    browser_page.emulate_media(media="print")
    browser_page.evaluate("dispatchEvent(new Event('beforeprint'))")
    assert browser_page.locator("details.deck-disclosure:not([open])").count() == 0
    assert browser_page.locator(".deck-chrome").first.evaluate("node => getComputedStyle(node).display") == "none"
    assert browser_page.locator(".deck-slide").nth(49).is_visible()
    assert browser_page.locator(".deck-source-list .portable-sources").is_visible()
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
    browser_page.wait_for_url("**#retrieval/retriever-matrix")
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
