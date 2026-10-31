import requests

from core.bibreader import extract_bib_entries
from core.refextract import parse_reference
from core.refverify import (CHECK, CONFIRMED, LIKELY, NOT_CHECKED, NOT_FOUND, build_bib,
                            check_bib_dois, check_connection, title_in_reference, verify_all, verify_reference)

EMAIL = "me@example.org"
TITLE = "Deep residual learning for image recognition"
PRINTED = ("[1] K. He, X. Zhang, S. Ren, J. Sun. Deep residual learning for image "
           "recognition. CVPR, 2016.")


# ===== a fake internet, so the tests run offline =====
class FakeResponse:
    def __init__(self, data=None, status=200):
        self.status_code, self._data = status, data

    def json(self):
        return self._data


class FakeGet:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def __call__(self, url, headers=None, params=None, timeout=None):
        self.calls.append(url)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def csl(title=TITLE, doi="10.1109/CVPR.2016.90", year=2016):
    return {"DOI": doi, "type": "article-journal", "title": title,
            "author": [{"given": "Kaiming", "family": "He"}],
            "container-title": "CVPR", "issued": {"date-parts": [[year]]}}


def search_result(title=TITLE, doi="10.1109/CVPR.2016.90", year=2016):
    return {"message": {"items": [{"DOI": doi, "title": [title], "type": "proceedings-article",
                                   "author": [{"family": "He"}],
                                   "issued": {"date-parts": [[year]]}}]}}


def ok(data):
    return FakeResponse(data)


def down():
    return requests.ConnectionError("no network")


# ===== does the title appear in the printed reference? =====
def test_a_matching_title_is_recognised_even_with_other_case_and_accents():
    assert title_in_reference("Déep Residual Learning: for Image Recognition", PRINTED)


def test_a_different_title_is_not_recognised():
    assert not title_in_reference("Attention is all you need", PRINTED)


def test_a_very_short_title_never_matches():
    assert not title_in_reference("Dropout", "Dropout: a simple way. 2014.")


# ===== one reference =====
def test_a_printed_doi_that_resolves_to_the_same_title_is_confirmed():
    ref = parse_reference(PRINTED + " doi:10.1109/CVPR.2016.90")
    result = verify_reference(ref, EMAIL, get=FakeGet(ok(csl())))
    assert result.status == CONFIRMED and result.record["DOI"] == "10.1109/CVPR.2016.90"


def test_a_doi_that_points_to_another_paper_is_not_trusted():
    ref = parse_reference(PRINTED + " doi:10.1109/CVPR.2016.90")
    result = verify_reference(ref, EMAIL, get=FakeGet(ok(csl(title="Attention is all you need"))))
    assert result.status == CHECK and result.record is None
    assert "Attention is all you need" in result.why


def test_a_dead_doi_falls_back_to_a_title_search():
    ref = parse_reference(PRINTED + " doi:10.1109/CVPR.2016.99")
    fake = FakeGet(FakeResponse(status=404), ok(search_result()), ok(csl()))
    result = verify_reference(ref, EMAIL, get=fake)
    assert result.status == LIKELY
    assert result.why.startswith("The printed DOI did not resolve.")


def test_without_a_doi_a_title_and_year_match_is_only_likely():
    fake = FakeGet(ok(search_result()), ok(csl()))
    result = verify_reference(parse_reference(PRINTED), EMAIL, get=fake)
    assert result.status == LIKELY and result.record


def test_a_year_that_disagrees_makes_it_a_check_not_a_match():
    fake = FakeGet(ok(search_result(year=2019)))
    result = verify_reference(parse_reference(PRINTED), EMAIL, get=fake)
    assert result.status == CHECK and result.record is None
    assert result.candidates[0]["year"] == "2019"


def test_an_unrelated_search_result_is_a_check():
    fake = FakeGet(ok(search_result(title="Attention is all you need")))
    assert verify_reference(parse_reference(PRINTED), EMAIL, get=fake).status == CHECK


def test_no_search_result_means_not_found():
    fake = FakeGet(ok({"message": {"items": []}}))
    assert verify_reference(parse_reference(PRINTED), EMAIL, get=fake).status == NOT_FOUND


def test_a_missing_connection_is_not_checked_never_not_found():
    result = verify_reference(parse_reference(PRINTED), EMAIL, get=FakeGet(down()))
    assert result.status == NOT_CHECKED and "Could not reach" in result.why


def test_too_many_requests_is_not_checked_never_not_found():
    result = verify_reference(parse_reference(PRINTED), EMAIL, get=FakeGet(FakeResponse(status=429)))
    assert result.status == NOT_CHECKED


def test_a_reference_too_short_to_search_is_not_found_not_a_server_problem():
    result = verify_reference(parse_reference("Li 2020"), EMAIL, get=FakeGet())   # 7 characters
    assert result.status == NOT_FOUND and "at least 8 characters" in result.why


# ===== a whole list =====
def test_three_connection_failures_in_a_row_stop_the_checking():
    refs = [parse_reference(PRINTED.replace("[1]", f"[{n}]")) for n in range(1, 6)]
    fake = FakeGet(down(), down(), down())
    results = verify_all(refs, EMAIL, get=fake)
    assert [r.status for r in results] == [NOT_CHECKED] * 5
    assert len(fake.calls) == 3
    assert "Skipped" in results[4].why


def test_progress_is_reported_after_each_reference():
    seen = []
    refs = [parse_reference(PRINTED)] * 2
    fake = FakeGet(ok({"message": {"items": []}}), ok({"message": {"items": []}}))
    verify_all(refs, EMAIL, get=fake, cache=None, progress=lambda done, total: seen.append((done, total)))
    assert seen == [(1, 2), (2, 2)]


# ===== the .bib draft =====
def test_a_confirmed_reference_becomes_a_full_entry_and_an_unknown_one_keeps_its_text():
    good = verify_reference(parse_reference(PRINTED + " doi:10.1109/CVPR.2016.90"), EMAIL,
                            get=FakeGet(ok(csl())))
    bad = verify_reference(parse_reference("[2] Nobody. A thing about {braces} & 100% more. 2020."),
                           EMAIL, get=FakeGet(ok({"message": {"items": []}})))
    text, rows = build_bib([good, bad])

    entries = extract_bib_entries(text)
    assert [e.key for e in entries] == ["he2016", "ref2"]
    assert entries[0].type == "article" and entries[1].type == "misc"
    assert "A thing about \\{braces\\} \\& 100\\% more" in entries[1].raw
    assert [r["status"] for r in rows] == [CONFIRMED, NOT_FOUND]
    assert rows[1]["key"] == "ref2"


def test_a_likely_match_is_marked_in_the_file():
    likely = verify_reference(parse_reference(PRINTED), EMAIL, get=FakeGet(ok(search_result()), ok(csl())))
    text, _ = build_bib([likely])
    assert text.startswith("% likely match: compare with the PDF")
    assert [e.key for e in extract_bib_entries(text)] == ["he2016"]


def test_a_check_result_lists_its_guesses_as_comments():
    result = verify_reference(parse_reference(PRINTED), EMAIL,
                              get=FakeGet(ok(search_result(year=2019))))
    text, _ = build_bib([result])
    assert "% guess: 10.1109/CVPR.2016.90" in text
    assert [e.type for e in extract_bib_entries(text)] == ["misc"]


def test_new_keys_do_not_collide_with_keys_already_in_your_bib():
    good = verify_reference(parse_reference(PRINTED + " doi:10.1109/CVPR.2016.90"), EMAIL,
                            get=FakeGet(ok(csl())))
    text, _ = build_bib([good, good], existing_keys=["he2016"])
    assert [e.key for e in extract_bib_entries(text)] == ["he2016a", "he2016b"]


def test_nothing_is_invented_for_an_unverified_reference():
    bad = verify_reference(parse_reference("[7] Nobody. Some title here. 2020."), EMAIL,
                           get=FakeGet(ok({"message": {"items": []}})))
    text, _ = build_bib([bad])
    raw = extract_bib_entries(text)[0].raw
    assert "author" not in raw and "year" not in raw and "doi" not in raw


# ===== the DOIs already in your .bib =====
BIB = """\
@article{good,
\ttitle = {Deep residual learning for image recognition},
\tdoi = {10.1109/CVPR.2016.90}
}
@article{typo,
\ttitle = {Some paper},
\tdoi = {10.1109/NOPE.1}
}
@article{wrong,
\ttitle = {Deep residual learning for image recognition},
\tdoi = {10.1000/other}
}
@article{nodoi,
\ttitle = {No doi here}
}
"""


def test_bib_dois_that_do_not_exist_or_point_elsewhere_are_found():
    entries = extract_bib_entries(BIB)
    fake = FakeGet(ok(csl()), FakeResponse(status=404),
                   ok(csl(title="Attention is all you need", doi="10.1000/other")))
    rows, checked, message = check_bib_dois(entries, EMAIL, get=fake)
    assert checked == 3 and message == ""
    assert [(r["key"], r["problem"]) for r in rows] == [
        ("typo", "DOI does not exist"), ("wrong", "DOI points to a different paper")]
    assert len(fake.calls) == 3                # the entry without a DOI is never asked about


def test_a_shorter_title_in_the_bib_is_not_flagged_as_a_different_paper():
    entries = extract_bib_entries("@article{k,\n\ttitle = {Deep residual learning},\n\tdoi = {10.1/x}\n}")
    long_title = ok(csl(title="Deep residual learning for image recognition", doi="10.1/x"))
    rows, _, _ = check_bib_dois(entries, EMAIL, get=FakeGet(long_title))
    assert rows == []


def test_bib_check_stops_after_three_server_problems_and_never_calls_them_missing():
    entries = extract_bib_entries(
        "".join(f"@article{{k{n},\n\ttitle = {{T}},\n\tdoi = {{10.1/{n}}}\n}}\n" for n in range(6)))
    fake = FakeGet(down(), down(), down())
    rows, checked, message = check_bib_dois(entries, EMAIL, get=fake)
    assert rows == [] and checked == 0 and "three server problems" in message
    assert len(fake.calls) == 3


# ===== references that only print an arXiv number =====
ARXIV_PRINTED = ("[19] J. Huang, X. Chen, D. Zhou. Large language models cannot self-correct "
                 "reasoning yet. In ICLR 2024, 2024. arXiv:2310.01798.")
ARXIV_TITLE = "Large Language Models Cannot Self-Correct Reasoning Yet"


def test_an_arxiv_only_reference_is_confirmed_through_its_arxiv_doi():
    fake = FakeGet(ok(csl(title=ARXIV_TITLE, doi="10.48550/arxiv.2310.01798", year=2023)))
    result = verify_reference(parse_reference(ARXIV_PRINTED), EMAIL, get=fake)
    assert result.status == CONFIRMED and "arXiv number" in result.why
    assert fake.calls == ["https://doi.org/10.48550/arXiv.2310.01798"]     # no title search needed


def test_the_printed_doi_is_tried_first_and_the_arxiv_number_is_not_asked_when_it_works():
    ref = parse_reference(PRINTED + " doi:10.1109/CVPR.2016.90 arXiv:1512.03385")
    fake = FakeGet(ok(csl()))
    assert verify_reference(ref, EMAIL, get=fake).status == CONFIRMED
    assert len(fake.calls) == 1


def test_a_wrong_printed_doi_does_not_hide_a_right_arxiv_number():
    ref = parse_reference(ARXIV_PRINTED.replace("arXiv:2310.01798", "doi:10.1000/typo arXiv:2310.01798"))
    fake = FakeGet(ok(csl(title="Attention is all you need", doi="10.1000/typo")),
                   ok(csl(title=ARXIV_TITLE, doi="10.48550/arxiv.2310.01798")))
    result = verify_reference(ref, EMAIL, get=fake)
    assert result.status == CONFIRMED and "arXiv number" in result.why


def test_when_every_identifier_points_to_another_paper_all_are_shown_as_guesses():
    ref = parse_reference(ARXIV_PRINTED.replace("arXiv:2310.01798", "doi:10.1000/typo arXiv:2310.01798"))
    fake = FakeGet(ok(csl(title="Attention is all you need", doi="10.1000/typo")),
                   ok(csl(title="Some other unrelated paper entirely", doi="10.48550/arxiv.2310.01798")))
    result = verify_reference(ref, EMAIL, get=fake)
    assert result.status == CHECK and result.record is None and len(result.candidates) == 2


def test_an_arxiv_doi_that_is_not_registered_falls_back_to_a_title_search():
    fake = FakeGet(FakeResponse(status=404), ok(search_result(title=ARXIV_TITLE, doi="10.1/x", year=2024)),
                   ok(csl(title=ARXIV_TITLE, doi="10.1/x", year=2024)))
    result = verify_reference(parse_reference(ARXIV_PRINTED), EMAIL, get=fake)
    assert result.status == LIKELY and result.why.startswith("The arXiv number did not resolve.")


def test_a_server_problem_on_the_arxiv_route_is_not_checked_not_wrong():
    result = verify_reference(parse_reference(ARXIV_PRINTED), EMAIL, get=FakeGet(FakeResponse(status=429)))
    assert result.status == NOT_CHECKED


def test_a_one_word_title_is_enough_when_the_printed_doi_resolves_but_not_for_a_search_guess():
    printed = "[1] N. Srivastava et al. Dropout: a simple way to prevent overfitting. JMLR, 2014. doi:10.1000/drop"
    confirmed = verify_reference(parse_reference(printed), EMAIL, get=FakeGet(ok(csl(title="Dropout", doi="10.1000/drop"))))
    assert confirmed.status == CONFIRMED
    no_doi = parse_reference("[1] N. Srivastava et al. Dropout: a simple way to prevent overfitting. JMLR, 2014.")
    guess = verify_reference(no_doi, EMAIL, get=FakeGet(ok(search_result(title="Dropout", doi="10.1000/drop", year=2014))))
    assert guess.status == CHECK


# ===== a DOI that was broken after a full stop =====
BROKEN = PRINTED + " doi: 10.1109/CVPR.2016. 90"


def test_the_second_reading_of_a_broken_doi_is_tried_when_the_first_is_a_dead_end():
    ref = parse_reference(BROKEN)
    assert ref.doi == "10.1109/CVPR.2016" and ref.alt_dois == ("10.1109/CVPR.2016.90",)
    fake = FakeGet(FakeResponse(status=404), ok(csl()))
    result = verify_reference(ref, EMAIL, get=fake)
    assert result.status == CONFIRMED and "line break closed" in result.why
    assert fake.calls == ["https://doi.org/10.1109/CVPR.2016", "https://doi.org/10.1109/CVPR.2016.90"]


def test_a_second_reading_that_does_not_resolve_leaves_no_note_and_the_search_still_runs():
    ref = parse_reference("A. One. Deep residual learning for image recognition. CVPR, 2016. doi:10.1000/abc. Next sentence here.")
    fake = FakeGet(FakeResponse(status=404), FakeResponse(status=404),
                   ok(search_result(year=2016)), ok(csl()))
    result = verify_reference(ref, EMAIL, get=fake)
    assert result.status == LIKELY
    assert "line break" not in result.why and "did not resolve" in result.why   # only the printed DOI is mentioned


def test_a_second_reading_that_points_to_another_paper_is_never_trusted():
    ref = parse_reference(BROKEN)
    fake = FakeGet(FakeResponse(status=404), ok(csl(title="A completely different subject of study", doi="10.1109/CVPR.2016.90")),
                   ok(search_result()), ok(csl()))
    result = verify_reference(ref, EMAIL, get=fake)
    assert result.status == CHECK and result.candidates


# ===== the connection test =====
def test_the_connection_test_passes_when_both_services_answer_correctly():
    fake = FakeGet(ok(csl()), ok(search_result(doi="10.1109/CVPR.2016.90")))
    results = check_connection(EMAIL, get=fake)
    assert [worked for _, worked, _ in results] == [True, True]


def test_the_connection_test_says_which_service_failed_and_why():
    fake = FakeGet(down(), ok(search_result(doi="10.1109/CVPR.2016.90")))
    (first, ok1, why1), (second, ok2, _) = check_connection(EMAIL, get=fake)
    assert not ok1 and "reach" in why1.lower() and ok2 and "doi.org" in first and "Crossref" in second


def test_the_connection_test_notices_a_wrong_answer():
    fake = FakeGet(ok(csl(title="Something else entirely")), ok(search_result(doi="10.1/other")))
    assert [worked for _, worked, _ in check_connection(EMAIL, get=fake)] == [False, False]
