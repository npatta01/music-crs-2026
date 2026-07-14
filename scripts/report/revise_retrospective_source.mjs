#!/usr/bin/env node
import { readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";

const sourcePath = process.argv[2];
if (!sourcePath) throw new Error("usage: revise_retrospective_source.mjs ARTIFACT_JSON");
const evidencePath = process.argv[3] || join(dirname(sourcePath), "evidence.json");

const artifact = JSON.parse(await readFile(sourcePath, "utf8"));
const blocks = new Map(artifact.manifest.blocks.map((block) => [block.id, block]));
const block = (id) => {
  const value = blocks.get(id);
  if (!value) throw new Error(`missing block: ${id}`);
  return value;
};
const replaceExact = (id, from, to) => {
  const target = block(id);
  if (target.body.includes(to)) return;
  if (!target.body.includes(from)) throw new Error(`${id}: missing expected source text: ${from}`);
  target.body = target.body.replace(from, to);
};
const replaceOneOf = (id, alternatives, to) => {
  const target = block(id);
  if (target.body.includes(to)) return;
  const from = alternatives.find((value) => target.body.includes(value));
  if (!from) throw new Error(`${id}: missing every expected source alternative`);
  target.body = target.body.replace(from, to);
};

replaceExact(
  "query_evidence_details",
  "<blockquote>Core principle: the state is for the NEXT recommendation, not a transcript summary.</blockquote>",
  `<blockquote>Core principle: the state is for the NEXT recommendation, not a transcript summary.</blockquote><div class="state-contract"><p><strong>What the active v1 state actually extracts</strong></p><ul><li><strong>Current request</strong> — the latest literal ask, its request class, supported alternatives, source turn, and evidence.</li><li><strong>Facts</strong> — artist, album, track, and retriever-useful attribute facts, each carrying its role, anchor use, source turn, and evidence.</li><li><strong>Exclusions</strong> — explicit hard or soft things to avoid on the next recommendation.</li><li><strong>Played-track feedback</strong> — sentiment plus whether each played track was accepted, rejected, satisfying, a contrast, neutral, or explicitly pinned as a seed.</li><li><strong>Explicit played-track references</strong> — references such as “that one” or “the second one.”</li><li><strong>Time and lyric guardrails</strong> — literal or style-era constraints, plus a lyrical theme only when lyrics, meaning, or story drive retrieval.</li></ul><p><strong>After extraction:</strong> V1 facts are projected into the compiler’s V0Plus compatibility view, and named artists, albums, and tracks are resolved to catalog IDs. The LLM does not directly emit the compiler’s routing tags or retriever profile.</p></div>`,
);

const oldInterpretation = "DeepSeek emits fact-first state covering current request, entities, feedback, explicit rejections, exploration policy, routing, lyrical theme, and era; resolver grounds names to catalog IDs.";
const newInterpretation = "DeepSeek emits fact-first V1 state covering the current request; artist, album, track, and attribute facts; exclusions; played-track feedback and explicit references; temporal constraints; and lyrical theme when relevant. V0Plus projection derives routing/profile fields, and the resolver grounds names to catalog IDs.";
const artifactQueryRow = artifact.snapshot.datasets.query_comparisons.find((row) => row.team === "npatta01");
if (!artifactQueryRow) throw new Error("missing npatta01 query comparison row");
if (artifactQueryRow.interpretation !== newInterpretation) {
  if (artifactQueryRow.interpretation !== oldInterpretation) throw new Error("unexpected artifact query interpretation");
  artifactQueryRow.interpretation = newInterpretation;
}

replaceExact("own_system_diagram", "<li>Fuse branch ranks into one RRF pool.</li>", "<li>Assemble one filtered branch-pool union.</li><li>Compiler ordering remains fallback evidence; it is not the submitted final ranker.</li>");
replaceOneOf("own_system_diagram", [
  "<li>Truncate the fused pool to 500 candidates.</li>",
  "<li>Take up to 500 candidates from the branch-pool union.</li>",
], "<li>Union up to 500 hits from each traced branch.</li>");
replaceExact(
  "own_system_walkthrough",
  "DeepSeek read the multi-turn session memory and emitted fact-first V1 state for the current request, entities, feedback, explicit rejections, exploration policy, routing, lyrical theme, and era.",
  "DeepSeek read the multi-turn session memory and emitted fact-first V1 state: the current request; artist, album, track, and attribute facts; explicit exclusions; played-track feedback and references; temporal constraints; and lyrical theme when relevant.",
);
replaceExact(
  "own_system_walkthrough",
  "entered RRF. Explicit track rejection",
  "formed the filtered candidate union. The compiler recorded a weighted fusion order for trace and fallback purposes, but LightGBM—not RRF—produced the submitted final ordering. Explicit track rejection",
);
replaceOneOf("own_system_walkthrough", [
  "Only the fused top **500** reached LightGBM;",
  "Up to **500** candidates from that union reached LightGBM;",
], "The union contained up to **500** hits from each traced branch; LightGBM scored that union;");
replaceExact("ranking_contributors", "Any relevant track outside the fused top 500 was irrecoverable.", "Any relevant track outside the union of up to 500 hits from each traced branch was irrecoverable.");
const retrospectiveTable = artifact.manifest.tables.find(({ id }) => id === "retrospective-choices");
if (!retrospectiveTable?.source?.query?.sql) throw new Error("missing retrospective choices SQL");
retrospectiveTable.source.query.sql = retrospectiveTable.source.query.sql
  .replace("Using a top-500 fused pool as the learned ranker''s hard boundary", "Using the union of up to 500 hits from each traced branch as the learned ranker''s hard boundary")
  .replace("Relevant tracks outside the pool were unrecoverable", "Relevant tracks outside the candidate union were unrecoverable");
const retrospectiveChoice = artifact.snapshot.datasets.retrospective_choices.find(({ category, choice }) => (
  category === "Reconsider" && /learned ranker.*hard boundary/i.test(choice)
));
if (!retrospectiveChoice) throw new Error("missing candidate-boundary retrospective choice");
retrospectiveChoice.choice = "Using the union of up to 500 hits from each traced branch as the learned ranker's hard boundary";
retrospectiveChoice.reason = retrospectiveChoice.reason.replace("outside the pool", "outside the candidate union");
replaceExact(
  "volart_comparison",
  "Both systems used hybrid retrieval, RRF, a top-500 learned-ranker boundary, and a separate response step.",
  "Both systems used hybrid retrieval, a top-500 learned-ranker boundary, and a separate response step. volart explicitly used RRF to fuse its lanes; our submitted final ordering came from LightGBM over the compiler’s candidate union.",
);
replaceExact(
  "volart_comparison",
  "Both systems used hybrid retrieval, a top-500 learned-ranker boundary, and a separate response step. volart explicitly used RRF to fuse its lanes; our submitted final ordering came from LightGBM over the compiler’s candidate union.",
  "Both systems used hybrid retrieval, a learned ranker, and a separate response step. volart explicitly used RRF to fuse a top-500 pool before LambdaMART; our system unioned up to 500 hits from each traced branch, then LightGBM produced the submitted final ordering.",
);

await writeFile(sourcePath, `${JSON.stringify(artifact, null, 2)}\n`);

const evidence = JSON.parse(await readFile(evidencePath, "utf8"));
const evidenceQueryRow = evidence.queryComparisons.find((row) => row.team === "npatta01");
if (!evidenceQueryRow) throw new Error("missing npatta01 evidence query comparison row");
if (evidenceQueryRow.interpretation !== newInterpretation) {
  if (evidenceQueryRow.interpretation !== oldInterpretation) throw new Error("unexpected evidence query interpretation");
  evidenceQueryRow.interpretation = newInterpretation;
}
await writeFile(evidencePath, `${JSON.stringify(evidence, null, 2)}\n`);
