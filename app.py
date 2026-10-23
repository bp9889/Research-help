# ===== SECTION 1: imports =====
import pandas as pd
import streamlit as st

from core.actions import (Plan, apply_plan, build_zip, find_duplicate_groups,
                          make_diff, read_citations, read_entries)
from core.compare import compare

# ===== SECTION 2: page settings =====
st.set_page_config(page_title="CiteDesk", page_icon="📚", layout="wide")

# ===== SECTION 3: header =====
st.title("CiteDesk")
st.caption("Check your citations before you compile. Everything runs on your computer. "
           "Your original files are never changed: corrections are downloaded as copies.")


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

if not tex_files or not bib_files:
    st.info("Give me at least one .tex file and one .bib file to start.")
    st.stop()                      # nothing below runs until both are present


# ===== SECTION 5: helper that shows one kind of finding =====
def show_finding(title, rows, ok_message):
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

show_finding("Missing from the .bib", report.missing, "Every citation has a matching entry.")
if report.nocite_all:
    st.subheader("Unused entries")
    st.info("\\nocite{*} is used, so every entry is included in the bibliography.")
else:
    show_finding("Unused entries", report.unused, "Every entry in the .bib is cited.")
show_finding("Duplicate keys in the .bib", report.duplicates, "No duplicate keys.")
show_finding("Case mismatches", report.case_mismatch, "No case mismatches.")

with st.expander("All citations found"):
    st.dataframe(pd.DataFrame(
        [{"file": c.file, "key": c.key, "command": "\\" + c.cmd, "line": c.line,
          "col": c.col, "context": c.context} for c in citations]), width="stretch")

# ===== SECTION 7: choose what to fix =====
st.divider()
st.header("Fix and clean")
st.caption("Pick actions, check the preview, then download. Steps run in this order: "
           "merge duplicates, fix case, remove unused.")

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

# 7b. Fix case mismatches
fix_on = st.checkbox("Fix case mismatches (changes the key inside \\cite in your .tex files)",
                     disabled=not report.case_mismatch)

# 7c. Remove unused entries (needs confirmation: it is the risky one)
all_files = st.checkbox("I have uploaded EVERY .tex file of this project")
clean_on = st.checkbox("Remove unused entries (they are saved in removed_entries.bib)",
                       disabled=not all_files or report.nocite_all)
clean_on = clean_on and all_files

plan = Plan(merge_duplicates=merge_on, keep_choice=keep_choice,
            fix_case=fix_on, clean_unused=clean_on)

# ===== SECTION 8: preview and download =====
if merge_on or fix_on or clean_on:
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
                    st.code(text, language="latex")
        st.subheader(f"Preview: {len(result.changes)} change(s)")
        st.dataframe(pd.DataFrame(result.changes), width="stretch")
        diff = make_diff({**tex_files, **bib_files}, {**result.tex_files, **result.bib_files})
        with st.expander("Show the exact differences"):
            st.code(diff, language="diff")
        st.download_button("Download corrected files (zip)", data=build_zip(result),
                           file_name="citedesk_corrected.zip", mime="application/zip")