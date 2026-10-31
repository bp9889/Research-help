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


# ===== SECTION 4: one converter per settings, built once =====
# Building a converter loads Docling's models from disk, which takes a while.
# They are kept here so a second PDF in the same run reuses them instead of
# loading them again. Docling is imported inside the function so the cite
# checker still starts on a computer that does not have Docling installed.
_CONVERTERS = {}


def _converter(formulas, ocr, tables, threads):
    key = (bool(formulas), bool(ocr), bool(tables), int(threads))
    if key in _CONVERTERS:
        return _CONVERTERS[key]

    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions()
    options.do_ocr = bool(ocr)                      # born-digital PDFs already have text
    options.do_table_structure = bool(tables)
    options.do_formula_enrichment = bool(formulas)  # the slowest step by far
    try:
        from docling.datamodel.pipeline_options import AcceleratorOptions
        options.accelerator_options = AcceleratorOptions(num_threads=int(threads))
    except Exception:
        pass        # an older Docling sets threads elsewhere; not worth failing over

    converter = DocumentConverter(format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
    _CONVERTERS[key] = converter
    return converter


# ===== SECTION 5: read a whole PDF =====
# Every expensive step is OFF unless the caller asks for it. Each one loads
# its own model and costs minutes on a CPU, so the caller decides what this
# particular run is worth paying for. pages=2 converts only the first two
# pages, which is what you want while trying things out.
def read_pdf(path, *, formulas=False, ocr=False, tables=False, pages=None,
             threads=4):
    converter = _converter(formulas, ocr, tables, threads)

    if pages:
        try:
            result = converter.convert(path, page_range=(1, pages))
        except TypeError:
            result = converter.convert(path)    # older Docling has no page_range
    else:
        result = converter.convert(path)

    blocks = []
    for item, _level in result.document.iterate_items():
        block = item_to_block(item)
        if block.kind == "other" and not block.text:
            continue        # structure-only items (like a list wrapper) hold no content
        blocks.append(block)
    return blocks