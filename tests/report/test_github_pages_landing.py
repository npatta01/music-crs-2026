from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "index.html"

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
