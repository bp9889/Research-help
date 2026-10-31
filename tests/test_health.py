from core.actions import read_citations, read_entries
from core.compare import compare
from core.fields import check_fields, find_same_paper_groups
from core.health import (build_health, find_retracted, load_retraction_list,
                         reference_profile)

THIS_YEAR = 2026


def entry(key, year="2020", doi="", title=None):
    title = title or f"A long enough title for {key}"
    doi_line = f",\n\tdoi = {{{doi}}}" if doi else ""
    return (f"@article{{{key},\n\tauthor = {{A. Author}},\n\ttitle = {{{title}}},\n"
            f"\tjournal = {{J}},\n\tyear = {year}{doi_line}\n}}\n")


def health(tex, bib, **extra):
    citations = read_citations({"a.tex": tex})
    entries = read_entries({"a.bib": bib})
    return build_health(compare(citations, entries), citations, entries, check_fields(entries),
                        find_same_paper_groups(entries), THIS_YEAR, **extra)


def item(h, name):
    return next(i for i in h.items if i.check == name)


# ===== the score =====
def test_a_clean_project_scores_100():
    h = health("\\cite{a,b}", entry("a") + entry("b"))
    assert h.score == 100 and h.label == "Healthy"
    assert all(i.penalty == 0 for i in h.items)


def test_one_missing_key_in_a_big_bibliography_still_costs_something():
    keys = [f"k{n}" for n in range(100)]
    tex = "\\cite{" + ",".join(keys) + ",ghost}"
    h = health(tex, "".join(entry(k) for k in keys))
    assert item(h, "Cited but missing from the .bib").penalty == 6.0     # 15% of the 40 points
    assert h.score == 94


def test_the_penalty_grows_with_the_share_and_stops_at_its_maximum():
    one_in_four = health("\\cite{a,b,c,ghost}", entry("a") + entry("b") + entry("c"))
    assert item(one_in_four, "Cited but missing from the .bib").penalty == 40.0
    all_missing = health("\\cite{x,y,z}", entry("a"))
    assert item(all_missing, "Cited but missing from the .bib").penalty == 40.0


def test_the_score_never_goes_below_zero():
    bib = "@article{dup,\n\ttitle = {x}\n}\n" * 4        # duplicate keys, no fields
    h = health("\\cite{a,b,c,d,e,f,g,h}", bib)
    assert 0 <= h.score <= 100


def test_items_are_listed_worst_first():
    h = health("\\cite{a,ghost}", entry("a") + entry("unused1"))
    penalties = [i.penalty for i in h.items]
    assert penalties == sorted(penalties, reverse=True)
    assert h.items[0].check == "Cited but missing from the .bib"


def test_every_problem_comes_with_advice():
    h = health("\\cite{ghost}", entry("a"))
    assert all(i.advice for i in h.items)


def test_entries_with_missing_fields_and_look_alikes_are_counted():
    same = entry("one", title="The very same long title here") + entry("two", title="The very same long title here")
    bare = "@article{bare,\n\ttitle = {Only a title}\n}\n"
    h = health("\\cite{one,two,bare}", same + bare)
    assert item(h, "Same paper under different keys").affected == 2
    assert item(h, "Entries with missing fields").affected == 1


# ===== checks that were not run =====
def test_unused_entries_are_skipped_when_nocite_star_is_used():
    h = health("\\nocite{*}", entry("a"))
    assert not any(i.check == "Unused entries" for i in h.items)
    assert any("nocite" in n for n in h.not_run)


def test_checks_that_were_not_run_are_listed_not_scored():
    h = health("\\cite{a}", entry("a"))
    assert len(h.not_run) == 2 and h.score == 100
    assert not any(i.check in ("DOI problems", "Retracted or corrected papers") for i in h.items)


def test_doi_rows_from_the_online_check_are_scored():
    rows = [{"key": "a", "problem": "DOI does not exist"}]
    h = health("\\cite{a,b,c,d}", "".join(entry(k, doi=f"10.1/{k}") for k in "abcd"),
               doi_rows=rows, doi_checked=4)
    assert item(h, "DOI problems").penalty == 20.0
    assert len(h.not_run) == 1


def test_a_clean_online_check_adds_a_zero_row_and_removes_the_note():
    h = health("\\cite{a}", entry("a", doi="10.1/a"), doi_rows=[], doi_checked=1)
    assert item(h, "DOI problems").penalty == 0
    assert not any("DOIs" in n for n in h.not_run)


# ===== the profile =====
def test_profile_shows_the_age_of_the_references():
    bib = entry("a", "2024", doi="10.1/a") + entry("b", "2010") + entry("c", "2000") + entry("d", "2020")
    entries = read_entries({"a.bib": bib})
    assert reference_profile(entries, THIS_YEAR) == {
        "entries": 4, "with a DOI": 1, "oldest year": 2000, "newest year": 2024,
        "median year": 2015, "older than 10 years": 2}


def test_profile_without_any_year_does_not_invent_one():
    entries = read_entries({"a.bib": "@misc{a,\n\ttitle = {t}\n}\n"})
    assert reference_profile(entries, THIS_YEAR) == {"entries": 1, "with a DOI": 0}


def test_an_empty_project_does_not_crash():
    h = health("", "")
    assert h.score == 100 and h.profile == {"entries": 0, "with a DOI": 0}


# ===== the retraction list =====
LIST = ("Record ID,Title,OriginalPaperDOI,RetractionDOI,RetractionNature\n"
        "1,Bad paper,10.1000/BAD.1,10.1000/notice1,Retraction\n"
        "2,Fixed paper,https://doi.org/10.1000/fix.2,10.1000/notice2,Correction\n"
        "3,No doi,unavailable,10.1000/notice3,Retraction\n")


def test_the_list_is_read_with_lower_case_dois_and_bad_rows_skipped():
    table, message = load_retraction_list(LIST)
    assert message == "" and set(table) == {"10.1000/bad.1", "10.1000/fix.2"}
    assert table["10.1000/bad.1"] == {"nature": "Retraction", "notice": "10.1000/notice1"}


def test_a_file_that_is_not_the_retraction_list_is_refused_with_a_message():
    table, message = load_retraction_list("a,b\n1,2\n")
    assert table == {} and "OriginalPaperDOI" in message


def test_a_missing_nature_column_still_works():
    table, _ = load_retraction_list("OriginalPaperDOI\n10.1000/x\n")
    assert table["10.1000/x"]["nature"] == "listed"


def test_retracted_papers_in_the_bib_are_found_whatever_the_doi_spelling():
    table, _ = load_retraction_list(LIST)
    entries = read_entries({"a.bib": entry("bad", doi="https://doi.org/10.1000/Bad.1")
                            + entry("fine", doi="10.1000/ok")})
    rows = find_retracted(entries, table)
    assert [(r["key"], r["listed as"]) for r in rows] == [("bad", "Retraction")]


def test_one_retracted_paper_costs_a_lot():
    table, _ = load_retraction_list(LIST)
    bib = entry("bad", doi="10.1000/bad.1") + "".join(entry(f"k{n}", doi=f"10.1/{n}") for n in range(49))
    entries = read_entries({"a.bib": bib})
    rows = find_retracted(entries, table)
    h = health("\\cite{bad}", bib, retracted=rows)
    assert item(h, "Retracted or corrected papers").penalty == 30.0     # 1 of 50 DOIs = 2%


# ===== the retraction file header is matched loosely =====
def test_column_names_with_other_capitals_spaces_or_underscores_are_accepted():
    for header in ("original_paper_doi,retraction_nature", "Original Paper DOI,Retraction Nature",
                   "ORIGINALPAPERDOI,RETRACTIONNATURE"):
        table, message = load_retraction_list(header + "\n10.1000/x,Retraction\n")
        assert message == "" and table["10.1000/x"]["nature"] == "Retraction", header


def test_a_column_that_merely_contains_the_name_is_the_last_resort():
    table, message = load_retraction_list("Record,OriginalPaperDOI (clean)\n1,10.1000/x\n")
    assert message == "" and "10.1000/x" in table


def test_the_refusal_shows_the_columns_that_were_found():
    table, message = load_retraction_list("Title,Journal,Year\nA,B,2020\n")
    assert table == {} and "Title, Journal, Year" in message


def test_an_empty_file_is_refused_not_crashed():
    table, message = load_retraction_list("")
    assert table == {} and "no columns" in message
