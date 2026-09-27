# Conference poster — RecSys Challenge 2026

A1 poster for our slot at the RecSys Challenge 2026 workshop, plus a 24×36in
render of the same source for US print shops.

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
| `poster.html` | **The source.** Hand-written HTML + SVG — not LaTeX. Edit this. |
| `poster.pdf` | True-size A1 (594×841mm), one page. |
| `poster-24x36.pdf` | **Send this to a US shop** (FedEx Office etc.), which stock 24×36in rather than A1. Same source, page size swapped by `render.sh`. |
| `render.sh` | Renders both PDFs and preflights them. |
| `figures/` | `architecture.svg`, `biencoder2.svg`, `relabelling.svg`, and `qr-site.svg` — the QR code, pointing at the project site (`npatta01.github.io/music-crs-2026/`), which links the poster. `qr-repo.svg` points at the repo. |

## Rebuilding

```bash
bash paper/talk/render.sh
```

The PDFs come from HTML rendered by headless Chrome — there is no LaTeX here.
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

## The poster

A1 portrait, 594×841mm. The layout is a header (title, three stats, the QR
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
~18pt at A1. Colour is never the only carrier: every coloured bar has a written
headline beside it, which the RecSys accessibility guidance asks for. Every
text/background pair clears 4.5:1 (large bold text in tinted diagram boxes
clears 3:1).

To resize, change `--w` / `--h` and the `@page size` in `poster.html`; every
dimension is in `cqw` so the whole layout rescales. That is how `render.sh` makes
the 24×36 version; the taller page just widens the gaps between sections. Both
columns end ~18mm above the bottom edge, the same as the side margins.

## Claims and where they come from

Every number traces to `paper/main.tex`, which is the camera-ready and the
source of truth. `docs/retrospective.html` predates it and should not be used to
check figures. If the paper changes, update the poster.

Still missing: leaderboard context. `0.3811` and 29/40 do not tell an attendee
whether that is a near-miss or off the pace, and most of that room will have
their own score. It needs the top and median composite from CodaBench — one
line, once we have it.
