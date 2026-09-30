# Deck plan — two audiences, one source

Canonical plan for the talk deck. `deck.html` is the only source; both outputs
are views of it.

## Objective

| Output | Audience | Mode | Built from |
|---|---|---|---|
| `deck-detailed.pdf` | Someone new to conversational recommendation or the challenge | Self-study: must stand alone | every slide |
| `talk-10min.pdf` | RecSys Challenge 2026 workshop attendees (mostly competitors) | Live, ~7 min + ~3 min Q&A | `data-tier="core"` slides only (`?core=1`) |

## Constraints (verified)

- Slot **14:50–15:00, Fri 2 Oct 2026**, last talk of Paper Session 3 "Ceilings,
  shift and negative results (why gains do not transfer)"; coffee break at 15:00.
  Program gives no Q&A split — budget ~7 min speaking. Source:
  https://www.recsyschallenge.com/2026/ (checked 2026-09-26).
- The talk before ours (14:40, Siwon Lee) analyses retrieval and evaluation in
  this track; a morning talk (Sanjeev Suresh, 09:50) audits label quality. Do
  not spend talk time re-establishing that the labels are noisy.
- Own laptop + HDMI; projector, podium mic. Deck is 16:9, 960×540pt.
- Every number traces to `paper/main.tex` or `reports/blindset-b-prediction-audit/audit.json`.
  Wording must match the poster's corrected claims (Metheny reply said "Got it";
  Silverthorn extracted but never filtered on; ranker trained and validated on
  the same dev turns; relabel split measured on training turns).

## Decisions

- One source, filtered views — the author's stated preference ("more slides,
  then hide or slim down").
- Talk has **no section dividers**; it opens with a "short version" slide
  carrying the thesis: extraction was richer than utilisation — 31 of 43
  diagnosed failures are ranking, 3 are extraction.
- Detailed deck gains a background primer inside §1 (renamed "Background and
  the task"): what a CRS does, retrieve→rank→respond, nDCG@20 by example, glossary.

## Talk path (core, file order)

Title · The short version · System in one picture · State on a real turn ·
The reranker · How it scored · Asked for, served · Where the failures were ·
Extracted, then ignored · What the training labels look like · What we would
do differently · Everything is released  — 12 slides, ~35 s each.

## Status

- [x] Primer slides (4) added to §1; system overview moved to close §1
- [x] "The short version" slide added after the title
- [x] Tiers retagged for the talk path; all dividers optional
- [x] Accuracy sync with the poster (state example, Metheny ×3, Kamelot, tempo/key)
- [x] Outputs renamed (`deck-detailed.pdf` 54, `talk-10min.pdf` 12); render-deck.sh + README updated
- [x] Rendered; no slide overflows its padding (54/54); 0 Type 3; closing QR → project site at 21cqw
- [x] Speaker-note timings on the talk path sum to 6:40
- [ ] Author rehearsal: time it aloud against the 8-minute slot; author trims live
- [ ] Deck PR (deck files + README + site links to both PDFs)

## Round 2 (2026-09-27): detailed deck rebuilt for beginners

Author feedback: too much information, too text-dense, score too early, issues
before the approach is understood, not grounded enough. Rebuilt:

- Main flow, 29 slides in 6 parts: the problem → where the data comes from
  (TalkPlayData 2: real LFM-2b sessions, four Gemini 2.5 Flash agents, the
  recommender agent never sees the goal and picks from a 16–32-track pool —
  its pick is the answer key) → scoring (no score of ours) → approach, one step
  per slide → results → lessons.
- 28 deep-dive slides moved to the appendix; "what we would do differently" cut
  from the flow; the close is QR + link only.
- Grounding fixes: reply-example quote corrected ("Sorry, 'Cthulhu Dawn'…");
  verdicts attributed to our LLM checker, not the organisers' judge; the
  failure tally labelled as a rule-based trace check; "category diversity"
  corrected to catalog diversity.
- New tier `talk` (talk-only) so the talk keeps its slides without them
  appearing in the beginner deck. Talk is 11 slides; revisit after the deck.

## Round 3 (2026-09-27): 18 markup notes

- Cut "Why it is hard" and the nDCG explainer; merged the two data slides into
  "How the conversations were made" (pipeline + who knows what).
- §4 steps renamed request understanding / retrieval / reranking / response
  generation; request understanding labels each turn; three more real state
  examples (Doherty lookup, Frank Ocean cover art, Ryan Adams "someone new").
- Promoted from the appendix: retrieval (technical branch names) and one index
  (with an organisers-vs-built column), what the ranker leans on, the
  bi-encoder, how the reply is written, how the relabelling worked, and a
  short "what the relabelling found".
- System diagram now full width, footnoted with which embeddings the
  organisers supplied (docs/data.md).
- §5: "Where we placed" from the official results table (static/results.csv):
  #1 0.689, median of 41 teams 0.474, us 29th 0.381, BM25 baseline 0.162.
  Table lists 41 teams (paper/poster say 40); verification in progress.
- §6 is "What is not ideal", led by the poster's four findings, then why we
  trained on the dev set (state extraction cost one paid LLM call per turn).

## Round 4 (2026-09-28): 13 markup notes

- Diagram edge-to-edge (it is width-bound at ~3:1); state-example, bi-encoder,
  placed and weights slides enlarged to use the space.
- "How the reply is written" is now the instruction, large, plus one setup line.
- Main flow gains: the state schema; down-weighting as weights (every turn starts
  at 1.0; ×0.6 artist rejected, ×0.3 track rejected or goal says no, floor 0.2);
  the anchoring example as chat bubbles.
- §6 has one slide per finding: dev-set training, extracted-then-ignored (with
  why: labels taught it; rejections = 0.7% of gain), no outside data (tempo/key,
  Breaking Bad soundtrack — both verified in the Blind-B audit), and "The reply
  was never checked" (the four real replies, promoted).

## Rounds 5–8 (2026-09-28/29)

RRF before the ranker; reply inputs shown (Röyksopp example, grounded in its
tags); reply failures limited to the paper's two (unavailable tracks,
unmet constraints); §4 subsections 4.1–4.4; §6 in story order (labels →
relabelling → dev-set training → ranker → outside data → reply); judge
verdicts on the label examples; 17% anchoring as the relabelling headline;
request understanding uses the Ryan Adams example (the Neko Case one relied on
an inferred artist). Presenter badges never print.

## Status

- [x] Detailed deck closed by the author (2026-09-29): 41-slide main flow,
      19-slide appendix, `deck-detailed.pdf` (60 pages).
- [x] 10-minute talk rebuilt from the finished deck (18 slides, 4 skippable); projector check: no text under ~26px at 1920 wide in talk mode.

## Talk (2026-09-29): 18 slides, 7:00 full, 5:00 with the skippable ones cut

Architecture first (author's choice), one slide per piece, then the lessons;
ends on the QR. No reference to other talks (their content is unknown).

Title (RecSys, date) · contents · system in one picture · request understanding · what the state can hold · retrieval · reranking ·
[what the ranker leans on] · response generation · how it scored ·
[label example] · [what the relabelling found] · why we trained on the dev set ·
extracted but not acted on · no data from outside the catalog · [the reply was never checked] · conclusion · questions + QR

[bracketed] = SKIP IF COVERED — marked in the speaker notes only; each stands
alone, so skipping never breaks the thread. Tier badges and the CORE PATH flag
are hidden on screen and in print.

## Next action

Author rehearses the 18-slide talk (about 7:05 by note timings) against the 8-minute slot and trims live; upload to the organizers' Drive only when the author says so.

## Talk round 2 (2026-09-29): 9 markup notes → 21 slides
- Organizers: 8-minute talk + 2-minute Q&A; slides named after the paper title, uploaded to their Drive by 30 Sep evening (author uploads when ready).
- Added: state→retrieval map (core, both decks), bi-encoder in the talk, reply inputs→model→reply, "Why we did not score higher" transition, one-slide relabelling (talk only).
- Changed: schema icons with two emphasised groups, dev-set cost named as state extraction, reply slide retitled "Gaps in our response generation", conclusion = state, pipeline, gaps, labels.
- Timing: ~8:10 by notes; author trims live, no further skip marking.

## Talk round 3 (2026-09-29): 6 notes → 18 slides, ~7:05
- One talk-only "Reranking" slide: flow, top three feature families, label weighting. The detailed deck keeps Reranking, The reranker, the bi-encoder, and down-weighting.
- Bi-encoder and relabelling slides leave the talk (detailed deck unchanged). The 17% / LLM-judges headline sits on the label example in talk view only.
- Label example retitled "Inconsistent labels — ‘from a different artist’"; why-list items match the titles of the slides that follow; conclusion in short bullets.

## Talk round 4 (2026-09-29): 9 notes + appendix in the talk PDF
- Talk PDF now ends with the appendix (index + 18 appendix slides + talk-only copies of the reranker features, label weighting, bi-encoder, and both relabelling slides): 42 pages.
- Request understanding names DeepSeek-V4-Flash and labels the output "Conversation state". Why-list lost its side column. Reply gaps: one example each. Questions slide: name and email. Conclusion: what we built | gaps in our system.
- "Extracted, but the ranker did not act on it" rebuilt from reports/blindset-b-prediction-audit/audit.json: state extracted → our top 20 (Deltron/Del 10 of 20 from rank 6; Ryan Adams 10 of 20, rank 1; Juanes 7 of 20, rank 1) + split-gain bars. The earlier version implied Deltron was served at rank 1; the rank-1 track there was Dead Prez.
- Fixed a CSS leak from round 7 (`.card .hi` broke highlighted table rows); appendix "category" → "catalog" diversity.
- Revised same day: the talk appendix is for workshop attendees (challenge participants), so it is curated, not the full 18. Talk appendix (numbered 1–11 in the talk): points decomposition, routing flags, eleven branches, reranker features, label weighting, bi-encoder, failure 3 (better track in pool), relabelling how + found, target ignores the request, what we would do differently. Kept slides carry `talkax`; talk-only copies carry `data-tier="talk"`. Talk PDF: 30 pages.
- Round 5: talk appendix drops the points decomposition and 'what we would do differently' (9 slides + index, 28 pages); Request understanding title names the conversation state; reranking feature box compacted with a one-line takeaway.

## Projector pass (2026-09-30), talk view only
- Darker text tokens and slide hues under `:root[data-talk]`; dimmed why-list rows now full-opacity dark grey; badges darkened; judge chips hidden on the label example (the 17% strip carries that point).
- System slide: a talk-only 5-box flow (Conversation → Typed state → 11 branches → Learned ranker → Top 20 + reply) replaces the dense architecture SVG, which stays in the detailed deck and on the poster (file untouched).
- Measured at 1920 px wide: every talk text node ≥ 7.2:1 contrast against its background; smallest text 27 px; no overflow on any of the 71 slides.
