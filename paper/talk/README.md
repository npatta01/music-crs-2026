# Talk deck and poster — RecSys Challenge 2026

24×36in poster for our slot at the RecSys Challenge 2026 workshop — the US stock
size the print shops near the venue carry, and one of the two sizes the RecSys
poster instructions recommend (the other is A1).

**Slot:** Friday 2 October 2026 — our paper is at **14:50–15:00**, last of
Session 3, and the **poster session runs 15:30–16:30**. Confirm with the
nlp4musa organizers whether every paper presents a poster.

The workshop puts posters on the room walls with **blue painter's tape**, so
print on plain matte paper with no lamination or mounting. See the
[workshop organizer instructions](https://recsys.acm.org/wp-content/uploads/2026/08/Workshop-Organizer-Instructions.pdf).

> The talk deck lives on the `backup/talk-deck-and-poster` branch and lands in a
> separate PR.

## Files

| File | What it is |
| --- | --- |
| `deck.html` | **Deck source.** The detailed record of the work — edit this. |
| `talk.html` | **Present from this.** Self-contained, figures inlined, no network. |
| `talk.pdf` | Full deck, 49 slides at 960×540pt. |
| `talk-core.pdf` | The short talk — the same source filtered to the core slides. |
| `render-deck.sh` | Builds `talk.html`, renders both deck PDFs, preflights them. |
| `build.py` | Inlines the deck's figures into `talk.html` (called by `render-deck.sh`). |
| `poster.html` | **Poster source.** Hand-written HTML + SVG — not LaTeX. Edit this. |
| `poster.pdf` | **Send this to the printer.** True-size 24×36in, one page. |
| `render.sh` | Renders the PDF and preflights it. |
| `figures/` | `architecture.svg`, `biencoder2.svg`, `relabelling.svg` (**shared** by the poster and the deck), and `qr-site.svg` — the QR code, pointing at the project site (`npatta01.github.io/music-crs-2026/`), which links the poster. `qr-repo.svg` points at the repo and is used by the deck. |

## Rebuilding

```bash
bash paper/talk/render.sh        # the poster
bash paper/talk/render-deck.sh   # the deck, both cuts
```

The PDF comes from HTML rendered by headless Chrome — there is no LaTeX here.
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
Lato does not contain. The poster pins `Lato` / `DejaVu Sans Mono` and stays
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
generation — then results and the full analysis. Forty-nine slides in eight sections, with a contents slide and a divider before each. The
approach is split into **state, retrieval, re-ranking and response generation** so each can
be skipped independently.

Slides are written to **stand alone**: each carries its own takeaway line, so a
reader gets the point without the speaker. The worked examples are all real
turns from the submitted Blind-B run, pulled from
`reports/blindset-b-prediction-audit/audit.json` — three fully worked state
examples plus six request types with the state the extractor actually produced;
three shapes of retrieval failure with the track we served; four ways the reply
went wrong with the judge's own verdict; and four training turns whose
ground-truth label repeats the artist the listener asked to move on from.

The short talk is a **filter over that same source**, never a second file:

- **`data-tier="core"`** marks the seventeen core slides — twelve of content plus the
  dividers for §4–§8. The §1–§3 dividers are optional, because the short talk
  has no core content behind them.
- **`C`** toggles core-only navigation while presenting — arrows skip the rest.
- **`?core=1`** hides everything else, so `talk-core.pdf` is the slimmed deck.

```bash
bash paper/talk/render-deck.sh      # talk.pdf (49) and talk-core.pdf (17)
```

To move a slide in or out of the short talk, change its `data-tier`. Nothing
else needs touching and the two PDFs stay in step by construction.

### Accessibility

Checked numerically, not by eye, because the RecSys guidance asks for it and a
conference room has people who need it.

- **Four colours, each meaning something:** blue for how the system works
  (sections 1–5), green for what it scored, red for what went wrong, amber for
  what we would change. An earlier version used eight decorative hues; nobody
  learns that teal means retrieval, and two pairs were hard to separate on a
  weak projector.
- **Contrast:** every text/background pair clears **4.5:1** (WCAG AA), lowest
  4.50. The first palette failed 21 pairs — the vivid amber, teal and green
  were far too light — so each hue was re-solved for the lightest shade that
  still passes white-on-hue, hue-on-paper, hue-on-white and hue-on-tint.
- **Greyscale:** all four sit at near-identical luminance, so in greyscale or
  to a viewer with achromatopsia they read the same. That is survivable only
  because nothing depends on the hue — see below — and it was checked by
  rendering the dividers in greyscale.
- **Type:** no content text below **12pt** at 960×540 (i.e. ~24pt on a
  1920×1080 projection); body is ~20pt and headings ~32pt. The only smaller
  glyphs are formula subscripts and the presenter-only CORE/OPTIONAL badges.
- **Never colour alone:** section identity is colour **plus** a number, an icon
  and a name; track status is colour **plus** a written badge; findings are
  colour **plus** a number. A viewer who cannot separate the hues loses nothing
  — confirmed by reading the greyscale renders.
- **Frame use:** content fills a median **85%** of the vertical space, worst
  case 74%, so nothing floats in a sea of white on a big screen.
- **Motion:** `prefers-reduced-motion` disables all transitions.
- **Focus:** a visible focus ring, so the deck is keyboard-navigable.
- Decorative art (the equaliser bars, the big divider numeral, section icons)
  is `aria-hidden`; the diagrams carry real `aria-label` descriptions.

To re-check after changing a colour or size, the contrast and type probes are
in the commit history for this file — both are short standalone scripts.

### Driving it

| Key | Action |
| --- | --- |
| `→` `space` / `←` | Next / previous |
| — | Section dividers double as a progress rail: five stops, current one lit |
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

24×36in portrait (609.6×914.4mm). The layout is a header (title, three stats, the QR
code), a full-width architecture diagram, then two equal columns: how the system
reads a conversation and ranks on the left; how it scored, what is not ideal, and
the training-label finding on the right. Each failure finding sits directly above
the example turn that shows it.

Print at 100% with no scaling, on **matte paper** — glossy or satin photo paper
glares under meeting-room lights. No lamination or mounting: the posters go on
walls with painter's tape. The PDF is fully vector (no raster images at all,
including the QR code), fonts embedded and subset, and needs no bleed because the
background is white — a shop's unprintable margin just becomes a white border.

**It is tuned for paper.** Rules are ~0.4mm and diagram strokes ~0.6mm, the
background is white with neutral greys (a flat tint over the whole sheet needs
bleed and can band on large-format inkjet), and nothing in the body text is under
~20pt. Colour is never the only carrier: every coloured bar has a written
headline beside it, which the RecSys accessibility guidance asks for. Every
text/background pair clears 4.5:1 (large bold text in tinted diagram boxes
clears 3:1).

To resize, change `--w` / `--h` and the `@page size` in `poster.html`; every
dimension is in `cqw` so the whole layout rescales — but a taller page leaves
empty gaps, so re-fit the type afterwards rather than just swapping the size.
Both columns end ~19mm above the bottom edge, the same as the side margins.

## Claims and where they come from

Every number traces to `paper/main.tex`, which is the camera-ready and the
source of truth. `docs/retrospective.html` predates it and should not be used to
check figures. If the paper changes, update the poster.

Still missing: leaderboard context. `0.3811` and 29/40 do not tell an attendee
whether that is a near-miss or off the pace, and most of that room will have
their own score. It needs the top and median composite from CodaBench — one
line, once we have it.
