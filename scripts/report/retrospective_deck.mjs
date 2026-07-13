#!/usr/bin/env node
import { readFile, rename, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

const slide = (slug, title, blocks) => ({ slug, title, blocks });

export const CHAPTERS = [
  {
    slug: "outcome",
    title: "Outcome & score",
    question: "What happened, and which metric terms made the gap?",
    slides: [
      slide("summary", "Executive answer", ["title", "executive_summary", "headline_metrics", "section_directory"]),
      slide("official-result", "Official result", ["how_scoring_works", "final_result_heading", "leaderboard_chart", "leaderboard_table"]),
      slide("gap", "Gap decomposition", ["gap_contribution_chart", "gap_interpretation"]),
    ],
  },
  {
    slug: "query",
    title: "Conversation → query",
    question: "How did each system turn dialogue into retriever inputs?",
    slides: [
      slide("lifecycle", "Shared lifecycle", ["lifecycle_heading", "lifecycle_map", "lifecycle_takeaway"]),
      slide("comparison", "Query comparison", ["query_heading", "query_explainer", "query_matrix"]),
      slide("data-knowledge", "Data and model knowledge", ["data_knowledge_heading", "data_knowledge_glossary", "data_knowledge_matrix", "data_knowledge_interpretation"]),
      slide("prompt-audit", "Prompt and file audit", ["query_evidence_details"]),
    ],
  },
  {
    slug: "retrieval",
    title: "Retrieval & ranking",
    question: "What candidates and features could the rankers actually see?",
    slides: [
      slide("retrievers", "Retriever inputs and constraints", ["retrieval_heading", "retrieval_glossary", "retrieval_matrix"]),
      slide("features", "Feature families and validation lineage", ["features_heading", "feature_glossary", "feature_matrix"]),
      slide("feature-audit", "Complete feature inventories", ["feature_details"]),
    ],
  },
  {
    slug: "response",
    title: "Response generation",
    question: "How did a selected track become grounded, checked prose?",
    slides: [
      slide("overview", "Response subsystem overview", ["response_heading", "response_explainer"]),
      slide("matrix", "Five-team response matrix", ["response_matrix"]),
      slide("pipelines", "Generation, selection, and repair pipelines", ["response_walkthroughs"]),
      slide("tradeoffs", "Trade-offs and source boundary", ["response_tradeoffs"]),
    ],
  },
  {
    slug: "ours",
    title: "Our submission",
    question: "What did we build, what worked, and where did confidence fail?",
    slides: [
      slide("system", "System diagram", ["own_system_heading", "own_system_diagram"]),
      slide("walkthrough", "Complete walkthrough", ["own_system_walkthrough"]),
      slide("strengths", "What worked", ["what_worked"]),
      slide("evaluation-mistake", "Evaluation mistake", ["evaluation_mistake"]),
      slide("contributors", "Best-supported contributors", ["ranking_contributors", "response_contributors"]),
    ],
  },
  {
    slug: "leaders",
    title: "Leading teams",
    question: "What did the leading public systems document differently?",
    slides: [
      slide("index", "Case-study index", ["competitor_case_studies_heading"]),
      slide("volart", "volart", ["volart_heading", "volart_outcome", "volart_diagram", "volart_walkthrough", "volart_comparison", "volart_limits"]),
      slide("niwatori", "niwatori", ["niwatori_heading", "niwatori_outcome", "niwatori_diagram", "niwatori_walkthrough", "niwatori_comparison", "niwatori_limits"]),
      slide("swyoo", "swyoo", ["swyoo_heading", "swyoo_outcome", "swyoo_diagram", "swyoo_walkthrough", "swyoo_comparison", "swyoo_limits"]),
      slide("team2", "team2_s2", ["team2_s2_heading", "team2_s2_outcome", "team2_s2_diagram", "team2_s2_walkthrough", "team2_s2_comparison", "team2_s2_limits"]),
    ],
  },
  {
    slug: "synthesis",
    title: "Synthesis & evidence",
    question: "What should the team preserve, reconsider, avoid, and credit?",
    slides: [
      slide("cross-team", "Cross-team synthesis", ["cross_team_heading", "cross_team_matrix"]),
      slide("choices", "Retrospective choices", ["preserve_reconsider_avoid", "retrospective_choices_table"]),
      slide("lessons", "Transferable lessons", ["future_competition_lessons"]),
      slide("acknowledgements", "Acknowledgements", ["acknowledgements_heading", "acknowledgements"]),
      slide("caveats-evidence", "Caveats and complete evidence", ["caveats", "evidence_notes"]),
    ],
  },
];

export const DISCLOSURES = {
  section_directory: "Open the original chapter outline",
  how_scoring_works: "Open the composite-score formula",
  leaderboard_table: "Open the exact leaderboard table",
  query_matrix: "Open the complete five-team query matrix",
  query_evidence_details: "Open prompt excerpts and the reviewed file inventory",
  data_knowledge_matrix: "Open the complete data and model-knowledge matrix",
  retrieval_matrix: "Open the complete retrieval matrix",
  feature_matrix: "Open the complete feature-family matrix",
  feature_details: "Open the per-team feature inventories",
  response_matrix: "Open the complete response-generation matrix",
  own_system_walkthrough: "Open the complete submitted-system walkthrough",
  evidence_notes: "Open the complete evidence notes",
};

const STYLE_START = "<!-- retrospective-deck-style:start -->";
const STYLE_END = "<!-- retrospective-deck-style:end -->";
const SCRIPT_START = "<!-- retrospective-deck-script:start -->";
const SCRIPT_END = "<!-- retrospective-deck-script:end -->";

const removeRange = (html, start, end) => {
  const pattern = new RegExp(`${start.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}[\\s\\S]*?${end.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\n?`, "g");
  return html.replace(pattern, "");
};

export function stripDeckInjection(html) {
  return removeRange(removeRange(html, STYLE_START, STYLE_END), SCRIPT_START, SCRIPT_END);
}

export function validateChapterMap(chapters, html) {
  const mappedIds = chapters.flatMap((chapter) => chapter.slides.flatMap((entry) => entry.blocks));
  const seen = new Set();
  for (const id of mappedIds) {
    if (seen.has(id)) throw new Error(`duplicate configured block: ${id}`);
    seen.add(id);
  }
  const renderedIds = [...html.matchAll(/data-artifact-block-id="([^"]+)"/g)].map((match) => match[1]);
  const renderedSet = new Set(renderedIds);
  if (renderedIds.length !== renderedSet.size) throw new Error("duplicate report block ID");
  if (renderedSet.has("title")) throw new Error("title must be represented by the portable page header");
  if (!html.includes('class="portable-page-header"')) throw new Error("missing portable page header for title block");
  const reportIds = ["title", ...renderedIds];
  const reportSet = new Set(reportIds);
  for (const id of mappedIds) if (!reportSet.has(id)) throw new Error(`missing configured block: ${id}`);
  for (const id of reportIds) if (!seen.has(id)) throw new Error(`unassigned report block: ${id}`);
  if (!html.includes('class="portable-block-stack"')) throw new Error("missing portable block stack");
  if (!html.includes('class="portable-sources"')) throw new Error("missing portable source list");
  if (!html.includes('id="data-analytics-portable-artifact-payload-source"')) throw new Error("missing artifact payload template");
  const slugs = new Set();
  for (const chapter of chapters) for (const entry of chapter.slides) {
    const slug = `${chapter.slug}/${entry.slug}`;
    if (slugs.has(slug)) throw new Error(`duplicate slide slug: ${slug}`);
    slugs.add(slug);
  }
  return { mappedIds, reportIds, slugs: [...slugs] };
}

export const DECK_STYLE = `
#data-analytics-portable-reader{display:none!important}
#data-analytics-portable-fallback{display:block!important;visibility:visible!important;position:relative!important}
`;

function runtimeMain(CONFIG) {
  window.__RETROSPECTIVE_DECK_CONFIG__ = CONFIG;
}

export const DECK_RUNTIME = `(${runtimeMain.toString()})(__CONFIG__);`;

export function enhanceHtml(input) {
  const html = stripDeckInjection(input);
  validateChapterMap(CHAPTERS, html);
  const config = JSON.stringify({ chapters: CHAPTERS, disclosures: DISCLOSURES }).replaceAll("<", "\\u003c");
  const style = `${STYLE_START}\n<style data-retrospective-deck-style>${DECK_STYLE}</style>\n${STYLE_END}`;
  const runtime = DECK_RUNTIME.replace("__CONFIG__", config);
  const script = `${SCRIPT_START}\n<script data-retrospective-deck-script>${runtime}</script>\n${SCRIPT_END}`;
  if (!html.includes("</head>") || !html.includes("</body>")) throw new Error("portable report is missing head/body terminators");
  return html.replace("</head>", `${style}\n</head>`).replace("</body>", `${script}\n</body>`);
}

function parseArgs(argv) {
  const args = { input: "", output: "", check: "" };
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (key === "--input" || key === "--output" || key === "--check") args[key.slice(2)] = argv[++index] ?? "";
    else throw new Error(`unknown argument: ${key}`);
  }
  if (args.check) return args;
  if (!args.input || !args.output) throw new Error("usage: retrospective_deck.mjs --input PATH --output PATH | --check PATH");
  return args;
}

async function main(argv) {
  const args = parseArgs(argv);
  const inputPath = args.check || args.input;
  const source = await readFile(inputPath, "utf8");
  const enhanced = enhanceHtml(source);
  if (args.check) {
    process.stdout.write(`PASS: ${validateChapterMap(CHAPTERS, stripDeckInjection(source)).reportIds.length} blocks mapped into ${CHAPTERS.length} chapters\n`);
    return;
  }
  const temp = `${args.output}.tmp-${process.pid}`;
  await writeFile(temp, enhanced, "utf8");
  await rename(temp, args.output);
  process.stdout.write(`wrote ${args.output}\n`);
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  main(process.argv.slice(2)).catch((error) => {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  });
}
