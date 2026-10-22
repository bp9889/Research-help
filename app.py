# ===== SECTION 1: imports =====
# pandas builds the table, and the new line imports our workshop function.
import pandas as pd
import streamlit as st

from core.citecheck import extract_citations

# ===== SECTION 2: page settings =====
st.set_page_config(page_title="CiteDesk", page_icon="📚", layout="wide")

# ===== SECTION 3: header =====
st.title("CiteDesk")
st.caption("Check your citations before you compile. Everything runs on your computer.")

# ===== SECTION 4: two input boxes =====
left, right = st.columns(2)
with left:
    tex_text = st.text_area("Paste your .tex text", height=300)
with right:
    bib_text = st.text_area("Paste your .bib text", height=300)

# ===== SECTION 5: button and result =====
# Ask the workshop for every citation, then show them as a table.
if st.button("Check"):
    citations = extract_citations(tex_text)
    if not citations:
        st.info("No citations found in the LaTeX text.")
    else:
        unique_keys = {c.key for c in citations}
        st.write(f"{len(citations)} citations found, {len(unique_keys)} different keys.")
        table = pd.DataFrame(
            [{"key": c.key, "command": "\\" + c.cmd, "line": c.line,
              "col": c.col, "context": c.context} for c in citations]
        )
        st.dataframe(table, width="stretch")