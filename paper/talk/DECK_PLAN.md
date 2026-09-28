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
- [ ] Author rehearsal: time it aloud, trim if over 7:00
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

## Next action

Author reviews both PDFs; then open the deck PR.
