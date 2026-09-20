# Talk deck and poster — RecSys Challenge 2026

A1 poster for our slot at the RecSys Challenge 2026 workshop.

**Slot:** Friday 2 October 2026 — our paper is at **14:50–15:00**, last of
Session 3, and the **poster session runs 15:30–16:30**. Confirm with the
nlp4musa organizers whether every paper presents a poster.

The workshop puts posters on the room walls with **blue painter's tape**, which
does not hold fabric well — sort out mounting in advance. See the
[workshop organizer instructions](https://recsys.acm.org/wp-content/uploads/2026/08/Workshop-Organizer-Instructions.pdf).

## Files

| File | What it is |
| --- | --- |
| `deck.html` | **Deck source.** The detailed record of the work — edit this. |
| `talk.html` | **Present from this.** Self-contained, figures inlined, no network. |
| `talk.pdf` | Full deck, 30 slides at 960×540pt. |
| `talk-core.pdf` | The short talk — 10 slides, same source filtered. |
| `poster.html` | **Poster source.** Hand-written HTML + inline SVG — not LaTeX. |
| `poster.pdf` | **Send this to the printer.** True-size A1 (594×841mm), one page. |
| `render.sh` | Renders and preflights the poster. |
| `render-deck.sh` | Builds `talk.html`, renders both deck PDFs, preflights them. |
| `build.py` | Inlines the deck's figures into `talk.html` (called by `render-deck.sh`). |
| `figures/` | `architecture.svg`, `biencoder2.svg`, `relabelling.svg` — **shared** by the poster and the deck — plus `qr-repo.svg`. |

## Rebuilding

```bash
bash paper/talk/render.sh        # the poster
bash paper/talk/render-deck.sh   # the deck, both cuts
```

Both come from HTML rendered by headless Chrome — there is no LaTeX here.
Only `paper/main.tex` (the paper itself) is LaTeX, and every number on the
poster traces to it.

`render.sh` serves the directory over HTTP for the duration of the run, because
Chrome resolves relative assets inconsistently when printing a `file://` URL and
drops them without warning. Chrome's print path emits real PDF vector operators,
so text stays text and the inline SVG stays paths — the output has no raster
images at all.

The script then preflights the result and **fails on a Type 3 font**. That check
is not cosmetic: Chrome emits Type 3 for fonts it cannot subset normally —
variable fonts, and fallbacks pulled in for a handful of glyphs — and some print
RIPs mishandle Type 3. Two real instances were caught this way: Inter, which is
a variable font, and DejaVu Sans pulled in as a fallback for `★` and `∈`, which
Lato does not contain. Both documents pin `Lato` / `DejaVu Sans Mono` and stay
inside those glyph sets.

**If you add a character and the preflight starts failing**, that character is
almost certainly missing from Lato. Find it with:

```bash
python3 - <<'EOF'
import re, pathlib, subprocess
from fontTools.ttLib import TTFont
txt = re.sub(r'data:image/[^"]+', '', pathlib.Path('paper/talk/poster.html').read_text())
cmap = set(TTFont(subprocess.run(['fc-match','-f','%{file}','Lato'],
           capture_output=True, text=True).stdout).getBestCmap())
print([c for c in sorted(set(txt)) if ord(c) > 127 and ord(c) not in cmap])
EOF
```

## The deck

**The deck is the detailed record of the work, not a conference cut.** It covers
the system properly — state extraction, entity resolution, all eleven branches,
the index, fusion, the ranker, the bi-encoder and its training, response
generation — then results and the full analysis. Thirty slides.

The short talk is a **filter over that same source**, never a second file:

- **`data-tier="core"`** marks the nine slides that make up the short path.
- **`C`** toggles core-only navigation while presenting — arrows skip the rest.
- **`?core=1`** hides everything else, so `talk-core.pdf` is the slimmed deck.

```bash
bash paper/talk/render-deck.sh      # talk.pdf (30) and talk-core.pdf (10)
```

To move a slide in or out of the short talk, change its `data-tier`. Nothing
else needs touching and the two PDFs stay in step by construction.

### Driving it

| Key | Action |
| --- | --- |
| `→` `space` / `←` | Next / previous |
| `C` | Core path — arrows skip the optional slides |
| `A` | Appendix index |
| digits then `Enter` | Jump to an appendix slide |
| `B` | Back to where you left the spine |
| `G` or `/` | Search every slide by title |
| `O` | Overview grid |
| `N` | Speaker notes (every slide has them, with a time budget) |
| `T` / `R` | Start-stop the timer / reset — amber at 6:00, red at 7:00 |
| `F` | Fullscreen |

## The poster

A1 portrait, 594×841mm. The layout is a header, a full-width architecture
diagram, then two columns; the footer sits at the foot of the **left** column
only, so the right column runs to the sheet edge.

Print `poster.pdf` at 100% with no scaling. The PDF is fully vector (no raster
images at all, including the QR code), fonts embedded and subset, no bleed
needed because the background is white.

**It is tuned for fabric and paper at once.** Dye-sublimation on cloth prints
with softer blacks and less contrast than paper, so: card tints sit at 12–16%
rather than 5–8% (lighter tints wash to white on fabric), hairlines are ~0.85mm
and SVG strokes ~1mm (finer lines disappear into the weave), secondary text is
`#4b5563` rather than a mid-grey, and the outer margin is ~18mm because fabric
curls at the edges once hung. None of that hurts paper — it just reads a little
bolder. Every text/background pair clears 4.5:1.

**Keep the background white.** On fabric a fold or ripple catches light and
reads as a visible line across a solid tone; on white it disappears. A white
ground also needs no bleed, and gives the best text contrast.

If ordering fabric: ask for polyester poplin or wrinkle-resistant poly, not
satin — satin's sheen undoes the matte finish the RecSys accessibility guidance
asks for. Sort out mounting too; the workshop puts posters on room walls with
blue painter's tape, which does not hold fabric well.

To resize, change `--w` / `--h` and the `@page size` in `poster.html`; every
dimension is in `cqw` so the whole layout rescales. Re-measure afterwards — both
columns currently run to within ~25px of full.

## Claims and where they come from

Every number traces to `paper/main.tex`, which is the camera-ready and the
source of truth. `docs/retrospective.html` predates it and should not be used to
check figures. If the paper changes, update the poster.

Still missing: leaderboard context. `0.3811` and 29/40 do not tell an attendee
whether that is a near-miss or off the pace, and most of that room will have
their own score. It needs the top and median composite from CodaBench — one
line, once we have it.
