# RecSys 2026 camera-ready

## Status

The source compiles with LuaLaTeX, TeX Live 2026, and `acmart` 2.19. The ACM
eRights rights block is in place, so `main.pdf` carries the assigned DOI,
ISBN, and CC BY licence. This is the version to submit, not a preflight
artifact. Note that TAPS recompiles from the uploaded source and publishes
*its* build, so the proofs TAPS returns are the authoritative output.

## ACM camera-ready items (both complete)

1. **Done.** The rights block from ACM's Publication Release Confirmation
   (2026-08-18) sits in the `main.tex` preamble, verbatim and unedited:
   `\setcopyright{cc}` with `\setcctype{by}`, DOI `10.1145/3842413.3842420`,
   ISBN `979-8-4007-2863-1/2026/10`, and the final conference metadata
   (October 02, 2026). **Do not edit those eight lines** — they are
   system-generated for this paper and this rights election.
2. **Done.** TAPS assigned proceeding acronym `recsyschallenge26` and paper
   ID `7`, so the upload archive is named `recsyschallenge26-7.zip`.

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
- Replaced the generic challenge-webpage citation with the RecSys '26 challenge
  overview citation supplied by the organizers, using their author list verbatim
  (Doh, Oramas, Sguerra, Bohra, Pomo, Barile). An earlier revision substituted
  this paper's own three author names; that was a misreading of the organizers'
  email and has been corrected.
- Added the remaining two organizer-recommended citations: the TalkPlay
  multimodal recommendation paper (cited with the TalkPlayData 2 dataset in
  Section 1) and the LLM-as-a-Judge evaluation paper (cited where the composite
  metric's judge term is defined). All four recommended references are now
  present.
- Added a generative-AI disclosure in Acknowledgments. Its scope was later
  widened to match the GenAI disclosure filed with submission 1275 (coding,
  debugging, analysis of experimental outputs, and drafting and editing the
  paper), so the published text and the declared disclosure agree.
- Tightened a few phrases and the official-results table typography to remove
  horizontal overflow without changing ACM margins or spacing.

## Verified output

- US Letter, double-column `sigconf` layout
- Five total pages; references begin on page 5; flexible-page use confirmed
- No page numbers
- All citations and cross-references resolve
- Nine figure/table descriptions present
- Fonts embedded in the main PDF and both external vector figures
- First-page rights strip renders the assigned DOI, ISBN, and CC BY statement
- All three authors carry ORCIDs, embedded as author links in the PDF

The build has no errors, no undefined references, and no unresolved citations.
It is *not* diagnostic-free; three warnings are expected and accepted:

- `Underfull \vbox (badness 1867)` while `\output` is active, on page 1. It
  comes from the CC BY licence badge that the rights block adds to the
  first-page strip. Cosmetic vertical spacing only, and removing it would mean
  altering ACM's mandated first-page layout.
- `Package balance Warning: You have called \balance in second column.` Emitted
  by `acmart`'s own last-page column balancing, not by anything in this source.
- BibTeX: `page numbers missing in both pages and numpages` for
  `doh2026recsyschallenge` and `doh2026llmjudge`. Both are to-appear RecSys '26
  proceedings papers; no pagination was invented before ACM assigns it.

Page-level appearance should be re-checked on the PDF and HTML proofs TAPS
returns, since those are what actually publish.

## The built archive

The assembled TAPS archive is attached to the GitHub release
[`recsyschallenge26-7`](https://github.com/npatta01/music-crs-2026/releases/tag/recsyschallenge26-7)
as `recsyschallenge26-7.zip`, so it does not have to be rebuilt to be inspected
or re-uploaded. It is built by the commands above from the source in `paper/`,
and its `pdf/main.pdf` is produced from exactly the `Source/` it ships with, so
the two cannot drift apart. Rebuild and replace it if `paper/` changes.

## Build

Run from this directory:

```sh
lualatex -interaction=nonstopmode -halt-on-error main.tex
bibtex main
lualatex -interaction=nonstopmode -halt-on-error main.tex
lualatex -interaction=nonstopmode -halt-on-error main.tex
```

The TAPS archive must be named `recsyschallenge26-7.zip` and use the two-folder
layout the author dashboard specifies — a flat archive is rejected:

```
recsyschallenge26-7.zip
├── pdf/
│   └── main.pdf
└── Source/
    ├── main.tex
    ├── references.bib
    └── figures/{pipeline,biencoder}.pdf
```

Do not include generated auxiliary files or a local copy of `acmart.cls`; TAPS
supplies its own class. Keep the archive under 10 MB to use the dashboard's
plain Upload button (it is currently ~385 KB). Build the PDF from exactly the
source you ship so the two cannot drift apart. After upload, TAPS returns PDF
and HTML5 proofs to approve or reject; "Reject" then "Resubmit" replaces a
file, so upload is reversible but approval is the commit point.
