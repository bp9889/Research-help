from core.bibreader import extract_bib_entries
from core.compare import citation_order
from core.citecheck import extract_citations
from core.fields import check_fields, find_same_paper, find_same_paper_groups, parse_fields


def entries(bib):
    return extract_bib_entries(bib)


def test_parse_fields_handles_braces_quotes_numbers_and_ignores_text_inside_values():
    raw = '@article{1,\n title = {A {nested} title with year = 1999},\n author = "Li, A",\n year = 2020\n}'
    f = parse_fields(raw)
    assert f["title"] == "A {nested} title with year = 1999"
    assert f["author"] == "Li, A" and f["year"] == "2020"


def test_missing_fields_are_reported_per_entry_type():
    bib = "@article{1,\n author={A},\n title={T},\n year={2020}\n}\n@misc{2,\n title={T}\n}\n"
    rows = check_fields(entries(bib))
    assert [(r["key"], r["missing"]) for r in rows] == [("1", "journal or journaltitle")]


def test_alternatives_are_accepted():
    bib = "@book{3,\n editor={E},\n title={T},\n publisher={P},\n date={2020}\n}\n"
    assert check_fields(entries(bib)) == []


def test_same_doi_in_different_formats_is_found():
    bib = ("@article{5,\n title={One},\n doi={10.1/ABC}\n}\n"
           "@article{12,\n title={Two},\n doi={https://doi.org/10.1/abc}\n}\n")
    rows = find_same_paper(entries(bib))
    assert rows[0]["keys"] == "5, 12" and "same DOI" in rows[0]["why"]


def test_same_title_with_different_years_is_found_and_years_are_shown():
    bib = ("@article{a,\n title={Deep learning for power systems},\n year={2019}\n}\n"
           "@article{b,\n title={Deep Learning for {Power} Systems},\n year={2020}\n}\n")
    rows = find_same_paper(entries(bib))
    assert rows[0]["years"] == "2019, 2020"


def test_same_key_twice_is_not_reported_here_and_short_titles_are_ignored():
    bib = ("@article{a,\n title={Deep learning for power systems}\n}\n"
           "@article{A,\n title={Deep learning for power systems}\n}\n"
           "@article{x,\n title={Introduction}\n}\n@article{y,\n title={Introduction}\n}\n")
    assert find_same_paper(entries(bib)) == []


def test_citation_order_numbers_follow_first_citation_and_skip_missing_keys():
    tex = "\\cite{b} \\cite{zzz} \\cite{a, B}"
    bib = "@article{a,\n}\n@article{b,\n}\n"
    rows = citation_order(extract_citations(tex), entries(bib))
    assert [(r["key"], r["number"]) for r in rows] == [("b", "1"), ("zzz", "[?]"), ("a", "2")]


def test_groups_carry_entries_reasons_and_a_stable_id():
    bib = ("@article{b,\n title={Deep learning for power systems},\n doi={10.1/x}\n}\n"
           "@article{A,\n title={Deep learning for power systems},\n doi={10.1/X}\n}\n")
    groups = find_same_paper_groups(entries(bib))
    assert len(groups) == 1
    assert [e.key for e in groups[0].entries] == ["b", "A"]
    assert groups[0].why == ["same DOI", "same title"]
    assert groups[0].id == "a|b"          # lowercase keys, sorted
