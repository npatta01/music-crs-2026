"""Generate an interactive recall-gap report for the Music CRS devset trace.

The report streams the large trace once, joins lightweight catalog metadata from
LanceDB, writes compact JSON, and embeds that JSON into a browser-friendly HTML
artifact.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_SOURCE_ROOT = Path("/Users/npatta01/data/projects/music-conversational-music-recomender-2026")
DEFAULT_TID = "v0plus_compiler_all_retrievers_devset"

FINAL_KS = (1, 5, 10, 20, 50, 100, 200, 500, 1000)
UNION_KS = (20, 50, 100, 200, 500, 1000)
BRANCH_KS = (20, 100, 200, 1000)


def _first(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return _first(value[0]) if value else None
    if hasattr(value, "tolist"):
        return _first(value.tolist())
    text = str(value).strip()
    return text or None


def _listify(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if v is not None]
    if hasattr(value, "tolist"):
        return _listify(value.tolist())
    return [str(value)]


def _norm_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _norm_tag(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _year_of(value: Any) -> int | None:
    if value is None:
        return None
    if hasattr(value, "year"):
        return int(value.year)
    match = re.search(r"(19|20)\d{2}", str(value))
    return int(match.group(0)) if match else None


def _rank_in_ids(ids: list[str], gt: str) -> int | None:
    for idx, track_id in enumerate(ids, 1):
        if track_id == gt:
            return idx
    return None


def _rank_in_hits(hits: list[Any], gt: str) -> int | None:
    for idx, hit in enumerate(hits or [], 1):
        if hit and hit[0] == gt:
            return idx
    return None


def _rank_bucket(rank: int | None) -> str:
    if rank is None:
        return "not_found"
    if rank == 1:
        return "001"
    if rank <= 5:
        return "002-005"
    if rank <= 10:
        return "006-010"
    if rank <= 20:
        return "011-020"
    if rank <= 50:
        return "021-050"
    if rank <= 100:
        return "051-100"
    if rank <= 200:
        return "101-200"
    if rank <= 500:
        return "201-500"
    if rank <= 1000:
        return "501-1000"
    return ">1000"


def _gap_bucket(final_rank: int | None, fused_rank: int | None, min_branch_rank: int | None) -> str:
    """User-facing bucket around union@20/100 gaps."""
    if final_rank is not None and final_rank <= 20:
        return "final_top20_hit"
    if min_branch_rank is not None and min_branch_rank <= 20:
        if fused_rank is not None and fused_rank <= 20:
            return "union20_postfusion_or_final_loss"
        return "union20_fusion_loss"
    if min_branch_rank is not None and min_branch_rank <= 100:
        return "union100_near_miss"
    if min_branch_rank is not None and min_branch_rank <= 200:
        return "union200_deep_miss"
    if min_branch_rank is not None and min_branch_rank <= 1000:
        return "union1000_deep_miss"
    return "not_in_any_branch_top1000"


def _mechanism_bucket(final_rank: int | None, fused_rank: int | None, min_branch_rank: int | None) -> str:
    """More diagnostic bucket separating fusion and post-fusion behavior."""
    if final_rank is not None and final_rank <= 20:
        return "final_top20_hit"
    if fused_rank is not None and fused_rank <= 20:
        return "fused_top20_postfusion_demoted"
    if min_branch_rank is not None and min_branch_rank <= 20:
        return "branch_top20_fusion_miss"
    if min_branch_rank is not None and min_branch_rank <= 100:
        return "branch_21_100_near_miss"
    if min_branch_rank is not None and min_branch_rank <= 200:
        return "branch_101_200_retrieved_weak"
    if min_branch_rank is not None and min_branch_rank <= 1000:
        return "branch_201_1000_deep_weak"
    return "not_in_any_branch_top1000"


def _tag_overlap_bucket(n: int) -> str:
    if n == 0:
        return "0"
    if n == 1:
        return "1"
    if n <= 3:
        return "2-3"
    return "4+"


def _popularity_bucket(popularity: float) -> str:
    if popularity >= 70:
        return "pop>=70"
    if popularity >= 50:
        return "pop50-69"
    if popularity >= 30:
        return "pop30-49"
    if popularity > 0:
        return "pop1-29"
    return "pop0_or_missing"


def _compact_pct(count: int, denom: int) -> float:
    return round((count / denom) * 100.0, 2) if denom else 0.0


def _counter_rows(counter: Counter[str], denom: int | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    total = denom if denom is not None else sum(counter.values())
    items = counter.most_common(limit)
    return [{"name": k, "n": v, "pct": _compact_pct(v, total)} for k, v in items]


def load_catalog(source_root: Path) -> dict[str, dict[str, Any]]:
    import lancedb

    table = lancedb.connect(str(source_root / "cache/lancedb")).open_table("music_track_catalog")
    columns = [
        "track_id",
        "track_name",
        "artist_name",
        "artist_id",
        "album_id",
        "release_date",
        "popularity",
        "tag_list",
    ]
    df = table.search().select(columns).limit(0).to_pandas()
    catalog: dict[str, dict[str, Any]] = {}
    for row in df.to_dict(orient="records"):
        track_id = str(row["track_id"])
        artist_names = _listify(row.get("artist_name"))
        artist_ids = _listify(row.get("artist_id"))
        catalog[track_id] = {
            "track_name": _first(row.get("track_name")),
            "artist_names": artist_names,
            "artist_first": artist_names[0] if artist_names else None,
            "artist_ids": set(artist_ids),
            "album_ids": set(_listify(row.get("album_id"))),
            "release_year": _year_of(row.get("release_date")),
            "popularity": float(row.get("popularity") or 0.0),
            "tags": {t for t in (_norm_tag(v) for v in _listify(row.get("tag_list"))) if t},
        }
    return catalog


def load_ground_truth(path: Path) -> dict[tuple[str, int], str]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {
        (row["session_id"], int(row["turn_number"])): row.get("ground_truth_track_id")
        for row in rows
        if row.get("ground_truth_track_id")
    }


def bump_xtab(
    xtabs: dict[str, dict[str, Counter[str]]],
    dim: str,
    value: Any,
    *,
    final_hit20: bool,
    union20: bool,
    union100: bool,
    union200: bool,
    union1000: bool,
    gap_bucket: str,
    mechanism: str,
) -> None:
    label = str(value if value not in (None, "") else "NONE")
    row = xtabs[dim][label]
    row["n"] += 1
    row["final_hit20"] += int(final_hit20)
    row["union20"] += int(union20)
    row["union100"] += int(union100)
    row["union200"] += int(union200)
    row["union1000"] += int(union1000)
    row[f"gap::{gap_bucket}"] += 1
    row[f"mechanism::{mechanism}"] += 1


def rank_or_dash(rank: int | None) -> str:
    return "-" if rank is None else str(rank)


def sample_example(
    examples: dict[str, list[dict[str, Any]]],
    key: str,
    *,
    limit: int,
    record: dict[str, Any],
) -> None:
    if len(examples[key]) < limit:
        examples[key].append(record)


def load_state_companion(out_dir: Path) -> dict[str, Any]:
    path = out_dir / "state_focus" / "state_report_data.json"
    if not path.exists():
        return {
            "available": False,
            "path": str(path),
            "message": "State-focus report data was not found. Run scripts/generate_state_focus_report.py first.",
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    holistic_plan = [
        {
            "area": "State extraction rerun",
            "cost": "expensive",
            "decision": "Run only for role/recency and target_artist_mode changes.",
            "evidence": "Roleless positive entity carryover, stale anchors, and novelty-prior-anchor conflicts are direct state-shape failures.",
            "first_test": "Use P0_roleless_stale_entity_failure, P0_novelty_prior_anchor_failure, and P0_new_artist_union20_gap_failure before a full devset rerun.",
        },
        {
            "area": "State field economy",
            "cost": "cheap before any extractor rerun",
            "decision": "Collapse or derive confusing overlapping fields before adding new schema surface.",
            "evidence": "Several current fields describe the same concept from different angles: intent/routing/process mode, year ranges/hard filters, positive entities/feedback/exact references.",
            "first_test": "Use the state confusion plan and replay packs to confirm fewer fields give clearer extraction and no recall regression.",
        },
        {
            "area": "Organizer session metadata",
            "cost": "cheap when fields are available",
            "decision": "Use listener_goal and preferred_musical_culture as context/affinity experiments; do not pay LLM calls to emulate organizer fields first.",
            "evidence": "conversation_goal and user_profile are session-level organizer fields; raw constants do not rank candidates within a turn unless transformed.",
            "first_test": "Run goal/culture candidate-varying features on novelty/popularity packs; keep category/specificity as slices and guardrails.",
        },
        {
            "area": "Routing / retrieval profiles",
            "cost": "cheap to medium",
            "decision": "Do before adding new retrievers: wire extracted routing tags into branch weights/profiles.",
            "evidence": "Routing tags fire in the trace, but routing_boost is empty in the current config.",
            "first_test": "Replay routing profiles on P0_new_artist_union20_gap_failure and report union@20/100.",
        },
        {
            "area": "Trained state-aware ranker",
            "cost": "medium",
            "decision": "High priority, but it must consume state/candidate features instead of raw session constants.",
            "evidence": "Union@100 is far above final@20; good-state/union@20 samples still miss final top-20.",
            "first_test": "Use P0_good_state_ranker_near_miss_failure, P0_named_artist_ranker_failure, and P0_same_album_ranker_failure, then session-grouped CV over union@100/200.",
        },
        {
            "area": "Album and artist recency",
            "cost": "medium",
            "decision": "Build candidate-level features; no extraction rerun required if history is already available.",
            "evidence": "Primary-album continuation has high union@20 but much lower final@20.",
            "first_test": "Add same_album_recent and artist_recency to the ranker and guardrail new-artist slices.",
        },
        {
            "area": "Temporal and rejection guardrails",
            "cost": "cheap",
            "decision": "Treat as deterministic replay tests, not a broad state rewrite.",
            "evidence": "Release ranges can exclude GT; strict rejection leaks have a lower-bound count.",
            "first_test": "Use P1_temporal_constraint_failure and P1_rejection_guardrail_failure; assert zero strict rejection leaks and compare no-year/soft-year replay.",
        },
        {
            "area": "New novelty retrievers",
            "cost": "medium to high",
            "decision": "Only after routing/profile tests show union@20 remains weak.",
            "evidence": "New-artist turns often miss union@20, so a ranker alone cannot rescue them.",
            "first_test": "Try genre/era-conditioned popularity, user-CF/culture affinity, and tag-first retrieval on novelty samples.",
        },
        {
            "area": "Raw tags / raw demographics",
            "cost": "low but distracting",
            "decision": "Do not make this the next big extraction project.",
            "evidence": "Tags are already often present; raw session/category/demographic constants do not rank candidates within a turn.",
            "first_test": "Only revisit as candidate-varying tag compatibility or culture/user affinity features.",
        },
    ]
    return {
        "available": True,
        "path": str(path),
        "generated_at": data.get("generated_at"),
        "headline": data.get("headline"),
        "state_scorecard": data.get("state_scorecard") or [],
        "task_modes": data.get("task_modes") or [],
        "continuation_deep_dive": data.get("continuation_deep_dive") or {},
        "newartist_deep_dive": data.get("newartist_deep_dive") or {},
        "schema_change_plan": data.get("schema_change_plan") or [],
        "ideal_state_targets": data.get("ideal_state_targets") or [],
        "state_confusion_plan": data.get("state_confusion_plan") or [],
        "metadata_decision_plan": data.get("metadata_decision_plan") or [],
        "blindset_metadata_availability": data.get("blindset_metadata_availability") or (data.get("organizer_metadata") or {}).get("blindset_availability") or {},
        "state_field_audit": data.get("state_field_audit") or [],
        "good_state_low_recall": data.get("good_state_low_recall") or [],
        "feature_catalog": data.get("feature_catalog") or [],
        "role_bug_examples": data.get("role_bug_examples") or [],
        "measured_levers": data.get("measured_levers") or [],
        "not_first": data.get("not_first") or [],
        "counting_reconciliation": data.get("counting_reconciliation") or [],
        "experiment_packs": data.get("state_experiment_packs") or [],
        "experiment_turns": data.get("state_experiment_turns") or [],
        "holistic_plan": holistic_plan,
        "links": {
            "state_focus": "state_focus/index.html#schema-audit",
            "state_markdown": "state_focus/agent_report.md",
            "state_markdown_html": "state_focus/agent_report.html",
            "state_json": "state_focus/state_report_data.json",
        },
    }


def escape_cell(value: Any) -> str:
    if value is None:
        return "-"
    return html.escape(str(value))


def format_rate(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return str(value)


def baseline_wording(value: Any) -> Any:
    if value is None:
        return value
    text = str(value)
    replacements = {
        "RRF-fused": "baseline-fused",
        "RRF/branch": "branch",
        "RRF/post-fusion": "baseline fusion/post-fusion",
        "RRF replacement": "baseline-fusion replacement",
        "Replace RRF": "Replace the current baseline fusion",
        "Tune RRF": "Tune the current baseline fusion",
        "RRF": "current baseline fusion",
        "equal-weight current baseline fusion": "equal-rank baseline fusion",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def render_markdown_inline(text: str) -> str:
    parts = re.split(r"(`[^`]*`)", text)
    rendered: list[str] = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) >= 2:
            rendered.append(f"<code>{html.escape(part[1:-1])}</code>")
            continue
        escaped = html.escape(part)

        def link_repl(match: re.Match[str]) -> str:
            label = match.group(1)
            href = match.group(2).strip()
            safe_href = html.escape(href, quote=True)
            return f'<a href="{safe_href}">{label}</a>'

        escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link_repl, escaped)
        escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
        rendered.append(escaped)
    return "".join(rendered)


def split_markdown_table_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def is_markdown_table_separator(line: str) -> bool:
    cells = split_markdown_table_row(line)
    if len(cells) < 2:
        return False
    return all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def is_markdown_table_start(lines: list[str], idx: int) -> bool:
    if idx + 1 >= len(lines):
        return False
    return "|" in lines[idx] and is_markdown_table_separator(lines[idx + 1])


def render_markdown_table(lines: list[str]) -> str:
    headers = split_markdown_table_row(lines[0])
    body_rows = [split_markdown_table_row(line) for line in lines[2:] if line.strip()]
    thead = "".join(f"<th>{render_markdown_inline(cell)}</th>" for cell in headers)
    rows = []
    for row in body_rows:
        padded = row + [""] * max(0, len(headers) - len(row))
        cells = "".join(f"<td>{render_markdown_inline(cell)}</td>" for cell in padded[: len(headers)])
        rows.append(f"<tr>{cells}</tr>")
    return f"<div class=\"table-wrap\"><table><thead><tr>{thead}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"


def render_markdown_blocks(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    out: list[str] = []
    paragraph: list[str] = []
    list_type: str | None = None
    code_lang: str | None = None
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            text = " ".join(part.strip() for part in paragraph).strip()
            if text:
                out.append(f"<p>{render_markdown_inline(text)}</p>")
            paragraph = []

    def close_list() -> None:
        nonlocal list_type
        if list_type:
            out.append(f"</{list_type}>")
            list_type = None

    idx = 0
    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()

        if code_lang is not None:
            if stripped.startswith("```"):
                out.append(
                    f'<pre><code class="language-{html.escape(code_lang, quote=True)}">'
                    f"{html.escape(chr(10).join(code_lines))}</code></pre>"
                )
                code_lang = None
                code_lines = []
            else:
                code_lines.append(line)
            idx += 1
            continue

        if stripped.startswith("```"):
            flush_paragraph()
            close_list()
            code_lang = stripped[3:].strip() or "text"
            code_lines = []
            idx += 1
            continue

        if not stripped:
            flush_paragraph()
            close_list()
            idx += 1
            continue

        if is_markdown_table_start(lines, idx):
            flush_paragraph()
            close_list()
            table_lines = [lines[idx], lines[idx + 1]]
            idx += 2
            while idx < len(lines) and lines[idx].strip() and "|" in lines[idx]:
                table_lines.append(lines[idx])
                idx += 1
            out.append(render_markdown_table(table_lines))
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            close_list()
            level = min(len(heading.group(1)), 6)
            out.append(f"<h{level}>{render_markdown_inline(heading.group(2).strip())}</h{level}>")
            idx += 1
            continue

        if re.fullmatch(r"[-*_]{3,}", stripped):
            flush_paragraph()
            close_list()
            out.append("<hr>")
            idx += 1
            continue

        unordered = re.match(r"^[-*]\s+(.+)$", stripped)
        ordered = re.match(r"^\d+\.\s+(.+)$", stripped)
        if unordered or ordered:
            flush_paragraph()
            next_type = "ul" if unordered else "ol"
            if list_type != next_type:
                close_list()
                out.append(f"<{next_type}>")
                list_type = next_type
            item = (unordered or ordered).group(1).strip()
            out.append(f"<li>{render_markdown_inline(item)}</li>")
            idx += 1
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            close_list()
            quote = stripped[1:].strip()
            out.append(f"<blockquote>{render_markdown_inline(quote)}</blockquote>")
            idx += 1
            continue

        close_list()
        paragraph.append(line)
        idx += 1

    flush_paragraph()
    close_list()
    if code_lang is not None:
        out.append(
            f'<pre><code class="language-{html.escape(code_lang, quote=True)}">'
            f"{html.escape(chr(10).join(code_lines))}</code></pre>"
        )
    return "\n".join(out)


def render_markdown_review_page(title: str, markdown_text: str, raw_href: str) -> str:
    safe_title = html.escape(title)
    safe_raw_href = html.escape(raw_href)
    rendered_markdown = render_markdown_blocks(markdown_text)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title>
<style>
:root {{
  --ink: #172033;
  --muted: #5f6b7a;
  --line: #dbe2ea;
  --paper: #f6f7f9;
  --panel: #ffffff;
  --blue: #2662d9;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  color: var(--ink);
  background: var(--paper);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
header {{
  padding: 24px clamp(18px, 4vw, 42px) 16px;
  background: var(--panel);
  border-bottom: 1px solid var(--line);
}}
h1 {{
  margin: 14px 0 8px;
  font-size: clamp(26px, 3.5vw, 42px);
  line-height: 1.05;
  letter-spacing: 0;
}}
p {{ max-width: 860px; color: var(--muted); line-height: 1.5; }}
.markdown-body {{
  max-width: 980px;
  margin: 0 auto;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: clamp(18px, 3vw, 34px);
  box-shadow: 0 1px 2px rgba(30, 42, 62, 0.05);
}}
.markdown-body > :first-child {{ margin-top: 0; }}
.markdown-body h1 {{
  margin: 0 0 16px;
  font-size: 32px;
  line-height: 1.12;
}}
.markdown-body h2 {{
  margin: 30px 0 10px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
  font-size: 23px;
  line-height: 1.2;
}}
.markdown-body h3 {{
  margin: 22px 0 8px;
  font-size: 17px;
  line-height: 1.25;
}}
.markdown-body h4 {{
  margin: 18px 0 6px;
  font-size: 14px;
  line-height: 1.3;
  color: #334155;
}}
.markdown-body p,
.markdown-body li {{
  color: var(--ink);
  line-height: 1.58;
}}
.markdown-body ul,
.markdown-body ol {{
  padding-left: 24px;
}}
.markdown-body li + li {{
  margin-top: 5px;
}}
.markdown-body code {{
  background: #eef2f6;
  border-radius: 4px;
  padding: 2px 4px;
  font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  overflow-wrap: anywhere;
}}
.markdown-body pre {{
  margin: 14px 0;
  padding: 14px;
  overflow: auto;
  white-space: pre;
  background: #0f172a;
  color: #f8fafc;
  border: 0;
  border-radius: 8px;
  box-shadow: none;
}}
.markdown-body pre code {{
  background: transparent;
  color: inherit;
  padding: 0;
}}
.table-wrap {{
  margin: 14px 0;
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 8px;
}}
.markdown-body table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}}
.markdown-body th,
.markdown-body td {{
  padding: 9px 10px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
}}
.markdown-body th {{
  background: #f8fafc;
  color: #465163;
  font-size: 12px;
}}
.markdown-body blockquote {{
  margin: 16px 0;
  padding: 10px 14px;
  border-left: 4px solid var(--blue);
  background: #f8fafc;
  border-radius: 6px;
}}
.actions {{
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}}
a {{
  color: var(--blue);
  text-decoration-thickness: 1px;
  text-underline-offset: 3px;
}}
.actions a {{
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 7px 11px;
  background: #fff;
  text-decoration: none;
  font-size: 13px;
}}
main {{
  padding: 18px clamp(18px, 4vw, 42px) 42px;
}}
</style>
</head>
<body>
<header>
  <div class="actions">
    <a href="../index.html#report-map">Back to report map</a>
    <a href="{safe_raw_href}">Raw markdown source</a>
  </div>
  <h1>{safe_title}</h1>
  <p>This page renders the markdown artifact as standalone HTML while preserving the raw source link for agent review.</p>
</header>
<main>
  <article class="markdown-body">
{rendered_markdown}
  </article>
</main>
</body>
</html>"""


def write_markdown_review_page(md_path: Path, title: str) -> Path | None:
    if not md_path.exists():
        return None
    out_path = md_path.with_suffix(".html")
    markdown_text = md_path.read_text(encoding="utf-8")
    out_path.write_text(
        render_markdown_review_page(title, markdown_text, md_path.name),
        encoding="utf-8",
    )
    return out_path


def render_static_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    head = "".join(f"<th>{html.escape(label)}</th>" for _, label in columns)
    body = []
    for row in rows:
        body.append(
            "<tr>"
            + "".join(f"<td>{escape_cell(row.get(key))}</td>" for key, _ in columns)
            + "</tr>"
        )
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def render_state_global_section(data: dict[str, Any]) -> str:
    state = data.get("state_companion") or {}
    if not state.get("available"):
        return f"""
  <section id="state-work" class="panel">
    <h2>State Changes And Small-Subset Experiments</h2>
    <p class="note">{escape_cell(state.get('message') or 'State companion data was unavailable.')}</p>
  </section>
"""

    schema_rows = [
        {
            "priority": row.get("priority"),
            "move": row.get("schema_move"),
            "failure_class": row.get("failure_class"),
            "change": row.get("change"),
            "validation": row.get("validation"),
        }
        for row in state.get("schema_change_plan", [])
    ]
    scorecard_rows = [
        {
            "area": row.get("area"),
            "evidence": row.get("current_evidence"),
            "audit_signal": row.get("audit_signal"),
            "decision": row.get("decision"),
        }
        for row in state.get("state_scorecard", [])
    ]
    task_mode_rows = [
        {
            "mode": row.get("label") or row.get("key"),
            "turns": row.get("n"),
            "share": format_rate(row.get("share")),
            "final20": format_rate(row.get("final20")),
            "union20": format_rate(row.get("union20")),
            "union100": format_rate(row.get("union100")),
            "rank_loss20": row.get("rank_loss20"),
            "candidate_gap20": row.get("candidate_gap20"),
            "read": row.get("interpretation"),
        }
        for row in state.get("task_modes", [])
    ]
    continuation = state.get("continuation_deep_dive") or {}
    continuation_rows = [
        {
            "bucket": row.get("label"),
            "turns": row.get("n"),
            "share": format_rate(row.get("share")),
            "cause": row.get("cause"),
            "fix": row.get("fix"),
        }
        for row in continuation.get("buckets", [])
    ]
    newartist = state.get("newartist_deep_dive") or {}
    newartist_slice_rows = [
        {
            "slice": row.get("slice"),
            "turns": row.get("n"),
            "final20": format_rate(row.get("final20")),
            "union20": format_rate(row.get("union20")),
            "union100": format_rate(row.get("union100")),
        }
        for row in newartist.get("current_slices", [])
    ]
    newartist_bucket_rows = [
        {
            "bucket": row.get("label"),
            "turns": row.get("n"),
            "share": format_rate(row.get("share")),
            "cause": row.get("cause"),
            "fix": row.get("fix"),
        }
        for row in newartist.get("buckets", [])
    ]
    measured_rows = [
        {
            "lever": baseline_wording(row.get("lever")),
            "status": baseline_wording(row.get("status")),
            "result": baseline_wording(row.get("result")),
            "decision": baseline_wording(row.get("decision")),
            "source": row.get("source"),
        }
        for row in state.get("measured_levers", [])
    ]
    not_first_rows = [
        {
            "idea": baseline_wording(row.get("idea")),
            "decision": baseline_wording(row.get("decision")),
            "evidence": baseline_wording(row.get("evidence")),
        }
        for row in state.get("not_first", [])
    ]
    feature_rows = [
        {
            "feature": row.get("feature"),
            "grain": row.get("grain"),
            "why": baseline_wording(row.get("why")),
            "validation": baseline_wording(row.get("validation")),
        }
        for row in state.get("feature_catalog", [])
    ]
    role_rows = [
        {
            "example": row.get("id"),
            "intent": row.get("intent"),
            "ask": row.get("ask"),
            "anchored": row.get("anchored"),
            "why_wrong": row.get("reason"),
            "ideal": row.get("ideal"),
        }
        for row in state.get("role_bug_examples", [])
    ]
    reconciliation_rows = [
        {
            "claim": row.get("claim"),
            "report_value": row.get("report_value"),
            "alternate_value": row.get("alternate_value"),
            "decision": row.get("decision"),
        }
        for row in state.get("counting_reconciliation", [])
    ]
    ideal_rows = [
        {
            "target_id": row.get("target_id"),
            "priority": row.get("priority"),
            "failure_classes": row.get("failure_classes"),
            "ideal_state_shape": row.get("ideal_state_shape"),
            "minimum_viable_state": row.get("minimum_viable_state"),
            "extraction_probe": row.get("extraction_probe"),
            "if_too_hard": row.get("if_too_hard"),
            "downstream_use": row.get("downstream_use"),
        }
        for row in state.get("ideal_state_targets", [])
    ]
    confusion_rows = [
        {
            "confusing_surface": row.get("confusing_surface"),
            "risk": row.get("risk"),
            "decision": row.get("decision"),
            "field_economy_move": row.get("field_economy_move"),
            "small_test": row.get("small_test"),
        }
        for row in state.get("state_confusion_plan", [])
    ]
    metadata_rows = [
        {
            "source": row.get("source"),
            "use_directly": row.get("use_directly"),
            "emulate_or_extract": row.get("emulate_or_extract"),
            "ranking_shape": row.get("ranking_shape"),
            "first_test": row.get("first_test"),
        }
        for row in state.get("metadata_decision_plan", [])
    ]
    blindset_metadata = state.get("blindset_metadata_availability") or {}
    blindset_rows = [
        {
            "item": row.get("item"),
            "blind_a_status": row.get("blind_a_status"),
            "evidence": row.get("evidence"),
            "report_decision": row.get("report_decision"),
        }
        for row in blindset_metadata.get("rows", [])
    ]
    holistic_rows = [
        {
            "area": row.get("area"),
            "cost": row.get("cost"),
            "decision": row.get("decision"),
            "first_test": row.get("first_test"),
        }
        for row in state.get("holistic_plan", [])
    ]
    pack_rows = [
        {
            "pack": pack.get("pack"),
            "class_type": pack.get("class_type"),
            "n": pack.get("n"),
            "target_n": pack.get("target_n"),
            "hypothesis": pack.get("hypothesis"),
            "state_targets": pack.get("ideal_state_targets"),
            "state_terms": pack.get("state_terms_to_check"),
            "success_metric": pack.get("success_metric"),
        }
        for pack in state.get("experiment_packs", [])
    ]
    turn_rows = []
    for sample in state.get("experiment_turns", []):
        baseline = sample.get("baseline") or {}
        turn_rows.append(
            {
                "sample_id": sample.get("sample_id"),
                "pack": sample.get("pack"),
                "class_type": sample.get("class_type"),
                "gt": f"{sample.get('gt_track')} by {sample.get('gt_artist')}",
                "baseline": (
                    f"final={rank_or_dash(baseline.get('final_rank'))}; "
                    f"fused={rank_or_dash(baseline.get('fused_rank'))}; "
                    f"branch={rank_or_dash(baseline.get('best_branch_rank'))}"
                ),
                "expected_change": sample.get("expected_change"),
            }
        )
    pack_file = state.get("experiment_pack_file") or "state_experiment_pack.json"
    return f"""
  <section id="state-work" class="panel">
    <div class="section-head">
      <div>
        <p class="eyebrow">State work</p>
        <h2>What To Change, What To Leave Alone</h2>
      </div>
      <div class="mini-actions" aria-label="State report links">
        <a class="primary" href="state_focus/index.html#examples">Open case studies</a>
        <a href="{escape_cell(state['links']['state_focus'])}">Schema audit</a>
        <a href="{escape_cell(pack_file)}">Replay JSON</a>
      </div>
    </div>
    <p class="note">State extraction is expensive, so this section is organized as a decision queue. Read the open summary first, then expand only the tables needed for implementation or review.</p>
    <div class="reader-path">
      <div><strong>P0</strong><span>Split roleless entities and add target artist mode.</span></div>
      <div><strong>P0</strong><span>Wire state routing into retriever profiles before adding retrievers.</span></div>
      <div><strong>P1</strong><span>Use guardrails for temporal constraints and rejections.</span></div>
      <div><strong>Do not start</strong><span>Do not add raw demographics, raw tags, or duplicate mode fields first.</span></div>
    </div>
    <div class="details-stack">
      <details open>
        <summary>Decision brief: task modes and state scorecard</summary>
        <p class="note">This restores the high-level diagnosis into the global report. Exact named tracks are mostly solved; continuation is a ranker/state-use lane; mid-conversation new-artist turns are the main candidate-generation lane.</p>
        {render_static_table(task_mode_rows, [
            ('mode','Mode'), ('turns','Turns'), ('share','Share'), ('final20','Final@20'),
            ('union20','Union@20'), ('union100','Union@100'), ('rank_loss20','Rank loss@20'),
            ('candidate_gap20','Candidate gap@20'), ('read','Read')
        ])}
        {render_static_table(scorecard_rows, [
            ('area','State area'), ('evidence','Current evidence'), ('audit_signal','Audit signal'), ('decision','Decision')
        ])}
      </details>
      <details open>
        <summary>Measured levers and what not to do first</summary>
        <p class="note">This is the practical work list. State extraction is expensive, so measured or cheap-routing work should come before broad extractor or retriever rewrites.</p>
        {render_static_table(measured_rows, [
            ('lever','Lever'), ('status','Status'), ('result','Measured result'), ('decision','Decision'), ('source','Source')
        ])}
        {render_static_table(not_first_rows, [
            ('idea','Do not start with'), ('decision','Decision'), ('evidence','Evidence')
        ])}
      </details>
      <details open>
        <summary>Continuation vs new-artist deep dive</summary>
        <p class="note">{escape_cell(continuation.get('summary'))}</p>
        <p class="note"><strong>Continuation work:</strong> {escape_cell(continuation.get('work'))}</p>
        {render_static_table(continuation_rows, [
            ('bucket','Continuation bucket'), ('turns','Turns'), ('share','Share'), ('cause','Cause'), ('fix','Fix')
        ])}
        <p class="note">{escape_cell(newartist.get('summary'))}</p>
        <p class="note"><strong>New-artist work:</strong> {escape_cell(newartist.get('work'))}</p>
        {render_static_table(newartist_slice_rows, [
            ('slice','New-artist slice'), ('turns','Turns'), ('final20','Final@20'), ('union20','Union@20'), ('union100','Union@100')
        ])}
        {render_static_table(newartist_bucket_rows, [
            ('bucket','Candidate-generation bucket'), ('turns','Turns'), ('share','Share'), ('cause','Cause'), ('fix','Fix')
        ])}
      </details>
      <details>
        <summary>Candidate feature catalog and role-bug examples</summary>
        <p class="note">These are the state/ranker features and concrete role-confusion examples to preserve as implementation tests.</p>
        {render_static_table(feature_rows, [
            ('feature','Feature'), ('grain','Grain'), ('why','Why it matters'), ('validation','Validation')
        ])}
        {render_static_table(role_rows, [
            ('example','Example'), ('intent','Intent'), ('ask','Ask'), ('anchored','Current anchor'),
            ('why_wrong','Why wrong'), ('ideal','Ideal state')
        ])}
      </details>
      <details open>
        <summary>Suggested state changes</summary>
        {render_static_table(schema_rows, [
            ('priority','Priority'), ('move','Move'), ('failure_class','Failure class'),
            ('change','Change'), ('validation','Validation')
        ])}
      </details>
      <details>
        <summary>Ideal extractor targets and minimum viable fields</summary>
        <p class="note">Concrete state shapes to try on small API-call batches. Each target includes a cheaper minimum viable state and a fallback if the full shape is not extractable reliably.</p>
        {render_static_table(ideal_rows, [
            ('target_id','State target'), ('priority','Priority'), ('failure_classes','Failure classes'),
            ('ideal_state_shape','Ideal state shape'), ('minimum_viable_state','Minimum viable'),
            ('extraction_probe','Extraction probe'), ('if_too_hard','Fallback'), ('downstream_use','Downstream use')
        ])}
      </details>
      <details>
        <summary>State confusion / field economy plan</summary>
        <p class="note">More fields can make the extractor and retrieval logic less clear. This table names overlapping state surfaces and the simplification rule to test before spending on broader extraction.</p>
        {render_static_table(confusion_rows, [
            ('confusing_surface','Confusing surface'), ('risk','Risk'), ('decision','Decision'),
            ('field_economy_move','Field-economy move'), ('small_test','Small test')
        ])}
      </details>
      <details>
        <summary>Organizer metadata decision</summary>
        <p class="note">Use organizer session metadata directly when available. Emulate or extract it only if a target split lacks it and a measured candidate-varying feature has shown value.</p>
        <p class="note">{escape_cell(blindset_metadata.get('summary') or 'Blind-A availability was not checked.')}</p>
        {render_static_table(blindset_rows, [
            ('item','Item'), ('blind_a_status','Blind-A status'), ('evidence','Evidence'), ('report_decision','Report decision')
        ])}
        {render_static_table(metadata_rows, [
            ('source','Source'), ('use_directly','Use directly?'), ('emulate_or_extract','Emulate / extract?'),
            ('ranking_shape','Ranking shape'), ('first_test','First test')
        ])}
      </details>
      <details>
        <summary>Holistic work plan</summary>
        {render_static_table(holistic_rows, [
            ('area','Area'), ('cost','Cost'), ('decision','Decision'), ('first_test','First test')
        ])}
      </details>
      <details>
        <summary>Small subset experiment packs</summary>
        {render_static_table(pack_rows, [
            ('pack','Pack'), ('class_type','Class type'), ('n','Turns'), ('target_n','Target'),
            ('hypothesis','Hypothesis'), ('state_targets','State targets'), ('state_terms','State terms to check'),
            ('success_metric','Success metric')
        ])}
      </details>
      <details>
        <summary>Sample turns to replay</summary>
        <p class="note">Use the JSON file for the full payload, including current user text, baseline ranks, diagnostics, expected change, and state snapshot.</p>
        {render_static_table(turn_rows, [
            ('sample_id','Sample id'), ('pack','Pack'), ('class_type','Class type'), ('gt','GT'), ('baseline','Baseline ranks'), ('expected_change','Expected change')
        ])}
      </details>
      <details>
        <summary>Counting reconciliation and caveats</summary>
        <p class="note">These notes keep definition-sensitive counts honest, especially album continuation and rejection matching.</p>
        {render_static_table(reconciliation_rows, [
            ('claim','Claim'), ('report_value','Report value'), ('alternate_value','Alternate value'), ('decision','Decision')
        ])}
      </details>
    </div>
  </section>
"""


def analyze(source_root: Path, tid: str) -> dict[str, Any]:
    trace_path = source_root / "exp/inference/devset" / f"{tid}_trace.jsonl"
    pred_path = source_root / "exp/inference/devset" / f"{tid}.json"
    gt_path = source_root / "evaluator/exp/ground_truth/devset.json"
    config_path = source_root / "configs" / f"{tid}.yaml"

    catalog = load_catalog(source_root)
    ground_truth = load_ground_truth(gt_path)

    n = 0
    final_hit = Counter({k: 0 for k in FINAL_KS})
    union_hit = Counter({k: 0 for k in UNION_KS})
    union_size = Counter({k: 0 for k in UNION_KS})
    branch_fired: Counter[str] = Counter()
    branch_hits: dict[str, Counter[int]] = defaultdict(Counter)
    best_branch = Counter()
    best_branch_by_gap: dict[str, Counter[str]] = defaultdict(Counter)
    best_branch_by_mechanism: dict[str, Counter[str]] = defaultdict(Counter)
    gap_buckets = Counter()
    mechanism_buckets = Counter()
    final_rank_buckets = Counter()
    fused_rank_buckets = Counter()
    min_branch_rank_buckets = Counter()
    entity_buckets = Counter()
    postfusion_counters = Counter()
    skipped_branch_status_by_gap: dict[str, Counter[str]] = defaultdict(Counter)
    xtabs: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    examples: dict[str, list[dict[str, Any]]] = defaultdict(list)

    with trace_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            key = (row["session_id"], int(row["turn_number"]))
            gt = ground_truth.get(key)
            if gt is None:
                continue

            trace = row.get("trace") or {}
            state = trace.get("state") or {}
            resolver = trace.get("resolver") or {}
            branches = trace.get("branches") or {}
            pools = branches.get("pools") or []
            final_ids = (branches.get("final") or {}).get("track_ids") or []
            fused_ids = [item[0] for item in (branches.get("fused") or [])]

            final_rank = _rank_in_ids(final_ids, gt)
            fused_rank = _rank_in_ids(fused_ids, gt)

            branch_ranks: dict[str, int] = {}
            for pool in pools:
                name = pool.get("name", "UNKNOWN")
                branch_fired[name] += 1
                rank = _rank_in_hits(pool.get("hits") or [], gt)
                if rank is not None:
                    branch_ranks[name] = rank
                    for k in BRANCH_KS:
                        if rank <= k:
                            branch_hits[name][k] += 1

            min_branch_rank = min(branch_ranks.values()) if branch_ranks else None
            best = min(branch_ranks.items(), key=lambda item: item[1])[0] if branch_ranks else "NONE"
            final_hit20 = final_rank is not None and final_rank <= 20
            union_flags = {k: min_branch_rank is not None and min_branch_rank <= k for k in UNION_KS}
            gap_bucket = _gap_bucket(final_rank, fused_rank, min_branch_rank)
            mechanism = _mechanism_bucket(final_rank, fused_rank, min_branch_rank)

            n += 1
            for k in FINAL_KS:
                if final_rank is not None and final_rank <= k:
                    final_hit[k] += 1
            for k in UNION_KS:
                if union_flags[k]:
                    union_hit[k] += 1
                seen: set[str] = set()
                for pool in pools:
                    for hit in (pool.get("hits") or [])[:k]:
                        if hit:
                            seen.add(hit[0])
                union_size[k] += len(seen)

            gap_buckets[gap_bucket] += 1
            mechanism_buckets[mechanism] += 1
            final_rank_buckets[_rank_bucket(final_rank)] += 1
            fused_rank_buckets[_rank_bucket(fused_rank)] += 1
            min_branch_rank_buckets[_rank_bucket(min_branch_rank)] += 1
            best_branch[best] += 1
            best_branch_by_gap[gap_bucket][best] += 1
            best_branch_by_mechanism[mechanism][best] += 1

            meta = catalog.get(gt, {})
            gt_artist_ids = meta.get("artist_ids", set())
            gt_artist_names = {_norm_text(v) for v in meta.get("artist_names", [])}
            resolved = trace.get("resolved_targets") or []
            resolved_track_ids = {item.get("entity_id") for item in resolved if item.get("kind") == "track"}
            resolved_artist_ids = {item.get("entity_id") for item in resolved if item.get("kind") == "artist"}
            anchor_tracks = set(resolver.get("anchor_track_ids") or [])
            anchor_artists_raw = set(resolver.get("anchor_artist_ids") or [])
            anchor_artists_norm = {_norm_text(v) for v in anchor_artists_raw}
            mentioned = state.get("mentioned_entities") or []
            mentioned_track_names = {
                _norm_text(item.get("value")) for item in mentioned if item.get("type") == "track"
            }
            mentioned_artist_names = {
                _norm_text(item.get("value")) for item in mentioned if item.get("type") == "artist"
            }
            gt_track_name = _norm_text(meta.get("track_name"))
            if gt in resolved_track_ids:
                entity_bucket = "resolved_exact_track"
            elif gt_artist_ids & resolved_artist_ids:
                entity_bucket = "resolved_gt_artist"
            elif gt in anchor_tracks:
                entity_bucket = "anchor_track_feedback"
            elif (gt_artist_ids & anchor_artists_raw) or (gt_artist_names & anchor_artists_norm):
                entity_bucket = "anchor_gt_artist"
            elif gt_track_name and gt_track_name in mentioned_track_names:
                entity_bucket = "mentioned_gt_track_name_unresolved"
            elif gt_artist_names and gt_artist_names & mentioned_artist_names:
                entity_bucket = "mentioned_gt_artist_name_unresolved"
            else:
                entity_bucket = "no_gt_track_or_artist_in_state"
            entity_buckets[entity_bucket] += 1

            positive_tags = {
                tag for tag in (_norm_tag(v) for v in (resolver.get("positive_tags") or [])) if tag
            }
            tag_overlap = len(positive_tags & meta.get("tags", set()))
            tag_bucket = _tag_overlap_bucket(tag_overlap)

            release_range = state.get("release_year_range") or {}
            release_year = meta.get("release_year")
            if release_range and release_year is not None:
                start = release_range.get("start")
                end = release_range.get("end")
                excludes = (start is not None and release_year < start) or (
                    end is not None and release_year > end
                )
                release_bucket = "release_range_excludes_gt" if excludes else "release_range_contains_gt"
            elif release_range:
                release_bucket = "release_range_gt_year_unknown"
            else:
                release_bucket = "no_release_range"

            popularity_bucket = _popularity_bucket(float(meta.get("popularity") or 0.0))
            routing = trace.get("routing_tags") or state.get("routing_tags") or {}
            true_routing = sorted(name for name, value in routing.items() if value)
            routing_combo = "+".join(true_routing) if true_routing else "none"
            policy = (state.get("process_constraints") or {}).get("exploration_policy") or "NONE"
            intent_mode = trace.get("intent_mode") or state.get("intent_mode") or "NONE"

            for dim, value in (
                ("turn_number", row["turn_number"]),
                ("intent_mode", intent_mode),
                ("exploration_policy", policy),
                ("entity_bucket", entity_bucket),
                ("tag_overlap", tag_bucket),
                ("release_bucket", release_bucket),
                ("popularity_bucket", popularity_bucket),
                ("routing_combo", routing_combo),
            ):
                bump_xtab(
                    xtabs,
                    dim,
                    value,
                    final_hit20=final_hit20,
                    union20=union_flags[20],
                    union100=union_flags[100],
                    union200=union_flags[200],
                    union1000=union_flags[1000],
                    gap_bucket=gap_bucket,
                    mechanism=mechanism,
                )
            for routing_tag in true_routing:
                bump_xtab(
                    xtabs,
                    "routing_true_tag",
                    routing_tag,
                    final_hit20=final_hit20,
                    union20=union_flags[20],
                    union100=union_flags[100],
                    union200=union_flags[200],
                    union1000=union_flags[1000],
                    gap_bucket=gap_bucket,
                    mechanism=mechanism,
                )

            branch_status = branches.get("branch_status") or {}
            for branch_name, status in branch_status.items():
                if not status.get("fired"):
                    skipped_branch_status_by_gap[gap_bucket][
                        f"{branch_name}::{status.get('skip_reason', 'not_fired')}"
                    ] += 1

            if mechanism == "fused_top20_postfusion_demoted":
                played = resolver.get("played_track_ids") or []
                played_artist_ids: set[str] = set()
                played_album_ids: set[str] = set()
                for played_id in played:
                    played_meta = catalog.get(played_id, {})
                    played_artist_ids |= played_meta.get("artist_ids", set())
                    played_album_ids |= played_meta.get("album_ids", set())
                if gt_artist_ids & played_artist_ids:
                    postfusion_counters["same_artist_as_played"] += 1
                if meta.get("album_ids", set()) & played_album_ids:
                    postfusion_counters["same_album_as_played"] += 1
                postfusion_counters[f"policy:{policy}"] += 1
                postfusion_counters[f"release:{release_bucket}"] += 1
                postfusion_counters[f"tag_overlap:{tag_bucket}"] += 1
                if final_rank and fused_rank:
                    postfusion_counters["rank_delta_sum"] += final_rank - fused_rank
                    postfusion_counters["rank_delta_n"] += 1

            example = {
                "session_id": row["session_id"],
                "turn": row["turn_number"],
                "intent": (state.get("turn_intent") or "")[:260],
                "gt_track_id": gt,
                "gt_track": meta.get("track_name") or gt,
                "gt_artist": meta.get("artist_first") or "-",
                "final_rank": final_rank,
                "fused_rank": fused_rank,
                "min_branch_rank": min_branch_rank,
                "best_branch": best,
                "top_branch_ranks": sorted(branch_ranks.items(), key=lambda item: item[1])[:6],
                "entity_bucket": entity_bucket,
                "policy": policy,
                "intent_mode": intent_mode,
                "routing": true_routing,
                "positive_tags": sorted(positive_tags)[:12],
                "gt_tag_overlap": sorted(positive_tags & meta.get("tags", set()))[:12],
                "release_year": release_year,
                "release_bucket": release_bucket,
                "popularity": meta.get("popularity"),
            }
            sample_example(examples, gap_bucket, limit=12, record=example)
            sample_example(examples, mechanism, limit=12, record=example)

    branch_rows = []
    for branch_name, fired in sorted(branch_fired.items()):
        row = {"name": branch_name, "fired": fired}
        for k in BRANCH_KS:
            row[f"recall@{k}"] = round(branch_hits[branch_name][k] / fired, 4) if fired else 0.0
            row[f"hit_count@{k}"] = branch_hits[branch_name][k]
        branch_rows.append(row)

    dimension_rows: dict[str, list[dict[str, Any]]] = {}
    for dim, labels in xtabs.items():
        rows = []
        for label, counts in labels.items():
            denom = counts["n"]
            row = {
                "name": label,
                "n": denom,
                "final_hit20_rate": round(counts["final_hit20"] / denom, 4) if denom else 0.0,
                "union20_rate": round(counts["union20"] / denom, 4) if denom else 0.0,
                "union100_rate": round(counts["union100"] / denom, 4) if denom else 0.0,
                "union200_rate": round(counts["union200"] / denom, 4) if denom else 0.0,
                "union1000_rate": round(counts["union1000"] / denom, 4) if denom else 0.0,
                "gap_counts": {
                    key.replace("gap::", ""): value
                    for key, value in counts.items()
                    if key.startswith("gap::")
                },
                "mechanism_counts": {
                    key.replace("mechanism::", ""): value
                    for key, value in counts.items()
                    if key.startswith("mechanism::")
                },
            }
            row["union20_gap_rate"] = round(1.0 - row["union20_rate"], 4)
            row["union100_gap_rate"] = round(1.0 - row["union100_rate"], 4)
            rows.append(row)
        if dim == "turn_number":
            rows.sort(key=lambda r: int(r["name"]))
        else:
            rows.sort(key=lambda r: (-r["n"], r["name"]))
        dimension_rows[dim] = rows

    postfusion_demotions = mechanism_buckets["fused_top20_postfusion_demoted"]
    postfusion_summary = _counter_rows(
        Counter({k: v for k, v in postfusion_counters.items() if not k.startswith("rank_delta_")}),
        denom=postfusion_demotions,
    )
    rank_delta_mean = None
    if postfusion_counters["rank_delta_n"]:
        rank_delta_mean = round(
            postfusion_counters["rank_delta_sum"] / postfusion_counters["rank_delta_n"],
            2,
        )

    metrics = {
        "n_turns": n,
        "final_hit": {str(k): round(final_hit[k] / n, 4) for k in FINAL_KS},
        "union_hit": {str(k): round(union_hit[k] / n, 4) for k in UNION_KS},
        "union_size": {str(k): round(union_size[k] / n, 1) for k in UNION_KS},
        "fusion_efficiency": {
            str(k): round((final_hit[k] / union_hit[k]), 4) if union_hit[k] else None
            for k in (20, 100, 200, 1000)
        },
    }
    ceilings = [
        {"name": "Current final top-20", "rate": metrics["final_hit"]["20"], "count": final_hit[20]},
        {"name": "If ranker recovers union@20", "rate": metrics["union_hit"]["20"], "count": union_hit[20]},
        {"name": "If ranker recovers union@100", "rate": metrics["union_hit"]["100"], "count": union_hit[100]},
        {"name": "If ranker recovers union@200", "rate": metrics["union_hit"]["200"], "count": union_hit[200]},
        {"name": "If retrieval reaches union@1000", "rate": metrics["union_hit"]["1000"], "count": union_hit[1000]},
    ]

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tid": tid,
        "snapshot_contract": {
            "status": "Baseline snapshot, not evergreen product documentation.",
            "applies_to": f"{tid} devset predictions, trace, config, and ground truth at generation time.",
            "valid_until": (
                "Rerun after changing state extraction, retriever routing, candidate generation, "
                "fusion/finalization, ranker features, catalog/index contents, or evaluation split."
            ),
            "how_to_use": (
                "Treat work items as experiment hypotheses and replay contracts. After an implementation, "
                "compare this baseline to a regenerated report before acting on old counts or examples."
            ),
        },
        "paths": {
            "source_root": str(source_root),
            "trace": str(trace_path),
            "predictions": str(pred_path),
            "ground_truth": str(gt_path),
            "config": str(config_path),
        },
        "config": {
            "branch_trace_topk": 1000,
            "final_topk": 1000,
            "rrf_k": 60,
        },
        "metrics": metrics,
        "ceilings": ceilings,
        "gap_buckets": _counter_rows(gap_buckets, n),
        "mechanism_buckets": _counter_rows(mechanism_buckets, n),
        "rank_buckets": {
            "final": _counter_rows(final_rank_buckets, n),
            "fused": _counter_rows(fused_rank_buckets, n),
            "branch": _counter_rows(min_branch_rank_buckets, n),
        },
        "entity_buckets": _counter_rows(entity_buckets, n),
        "best_branch": _counter_rows(best_branch, n),
        "best_branch_by_gap": {
            key: _counter_rows(counter, gap_buckets[key], limit=12)
            for key, counter in best_branch_by_gap.items()
        },
        "best_branch_by_mechanism": {
            key: _counter_rows(counter, mechanism_buckets[key], limit=12)
            for key, counter in best_branch_by_mechanism.items()
        },
        "branches": branch_rows,
        "dimensions": dimension_rows,
        "postfusion_summary": postfusion_summary,
        "postfusion_rank_delta_mean": rank_delta_mean,
        "skipped_branch_status_by_gap": {
            key: _counter_rows(counter, gap_buckets[key], limit=12)
            for key, counter in skipped_branch_status_by_gap.items()
        },
        "examples": examples,
        "recommendations": [
            {
                "theme": "Train a state-aware candidate scorer",
                "why": "Union@100 is 66.2%, but final top-20 is only 27.4%. The current equal-rank fusion baseline is evidence of the gap, not the desired end state.",
                "first_experiment": "Train a lightweight logistic or LambdaMART ranker over union@200 using branch ranks, branch-count features, state/entity features, policy, tag overlap, release distance, popularity, and same-artist flags.",
            },
            {
                "theme": "Protect trusted candidates before final policy",
                "why": "A large set of GTs are branch top-20 or fused top-20 but disappear, especially under diversify_artists.",
                "first_experiment": "Reserve a small number of slots for exact/discography/BM25/8B metadata/image anchor candidates before applying same-artist demotion.",
            },
            {
                "theme": "Soften diversify_artists and release-range penalties",
                "why": "Same-artist and era demotions are frequently misaligned with evaluator targets.",
                "first_experiment": "Ablate ANCHOR_ARTIST_DEMOTE_BY_POLICY diversify_artists from 0.4 to 0.7/0.85/1.0, and treat release ranges as positive boosts rather than negative penalties.",
            },
            {
                "theme": "Improve latent-target recall for union@100 misses",
                "why": "When the GT track/artist is not represented in state, union@100 and final top-20 collapse.",
                "first_experiment": "Add tag-popularity and similar-artist candidate generators keyed by normalized positive tags, accepted-track anchors, and hidden-target/visual routing.",
            },
            {
                "theme": "Make state route retrievers, not just adjust final scores",
                "why": "Lyric and visual routes work when fired, but they fire rarely; attributes branches fire often but are weak.",
                "first_experiment": "Use routing_tags to boost/fan out the right branches, fire lyric retrieval on lyrical-theme phrases, and clean attributes query text before adding new embeddings.",
            },
        ],
    }


def render_report(data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    safe_payload = payload.replace("</", "<\\/")
    title = "Music CRS Recall Gap Explorer"
    state_work_html = render_state_global_section(data)
    metrics = data.get("metrics", {})
    state_companion = data.get("state_companion") or {}

    def rate_at(mapping: dict[Any, Any], key: int) -> float:
        value = mapping.get(str(key), mapping.get(key, 0.0))
        return float(value or 0.0)

    n_turns = int(metrics.get("n_turns") or 8000)
    final20 = rate_at(metrics.get("final_hit", {}), 20)
    union20 = rate_at(metrics.get("union_hit", {}), 20)
    union50 = rate_at(metrics.get("union_hit", {}), 50)
    union100 = rate_at(metrics.get("union_hit", {}), 100)
    union1000 = rate_at(metrics.get("union_hit", {}), 1000)
    routing_counts = (state_companion.get("routing_counts") or {})
    routing_total = sum(int(v or 0) for v in routing_counts.values())
    same_artist = next((row for row in data.get("postfusion_summary", []) if row.get("name") == "same_artist_as_played"), {})
    diversify = next((row for row in data.get("postfusion_summary", []) if row.get("name") == "policy:diversify_artists"), {})
    funnel_steps = [
        ("Ships today", final20, f"{int(round(final20 * n_turns)):,} final top-20 hits", "ship"),
        ("Union@20", union20, "Strict first boundary: already candidate-visible", "rank"),
        ("Union@50", union50, "Shallow rerank/retrieval-profile workbench", "rank"),
        ("Union@100", union100, "Honest first-stage ranker ceiling for this pool", "reach"),
        ("Union@1000", union1000, "Deep oracle reference, not the next target", "oracle"),
    ]
    funnel_html = "".join(
        f"""
        <div class="funnel-card {css}">
          <div class="funnel-rate">{format_rate(rate)}</div>
          <div class="funnel-name">{html.escape(name)}</div>
          <div class="funnel-note">{html.escape(note)}</div>
        </div>
        """
        for name, rate, note, css in funnel_steps
    )
    queue_rows = [
        {
            "sev": "P0 bug",
            "css": "hot",
            "work": "Wire routing tags into retrieval profiles",
            "evidence": f"{routing_total:,} routing-tag firings, but current routing weights are empty; hidden_target_search alone fires {int(routing_counts.get('hidden_target_search') or 0):,}.",
            "change": "Set routing_boost/profile weights and replay by exact_entity_probe, feature_articulation, hidden_target_search, lyric, and visual slices.",
        },
        {
            "sev": "P0 state",
            "css": "hot",
            "work": "Replace roleless +1 artist carryover with keep-strength roles",
            "evidence": "Stale positive entities and novelty-prior-anchor conflicts explain why continuation wins while discovery collapses.",
            "change": "Extract seed, satisfied, contrast, history, rejected, source_turn, recency, and use_as_retrieval_seed; validate on the 110-turn pack before a full rerun.",
        },
        {
            "sev": "P0 scorer",
            "css": "warm",
            "work": "Train candidate scorer on practical union pools",
            "evidence": f"final@20 {format_rate(final20)} vs union@100 {format_rate(union100)}; new-artist union@20 remains weak, so ranker and routing must move together.",
            "change": "Use union@100/200 as the workbench; include branch ranks, artist role, album/artist recency, popularity, tag overlap, and candidate-varying goal/profile affinity.",
        },
        {
            "sev": "P0 score",
            "css": "hot",
            "work": "Add response generation evaluation",
            "evidence": "Codabench weights response quality at 0.30 and lexical diversity at 0.10; this run uses lm_type=dummy.",
            "change": "Run a real generator over dev predictions, measure Distinct-2, and inspect Gemini-judge style/grounding before prompt tuning.",
        },
        {
            "sev": "P1 policy",
            "css": "warm",
            "work": "Turn same-artist/album demotion into learned features",
            "evidence": f"Post-fusion loss is dominated by same_artist_as_played ({int(same_artist.get('n') or 0):,}) and diversify_artists ({int(diversify.get('n') or 0):,}).",
            "change": "Keep diversity as a feature, but add trusted-survivor slots and album/artist-recency features for continuation turns.",
        },
        {
            "sev": "P1 guardrail",
            "css": "warm",
            "work": "Separate style-era from hard release-date constraints and assert rejections",
            "evidence": "634 turns exclude the GT year; strict rejection leaks are a verified lower bound with name-match cases as an upper audit bound.",
            "change": "Soft-penalize era-style mismatches, keep hard ranges only for literal date asks, and add final strict-ID rejection assertions.",
        },
        {
            "sev": "Do not start",
            "css": "cool",
            "work": "Do not chase raw session constants or union@1000 first",
            "evidence": "Raw category/specificity/demographics are candidate-constant in a within-turn ranker; union@1000 is a huge-pool oracle.",
            "change": "Use metadata as routing context or candidate-varying affinity; use union@20 as the gap line and union@100/200 as the first ranker workbench.",
        },
    ]
    queue_html = "".join(
        f"""
        <article class="queue-card {row['css']}">
          <span class="severity">{html.escape(row['sev'])}</span>
          <h3>{html.escape(row['work'])}</h3>
          <p><strong>Evidence:</strong> {html.escape(row['evidence'])}</p>
          <p class="note"><strong>Incorporate:</strong> {html.escape(row['change'])}</p>
        </article>
        """
        for row in queue_rows
    )

    role_examples = state_companion.get("role_bug_examples") or []
    experiment_turns = state_companion.get("experiment_turns") or []
    role_examples_html = "".join(
        f"""
        <article class="bad-example-card role">
          <span class="severity">State bug</span>
          <h3>{escape_cell(row.get('id'))}</h3>
          <p><strong>Ask:</strong> {escape_cell(row.get('ask'))}</p>
          <p><strong>Wrong anchor:</strong> {escape_cell(row.get('anchored'))}</p>
          <p><strong>Why wrong:</strong> {escape_cell(row.get('reason'))}</p>
          <p class="note"><strong>Change:</strong> {escape_cell(row.get('ideal'))}</p>
        </article>
        """
        for row in role_examples[:6]
    ) or '<p class="note">No role-bug examples were found in the state companion data.</p>'

    failure_turns_by_pack: list[dict[str, Any]] = []
    seen_packs: set[str] = set()
    for row in experiment_turns:
        pack = str(row.get("pack") or "")
        if row.get("class_type") != "failure" or pack in seen_packs:
            continue
        seen_packs.add(pack)
        baseline = row.get("baseline") or {}
        failure_turns_by_pack.append(
            {
                "sample_id": row.get("sample_id"),
                "pack": pack,
                "user": row.get("current_user"),
                "gt": f"{row.get('gt_track') or '-'} by {row.get('gt_artist') or '-'}",
                "baseline": (
                    f"final={baseline.get('final_rank') or '-'}; "
                    f"fused={baseline.get('fused_rank') or '-'}; "
                    f"branch={baseline.get('best_branch_rank') or '-'} "
                    f"({baseline.get('best_branch') or '-'})"
                ),
                "why_wrong": row.get("why_wrong"),
                "what_should_change": row.get("what_should_change"),
            }
        )

    positive_turns = [
        {
            "sample_id": row.get("sample_id"),
            "pack": row.get("pack"),
            "gt": f"{row.get('gt_track') or '-'} by {row.get('gt_artist') or '-'}",
            "regression_test": row.get("regression_test"),
        }
        for row in experiment_turns
        if row.get("class_type") == "positive_control"
    ][:4]

    failure_turns_html = render_static_table(
        failure_turns_by_pack,
        [
            ("sample_id", "Sample"),
            ("pack", "Failure class"),
            ("user", "Current user ask"),
            ("gt", "GT"),
            ("baseline", "Baseline ranks"),
            ("why_wrong", "Why wrong"),
            ("what_should_change", "What should change"),
        ],
    )
    positive_turns_html = render_static_table(
        positive_turns,
        [
            ("sample_id", "Positive sample"),
            ("pack", "Pack"),
            ("gt", "GT"),
            ("regression_test", "Keep this working"),
        ],
    )

    ranker_bucket_actions = {
        "union20_fusion_loss": "GT is already in a branch top-20, but the fused/final path does not ship it. Use branch-rank features, state roles, and learned scorer/finalization guardrails.",
        "union100_near_miss": "GT is reachable in union@100, but too weak for the top candidate pool. Use retrieval-profile routing plus a trained scorer over union@100/200.",
        "not_in_any_branch_top1000": "GT is absent from every branch top-1000. This is a state/routing/retriever coverage gap, not a final-ranker gap.",
    }
    ranker_rows: list[dict[str, Any]] = []
    for bucket, action in ranker_bucket_actions.items():
        for row in (data.get("examples") or {}).get(bucket, [])[:3]:
            ranker_rows.append(
                {
                    "bucket": bucket,
                    "sample": f"{row.get('session_id')}::t{row.get('turn')}",
                    "gt": f"{row.get('gt_track') or '-'} by {row.get('gt_artist') or '-'}",
                    "ranks": (
                        f"final={row.get('final_rank') or '-'}; "
                        f"fused={row.get('fused_rank') or '-'}; "
                        f"branch={row.get('min_branch_rank') or '-'} "
                        f"({row.get('best_branch') or '-'})"
                    ),
                    "state": f"entity={row.get('entity_bucket') or '-'}; policy={row.get('policy') or '-'}; routing={', '.join(row.get('routing') or []) or '-'}",
                    "change": action,
                }
            )
    ranker_examples_html = render_static_table(
        ranker_rows,
        [
            ("bucket", "Gap bucket"),
            ("sample", "Sample"),
            ("gt", "GT"),
            ("ranks", "Ranks"),
            ("state", "State / route"),
            ("change", "What should change"),
        ],
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{
  --ink: #172033;
  --muted: #647084;
  --soft: #eef2f6;
  --line: #d8dee8;
  --panel: #ffffff;
  --blue: #2f6fd6;
  --teal: #16837a;
  --gold: #b7791f;
  --rose: #bf4b6a;
  --olive: #617a28;
  --bg: #f7f8fb;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: var(--ink);
  background: var(--bg);
}}
header {{
  padding: 28px clamp(18px, 4vw, 56px) 18px;
  border-bottom: 1px solid var(--line);
  background: #fff;
}}
h1 {{ margin: 0 0 8px; font-size: clamp(28px, 4vw, 44px); letter-spacing: 0; }}
h2 {{ margin: 0 0 12px; font-size: 22px; letter-spacing: 0; }}
h3 {{ margin: 0 0 10px; font-size: 16px; letter-spacing: 0; }}
p {{ line-height: 1.55; }}
section {{ scroll-margin-top: 74px; }}
.subhead {{ max-width: 980px; margin: 0; color: var(--muted); font-size: 16px; line-height: 1.55; }}
.meta {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }}
.pill {{
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 5px 9px;
  border: 1px solid var(--line);
  border-radius: 6px;
  color: var(--muted);
  background: #fff;
  font-size: 12px;
}}
.top-nav {{
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  gap: 6px;
  align-items: center;
  overflow-x: auto;
  padding: 10px clamp(14px, 3vw, 42px);
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(10px);
}}
.top-nav a {{
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 6px 10px;
  border: 1px solid transparent;
  border-radius: 6px;
  color: var(--muted);
  font-size: 13px;
  text-decoration: none;
  white-space: nowrap;
}}
.top-nav a.primary {{
  color: #fff;
  background: var(--ink);
  border-color: var(--ink);
}}
.top-nav a:hover {{
  color: var(--blue);
  border-color: var(--line);
  background: #f8fafc;
}}
.top-nav a.primary:hover {{
  color: #fff;
  background: #273247;
}}
.report-links {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}}
.report-link {{
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 7px 10px;
  border: 1px solid var(--blue);
  border-radius: 6px;
  color: var(--blue);
  background: #f4f8ff;
  font-size: 13px;
  text-decoration: none;
}}
.report-link.primary {{
  color: #fff;
  background: var(--blue);
}}
.report-link:hover {{ background: #eaf2ff; }}
.report-link.primary:hover {{ background: #255fb8; }}
main {{ padding: 22px clamp(14px, 3vw, 42px) 42px; }}
section {{ margin: 0 auto 18px; max-width: 1320px; }}
.report-hub {{
  display: grid;
  grid-template-columns: minmax(240px, .44fr) minmax(0, 1fr);
  gap: 16px;
  align-items: stretch;
}}
.report-hub-copy {{
  padding: 2px 0;
}}
.report-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 10px;
}}
.report-grid.primary-map {{
  grid-template-columns: repeat(4, minmax(210px, 1fr));
}}
.report-card {{
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 118px;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  color: var(--ink);
  text-decoration: none;
  box-shadow: 0 1px 2px rgba(30, 42, 62, 0.05);
}}
.report-card.current {{
  border-color: #9acbc5;
  background: #f7fffd;
}}
.report-card.primary {{
  border-color: #9bbcf4;
  background: #f5f8ff;
}}
.report-card:hover {{
  border-color: var(--blue);
  box-shadow: 0 8px 18px rgba(30, 42, 62, 0.08);
}}
.report-card span {{
  color: var(--muted);
  font-size: 11px;
  font-weight: 720;
  letter-spacing: 0;
  text-transform: uppercase;
}}
.report-card strong {{
  display: block;
  margin: 8px 0 6px;
  font-size: 15px;
  line-height: 1.25;
}}
.report-card small {{
  color: var(--muted);
  font-size: 12px;
  line-height: 1.4;
}}
.report-card .path {{
  margin-top: 10px;
  color: var(--blue);
  font-size: 12px;
  font-weight: 720;
}}
.artifact-drawer {{
  margin-top: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  padding: 12px;
}}
.artifact-drawer summary {{
  cursor: pointer;
  color: var(--blue);
  font-weight: 720;
}}
.artifact-links {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 8px;
  margin-top: 10px;
}}
.artifact-links a {{
  border: 1px solid var(--line);
  border-radius: 7px;
  padding: 9px 10px;
  background: #f8fafc;
  color: var(--ink);
  text-decoration: none;
  font-size: 13px;
}}
.artifact-links span {{
  display: block;
  color: var(--muted);
  font-size: 11px;
  margin-bottom: 3px;
}}
.section-head {{
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
  margin-bottom: 10px;
}}
.eyebrow {{
  margin: 0 0 4px;
  color: var(--teal);
  font-size: 12px;
  font-weight: 760;
  letter-spacing: 0;
  text-transform: uppercase;
}}
.mini-actions {{
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  justify-content: flex-end;
}}
.mini-actions a {{
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 6px 9px;
  border: 1px solid var(--line);
  border-radius: 6px;
  color: var(--blue);
  background: #fff;
  font-size: 12px;
  text-decoration: none;
}}
.mini-actions a.primary {{
  border-color: var(--blue);
  background: #f4f8ff;
  font-weight: 720;
}}
.reader-path {{
  display: grid;
  grid-template-columns: repeat(4, minmax(150px, 1fr));
  gap: 10px;
  margin: 14px 0;
}}
.reader-path div {{
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 11px;
  background: #f8fafc;
}}
.reader-path strong {{
  display: block;
  margin-bottom: 5px;
  color: var(--ink);
  font-size: 12px;
}}
.reader-path span {{
  display: block;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.4;
}}
.details-stack {{
  display: grid;
  gap: 8px;
  margin-top: 12px;
}}
details {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}}
summary {{
  cursor: pointer;
  padding: 12px 14px;
  color: var(--ink);
  font-weight: 740;
  background: #f8fafc;
}}
details > .table-wrap,
details > p.note {{
  margin: 12px;
}}
.reviewer-note {{
  display: grid;
  grid-template-columns: minmax(220px, 0.42fr) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}}
.panel {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
  box-shadow: 0 1px 2px rgba(30, 42, 62, 0.05);
}}
.summary {{
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(300px, 0.85fr);
  gap: 16px;
}}
.takeaways {{
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}}
.takeaways li {{
  padding: 12px 12px;
  border-left: 4px solid var(--blue);
  background: #f8fafc;
  border-radius: 6px;
  line-height: 1.5;
}}
.cards {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
}}
.card {{
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px;
  background: #fff;
}}
.metric {{ font-size: 27px; font-weight: 780; letter-spacing: 0; }}
.label {{ margin-top: 4px; color: var(--muted); font-size: 12px; line-height: 1.35; }}
.tabs, .controls {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 14px; }}
button {{
  border: 1px solid var(--line);
  border-radius: 6px;
  min-height: 34px;
  padding: 7px 11px;
  background: #fff;
  color: var(--ink);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}}
button.active {{ background: var(--ink); color: #fff; border-color: var(--ink); }}
.grid2 {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(320px, .82fr); gap: 16px; }}
.chart {{ display: grid; gap: 9px; }}
.bar-row {{
  display: grid;
  grid-template-columns: minmax(170px, 260px) minmax(120px, 1fr) 72px;
  gap: 10px;
  align-items: center;
  min-height: 31px;
}}
.bar-label {{ font-size: 13px; overflow-wrap: anywhere; }}
.bar-track {{ height: 18px; background: #edf1f6; border-radius: 4px; overflow: hidden; }}
.bar-fill {{ height: 100%; width: 0%; background: var(--blue); border-radius: 4px; transition: width .24s ease; }}
.bar-fill.teal {{ background: var(--teal); }}
.bar-fill.gold {{ background: var(--gold); }}
.bar-fill.rose {{ background: var(--rose); }}
.bar-fill.olive {{ background: var(--olive); }}
.bar-val {{ font-variant-numeric: tabular-nums; font-size: 13px; text-align: right; color: var(--muted); }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ padding: 9px 8px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
th {{ color: #465163; font-size: 12px; background: #f8fafc; position: sticky; top: 0; }}
.table-wrap {{ max-height: 470px; overflow: auto; border: 1px solid var(--line); border-radius: 8px; }}
.note {{ color: var(--muted); font-size: 13px; line-height: 1.5; }}
.callout {{
  border: 1px solid #d9c99b;
  background: #fffaf0;
  padding: 14px;
  border-radius: 8px;
}}
.evidence-funnel {{
  display: grid;
  grid-template-columns: repeat(5, minmax(135px, 1fr));
  gap: 10px;
}}
.funnel-card {{
  position: relative;
  min-height: 134px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 13px;
  background: #fff;
  overflow: hidden;
}}
.funnel-card::before {{
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 5px;
  background: var(--blue);
}}
.funnel-card.rank::before {{ background: var(--gold); }}
.funnel-card.reach::before {{ background: var(--teal); }}
.funnel-card.oracle::before {{ background: #9aa4b2; }}
.funnel-rate {{
  font-size: 26px;
  font-weight: 800;
  line-height: 1;
  margin: 4px 0 9px;
  font-variant-numeric: tabular-nums;
}}
.funnel-name {{ font-weight: 760; font-size: 13px; margin-bottom: 6px; }}
.funnel-note {{ color: var(--muted); font-size: 12px; line-height: 1.45; }}
.bug-queue {{
  display: grid;
  grid-template-columns: repeat(2, minmax(260px, 1fr));
  gap: 10px;
  margin-top: 14px;
}}
.queue-card {{
  border: 1px solid var(--line);
  border-left: 5px solid var(--blue);
  border-radius: 8px;
  padding: 13px;
  background: #fff;
}}
.queue-card.hot {{ border-left-color: var(--rose); }}
.queue-card.warm {{ border-left-color: var(--gold); }}
.queue-card.cool {{ border-left-color: var(--teal); }}
.severity {{
  display: inline-flex;
  padding: 3px 7px;
  border-radius: 999px;
  background: #eef2f6;
  color: var(--muted);
  font-size: 11px;
  font-weight: 750;
  text-transform: uppercase;
  letter-spacing: 0;
}}
.queue-card h3 {{ margin-top: 8px; }}
.bad-example-grid {{
  display: grid;
  grid-template-columns: repeat(2, minmax(280px, 1fr));
  gap: 10px;
  margin-top: 12px;
}}
.bad-example-card {{
  border: 1px solid var(--line);
  border-left: 5px solid var(--rose);
  border-radius: 8px;
  padding: 13px;
  background: #fff;
}}
.bad-example-card.role {{ border-left-color: var(--rose); }}
.example-links {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0 4px;
}}
.example-links a {{
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 7px 10px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
  color: var(--blue);
  font-size: 13px;
  text-decoration: none;
}}
.example-links a.primary {{
  border-color: var(--blue);
  background: #f4f8ff;
  font-weight: 700;
}}
.recommendations {{ display: grid; grid-template-columns: repeat(5, minmax(180px, 1fr)); gap: 10px; }}
.rec {{ border-top: 5px solid var(--teal); }}
.rec:nth-child(2) {{ border-top-color: var(--blue); }}
.rec:nth-child(3) {{ border-top-color: var(--rose); }}
.rec:nth-child(4) {{ border-top-color: var(--gold); }}
.rec:nth-child(5) {{ border-top-color: var(--olive); }}
.examples {{ display: grid; gap: 10px; }}
.example {{
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px;
  background: #fff;
}}
.example-title {{ font-weight: 720; margin-bottom: 5px; }}
.example-grid {{ display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 8px; margin-top: 8px; }}
.tiny {{ font-size: 12px; color: var(--muted); }}
.hidden {{ display: none; }}
.anchor-alias {{
  display: block;
  position: relative;
  top: -88px;
  visibility: hidden;
}}
code {{
  background: #eef2f6;
  padding: 2px 4px;
  border-radius: 4px;
  overflow-wrap: anywhere;
  word-break: break-word;
}}
a {{ color: var(--blue); }}
@media (max-width: 950px) {{
  .summary, .grid2, .recommendations, .report-hub, .reader-path, .reviewer-note, .evidence-funnel, .bug-queue, .bad-example-grid, .report-grid.primary-map {{ grid-template-columns: 1fr; }}
  .section-head {{ display: block; }}
  .mini-actions {{ justify-content: flex-start; margin-top: 8px; }}
  .cards {{ grid-template-columns: repeat(2, minmax(130px, 1fr)); }}
  .bar-row {{ grid-template-columns: minmax(120px, 1fr); gap: 5px; }}
  .bar-val {{ text-align: left; }}
  .example-grid {{ grid-template-columns: repeat(2, minmax(120px, 1fr)); }}
}}
</style>
</head>
<body>
<header>
  <h1>Music CRS Recall Gap Explorer</h1>
  <p class="subhead">Interactive diagnosis of the <code>{html.escape(data["tid"])}</code> devset run. The framing follows the requested rule: if the ground-truth item is not in branch union@20 or union@100, that is a gap, even if it appears deeper in union@200 or union@1000.</p>
  <div class="meta">
    <span class="pill">Generated {html.escape(data["generated_at"])}</span>
    <span class="pill">8,000 devset turns</span>
    <span class="pill">branch_trace_topk=1000</span>
    <span class="pill">Current baseline fusion: RRF k=60</span>
  </div>
</header>
<nav class="top-nav" aria-label="Report navigation">
  <a class="primary" href="#overview">Overview</a>
  <a href="#report-map">Report map</a>
  <a href="#evidence-funnel">Work queue</a>
  <a href="#bad-examples">Bad examples</a>
  <a href="#state-work">State plan</a>
  <a href="#gap-map">Gap explorer</a>
  <a href="#evidence-notes">Sources</a>
</nav>
<main>
  <section id="overview" class="summary">
    <div class="panel">
      <h2>Executive Summary</h2>
      <div class="callout">
        <strong>Snapshot contract:</strong> This is a baseline report for <code>{html.escape(data["tid"])}</code> generated at <code>{html.escape(data["generated_at"])}</code>. The decisions are valid as experiment hypotheses and replay tests for this exact trace/config; after extractor, routing, retriever, ranker, catalog, or split changes, rerun the report and compare before treating old counts as current.
      </div>
      <ul class="takeaways">
        <li><strong>The largest opportunity is not a new retriever by itself.</strong> Final Hit@20 is 27.4%, but branch union@100 is 66.2%; the target design is a state-aware candidate scorer over the retrieved pool, not another tweak to the current equal-rank fusion baseline.</li>
        <li><strong>Union@20 and union@100 expose two different problems.</strong> Union@20 misses are often ranker/final-policy losses; union@100 misses are more often weak retrieval or latent target failures where the GT entity is absent from state.</li>
        <li><strong>State is useful, but some state is being used too bluntly.</strong> Same-artist demotion under <code>diversify_artists</code> and literal release-range handling bury many plausible GTs.</li>
        <li><strong>Retriever improvements should target latent targets.</strong> When no GT track or artist appears in state, union@100 collapses. Improve tag-popularity, similar-artist, lyric, visual, and hidden-target routes before adding broad embedding branches.</li>
        <li><strong>The scoring lens changed the priority queue.</strong> Codabench weights nDCG@20 at 0.50, LLM-Judge at 0.30, LexicalDiversity at 0.10, and CatalogDiversity at 0.10. Retrieval work still matters most, but <code>lm_type=dummy</code> leaves a large response lane untouched.</li>
      </ul>
    </div>
    <div class="panel">
      <h2>Ceiling Ladder</h2>
      <div id="ceilingCards" class="cards"></div>
      <p class="note">Read this as an experiment map: trained ranking attacks the union@20/100 ceiling; better retrievers attack the gap between union@100 and union@1000.</p>
    </div>
  </section>

  <span id="reviewer-packet" class="anchor-alias" aria-hidden="true"></span>
  <section id="report-map" class="panel">
    <div class="section-head">
      <div>
        <p class="eyebrow">Report map</p>
        <h2>Where To Go For Each Question</h2>
      </div>
    </div>
    <p class="note">Use this as the only cross-report map. The sticky nav above moves within this report; the cards below open deeper reports or review artifacts.</p>
    <div class="report-grid primary-map" aria-label="Primary report links">
      <a class="report-card current" href="#overview">
        <span>Read first</span>
        <strong>Main recall report</strong>
        <small>Headline metrics, work queue, global gap explorer, examples, and sources.</small>
        <small class="path">Stay on this page</small>
      </a>
      <a class="report-card primary" href="state_focus/index.html#examples">
        <span>Best for state bugs</span>
        <strong>State case studies</strong>
        <small>Truncated conversation, returned tracks, extracted state, why wrong, and ideal state.</small>
        <small class="path">state_focus/#examples</small>
      </a>
      <a class="report-card" href="state_focus/index.html#schema-audit">
        <span>Best for extractor work</span>
        <strong>Schema audit + replay packs</strong>
        <small>Field decisions, ideal state targets, field economy, and 10-turn small test packs.</small>
        <small class="path">state_focus/#schema-audit</small>
      </a>
      <a class="report-card" href="ranker_decision/index.html#examples-section">
        <span>Best for scorer work</span>
        <strong>Ranker / retriever misses</strong>
        <small>Concrete near misses, union gaps, and ranker/retriever decision evidence.</small>
        <small class="path">ranker_decision/#examples-section</small>
      </a>
    </div>
    <details class="artifact-drawer">
      <summary>Agent/JSON artifacts for review</summary>
      <div class="artifact-links" aria-label="Agent and JSON artifacts">
        <a href="state_focus/agent_report.html"><span>HTML review artifact</span>State agent report</a>
        <a href="ranker_decision/agent_report.html"><span>HTML review artifact</span>Ranker agent report</a>
        <a href="state_experiment_pack.json"><span>JSON replay artifact</span>State experiment pack</a>
        <a href="recall_gap_data.json"><span>JSON data artifact</span>Global report data</a>
        <a href="state_focus/state_report_data.json"><span>JSON data artifact</span>State report data</a>
        <a href="ranker_decision/report_data.json"><span>JSON data artifact</span>Ranker report data</a>
      </div>
    </details>
  </section>

  <section id="evidence-funnel" class="panel">
    <div class="section-head">
      <div>
        <p class="eyebrow">Evidence funnel</p>
        <h2>Find vs Ship, Then What To Work On</h2>
      </div>
    </div>
    <div class="evidence-funnel">{funnel_html}</div>
    <div class="callout" style="margin-top:14px">
      <strong>How to read this:</strong> union@20 is still the strict gap line; union@100 is the honest first-stage ranker ceiling for the current pool; union@1000 is useful as a retrieval-capability reference, not as the immediate target. Anything below union@100 needs state/routing/retriever work, not only a better final scorer.
    </div>
    <h2 style="margin-top:18px">Bugs And Missing Work To Incorporate</h2>
    <p class="note">This queue is intentionally colored by action type: red = fix or validate now, amber = high-value follow-up, teal = avoid over-investing first. It is the compact checklist to carry into the next extraction/ranker cycle.</p>
    <div class="bug-queue">{queue_html}</div>
  </section>

  <section id="bad-examples" class="panel">
    <div class="section-head">
      <div>
        <p class="eyebrow">Bad examples</p>
        <h2>Failures To Replay, With Why Wrong And What To Change</h2>
      </div>
    </div>
    <p class="note">Nothing was removed: the examples were present in the data, but too buried in tabs and expandable sections. This section surfaces the replay set from the global report and links to the deeper state/ranker example pages.</p>
    <div class="example-links" aria-label="Bad example links">
      <a class="primary" href="state_focus/index.html#examples">State failure examples</a>
      <a href="state_focus/index.html#schema-audit">State schema audit</a>
      <a href="state_experiment_pack.json">Full 110-turn replay JSON</a>
      <a href="ranker_decision/index.html#examples-section">Ranker / retriever misses</a>
      <a href="#gap-map">Gap explorer</a>
    </div>
    <h3>State role bugs visible on this page</h3>
    <p class="note">These are the hand-auditable extraction failures: the state kept an old or contrast entity as a positive retrieval anchor. The fix is not just “more state”; it is role-typed, recency-aware state.</p>
    <div class="bad-example-grid">{role_examples_html}</div>
    <h3 style="margin-top:18px">One replay turn per failure class</h3>
    <p class="note">The state experiment pack contains 10 turns per failure class plus positive controls. This visible table shows one representative row for each class so the report can be skimmed before running small API-call experiments.</p>
    {failure_turns_html}
    <h3 style="margin-top:18px">Positive controls to protect</h3>
    <p class="note">These should stay good after extractor changes; use them as regression checks so a role/state rewrite does not break exact-entity and clean final-hit behavior.</p>
    {positive_turns_html}
    <h3 style="margin-top:18px">Ranker and retrieval misses</h3>
    <p class="note">These examples separate final scorer losses from candidate-generation failures. The current fusion method is only baseline instrumentation here; the ideal target is state-aware retrieval profiles plus a trained or calibrated candidate scorer.</p>
    {ranker_examples_html}
  </section>

{state_work_html}

  <span id="gap-explorer" class="anchor-alias" aria-hidden="true"></span>
  <section id="gap-map" class="panel">
    <h2>Gap Map: Candidate Pool vs Final Ranking</h2>
    <p class="note">This section uses the current run's fusion/ranking trace to classify failures. Treat the current fusion method as baseline instrumentation; the target system is state-aware retrieval profiles plus a trained or calibrated candidate scorer.</p>
    <div class="tabs">
      <button class="active" data-tab="gap">Gap buckets</button>
      <button data-tab="mechanism">Mechanisms</button>
      <button data-tab="branches">Branches</button>
      <button data-tab="dimensions">State slices</button>
      <button data-tab="examples">Examples</button>
      <button data-tab="actions">What to improve</button>
    </div>

    <div id="tab-gap" class="tab-body">
      <div class="grid2">
        <div>
          <h3>Bucketed by union@20/100</h3>
          <div id="gapChart" class="chart"></div>
        </div>
        <div class="callout">
          <h3>How to read it</h3>
          <p>Items in <code>union20_* </code> are already available to a final candidate scorer. Items in <code>union100_near_miss</code> are close enough that query cleanup, retrieval-profile routing, or a trained ranker may recover them. Items beyond union@100 need stronger retrieval or better state-targeting.</p>
          <div id="rankBuckets"></div>
        </div>
      </div>
    </div>

    <div id="tab-mechanism" class="tab-body hidden">
      <div class="grid2">
        <div>
          <h3>Mechanism buckets</h3>
          <div id="mechanismChart" class="chart"></div>
        </div>
        <div>
          <h3>Post-fusion demotion clues</h3>
          <div id="postFusionChart" class="chart"></div>
          <p class="note">The same-artist pattern points to <code>ANCHOR_ARTIST_DEMOTE_BY_POLICY</code> under <code>diversify_artists</code>.</p>
        </div>
      </div>
    </div>

    <div id="tab-branches" class="tab-body hidden">
      <div class="grid2">
        <div>
          <h3>Per-branch recall when branch fires</h3>
          <div class="table-wrap"><table id="branchTable"></table></div>
        </div>
        <div>
          <h3>Best branch for current focus bucket</h3>
          <div class="controls" id="branchFocusControls"></div>
          <div id="bestBranchChart" class="chart"></div>
        </div>
      </div>
    </div>

    <div id="tab-dimensions" class="tab-body hidden">
      <div class="controls" id="dimensionControls"></div>
      <div class="controls">
        <button class="active" data-rate="union20_gap_rate">Union@20 gap</button>
        <button data-rate="union100_gap_rate">Union@100 gap</button>
        <button data-rate="final_hit20_rate">Final Hit@20</button>
        <button data-rate="union100_rate">Union@100 coverage</button>
      </div>
      <div class="grid2">
        <div>
          <h3 id="dimensionTitle">Dimension</h3>
          <div id="dimensionChart" class="chart"></div>
        </div>
        <div>
          <h3>Detail table</h3>
          <div class="table-wrap"><table id="dimensionTable"></table></div>
        </div>
      </div>
    </div>

    <div id="tab-examples" class="tab-body hidden">
      <div class="controls" id="exampleControls"></div>
      <div id="examplesPanel" class="examples"></div>
    </div>

    <div id="tab-actions" class="tab-body hidden">
      <div class="recommendations" id="recommendations"></div>
      <div class="panel" style="margin-top:14px">
        <h3>Trained ranker recipe</h3>
        <p><strong>Candidate pool:</strong> start with union@200 for training and compare union@100 / union@1000 serving costs. <strong>Label:</strong> single GT track per turn. <strong>Model:</strong> logistic scorer or LambdaMART before cross-encoder complexity. <strong>Features:</strong> min branch rank, per-branch ranks, number of branches hitting top-20/top-100, trusted branch hit, resolved artist/track match, same-artist-as-accepted/rejected, positive and negative tag overlap, release-year in range or distance, popularity bucket, turn number, intent mode, exploration policy, and routing tags.</p>
        <p class="note">The report's ceiling ladder is the reason to try this: a good scorer over union@100 has a 66.2% top-20 ceiling before any new retriever work.</p>
      </div>
    </div>
  </section>

  <section id="evidence-notes" class="panel">
    <h2>Evidence Notes</h2>
    <p class="note"><strong>Scope:</strong> {html.escape(data["snapshot_contract"]["status"])} {html.escape(data["snapshot_contract"]["valid_until"])} {html.escape(data["snapshot_contract"]["how_to_use"])}</p>
    <p class="note">Sources: <code>{html.escape(data["paths"]["trace"])}</code>, <code>{html.escape(data["paths"]["predictions"])}</code>, <code>{html.escape(data["paths"]["ground_truth"])}</code>, <code>{html.escape(data["paths"]["config"])}</code>. The report streams the trace and uses LanceDB catalog metadata only for lightweight GT labels, artist matching, tags, release years, and popularity buckets.</p>
  </section>
</main>
<script id="report-data" type="application/json">{safe_payload}</script>
<script>
const DATA = JSON.parse(document.getElementById('report-data').textContent);
const fmtPct = x => `${{(x * 100).toFixed(1)}}%`;
const fmtRatePct = x => `${{(x * 100).toFixed(1)}}%`;
const pctFromRow = x => `${{Number(x).toFixed(1)}}%`;
const nice = s => String(s).replaceAll('_', ' ').replaceAll('::', ': ');
const colorClasses = ['blue', 'teal', 'gold', 'rose', 'olive'];

function makeBarChart(el, rows, opts={{}}) {{
  const valueField = opts.valueField || 'pct';
  const labelField = opts.labelField || 'name';
  const suffix = opts.suffix || '%';
  const maxValue = opts.maxValue ?? Math.max(...rows.map(r => Number(r[valueField]) || 0), 1);
  el.innerHTML = rows.map((r, i) => {{
    const v = Number(r[valueField]) || 0;
    const width = Math.max(1, (v / maxValue) * 100);
    const cls = colorClasses[i % colorClasses.length];
    const shown = suffix === '%' ? `${{v.toFixed(1)}}%` : String(v);
    const sub = r.n !== undefined ? ` <span class="tiny">n=${{r.n}}</span>` : '';
    return `<div class="bar-row">
      <div class="bar-label">${{nice(r[labelField])}}${{sub}}</div>
      <div class="bar-track"><div class="bar-fill ${{cls}}" style="width:${{width}}%"></div></div>
      <div class="bar-val">${{shown}}</div>
    </div>`;
  }}).join('');
}}

function renderCards() {{
  const el = document.getElementById('ceilingCards');
  el.innerHTML = DATA.ceilings.map(c => `<div class="card">
    <div class="metric">${{fmtRatePct(c.rate)}}</div>
    <div class="label">${{c.name}}<br>(${{c.count}} turns)</div>
  </div>`).join('');
}}

function renderRankBuckets() {{
  const rows = DATA.rank_buckets.branch;
  document.getElementById('rankBuckets').innerHTML = `<h3>Best branch rank distribution</h3>
    <div class="chart">${{rows.map((r, i) => `<div class="bar-row">
      <div class="bar-label">${{r.name}} <span class="tiny">n=${{r.n}}</span></div>
      <div class="bar-track"><div class="bar-fill ${{colorClasses[i % colorClasses.length]}}" style="width:${{r.pct}}%"></div></div>
      <div class="bar-val">${{pctFromRow(r.pct)}}</div>
    </div>`).join('')}}</div>`;
}}

function renderBranches() {{
  const rows = [...DATA.branches].sort((a,b) => b['recall@100'] - a['recall@100']);
  const table = document.getElementById('branchTable');
  table.innerHTML = `<thead><tr><th>Branch</th><th>Fired</th><th>r@20</th><th>r@100</th><th>r@200</th><th>r@1000</th></tr></thead><tbody>` +
    rows.map(r => `<tr><td>${{r.name}}</td><td>${{r.fired}}</td><td>${{fmtRatePct(r['recall@20'])}}</td><td>${{fmtRatePct(r['recall@100'])}}</td><td>${{fmtRatePct(r['recall@200'])}}</td><td>${{fmtRatePct(r['recall@1000'])}}</td></tr>`).join('') +
    `</tbody>`;
  const focusKeys = Object.keys(DATA.best_branch_by_gap);
  const controls = document.getElementById('branchFocusControls');
  controls.innerHTML = focusKeys.map((k,i) => `<button class="${{i===0?'active':''}}" data-branch-focus="${{k}}">${{nice(k)}}</button>`).join('');
  controls.querySelectorAll('button').forEach(btn => btn.addEventListener('click', () => {{
    controls.querySelectorAll('button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderBestBranch(btn.dataset.branchFocus);
  }}));
  renderBestBranch(focusKeys[0]);
}}

function renderBestBranch(key) {{
  makeBarChart(document.getElementById('bestBranchChart'), DATA.best_branch_by_gap[key] || [], {{maxValue: 100}});
}}

const dimensions = [
  ['entity_bucket', 'State entity bucket'],
  ['exploration_policy', 'Exploration policy'],
  ['intent_mode', 'Intent mode'],
  ['turn_number', 'Turn number'],
  ['tag_overlap', 'Positive-tag overlap'],
  ['release_bucket', 'Release range status'],
  ['routing_combo', 'Routing combo'],
  ['routing_true_tag', 'Routing tags'],
  ['popularity_bucket', 'GT popularity bucket'],
];
let currentDimension = 'entity_bucket';
let currentRate = 'union100_gap_rate';

function renderDimensionControls() {{
  const el = document.getElementById('dimensionControls');
  el.innerHTML = dimensions.map(([key, label], i) => `<button class="${{i===0?'active':''}}" data-dim="${{key}}">${{label}}</button>`).join('');
  el.querySelectorAll('button').forEach(btn => btn.addEventListener('click', () => {{
    el.querySelectorAll('button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentDimension = btn.dataset.dim;
    renderDimension();
  }}));
  document.querySelectorAll('[data-rate]').forEach(btn => btn.addEventListener('click', () => {{
    document.querySelectorAll('[data-rate]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentRate = btn.dataset.rate;
    renderDimension();
  }}));
}}

function renderDimension() {{
  const title = dimensions.find(d => d[0] === currentDimension)?.[1] || currentDimension;
  document.getElementById('dimensionTitle').textContent = `${{title}} - ${{nice(currentRate)}}`;
  const rows = [...(DATA.dimensions[currentDimension] || [])].sort((a,b) => b[currentRate] - a[currentRate]).slice(0, 16);
  makeBarChart(document.getElementById('dimensionChart'), rows.map(r => Object.assign({{}}, r, {{value: r[currentRate] * 100}})), {{valueField:'value', maxValue: 100}});
  const table = document.getElementById('dimensionTable');
  table.innerHTML = `<thead><tr><th>Segment</th><th>n</th><th>Final@20</th><th>Union@20</th><th>Union@100</th><th>Union@100 gap</th></tr></thead><tbody>` +
    rows.map(r => `<tr><td>${{nice(r.name)}}</td><td>${{r.n}}</td><td>${{fmtRatePct(r.final_hit20_rate)}}</td><td>${{fmtRatePct(r.union20_rate)}}</td><td>${{fmtRatePct(r.union100_rate)}}</td><td>${{fmtRatePct(r.union100_gap_rate)}}</td></tr>`).join('') +
    `</tbody>`;
}}

function renderExamplesControls() {{
  const keys = ['union20_fusion_loss','union20_postfusion_or_final_loss','union100_near_miss','union200_deep_miss','union1000_deep_miss','not_in_any_branch_top1000'];
  const controls = document.getElementById('exampleControls');
  controls.innerHTML = keys.map((k,i) => `<button class="${{i===0?'active':''}}" data-example="${{k}}">${{nice(k)}}</button>`).join('');
  controls.querySelectorAll('button').forEach(btn => btn.addEventListener('click', () => {{
    controls.querySelectorAll('button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderExamples(btn.dataset.example);
  }}));
  renderExamples(keys[0]);
}}

function renderExamples(key) {{
  const rows = DATA.examples[key] || [];
  document.getElementById('examplesPanel').innerHTML = rows.map(e => `<div class="example">
    <div class="example-title">${{e.gt_track}} - ${{e.gt_artist}}</div>
    <div class="tiny">session ${{e.session_id}}, turn ${{e.turn}}</div>
    <p>${{e.intent || '(no intent text)'}}</p>
    <div class="example-grid">
      <div><div class="tiny">Final rank</div><strong>${{e.final_rank ?? '-'}}</strong></div>
      <div><div class="tiny">Fused rank</div><strong>${{e.fused_rank ?? '-'}}</strong></div>
      <div><div class="tiny">Best branch rank</div><strong>${{e.min_branch_rank ?? '-'}}</strong></div>
      <div><div class="tiny">Best branch</div><strong>${{e.best_branch}}</strong></div>
      <div><div class="tiny">State</div>${{nice(e.entity_bucket)}}</div>
      <div><div class="tiny">Policy</div>${{e.policy}}</div>
      <div><div class="tiny">Routing</div>${{(e.routing || []).join(', ') || '-'}}</div>
      <div><div class="tiny">GT tags hit</div>${{(e.gt_tag_overlap || []).join(', ') || '-'}}</div>
    </div>
  </div>`).join('');
}}

function renderRecommendations() {{
  document.getElementById('recommendations').innerHTML = DATA.recommendations.map(r => `<div class="card rec">
    <h3>${{r.theme}}</h3>
    <p>${{r.why}}</p>
    <p class="note"><strong>First experiment:</strong> ${{r.first_experiment}}</p>
  </div>`).join('');
}}

function initTabs() {{
  document.querySelectorAll('[data-tab]').forEach(btn => btn.addEventListener('click', () => {{
    document.querySelectorAll('[data-tab]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.tab-body').forEach(el => el.classList.add('hidden'));
    document.getElementById(`tab-${{btn.dataset.tab}}`).classList.remove('hidden');
  }}));
}}

function init() {{
  renderCards();
  renderRankBuckets();
  makeBarChart(document.getElementById('gapChart'), DATA.gap_buckets, {{maxValue: 100}});
  makeBarChart(document.getElementById('mechanismChart'), DATA.mechanism_buckets, {{maxValue: 100}});
  makeBarChart(document.getElementById('postFusionChart'), DATA.postfusion_summary.slice(0, 12), {{maxValue: 100}});
  renderBranches();
  renderDimensionControls();
  renderDimension();
  renderExamplesControls();
  renderRecommendations();
  initTabs();
}}
init();
</script>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--tid", default=DEFAULT_TID)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06"),
    )
    args = parser.parse_args()

    data = analyze(args.source_root, args.tid)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    state_companion = load_state_companion(args.out_dir)
    if state_companion.get("available"):
        pack_path = args.out_dir / "state_experiment_pack.json"
        experiment_turns = state_companion.get("experiment_turns") or []
        sample_ids = [str(row.get("sample_id")) for row in experiment_turns]
        class_counts = Counter(str(row.get("class_type") or "unknown") for row in experiment_turns)
        pack_payload = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source_state_report": state_companion.get("path"),
            "summary": {
                "total_turns": len(experiment_turns),
                "unique_turns": len(set(sample_ids)),
                "packs": len(state_companion.get("experiment_packs") or []),
                "class_counts": dict(class_counts),
            },
            "ideal_state_targets": state_companion.get("ideal_state_targets") or [],
            "state_confusion_plan": state_companion.get("state_confusion_plan") or [],
            "metadata_decision_plan": state_companion.get("metadata_decision_plan") or [],
            "blindset_metadata_availability": state_companion.get("blindset_metadata_availability") or {},
            "packs": state_companion.get("experiment_packs") or [],
            "turns": experiment_turns,
        }
        pack_path.write_text(json.dumps(pack_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        state_companion["experiment_pack_file"] = pack_path.name
    markdown_pages = [
        (args.out_dir / "state_focus" / "agent_report.md", "State Agent Report"),
        (args.out_dir / "ranker_decision" / "agent_report.md", "Ranker Agent Report"),
    ]
    for markdown_path, title in markdown_pages:
        review_page = write_markdown_review_page(markdown_path, title)
        if review_page:
            print(f"wrote {review_page}")
    data["state_companion"] = state_companion
    data_path = args.out_dir / "recall_gap_data.json"
    report_path = args.out_dir / "index.html"
    data_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.write_text(render_report(data), encoding="utf-8")
    print(f"wrote {data_path}")
    print(f"wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
