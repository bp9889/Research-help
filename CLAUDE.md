# CiteDesk: project context for collaborators and AI assistants

Read this file first. It explains what the project is, how it is built, the
rules the owner cares about, the problems already found, and where to help next.
Last updated: 31 October 2026.

## 1. What this project is

CiteDesk is a local-first research helper for LaTeX users, built with Python
and Streamlit. It is one site with several tools. It is also a portfolio
project, so code quality, tests and clear documentation matter as much as
features.

Tool 1, the cite checker: built. The owner pastes or uploads .tex and .bib
files and gets a report plus safe, previewed corrections. BibTeX tidy, DOI to
BibTeX import, same-paper merge and CSV export are built too. Parked for later:
the renumber tool and the paper tracker.

Tool 2, PDF to LaTeX: the current focus. The reader, the writer and display
equations work; figures, tables, captions and the reference list are still
placeholders. It turns a
born-digital PDF (one that has a text layer) into a draft LaTeX project, using
only free Python libraries that run on the owner's computer (Docling first).
No paid services such as Mathpix, because the site must stay free for now. The
goal is a good first draft with every doubtful spot flagged, never a perfect
conversion. Think of the PDF as a baked cake and LaTeX as the recipe: we are
rebuilding the recipe from the cake.

The live status of every item is in `core/roadmap.py` (the owner edits it by
hand). Both tools must live on the same site.

## 2. The owner and how to help them

The owner is an engineering undergraduate who is learning Python (CS50P) while
building this. The goal is not only working code but understanding. So:

- Make small steps. One feature at a time, each with tests.
- Do not send whole files when only part changes. Say what to change and where.
  A brand-new file may be given in full.
- Label sections in code with `# ===== SECTION n: title =====` comments and
  explain what each section does in plain words.
- Prefer a memorable analogy over jargon when explaining an idea.
- Keep markup in explanations minimal.
- Never change the wording of the user's own text. The tools fix layout and
  keys, not prose.
- Ask when something is unclear (for example the Python version, or the output
  of a command). Do not guess about the owner's computer.

## 3. Safety and privacy principles (do not break these)

1. Research files are processed locally. Nothing is uploaded to any server by
   the checking engine or the converter.
2. Original files are never modified. Corrections are produced as copies, with
   a preview, a diff and a change log.
3. Cleaning and renumbering are separate operations. Renumbering changes every
   key and every \cite, so it must never happen as a side effect.
4. Network lookups (DOI, Crossref) are optional, explicit, and kept separate
   from the offline checker. An API failure must never stop checking.
5. Never invent metadata. If a field is not returned, leave it out.
6. Unsupported cases must be visible, not silently treated as valid.
7. Real manuscripts must never be committed. Keep them in `local_data/`, which
   is git-ignored.
8. The converter never invents or rewords content. Text in the .tex comes from
   the PDF text, apart from LaTeX escaping and layout (section numbers are
   dropped because LaTeX renumbers). Suspicious spots, such as glued words,
   lost hyphens or math symbols, are reported, not silently repaired.
9. Whatever the converter cannot convert becomes a `%` comment in the .tex AND
   a row in the notes list. Nothing disappears silently.
10. PDFs are processed on the owner's machine. A public demo uses bundled
    sample PDFs with open licences only. Do not commit a PDF whose licence you
    have not checked.

## 4. Run and test

Python 3.12 is used (the owner has 3.12.10). The cite checker alone runs on
3.10 or newer, but the PDF tool needs a Python version for which its
dependencies have ready-made packages. Python 3.15 failed: pip found no
package for pandas below 3 and tried to compile it, which needs Visual Studio
build tools. If you see "Preparing metadata ... error" and a .tar.gz being
downloaded, you have this problem: use 3.12.

Docling needs pandas below 3, so `requirements.txt` must say `pandas<3`
(check this line).

    python -m venv .venv
    .venv\Scripts\Activate.ps1          (macOS/Linux: source .venv/bin/activate)
    python -m pip install -r requirements.txt
    python -m pip install docling       (see section 9A about pinning)
    python -m pytest -q                 (all tests must pass)
    python -m streamlit run app.py

Experiments (run from the repository root, with local_data/ holding test PDFs):

    python experiments/try_docling.py local_data/one.pdf          (lists blocks, writes a .md)
    python -m experiments.try_writer local_data/one.pdf           (writes a .tex, prints notes and
                                                                   timings; reuses saved blocks)
    python -m experiments.try_writer local_data/one.pdf --fresh   (converts the PDF again)
    python -m experiments.time_docling local_data/one.pdf [pages] (times five Docling settings)

The owner's test files are local_data/one.pdf (two-column) and local_data/two.pdf
(single-column). The saved blocks (`<pdf>.blocks.json`) are not refreshed
automatically: use `--fresh` after changing the PDF or the Docling settings.

Use `-m` for anything that imports `core`. A plain script run puts the script's
own folder on the path, so `core` is not found. The project folder name
contains a space, so quote paths in PowerShell. The first conversion downloads
about 1 GB of models into a cache and is slow. Later runs reuse the cache.

Always run pytest as `python -m pytest` from the repository root so `core` can
be imported. Tested with Streamlit 1.66. The code uses `width="stretch"` and
`st.code(..., height=...)`; on an older Streamlit use `use_container_width=True`
and wrap code in `st.container(height=...)`.

## 5. Repository layout

    app.py                  the Streamlit page for the cite checker, sections 1 to 8
    pages/                  (planned) one file per extra tool, e.g. 1_PDF_to_LaTeX.py
    core/
      citecheck.py          find \cite commands; rewrite keys inside them
      bibreader.py          find entries in a .bib with exact positions
      compare.py            compare citations with entries; citation order
      fields.py             parse entry fields; missing-fields check;
                            same paper under different keys
      actions.py            merge duplicates, fix case, remove unused,
                            preview diff, zip download
      export.py             all findings as one CSV file
      tidy.py               strict entry reader, owner's BibTeX style, wording guard
      doi.py                DOI and title lookup (uses the internet)
      pdfreader.py          PDF to Blocks; the ONLY file that knows Docling
      latexwriter.py        Blocks to a .tex text, plus notes and raw references
      roadmap.py            the project plan shown in the sidebar
    experiments/            small scripts: try_docling, try_writer (saved blocks and
                            timings), time_docling
    tests/                  pytest tests, one file per module
    local_data/             private test files and PDFs (git-ignored)

The rule behind the layout: `core/` knows nothing about Streamlit, so every
rule can be tested without opening a browser. `app.py` and `pages/` only
gather input and display results. Docling objects never leave `pdfreader.py`.

## 6. How the code works

### 6a. Cite checker

Data flow: uploaded text -> `{file name: text}` dictionaries -> citations
(citecheck) and entries (bibreader) -> `compare` builds a Report -> the page
shows findings -> the user ticks actions -> `apply_plan` returns corrected
copies, a change log and removed entries -> preview, copyable text, zip.

Key facts and decisions:

- Citation = key, command, line, column, context, file. Many LaTeX paragraphs
  are a single line, so column and context are needed to locate a citation.
- Comments are masked with spaces of the same length (`mask_comments`), not
  deleted. Positions found in the masked text are valid in the original text,
  which is what makes safe editing possible.
- Edits and removals are applied from the end of the text backwards so earlier
  positions stay valid.
- BibEntry stores start, end and raw text. `_find_closing` counts braces and
  skips backslash-escaped characters.
- BibTeX ignores key case, so keys are compared in lowercase as well as exact.
  A case mismatch is reported separately from a missing key.
- `\nocite{*}` means every entry is included, so nothing is reported unused.
- `apply_plan` runs in a fixed order: merge duplicates, merge same paper,
  fix case, remove unused, tidy. Files are re-read after each step. Tests
  document why.
- "Remove unused" is only offered after the user confirms they uploaded every
  .tex file, because on one chapter most entries look unused.
- The page has no Check button. Results recompute on every rerun, because
  buttons nested inside buttons do not work in Streamlit. (The PDF converter
  is the exception: see section 9E.)
- `parse_fields` skips whole values, so text like "year = 1999" inside a title
  is not mistaken for a field.
- The citation order table is only meaningful for unsorted styles (unsrt,
  IEEEtran). Chapter order follows upload order.

### 6b. PDF to LaTeX (first slice)

Data flow: PDF -> `read_pdf` (Docling) -> list of `Block(kind, text, page)` ->
`blocks_to_latex` -> `Result(tex, references, notes)`.

- Block kinds: title, heading, text, list_item, caption, formula, table,
  figure, skip (page headers and footers), other. An unknown Docling label
  becomes "other" and is shown, never lost.
- `item_to_block` only uses `.label`, `.text` and `.prov`, so tests use small
  fake items and do not need Docling. Docling is imported inside `read_pdf`,
  so the cite checker still starts without it.
- Docling gives every heading the same level. The level comes from the section
  number: 3 is a section, 3.1 a subsection, 3.1.2 a subsubsection. A plain
  text line like "1. INTRODUCTION" is promoted to a heading only by the strict
  rule (needs a dot, at most 90 characters and 12 words, no final punctuation,
  so "2023 Annual report" is not promoted) and a note is written.
- The first unnumbered heading is the title. Blocks between the title and
  ABSTRACT go into `\author{...}` as they are. "Index Terms-" and "Keywords"
  lines are split off into keywords.
- `blocks_to_latex` is one pass with a mode: front, abstract, keywords, body,
  references. Reference text is collected raw in `Result.references` for a
  later step and is not typeset.
- `escape_latex` changes one character at a time, so nothing is escaped twice.
- Paragraphs with math-like characters (Greek, math operators, math-italic
  letters) get a note. The text itself is left as it is.
- `read_pdf` switches on Docling's formula recognition. Each formula comes back
  as LaTeX with spaces between tokens (`\hat { x } ( t , k )`), usually with
  the equation number inside the text (`\quad ( 2 )`).
- `formula_to_latex` turns the number into `\tag{n}` inside an `equation*`
  environment (the preamble loads amsmath and amssymb), so numbers and
  cross-references still match the paper. It checks braces, \left/\right and
  \begin/\end; a formula that fails stays a comment plus a note. Several rows
  are wrapped in `aligned`. Words after the last equation number that contain
  no relation sign are dropped and reported in the note (residue from the
  neighbouring column; written from the owner's description, so confirm it on
  the real PDF). A word spelled letter by letter (`d i a g`) is only warned
  about, never changed.
- Every inserted equation keeps the note "not compile-checked". The compile
  check is still done by hand in Overleaf.
- `save_blocks` and `load_blocks` store the Block list as JSON, so the writer
  can be changed and run again without converting the PDF again.
- The output uses `fontspec`, so it must be compiled with XeLaTeX or LuaLaTeX
  (in Overleaf: Menu, Compiler). With pdflatex it fails. Missing-glyph
  warnings are expected until the math step is built.
- Comment lines are built with f-strings. A string that starts with `%` breaks
  Python `%` formatting; a test caught this.

## 7. Conventions

- Add or change behaviour only together with tests in `tests/`.
- Small functions with a plain-language comment on what they do.
- Commit messages: short, imperative ("Add citation order table").
- Do not add dependencies without a clear reason. Current: streamlit, pandas,
  pytest, requests. Docling is a heavy optional dependency (see 9A).
- Files are decoded as UTF-8 (BOM removed). Non-UTF-8 files are skipped with a
  message, never altered.
- Every converter step that cannot do something adds a row to `notes`
  (page, kind, message). The notes list is the contract with the review page.
- Keep test PDFs in `local_data/`. Prefer papers with open licences (arXiv
  papers under Creative Commons) for anything that is committed.

## 8. Known limitations (cite checker)

- An entry must start at the beginning of a line to be seen.
- Citations produced by custom macros or inside verbatim blocks are not seen.
- Removing entries can leave an extra blank line.
- DOI import writes names and text as the server sends them (UTF-8, not
  LaTeX accents). Types it does not know become misc. A title search can only
  guess, so the user picks the paper. Markup is removed with a simple pattern,
  so text like a<b and c>d could lose a piece. Always read the result once.
- Same-paper detection can be wrong (two editions of a book share a title), so a
  group is merged only when the user picks the key to keep. After a merge a
  command that cited both keys, like \cite{a,b}, becomes \cite{a,a}.
- Fields are read by a small parser, not a full BibTeX parser.
- Tidy only rewrites an entry it can read exactly. Entries that join strings
  with #, have a % comment inside, or have unbalanced braces are left as
  they were and listed in the change log as "tidy skipped". Tidy never
  removes duplicates; use the merge actions for that. A comment written
  after a closing brace on the same line moves to its own line.

## 9. PDF to LaTeX: problems you will probably face

Items marked (seen) were observed in the markdown export of two real test
PDFs: a single-column journal-style review and a two-column conference paper.
Items marked (expected) are likely but not yet seen. Items marked (verify)
come from memory of the library's API or licence and must be checked.

### 9A. Environment and installation

- Python version: use 3.12 (see section 4). (seen)
- pip may spend minutes "backtracking" through old Docling versions when a
  dependency cannot be installed. Press Ctrl+C and read the first real error.
- Docling and PyTorch are large. Install them in a separate requirements file
  (`requirements-pdf.txt`, to be created) so the cite checker stays light.
  Pin the exact Docling version there (`pip show docling` gives it): Docling
  releases very often and its API and defaults change.
- First run downloads about 1 GB of models. Conversion of one paper on a CPU is
  slow (time it and note it in the README).
- A free hosting tier may not have enough memory for these models. Verify
  before promising a hosted converter. (verify) The safe plan is local use plus
  a demo with bundled sample output.
- Licences: Docling itself is MIT (verified), but check each model's licence
  before shipping. PyMuPDF is AGPL, which matters for a public site (verify).
  Marker, Nougat, MinerU and pix2tex each have their own terms (verify before
  using any of them).
- Docling calls used in `read_pdf` (`DocumentConverter().convert`,
  `document.iterate_items()`, `item.label.value`, `item.prov[0].page_no`) were
  written from memory of the API. (verify) If a name errors, fix it in
  `pdfreader.py` only.

### 9B. What the test papers showed (seen)

1. Heading levels are all the same, and some headings (for example
   "1. INTRODUCTION") arrive as plain text. Handled by numbering rules.
   IEEE papers use roman numerals and letters (I., A.). Not handled yet.
2. Every display equation was exported as "formula-not-decoded". Docling's
   formula recognition is off by default; switching it on (an option such as
   `do_formula_enrichment` in the pipeline options, verify the name) needs an
   extra model download.
3. Inline math is flattened. C_p arrives as math-italic letters with the
   subscript on the baseline, R^C arrives as "RC", (N+1)^2 as "(N+1)2". The
   text layer has lost the structure. Rebuilding it needs character positions
   and sizes from the PDF (bounding boxes, font sizes, baseline shifts), not
   the extracted text. Until then these paragraphs are only flagged.
4. Line-end hyphens in real compounds disappeared: "controloriented",
   "datadriven", "36channel", "drivetrainand" (from "drivetrain- and"). Small
   caps and kerning also glued words: "SEMACCODEC", "itemwas". This breaks the
   never-change-wording rule, so the plan is to report suspicious joins (for
   example with a word list), not to fix them silently.
5. A figure placed between columns can interrupt a sentence: the text before
   and after the figure arrive as two blocks with the caption and picture in
   between. The caption may come before or after the picture. Fixing this
   needs bounding boxes (`prov[0].bbox`, verify) to pair caption and figure and
   to rejoin the sentence.
6. A table that crosses a page break was split, and one row was merged with the
   next table's first row. The Markdown export is not enough; use the table
   cell data from the table item. Table captions are separate text blocks.
7. In the single-column paper some sections arrived as one huge block, so
   paragraph breaks inside them were lost. The cause is not known yet
   (possibly merging across page breaks). Check on more PDFs before choosing
   between a bounding-box fix (first-line indent, vertical gaps) and flagging.
8. References: one paper uses [Name, Year] citations and one uses [n], so the
   reference step needs two modes. One reference list arrived as one giant
   paragraph, the other as clean list items. Accents broke in names
   ("Sch¨orkhuber": the diaeresis comes before the letter).
9. Author lines arrive with superscript markers flattened to digits
   ("Hold1,2 , Buethe1"). They are written into `\author{}` as they are and
   need a proper split later.
10. The Markdown export HTML-escapes characters (`&gt;`, `&lt;`, `&amp;`
    appeared). The converter reads `item.text`, not the Markdown, so this
    should not reach the .tex, but check it on the first real output before
    adding any unescape step.
11. Page headers, footers and page numbers were removed correctly, and the
    reading order of the two-column paper was right.

12. Equation recognition works: all five display equations of the two-column
    test paper came back as usable LaTeX and compiled. Quality problems (seen):
    bold letters are lost; one symbol was misread (a stray tilde over a B);
    the equation number sits inside the text; a word is spelled letter by
    letter (`d i a g`); and words from the neighbouring column landed inside
    one equation. The model reads a picture of the formula area, so a formula
    box that touches another column picks up its words. The proper fix is
    bounding boxes (clip the box to its column). Until then there are only
    heuristics plus notes. A decoded equation cannot be trusted blindly, so a
    review view (the PDF crop beside the LaTeX, editable) is planned.
13. On the single-column test paper the reference list arrived as 7 blocks for
    about 33 references, and only 1 caption was found for 3 tables (table
    captions arrive as plain text).

### 9C. Likely next problems (expected)

- Figures are only placeholders. Cropping a figure region from the rendered page
  (about 200 dpi) into `figures/` is a separate step. Vector figures are
  rendered as images, which is fine for a draft.
- Footnotes, algorithm blocks and code appear as "other" blocks.
- Multi-line display equations, equation numbers and cross-references
  ("Eq. (3)", "Fig. 2") have no \label or \ref yet.
- Scanned PDFs have no text layer and need OCR (a later phase).
- Very long documents (theses): memory and time.

### 9D. Testing gaps

- `read_pdf` has no automatic test because Docling is too heavy. Only
  `item_to_block` is tested, with fake items. Add one tiny sample PDF with
  known content (generate it from LaTeX) and a test that uses
  `pytest.importorskip("docling")` so it is skipped where Docling is missing.
- The writer tests use hand-made Blocks. After each new real-PDF finding, add
  a Block list that reproduces it as a test (for example the figure that
  interrupts a sentence) before fixing it.
- Ground truth: for arXiv papers the original LaTeX source can be downloaded.
  Compare the converter output with it to measure quality (keep it in
  `local_data/`).

### 9E. Streamlit integration

- Streamlit reruns the whole script on every click. Converting a PDF takes far
  too long to repeat, so the converter page must NOT follow the "no button"
  rule of the cite checker. Use a Convert button, store the Result in
  `st.session_state`, and cache the converter object (`st.cache_resource`) and
  results keyed by the file bytes (`st.cache_data`).
- Add the tool as a separate file in `pages/`. In a multipage app each page is
  its own script, so the `st.stop()` in app.py does not hide it. Every page
  needs its own `st.set_page_config(...)` as the first Streamlit call, or only
  one page calls it. The sidebar progress bar is only drawn by app.py; move it
  into a shared function in `core/` or a small helper if it should show on every
  page.
- Review page idea: the original PDF page rendered next to the generated LaTeX
  and the notes table, with the notes filterable by kind.

### 9F. Speed

Conversion on a CPU is slow, and equation recognition adds to it. The owner
has not yet measured where the time goes. Plans, in order:

1. Measure with `experiments/time_docling.py` (five settings, first pages only).
2. Saved blocks, so only the first run is slow (done: `save_blocks`).
3. Switch off what a born-digital PDF does not need: OCR, perhaps table
   recognition, and make equations optional ("quick draft", then "add
   equations"). Option names such as `do_ocr`, `do_table_structure` and
   `do_formula_enrichment` and the `page_range` argument are from memory.
   (verify)
4. Convert only the first pages while developing.
5. Use all CPU threads (Docling has accelerator options; verify the name).
6. For a public site, assume conversion is heavy: limit the page count, show a
   progress bar and an estimate, cache results by file hash, or use the tool
   locally. Decide when the Streamlit page is built.

### 9G. Working together

- `core/roadmap.py` is edited by the owner by hand. Tell the owner which
  statuses to change rather than editing it in a feature branch, to avoid
  merge conflicts.
- Say which files you are editing before you start.

## 10. Good next tasks (each needs tests)

Cite checker (parked):

1. Separate renumber tool. Preconditions: no missing keys, no duplicates, no
   case mismatches, all .tex uploaded. New keys 1..N in order of first
   citation; uncited entries need numbers too or must be removed first, or
   keys can collide. Reuse `rewrite_keys` for .tex; add a key rename for .bib
   using `BibEntry.start` and `raw`. Show an old-to-new table first.
2. Paper tracker: one row per paper, a CSV file as the database, matched by DOI
   first and then key, so renumbering keys does not lose notes.
3. README with screenshots and a public demo using sample data only. A hosted
   Streamlit app receives uploaded files on its server, so a public demo must
   use bundled sample data unless processing moves into the browser.

PDF to LaTeX, in this order (one step at a time). Done: the reader and writer
slice, and equations inserted with number tags and checks.

1. Confirm on the real PDFs (owner): run the tests, rerun `one.pdf` with
   `--fresh`, check in Overleaf that the neighbouring-column residue is gone
   from the equation, and record the notes counts.
2. Speed: run `time_docling`, decide which Docling settings to switch off or
   make optional, and create `requirements-pdf.txt` with a pinned Docling.
3. Report suspicious text (glued words, lost hyphens, broken accents). Report
   only; never change wording. Idea without a dictionary: compare each unusual
   word with the words that appear elsewhere in the same paper.
4. Bounding boxes: add the box to `Block`; rejoin a sentence split by a figure,
   pair captions with figures and tables, restore paragraph breaks where the
   evidence is clear, and clip formula boxes to their column.
5. Tables to tabular (booktabs) from cell data; mark merged cells for review.
6. Figures cropped into `figures/` with `\includegraphics` and captions.
7. References: split the list, repair accents, optional DOI lookup (explicit
   button, reuse `doi.py` and `tidy.py`), then map [n] and [Name, Year] to
   `\cite{key}`. Run the cite checker on the result as a self-check.
8. The Streamlit page in `pages/`: upload, Convert button, notes table, zip
   download (main.tex, refs.bib, figures/), cached results.
9. Review view: the PDF crop beside the LaTeX of each equation, editable.
   Idea: restore bold letters from the PDF's font information.
10. Compile check when a TeX installation is found, with the log explained in
    plain words.
11. Later: IEEE-style headings (I., A.) and an IEEEtran output option, then
    scanned PDFs with OCR.

## 11. Git workflow

- `main` always passes the tests.
- One branch per feature: `git switch -c feature-name`. The PDF tool lives on
  `pdf-to-latex` until the first slice is confirmed.
- Run `python -m pytest -q` before every push.
- Open a pull request; the owner reviews and merges.
- Run `git pull` before starting work, and tell each other which files you are
  editing to avoid conflicts.

## 12. Things not to do

- Do not rewrite the user's text or the owner's data files.
- Do not make the checker depend on internet access.
- Do not mix cleaning and renumbering.
- Do not add features without tests.
- Do not paste real thesis content into issues, tests or commits.
- Do not import Docling anywhere except inside `read_pdf`.
- Do not "fix" suspicious PDF text silently. Flag it.
- Do not use paid conversion services. The site stays free for now.
- Do not commit PDFs, models, saved `.blocks.json` files or generated .tex files
  from private work.
- Do not remove the "not compile-checked" note from an equation until a real
  compile check exists.