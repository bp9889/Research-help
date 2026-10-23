from core.bibreader import extract_bib_entries
from core.citecheck import extract_citations
from core.compare import compare


def run(tex, bib):
    return compare(extract_citations(tex), extract_bib_entries(bib))


def test_missing_and_unused():
    r = run("See \\cite{1} and \\cite{3}.", "@article{1,\n}\n@article{2,\n}")
    assert [m["key"] for m in r.missing] == ["3"]
    assert [u["key"] for u in r.unused] == ["2"]


def test_missing_key_reports_where_it_was_cited():
    r = run("Text\nMore \\cite{3}.", "@article{1,\n}")
    assert r.missing[0]["where"] == "line 2, col 6"


def test_typo_gets_a_suggestion_but_numbers_do_not():
    r = run("\\cite{smith2021} \\cite{12}", "@article{smith2020,\n}\n@article{11,\n}")
    by_key = {m["key"]: m for m in r.missing}
    assert "smith2020" in by_key["smith2021"]["did you mean"]
    assert by_key["12"]["did you mean"] == ""


def test_case_mismatch_is_not_reported_as_missing():
    r = run("\\cite{Smith20}", "@article{smith20,\n}")
    assert r.missing == []
    assert r.case_mismatch[0]["entry is"] == "smith20"


def test_duplicate_keys():
    r = run("\\cite{2}", "@article{2,\n}\n@article{2,\n}")
    assert r.duplicates == [{"key": "2", "lines in .bib": "1, 3"}]


def test_nocite_star_means_nothing_is_unused():
    r = run("\\nocite{*}", "@article{1,\n}\n@article{2,\n}")
    assert r.nocite_all and r.unused == [] and r.missing == []


def test_everything_matches():
    r = run("\\cite{1,2}", "@article{1,\n}\n@article{2,\n}")
    assert (r.missing, r.unused, r.duplicates, r.case_mismatch) == ([], [], [], [])