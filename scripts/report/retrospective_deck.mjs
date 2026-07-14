#!/usr/bin/env node
import { readFile, rename, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

const slide = (slug, title, archetype, blocks, options = {}) => ({ slug, title, archetype, blocks, ...options });

export const PAGE_ARCHETYPES = new Set(["cover", "story", "visual", "matrix", "audit"]);

export const CONFIDENCE_LEVELS = new Set(["verified", "likely", "unknown"]);

export const DIAGNOSIS_SLIDES = [
  slide("score-location", "Where the score gap appeared", "visual", [], {
    diagnosisKind: "score",
    takeaway: "Ranking and judge terms explain most of the arithmetic gap; the chart does not prove which mechanism caused it.",
  }),
  slide("information-loss", "Where information was lost", "visual", [], {
    diagnosisKind: "bottleneck",
    stages: ["Conversation", "Extracted state", "Retriever actions", "Candidate sources", "Candidate union", "LightGBM", "Top-1 track", "Grounded context", "One draft", "Final response"],
    losses: [
      { after: "Extracted state", label: "Some facts remained soft or lacked a dedicated source action", confidence: "verified" },
      { after: "Candidate sources", label: "No direct co-occurrence or transition lane", confidence: "verified" },
      { after: "Candidate union", label: "Absent tracks were irrecoverable downstream", confidence: "verified" },
      { after: "One draft", label: "No independent selection, checking, or repair", confidence: "verified" },
    ],
  }),
  slide("constraint-wiring", "Extracted constraints versus operationalized constraints", "visual", [], {
    diagnosisKind: "wiring",
    connections: [
      { from: "Explicit rejections", to: "Hard track exclusion, tag demotion, and artist veto", confidence: "verified" },
      { from: "Era preference", to: "Soft preference and era lookup", confidence: "verified" },
      { from: "Played-track history", to: "Anchors and reranker features, without a direct track co-occurrence source", confidence: "verified" },
      { from: "Other soft state facts", to: "No dedicated source action documented for every field", confidence: "verified" },
    ],
    takeaway: "Rich extraction, uneven execution: not every fact became a filter, source-specific query, or dedicated candidate signal.",
  }),
  slide("features-seen", "What the 142-feature reranker saw", "visual", [], {
    diagnosisKind: "feature-map",
    featureFamilies: ["Retriever evidence", "Semantic and multimodal", "Behavioral and lookup", "Catalog", "Conversation and state", "Agreement and interactions"],
    takeaway: "The ranker was substantial; column count alone does not establish liveness, importance, robustness, or held-out benefit.",
  }),
  slide("evidence-missed", "Evidence the ranker could not see or recover", "visual", [], {
    diagnosisKind: "boundaries",
    boundaries: ["Missing upstream source", "Consequent missing feature", "Not missing"],
    takeaway: "Adding LightGBM columns cannot recreate a track or source signal that never entered the pipeline.",
  }),
  slide("confidence", "Response weakness and confidence-ranked diagnosis", "visual", [], {
    diagnosisKind: "confidence",
    confidence: {
      verified: ["Ranking and judge dominate the score gap", "Constraint execution was uneven", "Behavioral evidence was partial", "b1_cos was a reranker feature only", "Blind-B used one response call with echo_retries=0"],
      likely: ["Evidence diversity mattered more than feature count", "LLM knowledge was not consistently grounded and reused", "Distribution shift or objective mismatch contributed", "Response quality control was too thin"],
      unknown: ["Blind-B candidate recall", "Present-but-misranked frequency", "Per-session failure archetypes", "Causal effect of any one mechanism"],
    },
  }),
];

export const CURATED_PATH = [
  "outcome/executive-answer", "outcome/gap-chart",
  ...DIAGNOSIS_SLIDES.map(({ slug }) => `diagnosis/${slug}`),
  "ours/inference-rail", "retrieval/evidence-heatmap", "response/control-heatmap",
  "leaders/volart-retrieval", "synthesis/lessons",
];

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
    slug: "diagnosis",
    title: "Diagnosis",
    question: "Where did information and control weaken, and how confident is that diagnosis?",
    slides: DIAGNOSIS_SLIDES,
  },
  {
    slug: "ours",
    title: "Our submission",
    question: "What did we build, what worked, and where did confidence fail?",
    slides: [
      slide("cover", "Our submission", "cover", ["own_system_heading"]),
      slide("offline-rail", "Offline evidence rail", "visual", ["own_system_diagram"]),
      slide("inference-rail", "Inference rail", "visual", [], { lanes: [
        { label: "Deployed Blind-B path", steps: ["DeepSeek state extraction", "BM25, multimodal ANN, and lookup branches", "Top 500 from each branch → candidate union", "LightGBM LambdaMART reorders the union", "Top-1 selected track", "Single-pass response"] },
      ] }),
      slide("walkthrough", "Complete walkthrough and ranking handoff", "audit", ["own_system_walkthrough"]),
      slide("what-worked", "What worked", "story", ["what_worked"]),
      slide("evaluation-mistake", "Evaluation mistake and confidence boundary", "story", ["evaluation_mistake"]),
      slide("contributors", "Ranking and response contributors", "story", ["ranking_contributors", "response_contributors"]),
    ],
  },
  {
    slug: "query",
    title: "Conversation → query",
    question: "How did each system turn dialogue into retriever inputs?",
    slides: [
      slide("cover", "Conversation → query", "cover", []),
      slide("lifecycle", "Dialogue becomes several search signals", "visual", ["lifecycle_heading", "lifecycle_map", "lifecycle_takeaway", "query_heading", "query_explainer"], {
        visualKind: "mechanism",
        takeaway: "The important choice is not one perfect query. It is which conversation evidence becomes useful input for each retrieval lane.",
        stages: [
          { label: "Conversation window", detail: "Recent turns, longer history, and played tracks" },
          { label: "Interpretation", detail: "State, rewrite, entities, summary, or learned encoding" },
          { label: "Query variants", detail: "Lexical, dense, history, transition, and constraint signals" },
          { label: "Retriever inputs", detail: "Each source receives the representation suited to its evidence" },
        ],
      }),
      slide("query-matrix", "Same stages, different query evidence", "matrix", ["query_matrix"], {
        visualKind: "comparison",
        columns: ["Interpretation", "Query forms", "History boundary"],
        common: "All five systems transformed dialogue into more than one retriever input.",
        different: "They differed in conversation window, explicit structure, and whether history became text, entities, co-occurrence, or transitions.",
        teams: [
          { name: "npatta01", values: ["DeepSeek V1 structured state", "Weighted BM25, field-aligned dense strings, deterministic b1_cos", "Multi-turn memory, current request, played-track facts"] },
          { name: "volart", values: ["Concise rewrite plus JSON entities", "Rewrite for lexical/dense; entities and played IDs for separate lanes", "Goal, latest request, and available history"] },
          { name: "niwatori", values: ["Source-specific safe text and learned encodings", "Lexical, dense, history/co-occurrence, and transition forms", "Recent text, full played IDs, and last track by source"] },
          { name: "swyoo", values: ["Current request, music context, and cached summary", "BM25, QEmb, and two-tower representations", "Recent listens and chat-derived aggregates"] },
          { name: "team2_s2", values: ["Conversation text plus source-specific item context", "BM25 conversation, live text, and item/CF branches", "Prior turns and last one, three, or all played tracks"] },
        ],
      }),
      slide("data-glossary", "Four places system knowledge can come from", "visual", ["data_knowledge_heading", "data_knowledge_glossary"], {
        visualKind: "mechanism",
        takeaway: "Reproducibility depends on separating recorded facts from generated artifacts and latent model associations.",
        stages: [
          { label: "Challenge records", detail: "Catalog, conversations, users, labels, and played history" },
          { label: "External structured data", detail: "Lyrics, identifiers, credits, or outside interaction records" },
          { label: "Generated artifacts", detail: "States, rewrites, descriptions, candidates, critiques, and repairs" },
          { label: "LLM world knowledge", detail: "Uncited associations available only inside model generation" },
          { label: "Verification boundary", detail: "What another record can independently reproduce or check" },
        ],
      }),
      slide("provenance-stacks", "How evidence provenance stacks up", "visual", [], {
        visualKind: "mechanism",
        takeaway: "Recorded, generated, latent, and verified evidence have different reproducibility boundaries.",
        stages: [
          { label: "Recorded", detail: "Challenge records and external structured data" },
          { label: "Generated", detail: "States, rewrites, descriptions, and critiques" },
          { label: "Latent", detail: "Associations available only inside model generation" },
          { label: "Verified", detail: "Claims another record can independently check" },
        ],
      }),
      slide("data-matrix", "Common records, different knowledge boundaries", "matrix", ["data_knowledge_matrix", "data_knowledge_interpretation"], {
        visualKind: "comparison",
        columns: ["Recorded data", "Generated or latent knowledge", "Grounding boundary"],
        common: "Every reviewed system used official challenge data and persisted some model-generated artifacts.",
        different: "External datasets and the checks placed around model-authored musical claims varied substantially.",
        teams: [
          { name: "npatta01", values: ["Official catalog, embeddings, conversations/users, public labels", "Cached state and artist known-for text; response-model associations", "Catalog-resolved IDs; no independent response fact checker documented"], status: "limit" },
          { name: "volart", values: ["Official records plus train co-occurrence and frequency/MOVES priors", "Rewrites, descriptions, response candidates, critiques, and edits", "Track IDs held fixed; structured musical-fact verification not documented"], status: "limit" },
          { name: "niwatori", values: ["Official records plus TalkPlayData-1 statistics", "No LLM retrieval rewrite documented; ten response drafts", "Mapped external IDs, duplicate audits, and OOF training; response fact checking not documented"], status: "external" },
          { name: "swyoo", values: ["Official records plus LRCLIB, Genius, and MusicBrainz", "Summaries, themes, candidates, and repaired responses", "Broadest documented external fact path with field-level checks"], status: "verified" },
          { name: "team2_s2", values: ["Official catalog, conversations, users, labels, and embeddings", "Fact bundles, first-pass responses, and refinements", "Verified track facts supplied to generation; no external music dataset documented"], status: "verified" },
        ],
      }),
      slide("prompt-audit", "Prompt and file audit", "audit", ["query_evidence_details"]),
    ],
  },
  {
    slug: "retrieval",
    title: "Retrieval & ranking",
    question: "What candidates and features could the rankers actually see?",
    slides: [
      slide("cover", "Retrieval & ranking", "cover", []),
      slide("retriever-mechanism", "Many evidence lanes become one candidate boundary", "visual", [], {
        visualKind: "mechanism",
        takeaway: "A ranker can only rescue tracks that entered its candidate set; source diversity matters before feature richness does.",
        stages: [
          { label: "Query variants", detail: "Text, dense vectors, entities, history, and constraints" },
          { label: "Parallel sources", detail: "Lexical, semantic, collaborative, lookup, and transition lanes" },
          { label: "Candidate assembly", detail: "Union, late fusion, dedicated slots, or routing" },
          { label: "Feature computation", detail: "Per-source evidence, metadata, history, and agreement" },
          { label: "Final ordering", detail: "Learned ranker, selector, or deterministic fusion" },
        ],
      }),
      slide("retriever-matrix", "Same boundary, different retrieval evidence", "matrix", ["retrieval_heading", "retrieval_glossary", "retrieval_matrix"], {
        visualKind: "comparison",
        columns: ["Candidate sources", "History use", "Constraints"],
        common: "Every reviewed path combined multiple evidence sources before choosing final track IDs.",
        different: "Direct co-occurrence and transition lanes, history seeding, candidate union rules, and hard filters were not shared equally.",
        teams: [
          { name: "npatta01", values: ["BM25, multimodal ANN, CF/BPR centroids, discography, era lookup", "Accepted/referenced tracks anchor; rejected items demote or drop", "Hard track rejection, tag demotion, artist veto, soft era preference"], status: "limit" },
          { name: "volart", values: ["BM25, metadata dense, LLM-description dense, entities, train co-occurrence", "Played tracks seed co-occurrence and are excluded", "Dedicated entity/era slots and already-played exclusion"], status: "verified" },
          { name: "niwatori", values: ["Lexical, dense, co-occurrence/history, transition, and prior sources", "Full played history for co-occurrence; last track for transitions", "Source-specific safety and candidate handling"], status: "external" },
          { name: "swyoo", values: ["BM25, QEmb, two-tower, and metadata/demographic evidence", "Recent listens accompany current and summarized context", "Already-seen tracks excluded; cues stay soft; no general hard rejection documented"], status: "verified" },
          { name: "team2_s2", values: ["BM25 conversation, live text, CF/BPR, and item branches", "Last one, three, or all played tracks depending on source", "Played-track exclusion enforced; explicit rejection, era, popularity, and novelty rules not documented"], status: "verified" },
        ],
      }),
      slide("evidence-heatmap", "Which retrieval evidence each system could use", "visual", [], {
        visualKind: "comparison",
        takeaway: "Candidate-source coverage determines which evidence can become a ranking feature downstream.",
      }),
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
      slide("overview", "A selected track still needs a response pipeline", "visual", ["response_heading", "response_explainer"], {
        visualKind: "mechanism",
        takeaway: "Multiple drafts help only when a documented selector, verifier, critic, or repair pass decides what survives.",
        stages: [
          { label: "Selected track ID", detail: "Recommendation identity is fixed before prose work" },
          { label: "Grounding bundle", detail: "Dialogue state, catalog facts, and verified external facts when available" },
          { label: "Candidate generation", detail: "One response or several sampled alternatives" },
          { label: "Quality control", detail: "Selection, verification, critique, repair, or polishing" },
          { label: "Final response", detail: "Grounded explanation with the selected track preserved" },
        ],
      }),
      slide("grounding-heatmap", "What grounded each response", "visual", ["response_matrix"], {
        visualKind: "comparison",
        takeaway: "Grounding strength depended on which facts reached generation and which claims were independently checkable.",
        columns: ["Candidates", "Grounding", "Selection / repair"],
        common: "All five systems generated response prose after recommendation IDs were selected.",
        different: "Candidate count alone was not the distinction; independent checking, selection, and repair determined whether alternatives added control.",
        teams: [
          { name: "npatta01", values: ["One response", "Latest state and selected-track metadata", "No independent selector, critic, or fact checker documented"], status: "limit" },
          { name: "volart", values: ["Three temperature-diverse candidates", "Selected IDs remain fixed", "Independent critic, selective rewrite, hardening, lexical pass"], status: "verified" },
          { name: "niwatori", values: ["Ten seeded candidates", "Selected track and conversation context", "Lexical-diversity selector chooses a whole record; not a factual critic"], status: "verified" },
          { name: "swyoo", values: ["Deterministic PAS proposals plus one PAS prediction", "Catalog/crawl facts and legal title pool", "Validate and repair themes/citations; no best-of-N critic"], status: "verified" },
          { name: "team2_s2", values: ["First-pass response then refinement", "Verified track-fact bundle", "Second Gemini Pro polishing pass"], status: "verified" },
        ],
      }),
      slide("control-heatmap", "How each response was selected, checked, or repaired", "visual", [], {
        visualKind: "comparison",
        takeaway: "Multiple drafts add control only when a documented selector, verifier, critic, or repair pass decides what survives.",
      }),
      slide("tradeoffs", "Generation, selection, repair, and trade-offs", "audit", ["response_walkthroughs", "response_tradeoffs"]),
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
  ["query/comparison", "query/query-matrix"], ["query/data-knowledge", "query/data-matrix"], ["query/query-glossary", "query/lifecycle"],
  ["retrieval/retrievers", "retrieval/retriever-matrix"], ["retrieval/features", "retrieval/feature-glossary"], ["retrieval/feature-audit", "retrieval/feature-inventories"],
  ["response/pipelines", "response/overview"], ["response/author-volart", "response/tradeoffs"], ["response/niwatori-swyoo", "response/tradeoffs"], ["response/team2", "response/tradeoffs"],
  ["ours/system", "ours/cover"], ["ours/strengths", "ours/what-worked"],
  ["leaders/index", "leaders/cover"], ["leaders/volart", "leaders/volart-outcome"], ["leaders/niwatori", "leaders/niwatori-outcome"], ["leaders/swyoo", "leaders/swyoo-outcome"], ["leaders/team2", "leaders/team2-outcome"],
  ["synthesis/cross-team", "synthesis/cover"], ["synthesis/acknowledgements", "synthesis/lessons"], ["synthesis/caveats-evidence", "synthesis/evidence"],
  ["response/matrix", "response/grounding-heatmap"], ["response/overview", "response/overview"], ["response/tradeoffs", "response/tradeoffs"], ["query/prompt-audit", "query/prompt-audit"], ["ours/walkthrough", "ours/walkthrough"], ["ours/evaluation-mistake", "ours/evaluation-mistake"], ["ours/contributors", "ours/contributors"], ["synthesis/choices", "synthesis/choices"], ["synthesis/lessons", "synthesis/lessons"],
]);

export const resolveSlug = (slug) => LEGACY_ALIASES.get(slug) || slug;

export const DISCLOSURES = {
  section_directory: "Open the original chapter outline",
  how_scoring_works: "Open the composite-score formula",
  leaderboard_table: "Open exact values and repository links",
  lifecycle_heading: "Open the source-backed lifecycle introduction",
  lifecycle_map: "Open the complete lifecycle map",
  lifecycle_takeaway: "Open the original lifecycle takeaway",
  query_heading: "Open the query-audit heading",
  query_explainer: "Open definitions, qualifications, and sources",
  query_matrix: "Open the complete five-team query matrix",
  query_evidence_details: "Open prompt excerpts and the reviewed file inventory",
  data_knowledge_heading: "Open the data-provenance heading",
  data_knowledge_glossary: "Open definitions and evidence boundaries",
  data_knowledge_matrix: "Open the complete data and model-knowledge matrix",
  data_knowledge_interpretation: "Open the complete provenance interpretation",
  retrieval_heading: "Open the retrieval-audit heading",
  retrieval_glossary: "Open definitions and the candidate-set boundary",
  retrieval_matrix: "Open the complete retrieval matrix",
  feature_matrix: "Open the complete feature-family matrix",
  feature_details: "Open the per-team feature inventories",
  response_heading: "Open the response-audit heading",
  response_explainer: "Open the complete response-system explanation",
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
.deck-slide{min-height:100%;padding:clamp(20px,3vw,46px) clamp(78px,7vw,104px) clamp(20px,3vw,46px) clamp(16px,3vw,44px);scroll-snap-align:start;scroll-margin-top:12px}
.deck-slide-inner{width:min(1520px,100%);margin:0 auto;display:grid;gap:clamp(16px,2vw,28px)}
.deck-slide-heading{margin:0;font-size:clamp(22px,3vw,38px);line-height:1.12}.deck-question{margin:0;color:var(--portable-muted)}
.deck-page-copy{display:grid;min-width:0;align-content:center;gap:12px;max-width:78ch}.deck-page-copy .deck-slide-heading{font-size:clamp(30px,4vw,58px)}
.deck-visual{min-width:0;margin:0;border:1px solid color-mix(in srgb,var(--portable-border) 74%,transparent);border-radius:clamp(16px,2vw,28px);overflow:hidden;background:#101216;box-shadow:0 28px 80px rgba(0,0,0,.2)}
.deck-visual img{display:block;width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}
.deck-slide--cover .deck-slide-inner{grid-template-columns:minmax(400px,.9fr) minmax(0,2fr);align-items:center;min-height:calc(100dvh - 190px)}
.deck-slide--cover .deck-page-copy{grid-column:1;grid-row:1}
.deck-slide--cover .deck-slide-heading{max-width:100%;font-size:clamp(42px,5vw,72px);letter-spacing:-.045em;overflow-wrap:normal}.deck-slide--cover .deck-question{font-size:clamp(16px,1.6vw,22px);line-height:1.5}
.deck-chapter-map{grid-column:2;grid-row:1;display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:0;padding:0;list-style:none;counter-reset:chapter-page}
.deck-chapter-map li{display:grid;grid-template-columns:auto 1fr;gap:10px;align-items:start;min-height:78px;padding:14px;border:1px solid var(--portable-border);border-radius:14px;background:linear-gradient(145deg,color-mix(in srgb,var(--portable-accent) 9%,var(--portable-surface)),var(--portable-surface));counter-increment:chapter-page}
.deck-chapter-map li::before{content:counter(chapter-page);display:grid;place-items:center;width:28px;height:28px;border-radius:999px;background:var(--portable-accent);color:#fff;font-size:12px;font-weight:800}.deck-chapter-map span{font-weight:700;line-height:1.3}
.deck-flow{display:grid;gap:18px}.deck-flow-lane{display:grid;gap:10px;padding:16px;border:1px solid var(--portable-border);border-radius:16px;background:var(--portable-surface)}.deck-flow-lane h3{margin:0;font-size:16px}.deck-flow-lane ol{display:grid;grid-template-columns:repeat(var(--flow-count),minmax(0,1fr));gap:24px;margin:0;padding:0;list-style:none;counter-reset:flow-step}.deck-flow-step{position:relative;min-width:0;padding:13px;border:1px solid color-mix(in srgb,var(--portable-accent) 38%,var(--portable-border));border-radius:12px;background:color-mix(in srgb,var(--portable-accent) 7%,var(--portable-surface));overflow-wrap:anywhere;counter-increment:flow-step}.deck-flow-step::before{content:counter(flow-step);display:block;margin-bottom:6px;color:var(--portable-accent);font-size:12px;font-weight:850}.deck-flow-step:not(:last-child)::after{content:"→";position:absolute;top:50%;right:-19px;color:var(--portable-accent);font-size:20px;font-weight:900;transform:translateY(-50%)}
.deck-flow-only .deck-slide-inner{min-height:calc(100dvh - 190px);grid-template-rows:auto minmax(0,1fr)}.deck-flow-only .deck-flow{align-self:center}.deck-flow-only .deck-flow-step{display:grid;min-height:128px;align-content:center;font-size:clamp(15px,1.2vw,18px);line-height:1.4}
.deck-mechanism{display:grid;gap:22px;align-self:center}.deck-mechanism-stages{display:grid;grid-template-columns:repeat(var(--stage-count),minmax(0,1fr));gap:26px;margin:0;padding:0;list-style:none;counter-reset:mechanism-stage}.deck-mechanism-stage{position:relative;display:grid;align-content:center;min-height:150px;padding:18px;border:1px solid var(--portable-border);border-top:5px solid var(--stage-color);border-radius:14px;background:var(--portable-surface);counter-increment:mechanism-stage}.deck-mechanism-stage::before{content:counter(mechanism-stage);margin-bottom:10px;color:var(--stage-color);font-size:13px;font-weight:900}.deck-mechanism-stage:not(:last-child)::after{content:"→";position:absolute;top:50%;right:-21px;color:var(--portable-accent);font-size:22px;font-weight:900;transform:translateY(-50%)}.deck-mechanism-stage h3{margin:0 0 8px;font-size:clamp(16px,1.35vw,20px)}.deck-mechanism-stage p{margin:0;color:var(--portable-muted);font-size:14px;line-height:1.5}.deck-takeaway{margin:0;padding:14px 18px;border-left:5px solid #d89a2b;border-radius:10px;background:color-mix(in srgb,#d89a2b 10%,var(--portable-surface));font-size:clamp(15px,1.15vw,18px);line-height:1.5}.deck-takeaway strong{display:block;margin-bottom:3px;color:#a96f09;font-size:12px;letter-spacing:.05em;text-transform:uppercase}
.deck-comparison{display:grid;gap:10px}.deck-comparison-columns,.deck-team-row{display:grid;grid-template-columns:minmax(115px,.55fr) repeat(3,minmax(0,1fr));gap:14px}.deck-comparison-columns{padding:0 16px;color:var(--portable-muted);font-size:11px;font-weight:800;letter-spacing:.04em;text-transform:uppercase}.deck-team-row{padding:14px 16px;border:1px solid var(--portable-border);border-left:5px solid var(--team-color);border-radius:12px;background:var(--portable-surface)}.deck-team-row h3{margin:0;font-size:16px}.deck-team-value{display:grid;gap:4px;color:var(--portable-muted);font-size:13px;line-height:1.42}.deck-team-value::before{content:attr(data-label);display:none;color:var(--portable-ink);font-size:10px;font-weight:800;letter-spacing:.04em;text-transform:uppercase}.deck-team-status{display:inline-flex;width:max-content;margin-top:7px;padding:3px 8px;border:1px solid currentColor;border-radius:999px;color:var(--portable-muted);font-size:10px;font-weight:800;text-transform:uppercase}.deck-team-status--verified{color:#19724d}.deck-team-status--external{color:#176e9e}.deck-team-status--limit{color:#9a6810}.deck-common-different{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:6px}.deck-synthesis-card{padding:14px 16px;border-left:5px solid var(--synthesis-color);border-radius:11px;background:var(--portable-surface);font-size:14px;line-height:1.5}.deck-synthesis-card strong{display:block;margin-bottom:4px;color:var(--portable-ink)}
.deck-scoreboard{display:grid;align-self:start;grid-auto-rows:max-content;gap:6px;overflow-x:auto}.deck-score-header,.deck-score-row{display:grid;grid-template-columns:34px minmax(125px,1.25fr) minmax(130px,1fr) repeat(4,minmax(76px,.62fr));gap:12px;align-items:center;min-width:820px}.deck-score-header{padding:0 14px 5px;color:var(--portable-muted);font-size:10px;font-weight:800;letter-spacing:.04em;text-transform:uppercase}.deck-score-row{min-height:58px;padding:9px 14px;border:1px solid var(--portable-border);border-left:5px solid var(--score-color);border-radius:11px;background:var(--portable-surface)}.deck-score-rank{font-size:12px;font-weight:900}.deck-score-team{font-size:16px;font-weight:850}.deck-score-value{font-variant-numeric:tabular-nums;text-align:right}.deck-score-composite{position:relative;isolation:isolate;padding:7px 9px;border-radius:7px;overflow:hidden;text-align:right}.deck-score-composite::before{position:absolute;z-index:-1;inset:0 auto 0 0;width:var(--score-width);background:color-mix(in srgb,var(--score-color) 28%,transparent);content:""}
.deck-slide--story .deck-slide-inner{gap:clamp(24px,3vw,40px)}.deck-slide.deck-slide--story .portable-markdown{width:100%;max-width:1120px;font-size:clamp(17px,1.35vw,20px);line-height:1.65}.deck-slide--story .portable-markdown p{margin-block:0 1.15em}.deck-slide--story .portable-markdown a{font-weight:650}.deck-slide--story .portable-page-header,.deck-slide--story .portable-content-card{width:100%;max-width:1120px}.deck-slide--story .deck-question{font-size:clamp(15px,1.15vw,18px)}
.deck-slide--visual .deck-visual{max-width:1100px}.deck-slide--matrix .portable-content-card,.deck-slide--audit .portable-content-card{width:100%;max-width:none}
.deck-slide--matrix table{width:100%;table-layout:auto}.deck-slide--matrix th,.deck-slide--matrix td{white-space:normal;overflow-wrap:anywhere;vertical-align:top}
[id="synthesis/matrix"] [data-artifact-block-id],[id="synthesis/matrix"] .portable-content-card,[id="synthesis/matrix"] .portable-markdown,[id="synthesis/matrix"] .portable-table-scroll{width:100%;max-width:none}[id="synthesis/matrix"] table{table-layout:fixed}
.deck-slide--matrix .portable-table-scroll:has(.deck-prose-matrix){overflow:visible;border:0}.deck-prose-matrix{display:block!important;width:100%;font-size:14px!important}.deck-prose-matrix thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}.deck-prose-matrix tbody{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.deck-prose-matrix tbody tr{display:block;min-width:0;padding:4px 16px;border:1px solid var(--portable-border);border-radius:15px;background:var(--portable-surface)}.deck-prose-matrix tbody td{display:grid;grid-template-columns:minmax(130px,.34fr) minmax(0,1fr);gap:12px;width:100%;padding:11px 0;border-bottom:1px solid var(--portable-border);font-size:14px!important;line-height:1.45}.deck-prose-matrix tbody td:last-child{border-bottom:0}.deck-prose-matrix tbody td::before{content:attr(data-column-label);color:var(--portable-muted);font-size:11px;font-weight:750;letter-spacing:.035em;text-transform:uppercase}.deck-prose-matrix tbody td:first-child{font-weight:850;font-size:16px!important}.deck-prose-matrix tbody td:first-child::before{align-self:center}
.deck-embedded-document{display:block;width:100%;min-width:0;overflow:visible}.deck-embedded-document[hidden]{display:none}.portable-custom-html>iframe[hidden]{display:none!important}
.deck-slide .portable-page-header{position:static;width:auto;height:auto;min-height:0;margin:0;padding:0;border:0;background:transparent}
.deck-slide .portable-block-stack{display:contents}.deck-slide .portable-markdown{max-width:900px}
.deck-slide .portable-content-card,.deck-slide .portable-metric-card{box-shadow:none}
.deck-progressive .deck-slide-inner{grid-template-columns:1fr}.deck-progressive [data-artifact-block-id]{display:contents}.deck-insight-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;width:100%}.deck-insight-card{min-width:0;border:1px solid var(--portable-border);border-radius:14px;background:var(--portable-surface);overflow:clip}.deck-insight-card>summary{display:grid;gap:7px;min-height:118px;padding:16px 18px;cursor:pointer;list-style:none}.deck-insight-card>summary::-webkit-details-marker{display:none}.deck-insight-title{color:var(--portable-accent);font-size:clamp(16px,1.25vw,19px);font-weight:850}.deck-insight-lede{color:var(--portable-muted);font-size:14px;line-height:1.45}.deck-insight-card>summary::after{content:"Open detail +";align-self:end;color:var(--portable-accent);font-size:12px;font-weight:800}.deck-insight-card[open]>summary::after{content:"Close detail −"}.deck-insight-detail{margin:0;padding:0 18px 18px;border-top:1px solid var(--portable-border);font-size:14px;line-height:1.55}.deck-insight-detail strong:first-child{display:none}.deck-progressive .portable-markdown{display:contents}.deck-progressive .portable-content-card{display:contents}.deck-status{font-weight:800;text-align:center}.deck-status::before{display:inline-block;min-width:112px;padding:5px 10px;border:1px solid currentColor;border-radius:999px}.deck-status--yes{color:#19724d}.deck-status--yes::before{content:"Yes";background:color-mix(in srgb,#15945b 16%,transparent)}.deck-status--partial{color:#8b5b08}.deck-status--partial::before{content:"Partial";background:color-mix(in srgb,#c98612 16%,transparent)}.deck-status--missing{color:var(--portable-muted)}.deck-status--missing::before{content:"Not documented";background:color-mix(in srgb,var(--portable-muted) 10%,transparent)}.deck-status-label{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.deck-disclosure{border:1px solid var(--portable-border);border-radius:12px;background:var(--portable-surface);overflow:clip}
.deck-disclosure>summary{min-height:48px;padding:14px 18px;cursor:pointer;color:var(--portable-accent);font-weight:700}
.deck-disclosure:not([open])>:not(summary){display:none!important}
.deck-disclosure>[data-artifact-block-id]{border:0;border-radius:0}
.deck-source-list{margin-top:18px}.deck-source-list>.deck-disclosure{width:100%}#data-analytics-portable-fallback>.portable-sources,.deck-source-list>.portable-sources{display:block!important}
.deck-jump{position:fixed;inset:0;z-index:50;display:none;place-items:center;padding:20px;background:rgba(15,23,42,.72)}
.deck-jump[data-open="true"]{display:grid}.deck-jump-panel{width:min(720px,100%);max-height:min(720px,88dvh);overflow:auto;padding:18px;border:1px solid var(--portable-border);border-radius:16px;background:var(--portable-surface)}
.deck-jump-input{width:100%;min-height:46px;padding:10px 12px;border:1px solid var(--portable-border);border-radius:9px;background:var(--portable-canvas);color:var(--portable-ink)}
.deck-jump-list{display:grid;gap:8px;margin-top:12px}.deck-jump-item{width:100%;min-height:48px;padding:10px 12px;border:0;border-radius:9px;background:var(--portable-surface-subtle);color:var(--portable-ink);text-align:left;cursor:pointer}
.deck-live,.deck-skip{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}.deck-skip:focus{position:fixed;top:8px;left:8px;z-index:80;width:auto;height:auto;clip:auto;padding:10px;background:var(--portable-surface)}
html[data-deck-view="linear"],html[data-deck-view="linear"] body{height:auto;overflow:auto}
html[data-deck-view="linear"] .retrospective-deck{height:auto;display:block}html[data-deck-view="linear"] .deck-track{display:block;overflow:visible}html[data-deck-view="linear"] .deck-chapter,html[data-deck-view="linear"] .deck-slide{height:auto;min-height:0}html[data-deck-view="linear"] .deck-vertical{height:auto;overflow:visible}html[data-deck-view="linear"] .deck-vertical-rail{display:none}html[data-deck-view="linear"] .deck-disclosure>summary{display:none}html[data-deck-view="linear"] .deck-disclosure>[data-artifact-block-id]{display:block!important}html[data-deck-view="linear"] .deck-insight-grid{display:block}html[data-deck-view="linear"] .deck-insight-card{border:0;background:transparent;overflow:visible}html[data-deck-view="linear"] .deck-insight-card>summary{display:none}html[data-deck-view="linear"] .deck-insight-detail{display:block!important;margin:0 0 1em;padding:0;border:0}html[data-deck-view="linear"] .deck-insight-detail strong:first-child{display:inline}
@media(max-width:1100px){.deck-slide--cover .deck-slide-inner{grid-template-columns:1fr;min-height:0}.deck-slide--cover .deck-page-copy,.deck-chapter-map{grid-column:1;grid-row:auto}.deck-flow-lane ol,.deck-mechanism-stages{grid-template-columns:1fr;gap:22px}.deck-flow-step:not(:last-child)::after,.deck-mechanism-stage:not(:last-child)::after{content:"↓";top:auto;right:auto;bottom:-22px;left:50%;transform:translateX(-50%)}.deck-mechanism-stage{min-height:112px}.deck-comparison-columns{display:none}.deck-team-row{grid-template-columns:minmax(110px,.45fr) repeat(3,minmax(0,1fr))}.deck-prose-matrix tbody,.deck-insight-grid{grid-template-columns:1fr}.deck-flow-only .deck-slide-inner{min-height:0}}
@media(max-width:700px){.deck-title,.deck-breadcrumb,.deck-progress,.deck-axis-help,.deck-chapter-rail{display:none}.deck-mobile-orientation{display:block;min-width:0;margin-right:auto;overflow:hidden;font-weight:650;text-overflow:ellipsis;white-space:nowrap}.deck-topbar,.deck-footer{min-height:60px;padding:8px 10px}.deck-slide{padding:18px 12px}.deck-vertical-rail{display:none}.portable-table-scroll{max-width:calc(100vw - 24px)}.deck-button{min-width:48px;min-height:48px}.deck-slide--cover .deck-slide-heading{font-size:clamp(36px,13vw,58px)}.deck-team-row,.deck-common-different{grid-template-columns:1fr}.deck-team-value::before{display:block}.deck-slide--matrix .portable-table-scroll{overflow-x:auto}.deck-slide--matrix .portable-table-scroll:has(.deck-prose-matrix){overflow:visible}.deck-prose-matrix tbody td{grid-template-columns:1fr;gap:4px}.deck-slide--audit .portable-markdown{columns:1}}
@media(prefers-reduced-motion:reduce){.deck-track,.deck-vertical{scroll-behavior:auto!important}}
@media(forced-colors:active){.deck-button,.deck-chapter-button,.deck-rail-button,.deck-disclosure,.deck-jump-panel{border:1px solid CanvasText}}
@media print{html,body{height:auto!important;overflow:visible!important}.deck-chrome,.deck-jump,.deck-skip,.deck-live,.deck-vertical-rail{display:none!important}.retrospective-deck,.deck-track,.deck-chapter,.deck-vertical,.deck-slide{display:block!important;height:auto!important;min-height:0!important;overflow:visible!important;scroll-snap-type:none!important}.deck-disclosure>summary{display:none!important}.deck-disclosure>[data-artifact-block-id],.deck-disclosure:not([open])>*:not(summary){display:block!important}.deck-insight-grid{display:block!important}.deck-insight-card{display:block!important;border:0!important;background:transparent!important;overflow:visible!important}.deck-insight-card>summary{display:none!important}.deck-insight-detail{display:block!important;margin:0 0 1em!important;padding:0!important;border:0!important}.deck-insight-detail strong:first-child{display:inline!important}}
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
  const disclosure = (node, label) => {
    if (!label) return node;
    const details = document.createElement("details");
    details.className = "deck-disclosure";
    details.dataset.disclosureFor = node.dataset.artifactBlockId;
    const summary = document.createElement("summary");
    summary.textContent = label;
    details.append(summary, node);
    return details;
  };
  const stageColors = ["#58aaf7", "#8570e6", "#24a88b", "#d89a2b", "#df7aa9"];
  const teamColors = ["#58aaf7", "#8570e6", "#24a88b", "#df7aa9", "#e28d43"];
  const renderMechanism = (entry) => {
    const section = document.createElement("section");
    section.className = "deck-mechanism";
    section.setAttribute("aria-label", `${entry.title} mechanism`);
    const stages = document.createElement("ol");
    stages.className = "deck-mechanism-stages";
    stages.style.setProperty("--stage-count", String(entry.stages.length));
    entry.stages.forEach((stage, index) => {
      const item = document.createElement("li");
      item.className = "deck-mechanism-stage";
      item.style.setProperty("--stage-color", stageColors[index % stageColors.length]);
      const title = document.createElement("h3");
      title.textContent = stage.label;
      const detail = document.createElement("p");
      detail.textContent = stage.detail;
      item.append(title, detail);
      stages.append(item);
    });
    const takeaway = document.createElement("p");
    takeaway.className = "deck-takeaway";
    const label = document.createElement("strong");
    label.textContent = "Takeaway";
    takeaway.append(label, document.createTextNode(entry.takeaway));
    section.append(stages, takeaway);
    return section;
  };
  const renderComparison = (entry) => {
    const section = document.createElement("section");
    section.className = "deck-comparison";
    section.setAttribute("aria-label", `${entry.title} team comparison`);
    const columns = document.createElement("div");
    columns.className = "deck-comparison-columns";
    columns.append(document.createElement("span"));
    entry.columns.forEach((column) => {
      const label = document.createElement("span");
      label.textContent = column;
      columns.append(label);
    });
    section.append(columns);
    entry.teams.forEach((team, index) => {
      const row = document.createElement("article");
      row.className = "deck-team-row";
      row.style.setProperty("--team-color", teamColors[index % teamColors.length]);
      const identity = document.createElement("div");
      const name = document.createElement("h3");
      name.textContent = team.name;
      identity.append(name);
      if (team.status) {
        const status = document.createElement("span");
        status.className = `deck-team-status deck-team-status--${team.status}`;
        status.textContent = team.status === "limit" ? "Limit" : team.status === "external" ? "External data" : "Verified path";
        identity.append(status);
      }
      row.append(identity);
      team.values.forEach((value, valueIndex) => {
        const cell = document.createElement("span");
        cell.className = "deck-team-value";
        cell.dataset.label = entry.columns[valueIndex];
        cell.textContent = value;
        row.append(cell);
      });
      section.append(row);
    });
    const synthesis = document.createElement("div");
    synthesis.className = "deck-common-different";
    [["Common", entry.common, "#24a88b"], ["Different", entry.different, "#d89a2b"]].forEach(([title, text, color]) => {
      const card = document.createElement("div");
      card.className = "deck-synthesis-card";
      card.style.setProperty("--synthesis-color", color);
      const heading = document.createElement("strong");
      heading.textContent = title;
      card.append(heading, document.createTextNode(text));
      synthesis.append(card);
    });
    section.append(synthesis);
    return section;
  };

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
      if (entry.lanes?.length && entry.blocks.length === 0) slideNode.classList.add("deck-flow-only");
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
      if (entry.visualKind === "mechanism") inner.append(renderMechanism(entry));
      if (entry.visualKind === "comparison") inner.append(renderComparison(entry));
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

  app.querySelectorAll(".deck-slide--matrix table").forEach((table) => {
    const headers = [...table.querySelectorAll("thead th")].map((header) => header.textContent.trim());
    const cells = [...table.querySelectorAll("tbody td")];
    const averageCellLength = cells.length ? cells.reduce((total, cell) => total + cell.textContent.trim().length, 0) / cells.length : 0;
    if (headers.length < 4 || averageCellLength < 45) return;
    table.classList.add("deck-prose-matrix");
    table.querySelectorAll("tbody tr").forEach((row) => {
      [...row.children].forEach((cell, index) => { cell.dataset.columnLabel = headers[index] || `Column ${index + 1}`; });
    });
  });

  const leaderboardDetails = document.querySelector('[id="outcome/leaderboard-table"] details[data-disclosure-for="leaderboard_table"]');
  const leaderboardTable = leaderboardDetails?.querySelector("table");
  if (leaderboardDetails && leaderboardTable) {
    const numericText = (cell) => cell.textContent.trim().match(/^-?\d+(?:\.\d+)?/)?.[0] || "—";
    const rows = [...leaderboardTable.querySelectorAll("tbody tr")].map((row) => {
      const cells = [...row.cells];
      return [cells[0].textContent.trim(), cells[1].textContent.trim(), ...cells.slice(2, 7).map(numericText)];
    });
    const composites = rows.map((row) => Number.parseFloat(row[2])).filter(Number.isFinite);
    const maximum = Math.max(...composites, 1);
    const scoreboard = document.createElement("section");
    scoreboard.className = "deck-scoreboard";
    scoreboard.setAttribute("aria-label", "Compact official leaderboard");
    const header = document.createElement("div");
    header.className = "deck-score-header";
    ["Rank", "Team", "Composite", "nDCG@20", "Catalog", "Lexical", "LLM /5"].forEach((text) => {
      const label = document.createElement("span");
      label.textContent = text;
      header.append(label);
    });
    scoreboard.append(header);
    rows.forEach((values, index) => {
      const row = document.createElement("article");
      row.className = "deck-score-row";
      row.style.setProperty("--score-color", teamColors[index % teamColors.length]);
      row.setAttribute("aria-label", `${index + 1}. ${values[0]}, composite ${values[2]}`);
      const rank = document.createElement("span");
      rank.className = "deck-score-rank";
      rank.textContent = String(index + 1);
      const team = document.createElement("span");
      team.className = "deck-score-team";
      team.textContent = values[0];
      const composite = document.createElement("span");
      composite.className = "deck-score-value deck-score-composite";
      composite.style.setProperty("--score-width", `${(Number.parseFloat(values[2]) / maximum) * 100}%`);
      composite.textContent = values[2];
      row.append(rank, team, composite);
      values.slice(3, 7).forEach((value) => {
        const metric = document.createElement("span");
        metric.className = "deck-score-value";
        metric.textContent = value;
        row.append(metric);
      });
      scoreboard.append(row);
    });
    leaderboardDetails.before(scoreboard);
  }

  const progressiveSlides = [
    "ours/walkthrough",
    "leaders/volart-response",
    "leaders/niwatori-response",
    "leaders/swyoo-response",
    "leaders/team2-response",
  ];
  progressiveSlides.forEach((slug) => {
    const slideNode = document.getElementById(slug);
    const inner = slideNode?.querySelector(":scope > .deck-slide-inner");
    if (!slideNode || !inner) return;
    const paragraphs = [...slideNode.querySelectorAll("[data-artifact-block-id] .portable-markdown > p")]
      .filter((paragraph) => paragraph.querySelector(":scope > strong:first-child"));
    if (paragraphs.length < 3) return;
    slideNode.classList.add("deck-progressive");
    const grid = document.createElement("section");
    grid.className = "deck-insight-grid";
    grid.setAttribute("aria-label", `${slideNode.querySelector(".deck-slide-heading")?.textContent || "System"} detail cards`);
    paragraphs.forEach((paragraph) => {
      const strong = paragraph.querySelector(":scope > strong:first-child");
      const title = strong.textContent.trim().replace(/[.:]$/, "");
      const remainder = paragraph.textContent.slice(strong.textContent.length).trim();
      const sentence = remainder.match(/^.*?[.!?](?:\s|$)/)?.[0]?.trim() || remainder;
      const card = document.createElement("details");
      card.className = "deck-insight-card";
      const summary = document.createElement("summary");
      const titleNode = document.createElement("span");
      titleNode.className = "deck-insight-title";
      titleNode.textContent = title;
      const lede = document.createElement("span");
      lede.className = "deck-insight-lede";
      lede.textContent = sentence;
      summary.append(titleNode, lede);
      paragraph.classList.add("deck-insight-detail");
      card.append(summary, paragraph);
      grid.append(card);
    });
    const evidenceAnchor = [...inner.children].find((child) => (
      child.matches("[data-artifact-block-id]") || child.querySelector("[data-artifact-block-id]")
    ));
    inner.insertBefore(grid, evidenceAnchor || null);
  });

  document.querySelectorAll("#synthesis\\/matrix tbody td").forEach((cell) => {
    const value = cell.textContent.trim().toLowerCase();
    const variant = value === "yes" ? "yes" : value === "partial" ? "partial" : value === "not documented" ? "missing" : null;
    if (variant) {
      const label = document.createElement("span");
      label.className = "deck-status-label";
      label.textContent = cell.textContent.trim();
      cell.replaceChildren(label);
      cell.classList.add("deck-status", `deck-status--${variant}`);
    }
  });

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
      style.textContent = `${sourceCss}\n:host{display:block;min-width:0;color:CanvasText;background:Canvas;font:14px/1.5 system-ui,sans-serif}.deck-embedded-root{min-width:0;overflow:visible}*,*::before,*::after{box-sizing:border-box;max-width:100%}img,svg{height:auto}section,div,article,details{overflow:visible!important}table{width:100%!important;table-layout:fixed!important;border-collapse:collapse}th,td{min-width:0!important;white-space:normal!important;overflow-wrap:anywhere!important;word-break:normal!important;vertical-align:top}pre,code{white-space:pre-wrap;overflow-wrap:anywhere}.state-contract ul{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:10px 0;padding:0;list-style:none}.state-contract li{padding:12px;border:1px solid color-mix(in srgb,CanvasText 18%,Canvas);border-radius:10px;background:color-mix(in srgb,#1687ff 7%,Canvas)}.state-contract li strong{display:block;margin-bottom:4px;color:#0877da}@media(max-width:900px){.state-contract ul{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:700px){table{font-size:12px!important}th,td{padding:7px!important}.state-contract ul{grid-template-columns:1fr}}`;
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

  const disclosures = () => document.querySelectorAll("details.deck-disclosure,details.deck-insight-card");
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
