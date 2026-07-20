from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "submission-architecture.html"
CHROME_CANDIDATES = (
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    Path("/usr/bin/google-chrome"),
    Path("/usr/bin/chromium"),
)


def launch_chromium(playwright):
    executable = next((path for path in CHROME_CANDIDATES if path.exists()), None)
    if executable is None:
        return playwright.chromium.launch(headless=True)
    return playwright.chromium.launch(headless=True, executable_path=str(executable), args=["--no-sandbox"])


@pytest.fixture()
def page():
    with sync_playwright() as playwright:
        browser = launch_chromium(playwright)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        yield page, errors
        context.close()
        browser.close()


def open_deck(page: Page, suffix: str = "") -> None:
    page.goto(f"{REPORT.as_uri()}{suffix}")
    page.locator("html[data-submission-deck-ready='true']").wait_for()
    page.wait_for_function("window.Reveal && Reveal.isReady()")


def test_horizontal_vertical_keyboard_wheel_and_hash_navigation(page) -> None:
    browser_page, errors = page
    open_deck(browser_page)
    assert browser_page.evaluate("Reveal.getIndices()") == {"h": 0, "v": 0, "f": None}

    browser_page.keyboard.press("ArrowRight")
    browser_page.wait_for_function("Reveal.getIndices().h === 1")
    browser_page.wait_for_timeout(700)
    browser_page.keyboard.press("ArrowDown")
    browser_page.wait_for_function("Reveal.getIndices().h === 1 && Reveal.getIndices().v === 1")

    browser_page.wait_for_timeout(700)
    browser_page.mouse.wheel(0, 800)
    browser_page.wait_for_function("Reveal.getIndices().v === 2")
    assert browser_page.locator("#one-turn-data-flow.present").count() == 1

    browser_page.goto(f"{REPORT.as_uri()}#state-extraction-schema")
    browser_page.wait_for_function("Reveal.getIndices().h === 2 && Reveal.getIndices().v === 2")
    assert browser_page.url.endswith("#/state-extraction-schema")
    assert errors == []


def test_hash_history_and_local_contents_links(page) -> None:
    browser_page, errors = page
    open_deck(browser_page, "#retrieval")
    browser_page.locator("#retrieval a[href='#/dense-multimodal-retrieval']").click()
    browser_page.wait_for_function("Reveal.getIndices().h === 3 && Reveal.getIndices().v === 4")
    assert browser_page.url.endswith("#/dense-multimodal-retrieval")
    browser_page.go_back()
    browser_page.wait_for_function("Reveal.getIndices().h === 3 && Reveal.getIndices().v === 0")
    assert browser_page.url.endswith("#/retrieval")
    assert errors == []


def test_left_scrubber_focus_position_and_menu(page) -> None:
    browser_page, errors = page
    open_deck(browser_page)
    rail = browser_page.locator(".deck-section-rail")
    assert rail.is_visible()
    assert rail.get_by_role("button").count() == 9

    ranking = rail.get_by_role("button", name="5. Ranking")
    ranking.click()
    browser_page.wait_for_function("Reveal.getIndices().h === 5")
    assert ranking.get_attribute("aria-current") == "true"
    assert browser_page.locator(".deck-position").inner_text() == "5.0 · Ranking"
    assert browser_page.evaluate("document.activeElement === document.querySelector('[data-horizontal-index=\"5\"]')")

    ranking.click()
    browser_page.wait_for_function("Reveal.getPlugin('menu').isOpen()")
    assert browser_page.locator(".slide-menu--left.active").is_visible()
    assert errors == []


def test_dark_light_theme_and_reduced_motion(page) -> None:
    browser_page, errors = page
    open_deck(browser_page)
    assert browser_page.locator("html").get_attribute("data-deck-theme") == "dark"
    dark_background = browser_page.locator(".reveal-viewport").evaluate("node => getComputedStyle(node).backgroundColor")

    browser_page.get_by_role("button", name="Switch to light theme").click()
    assert browser_page.locator("html").get_attribute("data-deck-theme") == "light"
    light_background = browser_page.locator(".reveal-viewport").evaluate("node => getComputedStyle(node).backgroundColor")
    assert dark_background != light_background

    browser_page.emulate_media(reduced_motion="reduce")
    duration = browser_page.locator(".deck-rail-number").first.evaluate("node => getComputedStyle(node).transitionDuration")
    assert duration in {"0s", "0.000001s", "1e-06s"}
    assert errors == []


def test_section_opener_exposes_input_system_output_and_detail_links(page) -> None:
    browser_page, errors = page
    open_deck(browser_page, "#state-extraction")
    opener = browser_page.locator("#state-extraction")
    assert opener.locator(".overview-input").is_visible()
    assert opener.locator(".overview-system").is_visible()
    assert opener.locator(".overview-output").is_visible()
    assert opener.locator(".detail-strip a").count() == 5
    assert errors == []


def test_mobile_uses_scroll_view_and_hides_custom_rail() -> None:
    with sync_playwright() as playwright:
        browser = launch_chromium(playwright)
        context = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
        page = context.new_page()
        open_deck(page, "#state-extraction-schema")
        page.wait_for_function("Reveal.isScrollView()")
        page.wait_for_function("document.querySelector('#state-extraction-schema').getBoundingClientRect().top < innerHeight")
        assert not page.locator(".deck-section-rail").is_visible()
        assert page.locator(".slide-menu-button").is_visible()
        assert page.evaluate("Reveal.getConfig().touch") is True
        context.close()
        browser.close()


def test_print_mode_is_light_and_navigation_free(page) -> None:
    browser_page, errors = page
    browser_page.emulate_media(media="print")
    open_deck(browser_page, "?print-pdf")
    assert not browser_page.locator(".deck-section-rail").is_visible()
    background = browser_page.locator(".reveal-viewport").evaluate("node => getComputedStyle(node).backgroundColor")
    assert background in {"rgb(255, 255, 255)", "rgba(0, 0, 0, 0)"}
    assert errors == []


@pytest.mark.parametrize("viewport", [(1600, 900), (1024, 768), (390, 844)])
def test_visible_slides_do_not_clip_at_reference_viewports(viewport: tuple[int, int]) -> None:
    width, height = viewport
    with sync_playwright() as playwright:
        browser = launch_chromium(playwright)
        context = browser.new_context(viewport={"width": width, "height": height}, is_mobile=width < 500)
        page = context.new_page()
        open_deck(page, "#retrieval-branches")
        slide = page.locator("#retrieval-branches")
        audit = slide.evaluate(
            """node => ({
              scrollWidth: node.scrollWidth,
              clientWidth: node.clientWidth,
              scrollHeight: node.scrollHeight,
              clientHeight: node.clientHeight,
              bodyWidth: document.documentElement.scrollWidth,
              viewportWidth: document.documentElement.clientWidth
            })"""
        )
        assert audit["scrollWidth"] <= audit["clientWidth"] + 3, audit
        assert audit["bodyWidth"] <= audit["viewportWidth"] + 3, audit
        if width >= 760:
            assert audit["scrollHeight"] <= audit["clientHeight"] + 3, audit
        context.close()
        browser.close()
