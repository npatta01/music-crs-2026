#!/usr/bin/env node
import { readFile, rename, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

const slide = (slug, title, archetype, blocks, options = {}) => ({ slug, title, archetype, blocks, ...options });

export const PAGE_ARCHETYPES = new Set(["cover", "story", "visual", "matrix", "audit"]);


export const CHAPTERS = [
  {
    slug: "outcome",
    title: "Outcome & score",
    question: "What happened, and which metric terms made the gap?",
    slides: [
      slide("cover", "Outcome & score", "cover", []),
      slide("executive-answer", "Executive answer", "story", ["title", "executive_summary", "headline_metrics", "section_directory"]),
      slide("leaderboard-chart", "How the result was scored", "visual", ["how_scoring_works", "final_result_heading", "leaderboard_chart"]),
      slide("leaderboard-table", "Exact leaderboard", "matrix", ["leaderboard_table"]),
      slide("gap-chart", "Gap decomposition", "visual", ["gap_contribution_chart"]),
      slide("gap-interpretation", "What the score gap does—and does not—show", "story", ["gap_interpretation"]),
    ],
  },
  {
    slug: "query",
    title: "Conversation → query",
    question: "How did each system turn dialogue into retriever inputs?",
    slides: [
      slide("cover", "Conversation → query", "cover", []),
      slide("lifecycle", "Shared query lifecycle", "visual", ["lifecycle_heading", "lifecycle_map", "lifecycle_takeaway"], { lanes: [{ label: "Common lifecycle", steps: ["Conversation", "Interpretation or state", "Query variants", "Candidate sources", "Ranking or fusion", "Selected track IDs", "Response pipeline"] }] }),
      slide("query-glossary", "What counts as a query representation?", "story", ["query_heading", "query_explainer"]),
      slide("query-matrix", "Five-team query matrix", "matrix", ["query_matrix"]),
      slide("data-glossary", "Where system knowledge came from", "story", ["data_knowledge_heading", "data_knowledge_glossary"]),
      slide("data-matrix", "Data and model-knowledge matrix", "matrix", ["data_knowledge_matrix", "data_knowledge_interpretation"]),
      slide("prompt-audit", "Prompt and file audit", "audit", ["query_evidence_details"]),
    ],
  },
  {
    slug: "retrieval",
    title: "Retrieval & ranking",
    question: "What candidates and features could the rankers actually see?",
    slides: [
      slide("cover", "Retrieval & ranking", "cover", []),
      slide("retriever-matrix", "Retriever inputs and constraints", "matrix", ["retrieval_heading", "retrieval_glossary", "retrieval_matrix"], { lanes: [{ label: "Ranking boundary", steps: ["Conversation-derived queries", "Multiple candidate sources", "Candidate union or fusion", "Feature computation", "Ranker or rule-based ordering", "Top track IDs"] }] }),
      slide("feature-glossary", "Feature-family glossary", "story", ["features_heading", "feature_glossary"]),
      slide("feature-matrix", "Feature families and validation lineage", "matrix", ["feature_matrix"]),
      slide("feature-inventories", "Complete feature inventories", "audit", ["feature_details"]),
    ],
  },
  {
    slug: "response",
    title: "Response generation",
    question: "How did a selected track become grounded, checked prose?",
    slides: [
      slide("cover", "Response generation", "cover", []),
      slide("overview", "Response subsystem overview", "visual", ["response_heading", "response_explainer"], { lanes: [{ label: "Response quality path", steps: ["Selected track ID", "Track facts and dialogue context", "One or more response candidates", "Verification, critique, or repair", "Final response"] }] }),
      slide("matrix", "Five-team response matrix", "matrix", ["response_matrix"]),
      slide("author-volart", "Author and volart paths", "visual", [], { lanes: [
        { label: "Our submitted path", steps: ["Latest state and selected track metadata", "Single LLM pass", "One top-1 response"] },
        { label: "volart", steps: ["Selected track ID held fixed", "Generate response candidates", "Independent quality critic", "Selective rewrite and hardening", "Lexical-diversity pass"] },
      ] }),
      slide("niwatori-swyoo", "niwatori and swyoo paths", "visual", [], { lanes: [
        { label: "niwatori", steps: ["Selected track and conversation", "Ten seeded response candidates", "Candidate selector", "Final response"] },
        { label: "swyoo", steps: ["Selected track and response theme", "Generate candidates", "Validate themes and citations", "Repair unsupported content", "Final response"] },
      ] }),
      slide("team2", "team2_s2 path", "visual", [], { lanes: [
        { label: "team2_s2", steps: ["Selected track", "Verified track-fact bundle", "First-pass Gemini response", "Gemini Pro refinement", "Polished final response"] },
      ] }),
      slide("tradeoffs", "Generation, selection, repair, and trade-offs", "audit", ["response_walkthroughs", "response_tradeoffs"]),
    ],
  },
  {
    slug: "ours",
    title: "Our submission",
    question: "What did we build, what worked, and where did confidence fail?",
    slides: [
      slide("cover", "Our submission", "cover", ["own_system_heading"]),
      slide("offline-rail", "Offline evidence rail", "visual", ["own_system_diagram"]),
      slide("inference-rail", "Inference rail", "visual", [], { lanes: [
        { label: "Deployed Blind-B path", steps: ["DeepSeek state extraction", "BM25, multimodal ANN, and lookup branches", "RRF candidate pool to top 500", "LightGBM feature scoring", "Top-1 selected track", "Single-pass response"] },
      ] }),
      slide("walkthrough", "Complete walkthrough and ranking handoff", "audit", ["own_system_walkthrough"]),
      slide("what-worked", "What worked", "story", ["what_worked"]),
      slide("evaluation-mistake", "Evaluation mistake and confidence boundary", "story", ["evaluation_mistake"]),
      slide("contributors", "Ranking and response contributors", "story", ["ranking_contributors", "response_contributors"]),
    ],
  },
  {
    slug: "leaders",
    title: "Leading teams",
    question: "What did the leading public systems document differently?",
    slides: [
      slide("cover", "Leading teams", "cover", ["competitor_case_studies_heading"]),
      slide("volart-outcome", "volart · outcome, query, and data", "story", ["volart_heading", "volart_outcome"]),
      slide("volart-retrieval", "volart · retrieval and ranking", "visual", ["volart_diagram"]),
      slide("volart-response", "volart · response, comparison, and limits", "audit", ["volart_walkthrough", "volart_comparison", "volart_limits"]),
      slide("niwatori-outcome", "niwatori · outcome, query, and data", "story", ["niwatori_heading", "niwatori_outcome"]),
      slide("niwatori-retrieval", "niwatori · retrieval and ranking", "visual", ["niwatori_diagram"]),
      slide("niwatori-response", "niwatori · response, comparison, and limits", "audit", ["niwatori_walkthrough", "niwatori_comparison", "niwatori_limits"]),
      slide("swyoo-outcome", "swyoo · outcome, query, and data", "story", ["swyoo_heading", "swyoo_outcome"]),
      slide("swyoo-retrieval", "swyoo · retrieval and ranking", "visual", ["swyoo_diagram"]),
      slide("swyoo-response", "swyoo · response, comparison, and limits", "audit", ["swyoo_walkthrough", "swyoo_comparison", "swyoo_limits"]),
      slide("team2-outcome", "team2_s2 · outcome, query, and data", "story", ["team2_s2_heading", "team2_s2_outcome"]),
      slide("team2-retrieval", "team2_s2 · retrieval and ranking", "visual", ["team2_s2_diagram"]),
      slide("team2-response", "team2_s2 · response, comparison, and limits", "audit", ["team2_s2_walkthrough", "team2_s2_comparison", "team2_s2_limits"]),
    ],
  },
  {
    slug: "synthesis",
    title: "Synthesis & evidence",
    question: "What should the team preserve, reconsider, avoid, and credit?",
    slides: [
      slide("cover", "Synthesis & evidence", "cover", ["cross_team_heading"]),
      slide("matrix", "Cross-team synthesis", "matrix", ["cross_team_matrix"]),
      slide("choices", "Preserve, reconsider, and avoid", "story", ["preserve_reconsider_avoid", "retrospective_choices_table"]),
      slide("lessons", "Transferable lessons and acknowledgements", "story", ["future_competition_lessons", "acknowledgements_heading", "acknowledgements"]),
      slide("evidence", "Caveats and complete evidence", "audit", ["caveats", "evidence_notes"]),
    ],
  },
];

export const LEGACY_ALIASES = new Map([
  ["outcome/summary", "outcome/cover"], ["outcome/official-result", "outcome/leaderboard-chart"], ["outcome/gap", "outcome/gap-chart"],
  ["query/comparison", "query/query-matrix"], ["query/data-knowledge", "query/data-matrix"],
  ["retrieval/retrievers", "retrieval/retriever-matrix"], ["retrieval/features", "retrieval/feature-glossary"], ["retrieval/feature-audit", "retrieval/feature-inventories"],
  ["response/pipelines", "response/author-volart"],
  ["ours/system", "ours/cover"], ["ours/strengths", "ours/what-worked"],
  ["leaders/index", "leaders/cover"], ["leaders/volart", "leaders/volart-outcome"], ["leaders/niwatori", "leaders/niwatori-outcome"], ["leaders/swyoo", "leaders/swyoo-outcome"], ["leaders/team2", "leaders/team2-outcome"],
  ["synthesis/cross-team", "synthesis/cover"], ["synthesis/acknowledgements", "synthesis/lessons"], ["synthesis/caveats-evidence", "synthesis/evidence"],
  ["response/matrix", "response/matrix"], ["response/overview", "response/overview"], ["response/tradeoffs", "response/tradeoffs"], ["query/prompt-audit", "query/prompt-audit"], ["ours/walkthrough", "ours/walkthrough"], ["ours/evaluation-mistake", "ours/evaluation-mistake"], ["ours/contributors", "ours/contributors"], ["synthesis/choices", "synthesis/choices"], ["synthesis/lessons", "synthesis/lessons"],
]);

export const resolveSlug = (slug) => LEGACY_ALIASES.get(slug) || slug;

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
    if (!PAGE_ARCHETYPES.has(entry.archetype)) throw new Error(`unknown page archetype: ${entry.archetype}`);
    const slug = `${chapter.slug}/${entry.slug}`;
    if (slugs.has(slug)) throw new Error(`duplicate slide slug: ${slug}`);
    slugs.add(slug);
  }
  return {
    mappedIds,
    reportIds,
    slugs: [...slugs],
    pageCount: slugs.size,
    chapterCounts: chapters.map((chapter) => chapter.slides.length),
  };
}

export const DECK_STYLE = `
#data-analytics-portable-reader{display:none!important}
#data-analytics-portable-fallback{display:block!important;visibility:visible!important;position:relative!important;width:100%!important;max-width:none!important;padding:0!important}
html.retrospective-deck-ready,html.retrospective-deck-ready body{height:100%;overflow:hidden}
.retrospective-deck{height:100dvh;display:grid;grid-template-rows:auto minmax(0,1fr) auto;background:var(--portable-canvas);color:var(--portable-ink)}
.deck-chrome{position:relative;z-index:20;background:color-mix(in srgb,var(--portable-canvas) 92%,transparent);backdrop-filter:blur(12px)}
.deck-topbar,.deck-footer{display:flex;align-items:center;gap:12px;min-height:56px;padding:8px clamp(12px,2.5vw,32px);border-color:var(--portable-border)}
.deck-topbar{border-bottom:1px solid var(--portable-border)}
.deck-footer{justify-content:space-between;border-top:1px solid var(--portable-border)}
.deck-footer .deck-button{max-width:min(38vw,360px);padding:6px 12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.deck-title{margin-right:auto;font-weight:750}.deck-breadcrumb{color:var(--portable-muted)}
.deck-chapter-rail{display:flex;gap:4px}.deck-chapter-button{display:grid;place-items:center;width:32px;height:32px;padding:0;border:1px solid var(--portable-border);border-radius:999px;background:var(--portable-surface);color:var(--portable-muted);cursor:pointer}.deck-chapter-button[aria-current="true"]{border-color:var(--portable-accent);background:var(--portable-accent);color:#fff}.deck-mobile-orientation{display:none}
.deck-button{min-width:44px;min-height:44px;border:1px solid var(--portable-border);border-radius:10px;background:var(--portable-surface);color:var(--portable-ink);cursor:pointer}
.deck-button:focus-visible,.deck-jump-item:focus-visible,.deck-slide:focus-visible,.deck-rail-button:focus-visible,summary:focus-visible{outline:3px solid var(--portable-accent);outline-offset:3px}
.deck-track{display:flex;min-width:0;overflow-x:auto;overflow-y:hidden;scroll-snap-type:x mandatory;scroll-behavior:smooth;overscroll-behavior-x:contain;scrollbar-width:none}
.deck-chapter{position:relative;flex:0 0 100%;min-width:0;height:100%;scroll-snap-align:start}
.deck-vertical{height:100%;overflow-y:auto;overflow-x:hidden;scroll-snap-type:y proximity;overscroll-behavior-y:contain}
.deck-vertical-rail{position:absolute;z-index:10;right:12px;top:50%;transform:translateY(-50%);display:grid;gap:7px;padding:9px;border:1px solid var(--portable-border);border-radius:999px;background:color-mix(in srgb,var(--portable-surface) 88%,transparent)}
.deck-rail-button{position:relative;display:grid;place-items:center;width:28px;height:28px;padding:0;border:1px solid var(--portable-muted);border-radius:999px;background:var(--portable-surface);color:var(--portable-muted);font-size:11px;cursor:pointer}
.deck-rail-button[aria-current="true"]{border-color:var(--portable-accent);background:var(--portable-accent);color:#fff}
.deck-rail-button::after{position:absolute;right:36px;width:max-content;max-width:240px;padding:5px 8px;border:1px solid var(--portable-border);border-radius:7px;background:var(--portable-surface);color:var(--portable-ink);content:attr(data-label);font-size:12px;opacity:0;pointer-events:none;transform:translateX(4px);transition:opacity .12s,transform .12s}.deck-rail-button:hover::after,.deck-rail-button:focus::after{opacity:1;transform:translateX(0)}
.deck-slide{min-height:100%;padding:clamp(20px,3vw,46px) clamp(16px,3vw,44px);scroll-snap-align:start;scroll-margin-top:12px}
.deck-slide-inner{width:min(1520px,100%);margin:0 auto;display:grid;gap:clamp(16px,2vw,28px)}
.deck-slide-heading{margin:0;font-size:clamp(22px,3vw,38px);line-height:1.12}.deck-question{margin:0;color:var(--portable-muted)}
.deck-page-copy{display:grid;align-content:center;gap:12px;max-width:78ch}.deck-page-copy .deck-slide-heading{font-size:clamp(30px,4vw,58px)}
.deck-visual{min-width:0;margin:0;border:1px solid color-mix(in srgb,var(--portable-border) 74%,transparent);border-radius:clamp(16px,2vw,28px);overflow:hidden;background:#101216;box-shadow:0 28px 80px rgba(0,0,0,.2)}
.deck-visual img{display:block;width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}
.deck-slide--cover .deck-slide-inner{grid-template-columns:minmax(260px,.8fr) minmax(0,2fr);align-items:center;min-height:calc(100dvh - 190px)}
.deck-slide--cover .deck-page-copy{grid-column:1;grid-row:1}
.deck-slide--cover .deck-slide-heading{font-size:clamp(42px,6vw,84px);letter-spacing:-.045em}.deck-slide--cover .deck-question{font-size:clamp(16px,1.6vw,22px);line-height:1.5}
.deck-chapter-map{grid-column:2;grid-row:1;display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:0;padding:0;list-style:none;counter-reset:chapter-page}
.deck-chapter-map li{display:grid;grid-template-columns:auto 1fr;gap:10px;align-items:start;min-height:78px;padding:14px;border:1px solid var(--portable-border);border-radius:14px;background:linear-gradient(145deg,color-mix(in srgb,var(--portable-accent) 9%,var(--portable-surface)),var(--portable-surface));counter-increment:chapter-page}
.deck-chapter-map li::before{content:counter(chapter-page);display:grid;place-items:center;width:28px;height:28px;border-radius:999px;background:var(--portable-accent);color:#fff;font-size:12px;font-weight:800}.deck-chapter-map span{font-weight:700;line-height:1.3}
.deck-flow{display:grid;gap:18px}.deck-flow-lane{display:grid;gap:10px;padding:16px;border:1px solid var(--portable-border);border-radius:16px;background:var(--portable-surface)}.deck-flow-lane h3{margin:0;font-size:16px}.deck-flow-lane ol{display:grid;grid-template-columns:repeat(var(--flow-count),minmax(0,1fr));gap:24px;margin:0;padding:0;list-style:none;counter-reset:flow-step}.deck-flow-step{position:relative;min-width:0;padding:13px;border:1px solid color-mix(in srgb,var(--portable-accent) 38%,var(--portable-border));border-radius:12px;background:color-mix(in srgb,var(--portable-accent) 7%,var(--portable-surface));overflow-wrap:anywhere;counter-increment:flow-step}.deck-flow-step::before{content:counter(flow-step);display:block;margin-bottom:6px;color:var(--portable-accent);font-size:12px;font-weight:850}.deck-flow-step:not(:last-child)::after{content:"→";position:absolute;top:50%;right:-19px;color:var(--portable-accent);font-size:20px;font-weight:900;transform:translateY(-50%)}
.deck-slide--story .portable-markdown,.deck-slide--story .portable-page-header,.deck-slide--story .portable-content-card{max-width:78ch}
.deck-slide--visual .deck-visual{max-width:1100px}.deck-slide--matrix .portable-content-card,.deck-slide--audit .portable-content-card{max-width:none}
.deck-slide--matrix table{width:100%;table-layout:auto}.deck-slide--matrix th,.deck-slide--matrix td{white-space:normal;overflow-wrap:anywhere;vertical-align:top}
.deck-embedded-document{display:block;width:100%;min-width:0;overflow:visible}.deck-embedded-document[hidden]{display:none}.portable-custom-html>iframe[hidden]{display:none!important}
.deck-slide .portable-page-header{position:static;width:auto;height:auto;min-height:0;margin:0;padding:0;border:0;background:transparent}
.deck-slide .portable-block-stack{display:contents}.deck-slide .portable-markdown{max-width:900px}
.deck-slide .portable-content-card,.deck-slide .portable-metric-card{box-shadow:none}
.deck-disclosure{border:1px solid var(--portable-border);border-radius:12px;background:var(--portable-surface);overflow:clip}
.deck-disclosure>summary{min-height:48px;padding:14px 18px;cursor:pointer;color:var(--portable-accent);font-weight:700}
.deck-disclosure>[data-artifact-block-id]{border:0;border-radius:0}
.deck-source-list{margin-top:18px}.deck-source-list>.deck-disclosure{width:100%}#data-analytics-portable-fallback>.portable-sources,.deck-source-list>.portable-sources{display:block!important}
.deck-jump{position:fixed;inset:0;z-index:50;display:none;place-items:center;padding:20px;background:rgba(15,23,42,.72)}
.deck-jump[data-open="true"]{display:grid}.deck-jump-panel{width:min(720px,100%);max-height:min(720px,88dvh);overflow:auto;padding:18px;border:1px solid var(--portable-border);border-radius:16px;background:var(--portable-surface)}
.deck-jump-input{width:100%;min-height:46px;padding:10px 12px;border:1px solid var(--portable-border);border-radius:9px;background:var(--portable-canvas);color:var(--portable-ink)}
.deck-jump-list{display:grid;gap:8px;margin-top:12px}.deck-jump-item{width:100%;min-height:48px;padding:10px 12px;border:0;border-radius:9px;background:var(--portable-surface-subtle);color:var(--portable-ink);text-align:left;cursor:pointer}
.deck-live,.deck-skip{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}.deck-skip:focus{position:fixed;top:8px;left:8px;z-index:80;width:auto;height:auto;clip:auto;padding:10px;background:var(--portable-surface)}
html[data-deck-view="linear"],html[data-deck-view="linear"] body{height:auto;overflow:auto}
html[data-deck-view="linear"] .retrospective-deck{height:auto;display:block}html[data-deck-view="linear"] .deck-track{display:block;overflow:visible}html[data-deck-view="linear"] .deck-chapter,html[data-deck-view="linear"] .deck-slide{height:auto;min-height:0}html[data-deck-view="linear"] .deck-vertical{height:auto;overflow:visible}html[data-deck-view="linear"] .deck-vertical-rail{display:none}html[data-deck-view="linear"] .deck-disclosure>summary{display:none}html[data-deck-view="linear"] .deck-disclosure>[data-artifact-block-id]{display:block!important}
@media(max-width:1100px){.deck-slide--cover .deck-slide-inner{grid-template-columns:1fr;min-height:0}.deck-slide--cover .deck-page-copy,.deck-chapter-map{grid-column:1;grid-row:auto}.deck-flow-lane ol{grid-template-columns:1fr;gap:22px}.deck-flow-step:not(:last-child)::after{content:"↓";top:auto;right:auto;bottom:-21px;left:50%;transform:translateX(-50%)}}
@media(max-width:700px){.deck-title,.deck-breadcrumb,.deck-progress,.deck-axis-help,.deck-chapter-rail{display:none}.deck-mobile-orientation{display:block;min-width:0;margin-right:auto;overflow:hidden;font-weight:650;text-overflow:ellipsis;white-space:nowrap}.deck-topbar,.deck-footer{min-height:60px;padding:8px 10px}.deck-slide{padding:18px 12px}.deck-vertical-rail{display:none}.portable-table-scroll{max-width:calc(100vw - 24px)}.deck-button{min-width:48px;min-height:48px}.deck-slide--cover .deck-slide-heading{font-size:clamp(36px,13vw,58px)}.deck-slide--cover .deck-visual{max-height:none}.deck-slide--cover .deck-visual img{max-height:none}.deck-slide--matrix .portable-table-scroll{overflow-x:auto}.deck-slide--audit .portable-markdown{columns:1}}
@media(prefers-reduced-motion:reduce){.deck-track,.deck-vertical{scroll-behavior:auto!important}}
@media(forced-colors:active){.deck-button,.deck-chapter-button,.deck-rail-button,.deck-disclosure,.deck-jump-panel{border:1px solid CanvasText}}
@media print{html,body{height:auto!important;overflow:visible!important}.deck-chrome,.deck-jump,.deck-skip,.deck-live,.deck-vertical-rail{display:none!important}.retrospective-deck,.deck-track,.deck-chapter,.deck-vertical,.deck-slide{display:block!important;height:auto!important;min-height:0!important;overflow:visible!important;scroll-snap-type:none!important}.deck-disclosure>summary{display:none!important}.deck-disclosure>[data-artifact-block-id],.deck-disclosure:not([open])>*:not(summary){display:block!important}}
`;

function runtimeMain(CONFIG) {
  const html = document.documentElement;
  const fallback = document.getElementById("data-analytics-portable-fallback");
  const stack = fallback?.querySelector(".portable-block-stack");
  const sources = fallback?.querySelector(".portable-sources");
  const pageHeader = fallback?.querySelector(":scope > .portable-page-header");
  if (!fallback || !stack || !sources || !pageHeader) return;
  const blocks = new Map([...stack.querySelectorAll(":scope > [data-artifact-block-id]")].map((node) => [node.dataset.artifactBlockId, node]));
  pageHeader.dataset.artifactBlockId = "title";
  blocks.set("title", pageHeader);

  const app = document.createElement("main");
  app.className = "retrospective-deck";
  app.setAttribute("aria-label", "Music-CRS retrospective deck");
  const skip = Object.assign(document.createElement("a"), { className: "deck-skip", href: "#outcome/summary", textContent: "Skip to current slide" });
  const live = Object.assign(document.createElement("div"), { className: "deck-live" });
  live.setAttribute("aria-live", "polite");
  live.setAttribute("aria-atomic", "true");
  const topbar = document.createElement("header");
  topbar.className = "deck-topbar deck-chrome";
  topbar.innerHTML = '<strong class="deck-title">Music-CRS retrospective</strong><span class="deck-mobile-orientation"></span><span class="deck-breadcrumb"></span><span class="deck-progress"></span><button class="deck-button" type="button" data-action="linear">Linear view</button><button class="deck-button" type="button" data-action="jump">Jump</button>';
  const chapterRail = document.createElement("nav");
  chapterRail.className = "deck-chapter-rail";
  chapterRail.setAttribute("aria-label", "Chapters");
  CONFIG.chapters.forEach((chapter, chapterIndex) => {
    const button = document.createElement("button");
    button.className = "deck-chapter-button";
    button.type = "button";
    button.dataset.go = `${chapter.slug}/${chapter.slides[0].slug}`;
    button.setAttribute("aria-label", chapter.title);
    button.title = chapter.title;
    button.textContent = String(chapterIndex + 1);
    chapterRail.append(button);
  });
  topbar.querySelector(".deck-title").after(chapterRail);
  const track = document.createElement("div");
  track.className = "deck-track";
  const footer = document.createElement("footer");
  footer.className = "deck-footer deck-chrome";
  footer.innerHTML = '<button class="deck-button" type="button" data-action="previous">← Previous</button><span class="deck-axis-help">←/→ chapters · ↑/↓ depth</span><button class="deck-button" type="button" data-action="next">Next →</button>';
  const disclosure = (node) => node;

  for (const chapter of CONFIG.chapters) {
    const chapterNode = document.createElement("section");
    chapterNode.className = "deck-chapter";
    chapterNode.dataset.chapter = chapter.slug;
    chapterNode.setAttribute("aria-label", chapter.title);
    const vertical = document.createElement("div");
    vertical.className = "deck-vertical";
    const rail = document.createElement("nav");
    rail.className = "deck-vertical-rail";
    rail.setAttribute("aria-label", `${chapter.title} slides`);
    chapter.slides.forEach((entry, slideIndex) => {
      const slideNode = document.createElement("section");
      slideNode.className = `deck-slide deck-slide--${entry.archetype}`;
      slideNode.id = `${chapter.slug}/${entry.slug}`;
      slideNode.dataset.slug = slideNode.id;
      slideNode.dataset.pageIndex = String(slideIndex + 1);
      slideNode.tabIndex = -1;
      slideNode.setAttribute("aria-labelledby", `${chapter.slug}-${entry.slug}-title`);
      const inner = document.createElement("div");
      inner.className = "deck-slide-inner";
      const pageCopy = document.createElement("div");
      pageCopy.className = "deck-page-copy";
      const heading = document.createElement("h2");
      heading.className = "deck-slide-heading";
      heading.id = `${chapter.slug}-${entry.slug}-title`;
      heading.textContent = entry.title;
      const question = document.createElement("p");
      question.className = "deck-question";
      question.textContent = chapter.question;
      pageCopy.append(heading, question);
      inner.append(pageCopy);
      if (entry.archetype === "cover") {
        const map = document.createElement("ol");
        map.className = "deck-chapter-map";
        map.setAttribute("aria-label", `${chapter.title} page map`);
        chapter.slides.slice(1).forEach((page) => {
          const item = document.createElement("li");
          const label = document.createElement("span");
          label.textContent = page.title;
          item.append(label);
          map.append(item);
        });
        inner.append(map);
      }
      if (entry.lanes?.length) {
        const flow = document.createElement("section");
        flow.className = "deck-flow";
        flow.setAttribute("aria-label", `${entry.title} explanatory flow`);
        entry.lanes.forEach((lane) => {
          const laneNode = document.createElement("article");
          laneNode.className = "deck-flow-lane";
          const laneHeading = document.createElement("h3");
          laneHeading.textContent = lane.label;
          const steps = document.createElement("ol");
          steps.style.setProperty("--flow-count", String(lane.steps.length));
          lane.steps.forEach((step) => {
            const item = document.createElement("li");
            item.className = "deck-flow-step";
            item.textContent = step;
            steps.append(item);
          });
          laneNode.append(laneHeading, steps);
          flow.append(laneNode);
        });
        inner.append(flow);
      }
      for (const blockId of entry.blocks) inner.append(disclosure(blocks.get(blockId), CONFIG.disclosures[blockId]));
      slideNode.append(inner);
      vertical.append(slideNode);
      const railButton = document.createElement("button");
      railButton.className = "deck-rail-button";
      railButton.type = "button";
      railButton.dataset.go = slideNode.id;
      railButton.dataset.label = entry.title;
      railButton.setAttribute("aria-label", `Go to ${entry.title}`);
      railButton.textContent = String(slideIndex + 1);
      rail.append(railButton);
    });
    chapterNode.append(vertical, rail);
    track.append(chapterNode);
  }

  const finalSlide = track.querySelector('[id="synthesis/evidence"] .deck-slide-inner');
  const sourceDetails = document.createElement("details");
  sourceDetails.className = "deck-disclosure deck-source-list";
  sourceDetails.innerHTML = "<summary>Open the complete source list</summary>";
  sourceDetails.append(sources);
  finalSlide.append(sourceDetails);
  app.append(skip, topbar, track, footer, live);
  stack.replaceWith(app);

  const promoteEmbeddedDocument = (frame) => {
    const srcdoc = frame.getAttribute("srcdoc");
    if (!srcdoc) return null;
    const host = document.createElement("div");
    host.className = "deck-embedded-document";
    host.dataset.fitState = "promoted";
    host.setAttribute("role", "group");
    host.setAttribute("aria-label", frame.closest("[data-artifact-block-id]")?.dataset.artifactBlockId?.replaceAll("_", " ") || "Embedded report evidence");
    try {
      const parsed = new DOMParser().parseFromString(srcdoc, "text/html");
      const wrapper = document.createElement("div");
      wrapper.className = "deck-embedded-root";
      wrapper.innerHTML = parsed.body?.innerHTML || "";
      wrapper.querySelectorAll("script,iframe,object,embed,link,base,form,meta").forEach((node) => node.remove());
      wrapper.querySelectorAll("*").forEach((node) => {
        [...node.attributes].forEach((attribute) => {
          if (attribute.name.toLowerCase().startsWith("on")) node.removeAttribute(attribute.name);
        });
        if (node instanceof HTMLImageElement && !/^(data:|blob:)/.test(node.getAttribute("src") || "")) node.removeAttribute("src");
        if (node instanceof HTMLAnchorElement) node.rel = "noreferrer noopener";
      });
      if (frame.closest(".deck-slide--audit")) wrapper.querySelectorAll("details").forEach((details) => { details.open = true; });
      const sourceCss = [...parsed.querySelectorAll("style")].map((node) => node.textContent || "").join("\n")
        .replace(/@import[^;]+;?/gi, "")
        .replace(/url\((?!['\"]?(?:data:|blob:))[^)]+\)/gi, "none");
      const style = document.createElement("style");
      style.textContent = `${sourceCss}\n:host{display:block;min-width:0;color:CanvasText;background:Canvas;font:14px/1.5 system-ui,sans-serif}.deck-embedded-root{min-width:0;overflow:visible}*,*::before,*::after{box-sizing:border-box;max-width:100%}img,svg{height:auto}section,div,article,details{overflow:visible!important}table{width:100%!important;table-layout:fixed!important;border-collapse:collapse}th,td{min-width:0!important;white-space:normal!important;overflow-wrap:anywhere!important;word-break:normal!important;vertical-align:top}pre,code{white-space:pre-wrap;overflow-wrap:anywhere}@media(max-width:700px){table{font-size:12px!important}th,td{padding:7px!important}}`;
      const shadow = host.attachShadow({ mode: "open" });
      shadow.append(style, wrapper);
      frame.after(host);
      frame.hidden = true;
      return host;
    } catch (error) {
      host.dataset.fitState = "fallback";
      host.hidden = true;
      frame.after(host);
      return null;
    }
  };
  app.querySelectorAll(".portable-custom-html iframe[srcdoc]").forEach(promoteEmbeddedDocument);

  const disclosures = () => document.querySelectorAll("details.deck-disclosure");
  const setAllOpen = (stateKey) => disclosures().forEach((details) => {
    if (!(stateKey in details.dataset)) details.dataset[stateKey] = details.open ? "true" : "false";
    details.open = true;
  });
  const restoreOpen = (stateKey) => disclosures().forEach((details) => {
    if (stateKey in details.dataset) {
      details.open = details.dataset[stateKey] === "true";
      delete details.dataset[stateKey];
    }
  });
  const setCanonicalOrder = (enabled) => {
    const dataKnowledge = document.getElementById("query/data-glossary");
    const dataMatrix = document.getElementById("query/data-matrix");
    const promptAudit = document.getElementById("query/prompt-audit");
    const vertical = dataKnowledge?.parentElement;
    if (!vertical || dataMatrix?.parentElement !== vertical || promptAudit?.parentElement !== vertical) return;
    if (enabled) vertical.insertBefore(promptAudit, dataKnowledge);
    else vertical.insertBefore(promptAudit, dataMatrix.nextSibling);
  };

  const slides = CONFIG.chapters.flatMap((chapter, chapterIndex) => chapter.slides.map((entry, slideIndex) => ({
    chapter,
    entry,
    chapterIndex,
    slideIndex,
    slug: `${chapter.slug}/${entry.slug}`,
  })));
  const bySlug = new Map(slides.map((item) => [item.slug, item]));
  const resolveSlug = (slug) => CONFIG.aliases[slug] || slug;
  const breadcrumb = topbar.querySelector(".deck-breadcrumb");
  const progress = topbar.querySelector(".deck-progress");
  const mobileOrientation = topbar.querySelector(".deck-mobile-orientation");
  let active = slides[0];
  let scrollTimer = 0;
  let programmaticTarget = null;
  let gestureOrigin = null;

  const openRequestedDisclosure = () => {
    const params = new URLSearchParams(location.hash.split("?")[1] || "");
    const id = params.get("open");
    if (id) document.querySelector(`details[data-disclosure-for="${CSS.escape(id)}"]`)?.setAttribute("open", "");
  };
  const chapterSlidesFor = (item) => slides.filter((candidate) => candidate.chapterIndex === item.chapterIndex);
  const horizontal = (delta) => {
    const chapterIndex = active.chapterIndex + delta;
    if (chapterIndex < 0 || chapterIndex >= CONFIG.chapters.length) return active;
    return slides.find((item) => item.chapterIndex === chapterIndex && item.slideIndex === 0) || active;
  };
  const verticalItem = (delta) => {
    const chapterSlides = chapterSlidesFor(active);
    return chapterSlides[Math.max(0, Math.min(chapterSlides.length - 1, active.slideIndex + delta))];
  };
  const updateCurrent = (item, announce = false) => {
    active = item;
    document.querySelectorAll('.deck-slide[aria-current="true"],.deck-rail-button[aria-current="true"],.deck-chapter-button[aria-current="true"]').forEach((node) => node.removeAttribute("aria-current"));
    const target = document.getElementById(item.slug);
    target.setAttribute("aria-current", "true");
    document.querySelector(`.deck-rail-button[data-go="${CSS.escape(item.slug)}"]`)?.setAttribute("aria-current", "true");
    chapterRail.children[item.chapterIndex]?.setAttribute("aria-current", "true");
    breadcrumb.textContent = `${item.chapter.title} / ${item.entry.title}`;
    progress.textContent = `Chapter ${item.chapterIndex + 1}/${CONFIG.chapters.length} · slide ${item.slideIndex + 1}/${CONFIG.chapters[item.chapterIndex].slides.length}`;
    mobileOrientation.textContent = `${item.chapter.title} · ${item.slideIndex + 1}/${CONFIG.chapters[item.chapterIndex].slides.length}`;
    skip.href = `#${item.slug}`;
    const chapterSlides = chapterSlidesFor(item);
    const previousItem = item.slideIndex > 0
      ? chapterSlides[item.slideIndex - 1]
      : slides.find((candidate) => candidate.chapterIndex === item.chapterIndex - 1 && candidate.slideIndex === 0);
    const nextItem = item.slideIndex < chapterSlides.length - 1
      ? chapterSlides[item.slideIndex + 1]
      : slides.find((candidate) => candidate.chapterIndex === item.chapterIndex + 1 && candidate.slideIndex === 0);
    const previousButton = footer.querySelector('[data-action="previous"]');
    const nextButton = footer.querySelector('[data-action="next"]');
    previousButton.disabled = !previousItem;
    previousButton.textContent = previousItem ? `← ${previousItem.entry.title}` : "← Start";
    nextButton.disabled = !nextItem;
    nextButton.textContent = nextItem ? `${nextItem.entry.title} →` : "End";
    if (announce) live.textContent = `${item.chapter.title}, ${item.entry.title}`;
  };
  const goTo = (slug, { push = true, focus = true, announce = true, behavior = null } = {}) => {
    const requestedSlug = slug.split("?")[0];
    const cleanSlug = resolveSlug(requestedSlug);
    const item = bySlug.get(cleanSlug) || slides[0];
    const target = document.getElementById(item.slug);
    const scrollBehavior = behavior || (matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth");
    programmaticTarget = scrollBehavior === "smooth" ? item.slug : null;
    gestureOrigin = null;
    const scrollContainers = [track, target.closest(".deck-vertical")];
    const previousInlineBehavior = scrollContainers.map((node) => node.style.scrollBehavior);
    if (scrollBehavior === "auto") scrollContainers.forEach((node) => { node.style.scrollBehavior = "auto"; });
    target.scrollIntoView({ behavior: scrollBehavior, block: "start", inline: "start" });
    if (scrollBehavior === "auto") scrollContainers.forEach((node, index) => { node.style.scrollBehavior = previousInlineBehavior[index]; });
    updateCurrent(item, announce);
    const nextHash = `#${item.slug}${slug.includes("?") ? `?${slug.split("?")[1]}` : ""}`;
    if (push) history.pushState({ slug: item.slug }, "", nextHash);
    else history.replaceState({ slug: item.slug }, "", nextHash);
    openRequestedDisclosure();
    if (focus) target.focus({ preventScroll: true });
    return item;
  };
  const setLinear = (enabled) => {
    if (enabled) setAllOpen("deckLinearOpen"); else restoreOpen("deckLinearOpen");
    setCanonicalOrder(enabled);
    html.dataset.deckView = enabled ? "linear" : "deck";
    const url = new URL(location.href);
    if (enabled) url.searchParams.set("view", "linear"); else url.searchParams.delete("view");
    history.replaceState(history.state, "", url.href);
    topbar.querySelector('[data-action="linear"]').textContent = enabled ? "Deck view" : "Linear view";
  };
  const nearest = (nodes, axis) => [...nodes].reduce((best, node) => (
    Math.abs(node.getBoundingClientRect()[axis]) < Math.abs(best.getBoundingClientRect()[axis]) ? node : best
  ));
  const syncFromScroll = () => {
    if (html.dataset.deckView === "linear") return;
    const chapterNode = nearest(track.querySelectorAll(".deck-chapter"), "left");
    const slideNode = nearest(chapterNode.querySelectorAll(".deck-slide"), "top");
    const item = bySlug.get(slideNode.dataset.slug);
    if (!item) return;
    if (programmaticTarget) {
      const reachedTarget = item.slug === programmaticTarget;
      programmaticTarget = null;
      if (!reachedTarget) {
        updateCurrent(item, false);
        history.replaceState({ slug: item.slug }, "", `#${item.slug}`);
      }
      return;
    }
    if (item.slug !== active.slug) updateCurrent(item, false);
    if (gestureOrigin) {
      if (item.slug !== gestureOrigin) {
        history.replaceState({ slug: gestureOrigin }, "", `#${gestureOrigin}`);
        history.pushState({ slug: item.slug }, "", `#${item.slug}`);
      }
      gestureOrigin = null;
    }
  };
  const noteScroll = () => {
    if (!programmaticTarget && !gestureOrigin) gestureOrigin = active.slug;
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(syncFromScroll, 80);
  };
  track.addEventListener("scroll", noteScroll, { passive: true });
  track.querySelectorAll(".deck-vertical").forEach((node) => node.addEventListener("scroll", noteScroll, { passive: true }));

  const jump = document.createElement("div");
  jump.className = "deck-jump";
  jump.dataset.open = "false";
  jump.setAttribute("role", "dialog");
  jump.setAttribute("aria-modal", "true");
  jump.setAttribute("aria-label", "Jump anywhere");
  jump.innerHTML = '<div class="deck-jump-panel"><label>Search chapters, teams, or topics<input class="deck-jump-input" type="search" role="searchbox"></label><div class="deck-jump-list"></div></div>';
  app.append(jump);
  const input = jump.querySelector(".deck-jump-input");
  const list = jump.querySelector(".deck-jump-list");
  let jumpOpener = null;
  const searchText = (item) => {
    const slideNode = document.getElementById(item.slug);
    const iframeText = [...slideNode.querySelectorAll("iframe")].map((frame) => frame.getAttribute("srcdoc") || "").join(" ");
    return `${item.chapter.title} ${item.entry.title} ${item.slug} ${slideNode.textContent} ${iframeText}`.toLowerCase();
  };
  const renderJump = (query = "") => {
    list.replaceChildren();
    const normalized = query.trim().toLowerCase();
    for (const item of slides.filter((candidate) => searchText(candidate).includes(normalized))) {
      const button = document.createElement("button");
      button.className = "deck-jump-item";
      button.type = "button";
      button.textContent = `${item.chapter.title} — ${item.entry.title}`;
      button.addEventListener("click", () => {
        closeJump(false);
        goTo(item.slug);
      });
      list.append(button);
    }
  };
  const setBackgroundInert = (inert) => [topbar, track, footer].forEach((node) => { node.inert = inert; });
  const openJump = (opener = document.activeElement) => {
    jumpOpener = opener instanceof HTMLElement ? opener : topbar.querySelector('[data-action="jump"]');
    jump.dataset.open = "true";
    setBackgroundInert(true);
    renderJump();
    input.value = "";
    input.focus();
  };
  const closeJump = (restore = true) => {
    jump.dataset.open = "false";
    setBackgroundInert(false);
    if (restore) jumpOpener?.focus();
  };
  input.addEventListener("input", () => renderJump(input.value));
  const interactive = (target) => target instanceof Element && target.closest("input,textarea,select,button,a,summary,details,[contenteditable=true],iframe,.portable-table-scroll");
  app.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const destination = target?.closest("[data-go]")?.dataset.go;
    if (destination) {
      goTo(destination);
      return;
    }
    const action = target?.closest("[data-action]")?.dataset.action;
    if (action === "jump") openJump(target);
    if (action === "linear") setLinear(html.dataset.deckView !== "linear");
    if (action === "previous") goTo(active.slideIndex ? verticalItem(-1).slug : horizontal(-1).slug);
    if (action === "next") {
      const chapterSlides = chapterSlidesFor(active);
      goTo(active.slideIndex < chapterSlides.length - 1 ? verticalItem(1).slug : horizontal(1).slug);
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && jump.dataset.open === "true") {
      event.preventDefault();
      closeJump();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      jump.dataset.open === "true" ? closeJump() : openJump();
      return;
    }
    if (!event.ctrlKey && !event.metaKey && event.key.toLowerCase() === "j" && !interactive(event.target)) {
      event.preventDefault();
      openJump();
      return;
    }
    if (jump.dataset.open === "true" || interactive(event.target) || html.dataset.deckView === "linear") return;
    const destinations = {
      ArrowLeft: horizontal(-1),
      ArrowRight: horizontal(1),
      ArrowUp: verticalItem(-1),
      ArrowDown: verticalItem(1),
    };
    if (destinations[event.key]) {
      event.preventDefault();
      goTo(destinations[event.key].slug);
    }
  });
  addEventListener("popstate", () => goTo(location.hash.slice(1) || slides[0].slug, { push: false, focus: false, announce: true, behavior: "auto" }));
  addEventListener("beforeprint", () => {
    setAllOpen("deckPrintOpen");
    setCanonicalOrder(true);
  });
  addEventListener("afterprint", () => {
    restoreOpen("deckPrintOpen");
    if (html.dataset.deckView !== "linear") setCanonicalOrder(false);
  });
  const initial = location.hash.slice(1);
  const initialSlug = resolveSlug(initial.split("?")[0]);
  if (!bySlug.has(initialSlug)) goTo(slides[0].slug, { push: false, focus: false, announce: false, behavior: "auto" });
  else goTo(initial, { push: false, focus: false, announce: false, behavior: "auto" });
  setLinear(new URL(location.href).searchParams.get("view") === "linear");
  html.classList.add("retrospective-deck-ready");
  html.dataset.deckReady = "true";
  window.__retrospectiveDeck = { CONFIG, app, track, live, goTo, setLinear, currentSlug: () => active.slug };
}

export const DECK_RUNTIME = `(${runtimeMain.toString()})(__CONFIG__);`;

export function enhanceHtml(input) {
  const html = stripDeckInjection(input);
  validateChapterMap(CHAPTERS, html);
  const config = JSON.stringify({ chapters: CHAPTERS, disclosures: DISCLOSURES, aliases: Object.fromEntries(LEGACY_ALIASES) }).replaceAll("<", "\\u003c");
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
