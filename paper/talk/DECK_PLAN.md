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

## Next action

Author reviews both PDFs; then open the deck PR.
