# ===== SECTION 1: what one piece of a PDF looks like =====
# A Block is one piece found on a page: a heading, a paragraph, a formula...
# The rest of the converter only ever sees Blocks, never Docling objects.
from dataclasses import dataclass


@dataclass
class Block:
    kind: str       # title, heading, text, list_item, caption, formula, table, figure, skip, other
    text: str
    page: int = 0


# ===== SECTION 2: Docling label -> our kind =====
# Anything not listed here becomes "other", so it is shown, never silently lost.
LABEL_TO_KIND = {
    "title": "title",
    "section_header": "heading",
    "text": "text",
    "paragraph": "text",
    "list_item": "list_item",
    "caption": "caption",
    "formula": "formula",
    "table": "table",
    "picture": "figure",
    "page_header": "skip",
    "page_footer": "skip",
}


# ===== SECTION 3: turn one Docling item into a Block =====
# Works on anything that has .label, .text and .prov, so tests can use
# small fake items and do not need Docling installed.
def item_to_block(item):
    label = getattr(item, "label", None)
    name = str(getattr(label, "value", label)).split(".")[-1].lower()
    prov = getattr(item, "prov", None) or []
    page = prov[0].page_no if prov else 0
    text = (getattr(item, "text", "") or "").strip()
    return Block(LABEL_TO_KIND.get(name, "other"), text, page)


# ===== SECTION 4: read a whole PDF =====
# Docling is imported here, inside the function, so the cite checker
# still starts on a computer that does not have Docling installed.
def read_pdf(path):
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions()
    options.do_formula_enrichment = True      # asks Docling to turn equations into LaTeX
    converter = DocumentConverter(format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
    document = converter.convert(path).document
    blocks = []
    for item, _level in document.iterate_items():
        block = item_to_block(item)
        if block.kind == "other" and not block.text:
            continue        # structure-only items (like a list wrapper) hold no content
        blocks.append(block)
    return blocks