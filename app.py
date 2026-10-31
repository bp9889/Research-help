# ===== SECTION 1: imports =====
import datetime
import os
import tempfile

import pandas as pd
import streamlit as st

from core.actions import (Plan, apply_plan, build_zip, find_duplicate_groups,
                          make_diff, read_citations, read_entries)
from core.compare import citation_order, compare
from core.doi import (clean_doi, csl_to_bibtex, fetch_csl, missing_fields, search_title,
                      suggest_key, valid_key)
from core.export import findings_to_csv
from core.fields import check_fields, find_same_paper, find_same_paper_groups
from core.health import build_health, find_retracted, load_retraction_list
from core.refextract import from_text
from core.refverify import (CHECK, CONFIRMED, LIKELY, NOT_CHECKED, NOT_FOUND, build_bib, check_connection,
                            check_bib_dois, verify_all)

from core.roadmap import ICON, ROADMAP, score

# ===== SECTION 2: page settings =====
st.set_page_config(page_title="CiteDesk", page_icon="📚", layout="wide")

# ===== SECTION 3: header =====
st.title("CiteDesk")
st.caption("Check your citations before you compile. Everything runs on your computer. "
           "Your original files are never changed: corrections are downloaded as copies.")
# ===== SECTION 3b: progress bar for the project plan (sidebar) =====
with st.sidebar:
    st.header("Project progress")
    all_items = [item for _, items in ROADMAP for item in items]
    got, total = score(all_items)
    st.progress(got / total, text=f"Whole plan: {got / total:.0%}")
    for phase, items in ROADMAP:
        g, t = score(items)
        with st.expander(f"{phase} ({g / t:.0%})", expanded=phase == ROADMAP[0][0]):
            for name, status in items:
                st.write(f"{ICON[status]} {name}")

# ===== SECTION 4: reading the files you give us =====
# Uploaded files become a dictionary {file name: text}.
# A file that is not UTF-8 is skipped with a message instead of being damaged.
def read_uploads(files):
    out = {}
    for f in files or []:
        if f.name in out:
            st.warning(f"Two files are called {f.name}. Only the last one is used; rename one.")
        try:
            out[f.name] = f.getvalue().decode("utf-8-sig")
        except UnicodeDecodeError:
            st.error(f"{f.name} is not UTF-8 text, so it was skipped.")
    return out


mode = st.radio("How do you want to give me your files?",
                ["Upload files", "Paste text"], horizontal=True)
tex_files, bib_files = {}, {}
if mode == "Upload files":
    c1, c2 = st.columns(2)
    with c1:
        up_tex = st.file_uploader("Your .tex files (all chapters)", type=["tex"],
                                  accept_multiple_files=True)
    with c2:
        up_bib = st.file_uploader("Your .bib file(s)", type=["bib"],
                                  accept_multiple_files=True)
    tex_files, bib_files = read_uploads(up_tex), read_uploads(up_bib)
else:
    left, right = st.columns(2)
    with left:
        tex_text = st.text_area("Paste your .tex text", height=300)
    with right:
        bib_text = st.text_area("Paste your .bib text", height=300)
    if tex_text.strip():
        tex_files = {"pasted.tex": tex_text}
    if bib_text.strip():
        bib_files = {"pasted.bib": bib_text}

# ===== SECTION 4b: add a reference from a DOI or a title (needs internet) =====
# Nothing here runs until you press a button, and the checker below never
# depends on it. Answers are cached for the session, so a repeat is instant.
# The converted entry is shown for you to copy. Your files are not touched.
def load_paper(doi, email):
    cache = st.session_state.setdefault("lookup_cache", {})
    record, message = fetch_csl(doi, email, cache=cache)
    if record:
        st.session_state["doi_record"] = record
    else:
        st.session_state.pop("doi_record", None)
        st.error(message)

with st.expander("Add a reference from a DOI or a title (needs internet)"):
    email = st.text_input("Your email (sent to the server in the User-Agent, as Crossref asks)")
    ready = "@" in email
    if st.button("Test the connection", disabled=not ready,
                 help="Looks up one well-known paper on each service. Nothing is saved."):
        with st.spinner("Asking doi.org and Crossref..."):
            for service, worked, said in check_connection(email):
                (st.success if worked else st.error)(f"{service}: {said}")
    by_doi, by_title = st.tabs(["I have a DOI", "Search by title"])
    with by_doi:
        doi_text = st.text_input("DOI or doi.org link")
        if st.button("Fetch BibTeX", disabled=not ready):
            doi = clean_doi(doi_text)
            if doi:
                load_paper(doi, email)
            else:
                st.error("That does not look like a DOI. A DOI starts with 10.")
    with by_title:
        title_text = st.text_input("Part of the title")
        if st.button("Search Crossref", disabled=not ready):
            cache = st.session_state.setdefault("lookup_cache", {})
            found, message = search_title(title_text, email, cache=cache)
            st.session_state["doi_candidates"] = found
            if message:
                st.warning(message)
        found = st.session_state.get("doi_candidates", [])
        if found:
            st.dataframe(pd.DataFrame(found), width="stretch")
            index = st.radio("A title search can only guess. Which one is your paper?",
                             range(len(found)),
                             format_func=lambda i: f"{found[i]['authors']} ({found[i]['year']}): "
                                                   f"{found[i]['title'][:70]}")
            if st.button("Use this paper"):
                load_paper(found[index]["doi"], email)
    record = st.session_state.get("doi_record")
    if record:
        taken = {e.key for e in read_entries(bib_files)}
        key = st.text_input("Citation key (you can change it)", value=suggest_key(record, taken))
        if not valid_key(key):
            st.error("A key cannot be empty or contain spaces, commas, braces, # or %.")
        else:
            if key.lower() in {k.lower() for k in taken}:
                st.warning("This key is already in your .bib. Pick another one.")
            bibtex = csl_to_bibtex(record, key)
            st.code(bibtex, language="latex")
            gaps = missing_fields(bibtex)
            if gaps:
                st.warning(f"The server did not send: {gaps[0]['missing']}. Add it by hand if you need it.")
            st.caption("Copy it into your .bib file, then upload the .bib again.")

# ===== SECTION 4c: get the reference list out of a paper (PDF or pasted text) =====
# Reading the list happens on your computer. Checking it against Crossref needs
# the internet and only starts when you press its button, like the box above.
# The result is a DRAFT .bib for you to read: every reference says how sure we
# are, and a reference we could not match keeps its printed text, nothing more.
def references_from_pdf(uploaded):
    from core.refpdf import references_from_pdf as read_references   # Docling is loaded only now
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(uploaded.getvalue())
    try:
        return read_references(tmp.name)      # fast settings first; OCR only for a scan
    finally:
        os.remove(tmp.name)


def remember_references(refs, notes):
    st.session_state["refs"], st.session_state["ref_notes"] = refs, notes
    st.session_state.pop("ref_checked", None)    # old results belong to the old list


with st.expander("Get the references out of a paper (PDF or pasted text)"):
    from_pdf, from_paste = st.tabs(["Upload a PDF", "Paste the list"])
    with from_pdf:
        pdf = st.file_uploader("The paper (a PDF where you can select the text)", type=["pdf"],
                               key="ref_pdf")
        if st.button("Read the references", disabled=pdf is None):
            try:
                with st.spinner("Reading the PDF. The first time also loads the models..."):
                    remember_references(*references_from_pdf(pdf))
            except ModuleNotFoundError as err:
                st.error(f"Reading PDFs needs a package that is not installed ({err.name}). "
                         "Install it with: python -m pip install docling. "
                         "Or use the 'Paste the list' tab.")
            except Exception as err:             # a damaged PDF must not crash the page
                st.error(f"Could not read that PDF ({type(err).__name__}). Try the 'Paste the list' tab.")
    with from_paste:
        pasted = st.text_area("Paste the reference list (the heading 'References' is optional)",
                              height=200, key="ref_paste")
        if st.button("Split into references", disabled=not pasted.strip()):
            remember_references(*from_text(pasted))

    for note in st.session_state.get("ref_notes", []):
        st.warning(note)
    refs = st.session_state.get("refs", [])
    if refs:
        st.write(f"{len(refs)} reference(s) found, {sum(1 for r in refs if r.doi)} with a printed DOI.")
        st.dataframe(pd.DataFrame([{"#": r.label, "DOI": r.doi, "arXiv": r.arxiv, "year": r.year,
                                    "reference": r.raw[:120]} for r in refs]), width="stretch")
        if not ready:
            st.caption("To check them, type your email in the box above (Crossref asks for it).")
        if st.button("Check them against Crossref (needs internet)", disabled=not ready):
            bar = st.progress(0.0, text="Checking...")
            st.session_state["ref_checked"] = verify_all(
                refs, email, cache=st.session_state.setdefault("lookup_cache", {}),
                progress=lambda done, total: bar.progress(done / total, text=f"Checked {done} of {total}"))
            bar.empty()

    checked = st.session_state.get("ref_checked")
    if checked:
        counts = {s: sum(1 for c in checked if c.status == s)
                  for s in (CONFIRMED, LIKELY, CHECK, NOT_FOUND, NOT_CHECKED)}
        for column, (status, n) in zip(st.columns(5), counts.items()):
            column.metric(status.capitalize(), n)
        bib_text, rows = build_bib(checked, {e.key for e in read_entries(bib_files)})
        st.dataframe(pd.DataFrame(rows), width="stretch")
        st.caption("confirmed: the DOI resolves and its title matches. likely: best match agrees on "
                   "title and year. check: Crossref found something that does not clearly match, "
                   "see the guesses in the file. Always compare the draft with the PDF.")
        st.code(bib_text, language="latex", height=300)
        st.download_button("Download references.bib (draft)", data=bib_text.encode("utf-8"),
                           file_name="references.bib", mime="text/plain")

if not tex_files or not bib_files:
    st.info("Give me at least one .tex file and one .bib file to start.")
    st.stop()                      # nothing below runs until both are present


# ===== SECTION 5: helper that shows one kind of finding =====
# Every finding shown is also remembered in FINDINGS, so section 6b can put
# them all in one CSV file.
FINDINGS = {}

def show_finding(title, rows, ok_message):
    FINDINGS[title] = rows
    st.subheader(f"{title} ({len(rows)})")
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch")
    else:
        st.success(ok_message)

# ===== SECTION 6: the report =====
# No "Check" button any more: the report updates whenever the files change.
citations = read_citations(tex_files)
entries = read_entries(bib_files)
report = compare(citations, entries)

distinct = {c.key for c in citations}
st.write(f"{len(tex_files)} .tex file(s), {len(citations)} citations, {len(distinct)} different keys, "
         f"{len(entries)} entries in the .bib.")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Missing", len(report.missing))
m2.metric("Unused", len(report.unused))
m3.metric("Duplicate keys", len(report.duplicates))
m4.metric("Case mismatches", len(report.case_mismatch))

# ===== SECTION 6a: the health report =====
# One score with the reasons under it. The box is created first so it sits at
# the top, but it is filled in LAST: the optional checks below run before it,
# so a result you just fetched is already in the score when it is drawn.
health_box = st.container()

@st.cache_data(show_spinner="Reading the list...")
def read_retraction_file(raw):
    return load_retraction_list(raw.decode("utf-8-sig", errors="replace"))

with st.expander("Optional checks that make the score more complete"):
    st.markdown("**DOIs in your .bib** (needs internet): do they exist, and do they point to the "
                "paper you meant?")
    if not ready:
        st.caption("Type your email in the box near the top first (Crossref asks for it).")
    if st.button("Check the DOIs", disabled=not ready):
        bar = st.progress(0.0, text="Checking...")
        rows_, how_many, message_ = check_bib_dois(
            entries, email, cache=st.session_state.setdefault("lookup_cache", {}),
            progress=lambda done, total: bar.progress(done / total, text=f"Checked {done} of {total}"))
        bar.empty()
        st.session_state["doi_check"] = {"signature": tuple((e.key, e.raw) for e in entries),
                                         "rows": rows_, "checked": how_many, "message": message_}
    st.markdown("**Retracted or corrected papers** (no internet: the file is read on your computer). "
                "Download the Retraction Watch data from the "
                "[Crossref page](https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/) "
                "and upload the CSV here.")
    retraction_file = st.file_uploader("Retraction Watch CSV", type=["csv"], key="retraction_csv")

doi_state = st.session_state.get("doi_check")
if doi_state and doi_state["signature"] != tuple((e.key, e.raw) for e in entries):
    doi_state = None               # the .bib changed since the check, so its result is out of date
retraction_table = None
if retraction_file is not None:
    retraction_table, retraction_message = read_retraction_file(retraction_file.getvalue())
    if retraction_message:
        st.error(retraction_message)
        retraction_table = None

field_rows = check_fields(entries)
health = build_health(
    report, citations, entries, field_rows, find_same_paper_groups(entries),
    datetime.date.today().year,
    doi_rows=doi_state["rows"] if doi_state else None,
    doi_checked=doi_state["checked"] if doi_state else 0,
    retracted=find_retracted(entries, retraction_table) if retraction_table is not None else None)

with health_box:
    st.subheader("Citation health")
    left, right = st.columns([1, 4])
    left.metric("Score", f"{health.score} / 100")
    left.write(f"**{health.label}**")
    right.dataframe(pd.DataFrame(
        [{"problem": i.check, "affected": f"{i.affected} of {i.out_of}",
          "points lost": i.penalty, "what to do": i.advice} for i in health.items]),
        width="stretch", hide_index=True)
    p = health.profile
    if "oldest year" in p:
        st.caption(f"Your references: {p['entries']} entries, from {p['oldest year']} to "
                   f"{p['newest year']} (median {p['median year']}), {p['older than 10 years']} older "
                   f"than 10 years, {p['with a DOI']} with a DOI.")
    if health.not_run:
        st.caption("Not counted in the score because they were not run: " + "; ".join(health.not_run) + ".")
    if doi_state and doi_state["message"]:
        st.warning(doi_state["message"])
    if doi_state and doi_state["rows"]:
        st.write("DOI problems found:")
        st.dataframe(pd.DataFrame(doi_state["rows"]), width="stretch", hide_index=True)

show_finding("Missing from the .bib", report.missing, "Every citation has a matching entry.")
if report.nocite_all:
    st.subheader("Unused entries")
    st.info("\\nocite{*} is used, so every entry is included in the bibliography.")
else:
    show_finding("Unused entries", report.unused, "Every entry in the .bib is cited.")
show_finding("Duplicate keys in the .bib", report.duplicates, "No duplicate keys.")
show_finding("Case mismatches", report.case_mismatch, "No case mismatches.")
show_finding("Entries with missing fields", field_rows,
             "Every entry has its required fields.")
show_finding("Possible same paper under different keys", find_same_paper(entries),
             "No look-alike entries found.")

# ===== SECTION 6b: download the findings =====
# utf-8-sig adds a small marker so Excel shows accents and other scripts correctly.
st.download_button("Download all findings (CSV)",
                   data=findings_to_csv(FINDINGS).encode("utf-8-sig"),
                   file_name="citedesk_findings.csv", mime="text/csv")

with st.expander("Citation order: the number each reference gets (unsorted styles like IEEEtran)"):
    st.dataframe(pd.DataFrame(citation_order(citations, entries)), width="stretch")
    
with st.expander("All citations found"):
    st.dataframe(pd.DataFrame(
        [{"file": c.file, "key": c.key, "command": "\\" + c.cmd, "line": c.line,
          "col": c.col, "context": c.context} for c in citations]), width="stretch")

# ===== SECTION 7: choose what to fix =====
st.divider()
st.header("Fix and clean")
st.caption("Pick actions, check the preview, then download. Steps run in this order: "
           "merge duplicates, merge same paper, fix case, remove unused, tidy.")

# 7a. Merge duplicate keys
groups = find_duplicate_groups(bib_files)
merge_on = st.checkbox("Merge duplicate keys", disabled=not groups)
keep_choice = {}
if merge_on:
    for g in groups:
        if g.identical:
            st.caption(f"Key {g.key}: the copies are identical, so the first one is kept.")
            continue
        st.write(f"Key **{g.key}** has different versions. Choose the one to keep:")
        for i, v in enumerate(g.versions):
            st.code(f"% version {i + 1}  ({v.file}, line {v.line})\n{v.raw}", language="latex")
        keep_choice[g.key.lower()] = st.radio(
            f"Keep which version of {g.key}?", list(range(len(g.versions))),
            format_func=lambda i: f"Version {i + 1}", key=f"keep_{g.key.lower()}",
            horizontal=True)

# 7a2. Merge the same paper under different keys (you decide group by group)
same_groups = find_same_paper_groups(entries)
same_on = st.checkbox("Merge the same paper under different keys", disabled=not same_groups)
same_keep = {}
if same_on:
    st.caption("Look-alike entries can be different papers (two editions of a book), "
               "so a group is merged only when you choose the key to keep.")
    for g in same_groups:
        for e in g.entries:
            st.code(f"% {e.file}, line {e.line}\n{e.raw}", language="latex")
        choices = ["Do not merge"] + list(dict.fromkeys(e.key for e in g.entries))
        pick = st.radio("Key to keep", choices, key=f"same_{g.id}", horizontal=True)
        if pick != "Do not merge":
            same_keep[g.id] = pick

# 7b. Fix case mismatches
fix_on = st.checkbox("Fix case mismatches (changes the key inside \\cite in your .tex files)",
                     disabled=not report.case_mismatch)

# 7c. Remove unused entries (needs confirmation: it is the risky one)
all_files = st.checkbox("I have uploaded EVERY .tex file of this project")
clean_on = st.checkbox("Remove unused entries (they are saved in removed_entries.bib)",
                       disabled=not all_files or report.nocite_all)
clean_on = clean_on and all_files

# 7d. Tidy the .bib files (last step; it reformats every entry)
tidy_on = st.checkbox("Tidy the .bib files in my style (layout only: words are never changed, "
                      "entries are never sorted or removed)")

plan = Plan(merge_duplicates=merge_on, keep_choice=keep_choice,
            merge_same_paper=same_on, same_keep=same_keep,
            fix_case=fix_on, clean_unused=clean_on, tidy=tidy_on)

# ===== SECTION 8: preview and download =====
if merge_on or same_on or fix_on or clean_on or tidy_on:
    result = apply_plan(tex_files, bib_files, plan)
    if not result.changes:
        st.info("Nothing to change with the selected options.")
    else:
        # Corrected files first: visible immediately, copy icon at the top right of each box.
        originals = {**tex_files, **bib_files}
        corrected = {**result.tex_files, **result.bib_files}
        changed = {n: t for n, t in corrected.items() if t != originals[n]}
        if changed:
            st.subheader("Corrected files (copy icon at the top right of each box)")
            tabs = st.tabs(list(changed))
            for tab, (name, text) in zip(tabs, changed.items()):
                with tab:
                    st.code(text, language="latex", height = 400)
        st.subheader(f"Preview: {len(result.changes)} change(s)")
        st.dataframe(pd.DataFrame(result.changes), width="stretch")
        diff = make_diff({**tex_files, **bib_files}, {**result.tex_files, **result.bib_files})
        with st.expander("Show the exact differences"):
            st.code(diff, language="diff", height = 300)
        st.download_button("Download corrected files (zip)", data=build_zip(result),
                           file_name="citedesk_corrected.zip", mime="application/zip")