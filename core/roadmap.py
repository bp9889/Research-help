# status is "done", "doing" or "todo". To update the progress bar you only
# change a word here, nothing else.
ROADMAP = [
    ("Phase 1: Cite checker", [
        ("Project setup (Python, venv, Git, GitHub)", "done"),
        ("Citation finder, .bib reader, compare", "done"),
        ("Upload several files, fix/merge/clean with preview", "done"),
        ("Same paper under different keys, citation order", "done"),
        ("Missing-fields check, findings CSV", "done"),
    ]),
    ("Phase 2: Reference tools", [
        ("BibTeX tidy in my style", "done"),
        ("DOI to BibTeX import", "done"),
        ("Separate renumber tool (parked)", "todo"),
        ("Paper tracker (parked)", "todo"),
    ]),
    ("Phase 3: PDF to LaTeX", [
        ("Scope: born-digital papers first, one and two columns", "done"),
        ("PDF reader: Docling to blocks", "done"),
        ("LaTeX writer: title, abstract, headings, paragraphs, lists", "done"),
        ("Equations inserted with number tags and checks", "done"),
        ("Equation residue rule (needs a test on the real PDF)", "doing"),
        ("Speed: saved blocks and timing script", "doing"),
        ("Report suspicious text (glued words, lost hyphens)", "todo"),
        ("Paragraph repair with bounding boxes", "todo"),
        ("Tables to tabular", "todo"),
        ("Figures cropped with captions", "todo"),
        ("References to .bib and [n] to \\cite", "todo"),
        ("Review page: PDF crop beside LaTeX, edit equations", "todo"),
        ("Streamlit page on the same site", "todo"),
        ("Scanned PDFs with OCR", "todo"),
    ]),
    ("Phase 4: Portfolio", [
        ("README with screenshots", "todo"),
        ("Public demo with sample data", "todo"),
        ("Short technical write-up", "todo"),
    ]),
]

ICON = {"done": "✅", "doing": "🔄", "todo": "⬜"}

# A finished item counts 1, an item in progress counts half.
def score(items):
    points = sum({"done": 1, "doing": 0.5}.get(status, 0) for _, status in items)
    return points, len(items)