import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  CHAPTERS,
  LEGACY_ALIASES,
  PAGE_ARCHETYPES,
  VISUALS,
  enhanceHtml,
  loadVisualDataUrls,
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

test("visual-first manifest has fifty content-aware pages", async () => {
  const html = await readFile(REPORT, "utf8");
  const result = validateChapterMap(CHAPTERS, stripDeckInjection(html));
  assert.equal(CHAPTERS.length, 7);
  assert.equal(result.pageCount, 50);
  assert.deepEqual(result.chapterCounts, [6, 7, 5, 7, 7, 13, 5]);
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
  assert.equal(resolveSlug("response/matrix"), "response/matrix");
  assert.equal(resolveSlug("unknown/page"), "unknown/page");
});

test("visual manifest embeds ten compact, alt-described WebP assets", async () => {
  const visualEntries = Object.entries(VISUALS);
  assert.equal(visualEntries.length, 10);
  assert.equal(new Set(visualEntries.map(([, visual]) => visual.path)).size, 10);
  assert.ok(visualEntries.every(([, visual]) => visual.alt.trim().length > 20));
  const dataUrls = await loadVisualDataUrls(new URL("../../", import.meta.url));
  assert.deepEqual(Object.keys(dataUrls).sort(), Object.keys(VISUALS).sort());
  assert.ok(Object.values(dataUrls).every((url) => url.startsWith("data:image/webp;base64,")));
  const decodedBytes = Object.values(dataUrls).reduce(
    (total, url) => total + Buffer.from(url.split(",", 2)[1], "base64").byteLength,
    0,
  );
  assert.ok(decodedBytes <= 3 * 1024 * 1024, `visual payload is ${decodedBytes} bytes`);
});

test("enhanced configuration contains all project-bound visual data", async () => {
  const html = stripDeckInjection(await readFile(REPORT, "utf8"));
  const dataUrls = await loadVisualDataUrls(new URL("../../", import.meta.url));
  const enhanced = enhanceHtml(html, dataUrls);
  assert.equal((enhanced.match(/data:image\/webp;base64,/g) ?? []).length, 10);
  for (const visual of Object.values(VISUALS)) assert.ok(enhanced.includes(JSON.stringify(visual.alt).slice(1, -1)));
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
