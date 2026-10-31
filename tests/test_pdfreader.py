from types import SimpleNamespace as Fake

from core import pdfreader
from core.pdfreader import item_to_block


def fake(label, text="", page=1):
    return Fake(label=Fake(value=label), text=text, prov=[Fake(page_no=page)])


def test_known_label_becomes_a_kind():
    block = item_to_block(fake("section_header", " 1. Intro ", page=3))
    assert (block.kind, block.text, block.page) == ("heading", "1. Intro", 3)


def test_label_written_as_enum_text_still_works():
    item = Fake(label="DocItemLabel.PICTURE", text="", prov=[])
    assert item_to_block(item).kind == "figure"


def test_unknown_label_is_other_not_lost():
    assert item_to_block(fake("code", "x = 1")).kind == "other"


def test_page_header_is_skipped_kind():
    assert item_to_block(fake("page_header", "Journal 2026")).kind == "skip"


# ===== read_pdf asks Docling for the cheap settings unless told otherwise =====
# A fake converter is used, so these tests run without Docling installed.
def spy_converter(seen, items):
    class FakeConverter:
        def convert(self, path, **kwargs):
            seen["convert_kwargs"] = kwargs
            return Fake(document=Fake(iterate_items=lambda: items))

    def build(formulas, ocr, tables, threads):
        seen["settings"] = (formulas, ocr, tables, threads)
        return FakeConverter()

    return build


def test_read_pdf_leaves_every_expensive_step_off_by_default(monkeypatch):
    seen = {}
    items = [(fake("text", "hello"), 0)]
    monkeypatch.setattr(pdfreader, "_converter", spy_converter(seen, items))

    blocks = pdfreader.read_pdf("paper.pdf")

    assert seen["settings"] == (False, False, False, 4)
    assert seen["convert_kwargs"] == {}
    assert [b.text for b in blocks] == ["hello"]


def test_read_pdf_passes_on_what_the_caller_asked_for(monkeypatch):
    seen = {}
    monkeypatch.setattr(pdfreader, "_converter", spy_converter(seen, []))

    pdfreader.read_pdf("paper.pdf", formulas=True, pages=2, threads=8)

    assert seen["settings"] == (True, False, False, 8)
    assert seen["convert_kwargs"] == {"page_range": (1, 2)}