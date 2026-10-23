from core.bibreader import extract_bib_entries

SAMPLE = "\n".join([
    "@article{1,",          # line 1
    "  title = {A}",        # line 2
    "}",                    # line 3
    "@book{Smith20, title={C}}",   # line 4
    "@comment{ignored}",    # line 5
    "% @article{99, title={commented out}}",   # line 6
    "   @inproceedings{ 7 ,",   # line 7
    "  title = {D}",
    "}",
])


def test_finds_keys_types_and_lines():
    result = extract_bib_entries(SAMPLE)
    assert [(e.key, e.type, e.line) for e in result] == [
        ("1", "article", 1),
        ("Smith20", "book", 4),
        ("7", "inproceedings", 7),
    ]


def test_comment_entries_and_commented_out_entries_are_ignored():
    keys = [e.key for e in extract_bib_entries(SAMPLE)]
    assert "99" not in keys
    assert "ignored" not in keys


def test_empty_text_gives_no_entries():
    assert extract_bib_entries("") == []

def test_entry_text_and_position_are_recorded():
    text = "@article{1,\n  title = {A {nested} title}\n}\n\n@book{2,\n}\n"
    first, second = extract_bib_entries(text, "refs.bib")
    assert first.raw == "@article{1,\n  title = {A {nested} title}\n}"
    assert text[first.start:first.end] == first.raw
    assert second.line == 5 and second.file == "refs.bib"