from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import pytest
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "index.html"
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

EXPECTED_LINKS = {
    "docs/submission-architecture.html",
    "docs/retrospective.html",
    "paper/main.pdf",
    "submission/v10_lgbm_A.zip",
    "submission/v10_lgbm_B_v1.zip",
    "reports/blindset-a-submission-audit/report.html",
    "reports/blindset-b-submission-audit/report.html",
    "https://github.com/npatta01/music-crs-2026",
    "https://huggingface.co/collections/talkpl-ai/talkplay-data-challenge",
    "https://huggingface.co/datasets/Npatta01/music-crs-repro-2026",
    "data/anchor_labels_v1/README.md",
    "https://nlp4musa.github.io/music-crs-challenge/",
    "LICENSE",
}


def page_text() -> str:
    assert PAGE.exists(), "Create the repository-root GitHub Pages entrypoint"
    return PAGE.read_text()


def test_landing_page_has_exact_six_link_groups() -> None:
    html = page_text()
    assert len(re.findall(r'<article class="link-card ', html)) == 6
    for title in ("Reports", "Paper", "Submissions", "Audits", "Code", "Data"):
        assert f">{title}</h2>" in html


def test_landing_page_contains_only_the_approved_destinations() -> None:
    html = page_text()
    hrefs = set(re.findall(r'href="([^"]+)"', html))
    assert hrefs == EXPECTED_LINKS
    assert "paper/draft.md" not in html
    assert "docs/codebase/README.md" not in html
    assert "docs/reproduce_offline_bundle.md" not in html


def test_every_relative_link_exists() -> None:
    for href in EXPECTED_LINKS:
        if urlparse(href).scheme:
            continue
        assert (ROOT / href).exists(), href


def test_page_has_no_remote_resource_dependencies_or_scripts() -> None:
    html = page_text()
    assert "<script" not in html.lower()
    assert not re.search(r'<(?:img|iframe|audio|video|source)[^>]+src="https?://', html, re.I)
    assert not re.search(r'<link[^>]+href="https?://', html, re.I)
    assert "@import" not in html


def launch_browser(playwright):
    if CHROME.exists():
        return playwright.chromium.launch(headless=True, executable_path=str(CHROME))
    return playwright.chromium.launch(headless=True)


@pytest.mark.parametrize(
    ("viewport", "columns"),
    [((1440, 900), 3), ((900, 900), 2), ((390, 844), 1)],
)
def test_responsive_grid_and_no_horizontal_overflow(viewport, columns) -> None:
    with sync_playwright() as playwright:
        browser = launch_browser(playwright)
        page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
        page.goto(PAGE.as_uri())
        template = page.locator(".link-grid").evaluate("node => getComputedStyle(node).gridTemplateColumns")
        assert len(template.split()) == columns
        assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth + 2")
        browser.close()


def test_focus_light_reduced_motion_and_print_are_readable() -> None:
    with sync_playwright() as playwright:
        browser = launch_browser(playwright)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark")
        page.goto(PAGE.as_uri())
        dark_bg = page.locator("body").evaluate("node => getComputedStyle(node).backgroundColor")
        page.keyboard.press("Tab")
        outline = page.locator(":focus").evaluate("node => getComputedStyle(node).outlineStyle")
        assert outline != "none"

        page.emulate_media(color_scheme="light", reduced_motion="reduce")
        light_bg = page.locator("body").evaluate("node => getComputedStyle(node).backgroundColor")
        assert light_bg != dark_bg
        assert page.locator(".link-card").first.evaluate("node => getComputedStyle(node).transitionDuration") in {"0s", "0.000001s", "1e-06s"}

        page.emulate_media(media="print")
        assert page.locator("body").evaluate("node => getComputedStyle(node).backgroundColor") in {"rgb(255, 255, 255)", "rgba(0, 0, 0, 0)"}
        browser.close()
