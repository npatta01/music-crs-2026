from __future__ import annotations

import hashlib
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
    page.wait_for_selector('html[data-deck-ready="true"]')


def test_groups_every_block_once(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report)
    assert browser_page.locator(".deck-chapter").count() == 7
    assert browser_page.locator(".deck-slide").count() == 29
    assert browser_page.locator(".deck-vertical-rail").count() == 7
    assert browser_page.locator(".deck-rail-button").count() == 29
    assigned = browser_page.locator(".deck-slide [data-artifact-block-id]")
    assert assigned.count() == 74
    ids = assigned.evaluate_all("nodes => nodes.map(node => node.dataset.artifactBlockId)")
    assert len(ids) == len(set(ids)) == 74
    assert errors == []


def test_progressive_disclosure_and_sources(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report)
    exact_table = browser_page.locator('details[data-disclosure-for="leaderboard_table"]')
    assert exact_table.locator("summary").inner_text() == "Open the exact leaderboard table"
    assert not exact_table.get_attribute("open")
    assert browser_page.locator(".deck-source-list .portable-sources").count() == 1
    assert browser_page.locator(".deck-source-list .portable-sources > ol > li").count() == 10
    assert browser_page.locator(".retrospective-deck a[href^='https://']").count() >= 27


def test_linear_and_print_modes(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report, "?view=linear")
    assert browser_page.locator("html").get_attribute("data-deck-view") == "linear"
    assert browser_page.locator(".deck-chapter").first.is_visible()
    assert browser_page.locator("details.deck-disclosure:not([open])").count() == 0
    browser_page.goto(enhanced_report.as_uri())
    browser_page.wait_for_selector('html[data-deck-ready="true"]')
    assert browser_page.locator("details.deck-disclosure:not([open])").count() > 0
    browser_page.emulate_media(media="print")
    browser_page.evaluate("dispatchEvent(new Event('beforeprint'))")
    assert browser_page.locator("details.deck-disclosure:not([open])").count() == 0
    assert browser_page.locator(".deck-chrome").first.evaluate("node => getComputedStyle(node).display") == "none"
    assert browser_page.locator(".deck-slide").nth(28).is_visible()
    browser_page.evaluate("dispatchEvent(new Event('afterprint'))")
    assert browser_page.locator("details.deck-disclosure:not([open])").count() > 0


def test_mobile_has_bounded_content_and_touch_targets(enhanced_report: Path) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 390, "height": 844})
        open_deck(page, enhanced_report)
        assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        sizes = page.locator(".deck-chrome button").evaluate_all(
            "nodes => nodes.map(node => ({width: node.getBoundingClientRect().width, height: node.getBoundingClientRect().height}))"
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
    assert next_button.inner_text() == "Official result →"
    next_button.click()
    browser_page.wait_for_url("**#outcome/official-result")
    browser_page.keyboard.press("ArrowRight")
    browser_page.wait_for_url("**#query/lifecycle")
    browser_page.keyboard.press("ArrowRight")
    browser_page.wait_for_url("**#retrieval/retrievers")
    browser_page.keyboard.press("ArrowDown")
    browser_page.wait_for_url("**#retrieval/features")
    browser_page.go_back()
    browser_page.wait_for_url("**#retrieval/retrievers")
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
    palette.get_by_role("button", name="Leading teams — volart").click()
    browser_page.wait_for_url("**#leaders/volart")
    opener.focus()
    browser_page.keyboard.press("Control+K")
    browser_page.keyboard.press("Escape")
    assert opener.evaluate("node => document.activeElement === node")


def test_direct_and_invalid_hashes(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report, "#response/matrix")
    assert browser_page.locator('#response\\/matrix').get_attribute("aria-current") == "true"
    browser_page.goto(f"{enhanced_report.as_uri()}#not/a-slide")
    browser_page.wait_for_url("**#outcome/summary")


def test_direct_hash_opens_disclosure(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report, "#retrieval/features?open=feature_matrix")
    details = browser_page.locator('details[data-disclosure-for="feature_matrix"]')
    assert details.get_attribute("open") is not None


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
