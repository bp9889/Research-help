# ===== SECTION 1: imports =====
# Streamlit is the library that turns Python into a web page.
import streamlit as st

# ===== SECTION 2: page settings =====
# Sets the browser tab title and uses the full screen width.
st.set_page_config(page_title="CiteDesk", page_icon="📚", layout="wide")

# ===== SECTION 3: header =====
st.title("CiteDesk")
st.caption("Check your citations before you compile. Everything runs on your computer.")

# ===== SECTION 4: two input boxes =====
# Two side-by-side columns, one box for LaTeX text, one for BibTeX text.
left, right = st.columns(2)
with left:
    tex_text = st.text_area("Paste your .tex text", height=300)
with right:
    bib_text = st.text_area("Paste your .bib text", height=300)

# ===== SECTION 5: button and result =====
# For now we only count lines to prove the boxes are connected.
if st.button("Check"):
    st.write(f"LaTeX: {len(tex_text.splitlines())} lines")
    st.write(f"BibTeX: {len(bib_text.splitlines())} lines")