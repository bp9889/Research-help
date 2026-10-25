import csv
import io

from core.bibreader import extract_bib_entries
from core.citecheck import extract_citations
from core.compare import compare
from core.export import findings_to_csv


def read_back(text):
    return list(csv.DictReader(io.StringIO(text)))


def test_every_row_gets_the_name_of_its_finding():
    findings = {"Missing": [{"key": "a", "where": "line 1"}],
                "Unused": [{"key": "b", "line in .bib": 3}]}
    rows = read_back(findings_to_csv(findings))
    assert [r["finding"] for r in rows] == ["Missing", "Unused"]
    assert rows[0]["key"] == "a" and rows[1]["key"] == "b"


def test_columns_that_do_not_apply_are_left_empty():
    findings = {"Missing": [{"key": "a", "where": "line 1"}],
                "Unused": [{"key": "b", "line in .bib": 3}]}
    rows = read_back(findings_to_csv(findings))
    assert rows[0]["line in .bib"] == "" and rows[1]["where"] == ""


def test_commas_quotes_and_line_breaks_survive_a_round_trip():
    tricky = 'He said "hi", then\nleft'
    rows = read_back(findings_to_csv({"Missing": [{"key": "a", "where": tricky}]}))
    assert rows[0]["where"] == tricky


def test_no_findings_gives_only_the_header():
    text = findings_to_csv({"Missing": [], "Unused": []})
    assert text.strip() == "finding"
    assert read_back(text) == []


def test_a_real_report_can_be_exported():
    tex = "\\cite{a} \\cite{zzz}"
    bib = "@article{a,\n}\n@article{b,\n}\n"
    report = compare(extract_citations(tex), extract_bib_entries(bib))
    rows = read_back(findings_to_csv({"Missing from the .bib": report.missing,
                                      "Unused entries": report.unused}))
    assert [(r["finding"], r["key"]) for r in rows] == [
        ("Missing from the .bib", "zzz"), ("Unused entries", "b")]
