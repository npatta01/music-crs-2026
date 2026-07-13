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
.deck-slide{min-height:100%;padding:clamp(18px,3vw,42px) clamp(16px,5vw,72px);scroll-snap-align:start;scroll-margin-top:12px}
.deck-slide-inner{width:min(1180px,100%);margin:0 auto;display:grid;gap:18px}
.deck-slide-heading{margin:0;font-size:clamp(22px,3vw,38px);line-height:1.12}.deck-question{margin:0;color:var(--portable-muted)}
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
@media(max-width:700px){.deck-title,.deck-breadcrumb,.deck-progress,.deck-axis-help,.deck-chapter-rail{display:none}.deck-mobile-orientation{display:block;min-width:0;margin-right:auto;overflow:hidden;font-weight:650;text-overflow:ellipsis;white-space:nowrap}.deck-topbar,.deck-footer{min-height:60px;padding:8px 10px}.deck-slide{padding:18px 12px}.deck-vertical-rail{display:none}.portable-table-scroll{max-width:calc(100vw - 24px)}.deck-button{min-width:48px;min-height:48px}}
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
      slideNode.className = "deck-slide";
      slideNode.id = `${chapter.slug}/${entry.slug}`;
      slideNode.dataset.slug = slideNode.id;
      slideNode.tabIndex = -1;
      slideNode.setAttribute("aria-labelledby", `${chapter.slug}-${entry.slug}-title`);
      const inner = document.createElement("div");
      inner.className = "deck-slide-inner";
      const heading = document.createElement("h2");
      heading.className = "deck-slide-heading";
      heading.id = `${chapter.slug}-${entry.slug}-title`;
      heading.textContent = entry.title;
      const question = document.createElement("p");
      question.className = "deck-question";
      question.textContent = chapter.question;
      inner.append(heading, question);
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

  const finalSlide = track.querySelector('[id="synthesis/caveats-evidence"] .deck-slide-inner');
  const sourceDetails = document.createElement("details");
  sourceDetails.className = "deck-disclosure deck-source-list";
  sourceDetails.innerHTML = "<summary>Open the complete source list</summary>";
  sourceDetails.append(sources);
  finalSlide.append(sourceDetails);
  app.append(skip, topbar, track, footer, live);
  stack.replaceWith(app);

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
    const dataKnowledge = document.getElementById("query/data-knowledge");
    const promptAudit = document.getElementById("query/prompt-audit");
    const vertical = dataKnowledge?.parentElement;
    if (!vertical || promptAudit?.parentElement !== vertical) return;
    if (enabled) vertical.insertBefore(promptAudit, dataKnowledge);
    else vertical.insertBefore(dataKnowledge, promptAudit);
  };

  const slides = CONFIG.chapters.flatMap((chapter, chapterIndex) => chapter.slides.map((entry, slideIndex) => ({
    chapter,
    entry,
    chapterIndex,
    slideIndex,
    slug: `${chapter.slug}/${entry.slug}`,
  })));
  const bySlug = new Map(slides.map((item) => [item.slug, item]));
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
    const cleanSlug = slug.split("?")[0];
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
  const initialSlug = initial.split("?")[0];
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
