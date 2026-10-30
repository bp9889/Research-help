# CiteDesk

A local-first research helper for LaTeX users, built with Python and Streamlit.
Everything runs on your own computer. Your files are not uploaded anywhere, and
your original files are never changed: corrections are produced as copies, with
a preview and a change log.

Screenshots: to be added.

## Tools

### 1. Cite checker (built)

Give it your .tex and .bib files and it reports:

- citations with no entry in the .bib (missing), entries nobody cites (unused),
  duplicate keys, and keys that differ only in capital letters
- entries with missing required fields
- the same paper stored under different keys
- the number each reference gets in unsorted styles such as IEEEtran

It can then fix what you tick, with a preview, an exact diff and a zip download:
merge duplicates, merge the same paper, fix key case, remove unused entries,
and tidy the .bib in a fixed personal style (layout only, wording never
changes). A DOI or a title search can add a reference as BibTeX (this part
needs the internet and is always optional). All findings can be downloaded as
one CSV file.

### 2. PDF to LaTeX (in progress)

Turns a PDF that has a text layer (a normal paper, not a scan) into a draft
LaTeX file, using free libraries that run locally (Docling). No paid service is
used. The goal is a good first draft where every doubtful spot is flagged, not
a perfect conversion.

What works now: title, authors, abstract, keywords, section and subsection
levels (read from the section numbers), paragraphs, lists, and display
equations (inserted with their original numbers and a basic check for broken
LaTeX). It has been tried on one single-column and one two-column paper.

What is still a placeholder, and shown as a comment in the .tex plus a row in
the notes list: figures, tables, captions and the reference list.

Known limits: inline math loses subscripts and superscripts, bold letters in
equations are lost, an equation can be misread by the model, some real
hyphens at line ends disappear in the text ("control-oriented" becomes
"controloriented"), and paragraph breaks are sometimes lost. The notes list
exists so none of this is silent. The output must be compiled with XeLaTeX or
LuaLaTeX.

## Install and run

Python 3.12 is recommended (the PDF tool needs a Python version that its
dependencies support; 3.15 did not work when this was written). The cite
checker alone runs on Python 3.10 or newer.

    python -m venv .venv
    .venv\Scripts\Activate.ps1          (macOS/Linux: source .venv/bin/activate)
    python -m pip install -r requirements.txt
    python -m pip install docling       (only for the PDF tool, large download)
    python -m pytest -q
    python -m streamlit run app.py

The first PDF conversion downloads about 1 GB of models and is slow.

Try the PDF converter from the command line (put test PDFs in `local_data/`):

    python -m experiments.try_writer local_data/paper.pdf          (reuses saved blocks)
    python -m experiments.try_writer local_data/paper.pdf --fresh  (converts again)
    python -m experiments.time_docling local_data/paper.pdf        (compares settings)

## How the project is organised

    app.py          the Streamlit page for the cite checker
    core/           all the logic, with no Streamlit in it
    experiments/    small scripts to try a library or measure speed
    tests/          pytest tests, one file per module
    local_data/     private test files (git-ignored, never committed)

`core/` knows nothing about Streamlit, so every rule can be tested without a
browser. Only `core/pdfreader.py` knows Docling.

## Principles

- Local first: research files are processed on your computer.
- Originals are never modified; changes come as copies with a preview.
- Cleaning and renumbering are separate operations.
- Never invent data: if a field or a piece of text is missing, it is left out
  or flagged.
- Unsupported cases are visible, never silently treated as valid.

## Plan and contributing

The live plan is in `core/roadmap.py` and shown in the app's sidebar.
Collaborators and AI assistants: read `CLAUDE.md` first. Work on one branch per
feature, run `python -m pytest -q` before every push, and open a pull request.

## Licence

Not chosen yet.