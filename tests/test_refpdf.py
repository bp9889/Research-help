from core.pdfreader import Block
from core.refpdf import references_from_pdf

PAPER = [Block("heading", "References", 5),
         Block("text", "[1] K. He, X. Zhang. Deep residual learning for image recognition. CVPR, 2016.", 5),
         Block("text", "[2] A. Vaswani et al. Attention is all you need. NeurIPS, 2017.", 5)]


class FakeReader:
    """Gives `plain` for the normal read and `scanned` when OCR is asked for."""
    def __init__(self, plain, scanned=None, error=None):
        self.plain, self.scanned, self.error, self.calls = plain, scanned, error, []

    def __call__(self, path, **options):
        self.calls.append(options)
        if options.get("ocr"):
            if self.error:
                raise self.error
            return self.scanned
        return self.plain


def test_a_normal_pdf_is_read_once_and_without_ocr():
    reader = FakeReader(PAPER)
    refs, notes = references_from_pdf("x.pdf", read=reader)
    assert len(refs) == 2 and reader.calls == [{}]
    assert not any("OCR" in n for n in notes)


def test_a_scan_is_read_again_with_ocr_and_the_person_is_told():
    reader = FakeReader([Block("figure", "", 1)], scanned=PAPER)
    refs, notes = references_from_pdf("x.pdf", read=reader)
    assert len(refs) == 2 and reader.calls == [{}, {"ocr": True}]
    assert "OCR" in notes[0] and "check" in notes[0].lower()


def test_a_pdf_with_no_text_even_after_ocr_says_so():
    reader = FakeReader([], scanned=[])
    refs, notes = references_from_pdf("x.pdf", read=reader)
    assert refs == [] and "even with OCR" in notes[0]


def test_missing_ocr_packages_give_a_plain_note_not_a_crash():
    reader = FakeReader([], error=ModuleNotFoundError("no rapidocr", name="rapidocr"))
    refs, notes = references_from_pdf("x.pdf", read=reader)
    assert refs == [] and "rapidocr" in notes[0] and "Paste the list" in notes[0]


def test_any_other_ocr_failure_is_reported_with_its_type():
    reader = FakeReader([], error=RuntimeError("boom"))
    refs, notes = references_from_pdf("x.pdf", read=reader)
    assert refs == [] and "RuntimeError" in notes[0]


def test_a_pdf_with_text_but_no_heading_is_not_sent_to_ocr():
    reader = FakeReader([Block("text", "Only a body paragraph.", 1)])
    refs, notes = references_from_pdf("x.pdf", read=reader)
    assert refs == [] and reader.calls == [{}] and "Paste the list" in notes[0]
