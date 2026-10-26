# CiteDesk: project context for collaborators and AI assistants

Read this file first. It explains what the project is, how it is built, the
rules the owner cares about, and where to help next.

## 1. What this project is

CiteDesk is a local-first citation checker for LaTeX research projects, built
with Python and Streamlit. The owner pastes or uploads .tex and .bib files and
gets a report plus safe, previewed corrections. It is also a portfolio project,
so code quality, tests and clear documentation matter as much as features.

Phase 1 (the cite checker), BibTeX tidy and DOI-to-BibTeX import are built.
Still to do: the renumber tool, a paper tracker, and a public demo. The live
status of every item is in `core/roadmap.py` (the owner edits it by hand).

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
- Never change the wording of the user's own text. The tool fixes layout and
  keys, not prose.

## 3. Safety and privacy principles (do not break these)

1. Research files are processed locally. Nothing is uploaded to any server by
   the checking engine.
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

## 4. Run and test

Python 3.10 or newer. Developed on Windows with VS Code.

    python -m venv .venv
    .venv\Scripts\Activate.ps1          (macOS/Linux: source .venv/bin/activate)
    python -m pip install -r requirements.txt
    python -m pytest -q                 (all tests must pass)
    python -m streamlit run app.py

Always run pytest as `python -m pytest` from the repository root so `core` can
be imported. Tested with Streamlit 1.66. The code uses `width="stretch"` and
`st.code(..., height=...)`; on an older Streamlit use `use_container_width=True`
and wrap code in `st.container(height=...)`.

## 5. Repository layout

    app.py                  the Streamlit page (shop front), sections 1 to 8
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
      doi.py                DOI and title lookup (the only file that uses the internet)
      roadmap.py            the project plan shown in the sidebar
    tests/                  pytest tests, one file per module
    local_data/             private test files (git-ignored)

The rule behind the layout: `core/` knows nothing about Streamlit, so every
rule can be tested without opening a browser. `app.py` only gathers input and
displays results.

## 6. How the code works

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
  buttons nested inside buttons do not work in Streamlit.
- `parse_fields` skips whole values, so text like "year = 1999" inside a title
  is not mistaken for a field.
- The citation order table is only meaningful for unsorted styles (unsrt,
  IEEEtran). Chapter order follows upload order.

## 7. Conventions

- Add or change behaviour only together with tests in `tests/`.
- Small functions with a plain-language comment on what they do.
- Commit messages: short, imperative ("Add citation order table").
- Do not add dependencies without a clear reason. Current: streamlit, pandas,
  pytest, requests.
- Files are decoded as UTF-8 (BOM removed). Non-UTF-8 files are skipped with a
  message, never altered.

## 8. Known limitations

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

## 9. Good next tasks (each needs tests)

1. Separate renumber tool. Preconditions: no missing keys, no duplicates, no
   case mismatches, all .tex uploaded. New keys 1..N in order of first
   citation; uncited entries need numbers too or must be removed first, or
   keys can collide. Reuse `rewrite_keys` for .tex; add a key rename for .bib
   using `BibEntry.start` and `raw`. Show an old-to-new table first.
2. (done) Merge action for "same paper under different keys": pick one key, rewrite
   the other key in every \cite, remove the extra entry, log everything.
3. (done) Download the findings as CSV.
4. (done) BibTeX tidy with the owner's profile: lowercase field names, values in curly
   braces, bare numbers (year = 2020), tab indent, values aligned (name padded
   to 13 characters then "= "), no blank lines between entries, no trailing
   commas, duplicates by key and citation, comments kept, entries unsorted,
   field order: title, shorttitle, author, year, month, day, journal,
   booktitle, location, on, publisher, address, series, volume, number, pages,
   doi, isbn, issn, url, urldate, copyright, category, note, metadata. Add a
   guard that proves wording did not change.
5. (done) DOI to BibTeX: fetch CSL-JSON from doi.org with the header
   `Accept: application/vnd.citationstyles.csl+json` (works for all DOI
   registries); title search through the Crossref API returning candidates the
   user must confirm. Send a contact email in the User-Agent, cache results,
   map types carefully, escape & % # in text, strip markup.
6. Paper tracker: one row per paper, a CSV file as the database, matched by DOI
   first and then key, so renumbering keys does not lose notes.
7. README with screenshots and a public demo using sample data only. Note: a
   hosted Streamlit app receives uploaded files on its server, so a public demo
   must use bundled sample data unless processing moves into the browser.

## 10. Git workflow

- `main` always passes the tests.
- One branch per feature: `git switch -c feature-name`.
- Run `python -m pytest -q` before every push.
- Open a pull request; the owner reviews and merges.
- Run `git pull` before starting work, and tell each other which files you are
  editing to avoid conflicts.

## 11. Things not to do

- Do not rewrite the user's text or the owner's data files.
- Do not make the checker depend on internet access.
- Do not mix cleaning and renumbering.
- Do not add features without tests.
- Do not paste real thesis content into issues, tests or commits.
