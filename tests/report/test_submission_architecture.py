from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs" / "submission-architecture.qmd"
OUTPUT = ROOT / "docs" / "submission-architecture.html"

SECTIONS = [
    ("High-Level Architecture", 3),
    ("State Extraction", 6),
    ("Retrieval", 7),
    ("Bi-Encoder", 6),
    ("Ranking", 5),
    ("Response Generation", 4),
    ("Examples", 5),
    ("Label Audit", 5),
    ("References", 1),
]

SLIDE_IDS = [
    "toc-and-links",
    "high-level-architecture",
    "deployed-pipeline",
    "one-turn-data-flow",
    "state-extraction",
    "state-session-example",
    "state-extraction-schema",
    "state-to-retrieval-view",
    "entity-resolution",
    "retrieval-contract",
    "retrieval",
    "lancedb-catalog",
    "retrieval-branches",
    "lexical-tag-retrieval",
    "dense-multimodal-retrieval",
    "anchor-cf-lookups",
    "routing-candidate-pool",
    "bi-encoder",
    "biencoder-architecture",
    "biencoder-example",
    "biencoder-training",
    "biencoder-serving",
    "biencoder-evidence",
    "ranking",
    "ranking-input",
    "ranking-feature-gain",
    "ranking-sample-features",
    "lambdamart-training",
    "response-generation",
    "response-example",
    "response-inputs",
    "response-prompt",
    "examples",
    "example-neko-case",
    "example-kamelot",
    "example-metadata",
    "example-watercolors",
    "label-audit",
    "label-bonobo",
    "label-judging-flow",
    "label-audit-counts",
    "label-outcome-limitations",
    "references",
]


def _source() -> str:
    assert SOURCE.exists(), "Add the Markdown-authored Quarto source"
    return SOURCE.read_text()


def test_exact_horizontal_order_and_progressive_slide_structure() -> None:
    source = _source()
    horizontal = re.findall(r"^# (.+?) \{#([\w-]+).*?\}$", source, re.MULTILINE)
    assert horizontal == [
        ("Music-CRS Submission Architecture", "toc-and-links"),
        *[(f"{index}. {title}", SLIDE_IDS[sum(count for _, count in SECTIONS[:index - 1]) + 1]) for index, (title, _) in enumerate(SECTIONS, 1)],
    ]

    headings = re.findall(r"^#{1,2} .+? \{#([\w-]+).*?\}$", source, re.MULTILINE)
    assert headings == SLIDE_IDS
    assert len(headings) == len(set(headings)) == 43

    cursor = 1
    for _, expected_count in SECTIONS:
        next_cursor = cursor + expected_count
        assert len(SLIDE_IDS[cursor:next_cursor]) == expected_count
        cursor = next_cursor
    assert cursor == 43


def test_each_section_landing_links_to_its_vertical_slides() -> None:
    source = _source()
    horizontal_starts = list(re.finditer(r"^# .+? \{#[\w-]+.*?\}$", source, re.MULTILINE))
    for section_index, (_, expected_count) in enumerate(SECTIONS, 1):
        start = horizontal_starts[section_index].start()
        end = horizontal_starts[section_index + 1].start() if section_index + 1 < len(horizontal_starts) else len(source)
        block = source[start:end]
        vertical_ids = re.findall(r"^## .+? \{#([\w-]+).*?\}$", block, re.MULTILINE)
        assert len(vertical_ids) == expected_count - 1
        for slide_id in vertical_ids:
            assert re.search(rf"\[[^\]]+\]\(#{slide_id}\)", block)


def test_section_openers_use_visual_input_system_output_overviews() -> None:
    source = _source()
    horizontal_starts = list(re.finditer(r"^# .+? \{#[\w-]+.*?\}$", source, re.MULTILINE))
    for section_index, (title, _) in enumerate(SECTIONS[:-1], 1):
        start = horizontal_starts[section_index].start()
        end = horizontal_starts[section_index + 1].start()
        opener = source[start:end].split("\n## ", 1)[0]
        assert re.search(r"\{[^}]*\.system-overview(?:\s|\})", opener), title
        assert "{.overview-input}" in opener, title
        assert "{.overview-system}" in opener, title
        assert "{.overview-output}" in opener, title
        assert "{.detail-strip}" in opener, title


def test_terminology_and_scope_are_consistent() -> None:
    source = _source()
    required_terms = [
        "LanceDB",
        "Bi-Encoder",
        "LambdaMART",
        "Response Generation",
        "Label Audit",
    ]
    for term in required_terms:
        assert term in source
    assert "Blind-A vs" not in source
    assert "Blind-B vs" not in source
    assert not re.search(r"Blind[- ]A.{0,80}(architecture|pipeline).{0,80}Blind[- ]B", source, re.IGNORECASE | re.DOTALL)
    assert "# 4. RRF" not in source
    assert "# 10." not in source
    assert "Final guards and evaluation caveat" not in source
    assert "Validate V1" not in source
    assert "The final submission kept original challenge labels" not in source
    assert "ConversationStateV1" not in source
    assert "ConversationStateV0Plus" not in source
    assert "project_v1_to_v0plus" not in source
    assert "through Modal" not in source
    assert "Positives are turns whose next-turn annotation" not in source


def test_examples_use_traceable_sessions_and_exact_reader_facing_artifacts() -> None:
    source = _source()

    # The repeated Neko Case example should remain traceable across extraction,
    # bi-encoder, generation, and the end-to-end walkthrough.
    assert source.count("024a2738-a96c-4e11-adf3-b2cb8311a493") >= 4
    assert "016099ac-567c-4cd7-81f5-d385be38a4bc" in source
    assert "bf27c872-87df-46f0-8e4d-328d11baec30" in source
    assert "b26791c3-ceaf-4de8-9c9a-7b2db7163e60" in source

    assert '"turn": 3' in source
    assert '"request_type": "hidden_target"' in source
    assert "The Worse Things Get, The Harder I Fight" in source
    assert "unavailable; catalog tag: 2013" in source
    assert "Neko Case is best known for her alt-country and indie rock style" in source
    assert "Album/year + cleaned tags" not in source

    # Preserve the complete submitted response and deployed prompt wording.
    assert "like a solitary figure in a weathered room" in source
    assert "You are the conversational voice of a music recommender" in source
    assert "always write a natural conversational sentence" in source
    assert "STYLE INSTRUCTIONS" in source

    # Visual semantics must not overclaim relevance for unjudged Blind-B ranks.
    assert "Selected Top 1" in source
    assert "Ranks 2–5 · not independently judged" in source
    assert "metadata_qwen3_embedding_8b" in source
    assert "attributes_qwen3_embedding_8b" in source
    assert "lyrics_qwen3_embedding_0_6b" in source
    assert "audio_laion_clap" in source
    assert "Gemma-4-26B" in source
    assert "DeepSeek-V4-Flash" in source
    assert "Claude Opus" in source
    assert r'Got it — here’s \"Alfie\" by Pat Metheny' in source
    assert "performed worse on development data, so we did not ship it" in source


def test_reviewed_slides_explain_runtime_contracts_and_state_fields() -> None:
    source = _source()
    pipeline_svg = (ROOT / "docs" / "submission-architecture" / "submission-pipeline-dark.svg").read_text()

    assert "dashed baseline" not in source
    assert "dashed baseline" not in pipeline_svg
    assert "stage-contract-list" in source
    assert "Inference-time ranking" in source
    assert "goal fields" in source
    assert "#goal-free-boundary" not in source

    for field_name in (
        "current_request.request_type",
        "facts[].artist",
        "facts[].mood",
        "facts[].lyrical_theme",
        "facts[].sonic",
        "exclusions[].track",
    ):
        assert field_name in source

    assert "facts[].facet=sonic" in source
    assert "current_request.summary" in source
    assert "RUNTIME INPUT · appended per turn" in source
    assert "roleplay.txt + response_generation.txt" not in source
    assert "DISAGREEMENT ONLY" in source
    assert "Success: Neko Case" in source
    assert "Constraint lost: Kamelot album" in source
    assert "Exact-track request recognized, but Watercolors was not found" in source


def test_ranking_has_a_distinct_final_ordering_phase() -> None:
    source = _source()
    pipeline_svg = (ROOT / "docs" / "submission-architecture" / "submission-pipeline-dark.svg").read_text()

    assert "Final ordering" in source
    assert "Exact-track pin + final artist check" in source
    assert "Final ordering" in pipeline_svg
    assert "exact-track pin + artist check" in pipeline_svg


def test_only_deployed_dense_branches_are_documented() -> None:
    source = _source()

    assert "visual request" not in source
    assert "image_siglip2" not in source
    assert "The 11 modeled branches preserve" in source


def test_response_prompt_has_one_sentence_count_instruction() -> None:
    source = _source()

    assert "1-3 sentences" not in source
    assert source.count("1-2 concise sentences") == 1


def test_reviewed_labels_and_scope_are_unambiguous() -> None:
    source = _source()

    assert "Whole-system input" in source
    assert "Goal not fully materialized" in source
    assert "Training-label failure examples" in source
    assert "Bonobo / Cornelia" not in source
    assert "Bonobo — “Pieces”" in source


def test_diagram_legends_and_retired_biencoder_path_are_explicit() -> None:
    pipeline_svg = (ROOT / "docs" / "submission-architecture" / "submission-pipeline-dark.svg").read_text()
    biencoder_svg = (ROOT / "docs" / "submission-architecture" / "biencoder-dark.svg").read_text()

    assert "AMBER = WEIGHTED RRF BASELINE / FALLBACK" in pipeline_svg
    assert 'class="fallback-label"' in pipeline_svg
    assert "EARLIER EXPERIMENT" in biencoder_svg
    assert "not deployed" in biencoder_svg


def test_reviewed_visual_components_have_non_overlapping_layout_rules() -> None:
    theme = (ROOT / "docs" / "submission-architecture" / "theme.scss").read_text()
    assert re.search(r"\.turn p\s*\{[^}]*padding-left:", theme, re.DOTALL)
    assert re.search(r"\.generator-core\s*\{(?![^}]*aspect-ratio)[^}]*grid-column:", theme, re.DOTALL)
    assert re.search(r"\.second-anchor-example\s*\{[^}]*border:", theme, re.DOTALL)
    assert ".state-field-list" in theme


def test_reader_view_hides_provenance_footers_and_uses_visual_story_classes() -> None:
    source = _source()
    theme = (ROOT / "docs" / "submission-architecture" / "theme.scss").read_text()
    assert re.search(r"\.source-line\s*\{[^}]*display:\s*none", theme, re.DOTALL)
    for visual_class in (
        "opener-icon",
        "state-facts-map",
        "resolver-ladder",
        "bm25-example",
        "failure-story",
        "metadata-story",
        "audit-motivation",
    ):
        assert visual_class in source or visual_class in theme


def test_required_links_and_local_output_contract() -> None:
    source = _source()
    required_links = [
        "https://github.com/",
        "paper/main.pdf",
        "https://nlp4musa.github.io/music-crs-challenge/",
        "../data/anchor_labels_v1/README.md",
        "reports/blindset-a-submission-audit/report.html",
        "reports/blindset-b-submission-audit/report.html",
        "retrospective.html",
    ]
    for link in required_links:
        assert link in source
    assert "embed-resources: true" in source
    assert 'html-math-method: plain' in source
    assert OUTPUT.name == "submission-architecture.html"


def test_checked_in_html_is_self_contained_and_complete() -> None:
    assert OUTPUT.exists(), "Render the checked-in HTML with Quarto"
    html = OUTPUT.read_text()
    assert "_files/" not in html
    assert len(re.findall(r'<section[^>]+class="[^"]*\bslide\b[^"]*"', html)) == 43
    for slide_id in SLIDE_IDS:
        assert f'id="{slide_id}"' in html

    external_resources = re.findall(
        r'<(?:script|img|iframe|audio|video|source)[^>]+src=["\']https?://|'
        r'<link[^>]+href=["\']https?://',
        html,
        re.IGNORECASE,
    )
    assert external_resources == []
    for link in (
        "https://github.com/npatta01/music-crs-2026",
        "../paper/main.pdf",
        "https://nlp4musa.github.io/music-crs-challenge/",
        "../data/anchor_labels_v1/README.md",
        "../reports/blindset-a-submission-audit/report.html",
        "../reports/blindset-b-submission-audit/report.html",
    ):
        assert link in html


def test_quarto_version_and_readme_entrypoint() -> None:
    version = subprocess.run(["quarto", "--version"], check=True, capture_output=True, text=True).stdout.strip()
    assert version == "1.9.38"
    readme = (ROOT / "readme.md").read_text()
    assert "[Submission architecture deck]" in readme
    assert "(docs/submission-architecture.html)" in readme
    assert "https://npatta01.github.io/music-crs-2026/index.html" in readme
    assert "https://npatta01.github.io/music-crs-2026/docs/submission-architecture.html#/high-level-architecture" in readme
    assert "## Start here" in readme
    assert "Open the interactive architecture deck →" in readme
    assert "## Approach overview" not in readme
    assert "docs/architectures/submission_pipeline.svg" not in readme
