# RecSys 2026 camera-ready preflight

## Status

The source compiles successfully with LuaLaTeX, TeX Live 2026, and `acmart`
2.19. The generated PDF is a **preflight artifact**, not the file to upload,
until the author-supplied items below are completed.

## Author-supplied blockers

1. Paste the exact LaTeX rights-management block from the ACM eRights email
   into `main.tex`. It must replace the provisional conference metadata and
   supply the final `\setcopyright`, `\acmDOI`, `\acmISBN`, and related
   commands. Without it, `acmart` prints dummy DOI and ISBN values.
2. Rename the final source ZIP using the exact proceeding acronym and paper ID
   supplied by ACM before uploading it to TAPS.

## Page-limit confirmation

The authors confirm use of the flexible fifth content page. The additional
space supports the reviewer-response material, chiefly the expanded disclosure
of in-sample evaluation, label disagreement and relabeling, failure analysis,
and study limitations. The five-page PDF contains about 4.3 pages of content
followed by references, so it is inside the announced flexible limit of up to
five content pages excluding references.

## Audit changes and rationale

- Removed `printacmref=false`, `\setcopyright{none}`, and the copyright-footnote
  override. Those commands suppress proceedings metadata and are appropriate
  only for a draft.
- Kept the required `\documentclass[sigconf]{acmart}` and rebuilt with the
  latest available class, version 2.19 (2026-06-27).
- Removed explicit `booktabs` loading because `acmart` already loads it.
- Replaced TikZ source with two cropped vector PDF figures. TikZ/PGF is not on
  ACM's current accepted-package list; the vector conversion preserves sharp
  text and embedded fonts without adding a TAPS dependency.
- Added `\Description[short]{long}` text to all four figures and description
  text to all five tables for accessibility and TAPS HTML generation.
- Replaced the hand-written bibliography with `references.bib` and
  `ACM-Reference-Format`, completing authors, proceedings metadata, URLs, and
  persistent identifiers where available.
- Added an explicit short-author form for running heads.
- Added Hoboken, New Jersey, USA to every author affiliation as confirmed by
  the authors.
- Replaced the generic challenge-webpage citation with the supplied RecSys '26
  proceedings citation and used the three author names printed in this paper,
  as instructed by the authors.
- Added a generative-AI disclosure in Acknowledgments because AI assisted with
  camera-ready language editing, reference normalization, and formatting.
- Tightened a few phrases and the official-results table typography to remove
  horizontal overflow without changing ACM margins or spacing.

## Verified output

- US Letter, double-column `sigconf` layout
- Five total pages; references begin on page 5; flexible-page use confirmed
- No page numbers
- All citations and cross-references resolve
- Nine figure/table descriptions present
- Fonts embedded in the main PDF and both external vector figures
- All five pages visually inspected for clipping, overlap, and missing glyphs

The final LaTeX log has no warnings or layout diagnostics. BibTeX reports that
the supplied, to-appear RecSys Challenge overview citation has no `pages` or
`numpages` value; no pagination was invented before ACM assigns it.

## Build

Run from this directory:

```sh
lualatex -interaction=nonstopmode -halt-on-error main.tex
bibtex main
lualatex -interaction=nonstopmode -halt-on-error main.tex
lualatex -interaction=nonstopmode -halt-on-error main.tex
```

The TAPS source archive should contain only `main.tex`, `references.bib`, and
the two files in `figures/`; do not include generated auxiliary files or a
local copy of `acmart.cls`.
