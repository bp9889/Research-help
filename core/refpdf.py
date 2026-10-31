# ===== Reading the references out of a PDF file =====
# Kept out of app.py so it can be tested with a fake reader, without Docling.
# First the PDF is read the fast way (no OCR). Only when that finds no text at
# all, which is what a scan looks like, is it read again with OCR switched on,
# because OCR costs time and can misread letters.
from core.refextract import from_blocks

_TEXT_KINDS = {"text", "heading", "list_item", "title", "caption"}


def _has_text(blocks):
    return any(b.kind in _TEXT_KINDS and b.text.strip() for b in blocks)


def references_from_pdf(path, read=None):
    if read is None:
        from core.pdfreader import read_pdf      # Docling is only loaded now
        read = read_pdf
    blocks = read(path)
    if _has_text(blocks):
        return from_blocks(blocks)

    try:
        scanned = read(path, ocr=True)
    except ModuleNotFoundError as err:
        return [], [f"This PDF has no selectable text (it looks like a scan). Reading scans "
                    f"needs a package that is not installed ({err.name}). "
                    "Copy the list and use the 'Paste the list' tab."]
    except Exception as err:                     # OCR failing must not hide the real situation
        return [], [f"This PDF has no selectable text (it looks like a scan) and reading it "
                    f"with OCR failed ({type(err).__name__}). Copy the list and use the "
                    "'Paste the list' tab."]
    if not _has_text(scanned):
        return from_blocks([])
    refs, notes = from_blocks(scanned)
    return refs, (["This PDF has no selectable text, so it was read with OCR (slower). "
                   "OCR can misread letters, so check every DOI, name and year against "
                   "the paper."] + notes)
