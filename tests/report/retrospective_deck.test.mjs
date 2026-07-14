import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  CHAPTERS,
  CONFIDENCE_LEVELS,
  CURATED_PATH,
  DIAGNOSIS_SLIDES,
  LEGACY_ALIASES,
  PAGE_ARCHETYPES,
  enhanceHtml,
  resolveSlug,
  stripDeckInjection,
  validateChapterMap,
} from "../../scripts/report/retrospective_deck.mjs";

const REPORT = new URL("../../retrospective.html", import.meta.url);
const payload = (html) =>
  html.match(/<template id="data-analytics-portable-artifact-payload-source"[\s\S]*?<\/template>/)?.[0];
const blockIds = (html) =>
  [...html.matchAll(/data-artifact-block-id="([^"]+)"/g)].map((match) => match[1]);
const hrefs = (html) =>
  [...html.matchAll(/<a\b[^>]*href="([^"]+)"/g)].map((match) => match[1]).sort();
const srcdocs = (html) =>
  [...html.matchAll(/\bsrcdoc="([^"]*)"/g)].map((match) => match[1]);

test("chapter map assigns all 74 report blocks exactly once", async () => {
  const html = await readFile(REPORT, "utf8");
  const result = validateChapterMap(CHAPTERS, stripDeckInjection(html));
  assert.equal(result.reportIds.length, 74);
  assert.deepEqual(result.mappedIds.sort(), result.reportIds.sort());
});

test("answer-first order puts diagnosis directly after outcome", () => {
  assert.deepEqual(CHAPTERS.slice(0, 3).map(({ slug }) => slug), ["outcome", "diagnosis", "ours"]);
  assert.equal(CHAPTERS.find(({ slug }) => slug === "diagnosis").slides.length, 6);
  assert.deepEqual(
    DIAGNOSIS_SLIDES.map(({ slug }) => slug),
    ["score-location", "information-loss", "constraint-wiring", "features-seen", "evidence-missed", "confidence"],
  );
});

test("answer-first deck keeps a complete content-aware chapter map", async () => {
  const html = await readFile(REPORT, "utf8");
  const result = validateChapterMap(CHAPTERS, stripDeckInjection(html));
  assert.equal(CHAPTERS.length, 8);
  assert.equal(result.pageCount, 57);
  assert.deepEqual(result.chapterCounts, [6, 6, 7, 7, 7, 5, 13, 6]);
  assert.equal(result.mappedIds.length, 74);
});

test("diagnosis copy preserves evidence boundaries", () => {
  const copy = JSON.stringify(DIAGNOSIS_SLIDES);
  const connections = DIAGNOSIS_SLIDES.find(({ slug }) => slug === "constraint-wiring").connections;
  assert.match(copy, /rich extraction, uneven execution/i);
  assert.match(copy, /grounded and reused/i);
  assert.match(copy, /direct track co-occurrence/i);
  assert.match(copy, /sequential|Markov|transition/i);
  assert.match(copy, /b1_cos.*feature/i);
  assert.doesNotMatch(copy, /did not convert conversation into constraints/i);
  assert.doesNotMatch(copy, /did not use LLM world knowledge/i);
  assert.ok(connections.length >= 3);
  assert.ok(connections.every(({ from, to, confidence }) => from && to && CONFIDENCE_LEVELS.has(confidence)));
  assert.deepEqual([...CONFIDENCE_LEVELS], ["verified", "likely", "unknown"]);
});

test("every diagnosis claim-bearing field carries confidence metadata", () => {
  for (const entry of DIAGNOSIS_SLIDES) {
    if (entry.takeaway) {
      assert.equal(typeof entry.takeaway.text, "string", `${entry.slug} takeaway has text`);
      assert.ok(CONFIDENCE_LEVELS.has(entry.takeaway.confidence), `${entry.slug} takeaway has confidence`);
    }

    for (const field of ["losses", "connections"]) {
      for (const claim of entry[field] ?? []) {
        assert.ok(CONFIDENCE_LEVELS.has(claim.confidence), `${entry.slug} ${field} claim has confidence`);
      }
    }

    if (entry.confidence) {
      assert.deepEqual(Object.keys(entry.confidence).sort(), [...CONFIDENCE_LEVELS].sort());
      for (const [confidence, claims] of Object.entries(entry.confidence)) {
        assert.ok(CONFIDENCE_LEVELS.has(confidence));
        assert.ok(claims.length > 0 && claims.every((claim) => typeof claim === "string" && claim.length > 0));
      }
    }
  }
});

test("curated path is short, answer-first, and references canonical slides", () => {
  const allSlugs = new Set(CHAPTERS.flatMap((chapter) => chapter.slides.map((entry) => `${chapter.slug}/${entry.slug}`)));
  assert.ok(CURATED_PATH.length >= 12 && CURATED_PATH.length <= 15);
  assert.equal(CURATED_PATH[0], "outcome/executive-answer");
  assert.equal(CURATED_PATH[1], "outcome/gap-chart");
  assert.equal(CURATED_PATH[2], "diagnosis/score-location");
  assert.ok(CURATED_PATH.every((slug) => allSlugs.has(slug)));
});

test("synthesis decoder makes compressed matrix terms concrete", () => {
  const synthesis = CHAPTERS.find(({ slug }) => slug === "synthesis");
  const matrixIndex = synthesis.slides.findIndex(({ slug }) => slug === "matrix");
  const decoder = synthesis.slides[matrixIndex + 1];
  assert.equal(decoder.slug, "decoder");
  assert.equal(decoder.visualKind, "matrix-decoder");
  assert.equal(decoder.concepts.length, 3);
  const copy = JSON.stringify(decoder);
  for (const phrase of [
    "direct track co-occurrence",
    "Markov transition probability",
    "learned-retriever",
    "generated-description similarity",
    "up to 500 hits from each traced branch",
    "LightGBM",
    "verified fact bundle",
    "checker or repair",
  ]) assert.match(copy, new RegExp(phrase, "i"));
  assert.doesNotMatch(copy, /RRF.{0,80}LightGBM|LightGBM.{0,80}RRF/i);
  assert.ok(CURATED_PATH.includes("synthesis/decoder"));
  assert.ok(CURATED_PATH.indexOf("synthesis/decoder") < CURATED_PATH.indexOf("synthesis/lessons"));
});

test("enhancement injects the curated path as navigation metadata", async () => {
  const html = stripDeckInjection(await readFile(REPORT, "utf8"));
  const enhanced = enhanceHtml(html);
  const encodedPath = JSON.stringify(CURATED_PATH).replaceAll("<", "\\u003c");
  assert.ok(enhanced.includes(`"curatedPath":${encodedPath}`));
  assert.match(enhanced, /currentReadingPath/);
  assert.match(enhanced, /setReadingPath/);
});

test("visual-first manifest has at least fifty content-aware pages", async () => {
  const html = await readFile(REPORT, "utf8");
  const result = validateChapterMap(CHAPTERS, stripDeckInjection(html));
  assert.equal(CHAPTERS.length, 8);
  assert.equal(result.pageCount, 57);
  assert.deepEqual(result.chapterCounts, [6, 6, 7, 7, 7, 5, 13, 6]);
  for (const chapter of CHAPTERS) {
    for (const entry of chapter.slides) {
      assert.ok(PAGE_ARCHETYPES.has(entry.archetype), `${chapter.slug}/${entry.slug} has a known archetype`);
    }
  }
});

test("legacy slide hashes resolve to canonical split pages", () => {
  assert.ok(LEGACY_ALIASES.size >= 20);
  assert.equal(resolveSlug("outcome/summary"), "outcome/cover");
  assert.equal(resolveSlug("leaders/volart"), "leaders/volart-outcome");
  assert.equal(resolveSlug("query/query-glossary"), "query/lifecycle");
  assert.equal(resolveSlug("response/matrix"), "response/grounding-heatmap");
  assert.equal(resolveSlug("response/author-volart"), "response/tradeoffs");
  assert.equal(resolveSlug("response/niwatori-swyoo"), "response/tradeoffs");
  assert.equal(resolveSlug("response/team2"), "response/tradeoffs");
  assert.equal(resolveSlug("unknown/page"), "unknown/page");
});

test("enhancement uses structured explanatory flows instead of decorative raster art", async () => {
  const html = stripDeckInjection(await readFile(REPORT, "utf8"));
  const enhanced = enhanceHtml(html);
  assert.equal((enhanced.match(/data:image\/webp;base64,/g) ?? []).length, 0);
  const flowPages = CHAPTERS.flatMap((chapter) => chapter.slides).filter((entry) => entry.lanes?.length || entry.visualKind === "mechanism");
  assert.ok(flowPages.length >= 5);
  assert.ok(flowPages.every((entry) => (
    entry.lanes?.every((lane) => lane.steps.length >= 2) ?? entry.stages.length >= 2
  )));
});

test("submitted inference lane distinguishes candidate assembly from LightGBM ranking", () => {
  const lane = CHAPTERS.find((chapter) => chapter.slug === "ours")
    .slides.find((entry) => entry.slug === "inference-rail").lanes[0];
  assert.equal(lane.steps.some((step) => /RRF/i.test(step)), false);
  assert.ok(lane.steps.some((step) => /each traced branch.*candidate union/i.test(step)));
  assert.ok(lane.steps.some((step) => /LightGBM|LambdaMART/i.test(step)));
});

test("dense comparison topics use teach-then-compare pairs", () => {
  const pairs = [
    ["query/lifecycle", "query/query-matrix"],
    ["query/data-glossary", "query/data-matrix"],
    ["retrieval/retriever-mechanism", "retrieval/retriever-matrix"],
    ["response/overview", "response/grounding-heatmap"],
  ];
  const pages = new Map(CHAPTERS.flatMap((chapter) => (
    chapter.slides.map((entry) => [`${chapter.slug}/${entry.slug}`, entry])
  )));
  for (const [mechanismSlug, comparisonSlug] of pairs) {
    assert.equal(pages.get(mechanismSlug)?.visualKind, "mechanism");
    assert.equal(pages.get(comparisonSlug)?.visualKind, "comparison");
    assert.ok(pages.get(comparisonSlug)?.teams?.length >= 4);
  }
});

test("submitted inference preserves the deployed candidate boundary and final ordering stage", () => {
  const lane = CHAPTERS.find((chapter) => chapter.slug === "ours")
    .slides.find((entry) => entry.slug === "inference-rail").lanes[0];
  const unionIndex = lane.steps.indexOf("Up to 500 hits from each traced branch → candidate union");
  const finalOrderIndex = lane.steps.findIndex((step) => /LightGBM.*reorders the union/i.test(step));
  assert.notEqual(unionIndex, -1);
  assert.ok(finalOrderIndex > unionIndex, "LightGBM remains the final-order stage after candidate union");
});

test("submitted-system copy uses the per-branch candidate boundary everywhere", async () => {
  const html = stripDeckInjection(await readFile(REPORT, "utf8"));
  const submitted = [
    JSON.stringify(CHAPTERS.find(({ slug }) => slug === "ours")),
    html.match(/data-artifact-block-id="own_system_diagram"[\s\S]*?data-artifact-block-id="own_system_walkthrough"/)?.[0] ?? "",
    html.match(/data-artifact-block-id="own_system_walkthrough"[\s\S]*?data-artifact-block-id="what_worked"/)?.[0] ?? "",
    html.match(/data-artifact-block-id="ranking_contributors"[\s\S]*?data-artifact-block-id="response_contributors"/)?.[0] ?? "",
    html.match(/data-artifact-block-id="retrospective_choices_table"[\s\S]*?data-artifact-block-id="future_competition_lessons"/)?.[0] ?? "",
  ].join("\n");
  assert.match(submitted, /up to (?:<strong>)?500(?:<\/strong>)? hits from each traced branch/i);
  assert.doesNotMatch(submitted, /up to (?:<strong>)?500(?:<\/strong>)? candidates from (?:that|the|a|each)? ?union/i);
  assert.doesNotMatch(submitted, /top-500 fused pool/i);
  assert.doesNotMatch(submitted, /fused top (?:<strong>)?500/i);
});

test("visual summaries preserve documented evidence boundaries", () => {
  const pages = new Map(CHAPTERS.flatMap((chapter) => (
    chapter.slides.map((entry) => [`${chapter.slug}/${entry.slug}`, entry])
  )));
  const team = (slug, name) => pages.get(slug).teams.find((entry) => entry.name === name).values.join(" ");
  assert.match(team("query/data-matrix", "niwatori"), /No LLM retrieval rewrite documented; ten response drafts/i);
  assert.doesNotMatch(team("query/data-matrix", "niwatori"), /generated query\/description/i);
  assert.match(team("retrieval/retriever-matrix", "swyoo"), /already-seen tracks.*no general hard rejection/i);
  assert.match(team("retrieval/retriever-matrix", "team2_s2"), /played-track exclusion.*explicit rejection.*not documented/i);
  assert.match(team("response/grounding-heatmap", "niwatori"), /lexical-diversity selector.*not a factual critic/i);
  assert.match(team("response/grounding-heatmap", "swyoo"), /one PAS prediction.*no best-of-N critic/i);
});

test("primary comparisons use evidence heatmaps, provenance stacks, and control lanes", () => {
  const pages = new Map(CHAPTERS.flatMap((chapter) => chapter.slides.map((entry) => [`${chapter.slug}/${entry.slug}`, entry])));
  assert.equal(pages.get("retrieval/evidence-heatmap").visualKind, "heatmap");
  assert.equal(pages.get("query/provenance-stacks").visualKind, "provenance");
  assert.equal(pages.get("response/control-heatmap").visualKind, "control-lanes");
});

test("enhancement is deterministic and idempotent", async () => {
  const html = await readFile(REPORT, "utf8");
  const once = enhanceHtml(html);
  const twice = enhanceHtml(once);
  assert.equal(twice, once);
  assert.equal((once.match(/retrospective-deck-style:start/g) ?? []).length, 1);
  assert.equal((once.match(/retrospective-deck-script:start/g) ?? []).length, 1);
});

test("enhancement preserves payload, blocks, links, and iframe documents", async () => {
  const html = stripDeckInjection(await readFile(REPORT, "utf8"));
  const enhanced = enhanceHtml(html);
  assert.equal(payload(enhanced), payload(html));
  assert.deepEqual(blockIds(enhanced), blockIds(html));
  assert.deepEqual(hrefs(enhanced), hrefs(html));
  assert.deepEqual(srcdocs(enhanced), srcdocs(html));
});

test("missing report block fails with its exact ID", async () => {
  const html = stripDeckInjection(await readFile(REPORT, "utf8"));
  const broken = html.replace('data-artifact-block-id="own_system_diagram"', 'data-artifact-block-id="removed"');
  assert.throws(
    () => validateChapterMap(CHAPTERS, broken),
    /missing configured block: own_system_diagram/,
  );
});

test("duplicate mapping fails before injection", async () => {
  const html = stripDeckInjection(await readFile(REPORT, "utf8"));
  const duplicate = structuredClone(CHAPTERS);
  duplicate[0].slides[0].blocks.push("executive_summary");
  assert.throws(
    () => validateChapterMap(duplicate, html),
    /duplicate configured block: executive_summary/,
  );
});
