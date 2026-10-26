from types import SimpleNamespace as Fake

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