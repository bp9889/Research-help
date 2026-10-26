import pytest
import requests

from core.bibreader import extract_bib_entries
from core.doi import (bibtex_type, clean_doi, clean_text, csl_to_bibtex, escape_latex,
                      fetch_csl, missing_fields, search_title, suggest_key, valid_key)
from core.tidy import tidy_bib

ARTICLE = {
    "DOI": "10.1234/abc.5678", "URL": "https://doi.org/10.1234/abc.5678", "type": "article-journal",
    "title": "Flood <i>nowcasting</i> with CNN &amp; LSTM: 100% better",
    "author": [{"given": "Li", "family": "Zhang"},
               {"given": "Hans", "family": "Müller", "non-dropping-particle": "von"},
               {"literal": "World Bank"}],
    "container-title": "Water Resources Research", "volume": "56", "issue": "3", "page": "1-12",
    "issued": {"date-parts": [[2020, 3]]}, "publisher": "Wiley", "ISSN": ["0043-1397", "1944-7973"],
}

ARTICLE_BIBTEX = (
    "@article{zhang2020,\n"
    "\ttitle        = {Flood nowcasting with CNN \\& LSTM: 100\\% better},\n"
    "\tauthor       = {Zhang, Li and von Müller, Hans and {World Bank}},\n"
    "\tyear         = 2020,\n"
    "\tmonth        = 3,\n"
    "\tjournal      = {Water Resources Research},\n"
    "\tvolume       = 56,\n"
    "\tnumber       = 3,\n"
    "\tpages        = {1--12},\n"
    "\tdoi          = {10.1234/abc.5678},\n"
    "\tissn         = {0043-1397, 1944-7973}\n"
    "}"
)


# ===== a fake internet, so the tests run offline =====
class FakeResponse:
    def __init__(self, data=None, status=200, bad_json=False):
        self.status_code, self._data, self._bad = status, data, bad_json

    def json(self):
        if self._bad:
            raise ValueError("not json")
        return self._data


class FakeGet:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def __call__(self, url, headers=None, params=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "params": params})
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


# ===== the conversion (pure, no internet) =====
def test_a_journal_article_becomes_bibtex_in_the_owners_style():
    assert csl_to_bibtex(ARTICLE, "zhang2020") == ARTICLE_BIBTEX


def test_the_output_is_already_tidy_and_readable_by_the_checker():
    assert tidy_bib(ARTICLE_BIBTEX + "\n")[0] == ARTICLE_BIBTEX + "\n"
    assert [e.key for e in extract_bib_entries(ARTICLE_BIBTEX)] == ["zhang2020"]
    assert missing_fields(ARTICLE_BIBTEX) == []


def test_nothing_is_invented_when_the_server_sends_little():
    out = csl_to_bibtex({"type": "article-journal", "title": "Only a title"}, "k")
    assert out == "@article{k,\n\ttitle        = {Only a title}\n}"
    assert missing_fields(out)[0]["missing"] == "author, journal or journaltitle, year or date"


@pytest.mark.parametrize("csl_type, genre, expected", [
    ("article-journal", "", "article"), ("article-magazine", "", "article"),
    ("paper-conference", "", "inproceedings"), ("book", "", "book"),
    ("chapter", "", "incollection"), ("report", "", "techreport"),
    ("thesis", "PhD thesis", "phdthesis"), ("thesis", "Master's thesis", "mastersthesis"),
    ("thesis", "", "misc"), ("dataset", "", "misc"), ("article", "", "misc"), ("", "", "misc"),
])
def test_types_are_mapped_and_unknown_ones_become_misc(csl_type, genre, expected):
    assert bibtex_type({"type": csl_type, "genre": genre}) == expected


BASE = {"title": "T", "author": [{"given": "A", "family": "B"}], "issued": {"date-parts": [[2020]]},
        "publisher": "P", "container-title": "C"}


@pytest.mark.parametrize("csl_type, genre", [
    ("article-journal", ""), ("paper-conference", ""), ("book", ""), ("chapter", ""),
    ("report", ""), ("thesis", "PhD thesis"), ("thesis", "Master's thesis"),
])
def test_every_mapped_type_fills_the_fields_the_existing_check_requires(csl_type, genre):
    out = csl_to_bibtex({**BASE, "type": csl_type, "genre": genre}, "k")
    assert missing_fields(out) == []


def test_publisher_goes_where_the_entry_type_expects_it():
    report = csl_to_bibtex({**BASE, "type": "report"}, "k")
    thesis = csl_to_bibtex({**BASE, "type": "thesis", "genre": "PhD thesis"}, "k")
    assert "institution  = {P}" in report and "school       = {P}" in thesis
    assert "publisher" not in report + thesis
    assert "publisher" not in csl_to_bibtex({**BASE, "type": "article-journal"}, "k")


def test_markup_is_removed_but_a_lone_less_than_sign_stays():
    assert clean_text("A <jats:italic>b</jats:italic> <sub>2</sub> &amp; c") == "A b 2 & c"
    assert clean_text("p < 0.05 and q > 3") == "p < 0.05 and q > 3"
    assert clean_text(["Crossref sends lists"]) == "Crossref sends lists"


def test_special_characters_are_escaped_once():
    assert escape_latex("A & B, 5% of #1") == "A \\& B, 5\\% of \\#1"
    assert escape_latex("already \\& done") == "already \\& done"


def test_doi_and_url_are_not_escaped():
    csl = {**ARTICLE, "DOI": "10.1/a_b", "URL": "https://example.org/a?x=1&y=2#top"}
    out = csl_to_bibtex(csl, "k")
    assert "doi          = {10.1/a_b}" in out and "url          = {https://example.org/a?x=1&y=2#top}" in out


def test_a_plain_doi_link_is_not_repeated_as_a_url():
    assert "url" not in csl_to_bibtex(ARTICLE, "k")


def test_page_ranges_get_double_dashes_and_article_numbers_are_left_alone():
    assert "pages        = {123--130}" in csl_to_bibtex({**ARTICLE, "page": "123\u2013130"}, "k")
    assert "pages        = {e2019WR026}" in csl_to_bibtex({**ARTICLE, "page": "e2019WR026"}, "k")


def test_the_year_is_read_from_a_raw_date_only_when_there_are_no_date_parts():
    out = csl_to_bibtex({"type": "book", "issued": {"raw": "Spring 1999"}}, "k")
    assert "year         = 1999" in out and "month" not in out


def test_a_suffix_goes_between_family_and_given_name():
    csl = {"type": "book", "author": [{"given": "Martin", "family": "King", "suffix": "Jr."}]}
    assert "author       = {King, Jr., Martin}" in csl_to_bibtex(csl, "k")


# ===== keys and DOI text =====
@pytest.mark.parametrize("typed", [
    "10.1234/abc.5678", "doi:10.1234/abc.5678", "  https://doi.org/10.1234/abc.5678.  ",
    "doi.org/10.1234/abc.5678", "DOI: 10.1234/abc.5678;",
])
def test_the_doi_is_found_in_what_people_type(typed):
    assert clean_doi(typed) == "10.1234/abc.5678"


def test_text_without_a_doi_gives_an_empty_answer():
    assert clean_doi("hello") == "" and clean_doi(None) == ""


def test_suggested_keys_are_plain_letters_and_avoid_taken_keys():
    assert suggest_key(ARTICLE) == "zhang2020"
    assert suggest_key({"author": [{"family": "Müller"}], "issued": {"date-parts": [[2019]]}}) == "muller2019"
    assert suggest_key(ARTICLE, existing={"Zhang2020", "zhang2020a"}) == "zhang2020b"
    assert suggest_key({"issued": {"date-parts": [[2001]]}}) == "ref2001"
    assert suggest_key({"author": [{"literal": "World Bank"}]}) == "worldbank"


def test_a_key_may_not_contain_spaces_commas_or_braces():
    assert valid_key("smith2020") and valid_key("12") and valid_key("a_b-c:d")
    assert not any(valid_key(k) for k in ["", "a b", "a,b", "a{b", "a#b", "a%b"])


# ===== the internet part (with a fake one) =====
def test_fetch_sends_the_right_headers_and_url():
    get = FakeGet(FakeResponse(ARTICLE))
    csl, message = fetch_csl("10.1234/abc.5678", "me@x.org", get=get)
    assert csl == ARTICLE and message == ""
    call = get.calls[0]
    assert call["url"] == "https://doi.org/10.1234/abc.5678"
    assert call["headers"]["Accept"] == "application/vnd.citationstyles.csl+json"
    assert "mailto:me@x.org" in call["headers"]["User-Agent"]


def test_a_cached_answer_is_not_asked_for_twice():
    get, cache = FakeGet(FakeResponse(ARTICLE)), {}
    fetch_csl("10.1234/ABC.5678", "me@x.org", get=get, cache=cache)
    csl, _ = fetch_csl("10.1234/abc.5678", "me@x.org", get=get, cache=cache)
    assert csl == ARTICLE and len(get.calls) == 1


@pytest.mark.parametrize("response, words", [
    (FakeResponse(status=404), "No record"),
    (FakeResponse(status=429), "too many"),
    (FakeResponse(status=500), "error 500"),
    (FakeResponse(bad_json=True), "could not be read"),
    (FakeResponse(["not", "a", "dict"]), "unexpected"),
    (requests.ConnectionError("no wifi"), "Could not reach"),
    (requests.Timeout("slow"), "Could not reach"),
])
def test_failures_never_raise_and_say_what_happened(response, words):
    csl, message = fetch_csl("10.1/x", "me@x.org", get=FakeGet(response))
    assert csl is None and words in message


def test_a_failure_is_not_cached_so_the_next_try_asks_again():
    get, cache = FakeGet(FakeResponse(status=500), FakeResponse(ARTICLE)), {}
    assert fetch_csl("10.1/x", "me@x.org", get=get, cache=cache)[0] is None
    assert fetch_csl("10.1/x", "me@x.org", get=get, cache=cache)[0] == ARTICLE
    assert len(get.calls) == 2


CROSSREF_ANSWER = {"message": {"items": [
    {"DOI": "10.1/a", "title": ["Flood <i>nowcasting</i> methods"], "type": "journal-article",
     "author": [{"given": "A", "family": "One"}, {"family": "Two"}, {"family": "Three"}, {"family": "Four"}],
     "issued": {"date-parts": [[2021, 5]]}, "container-title": ["Journal of Water"]},
    {"DOI": "10.1/b", "title": ["Another paper"], "author": [{"name": "Some Organisation"}],
     "issued": {"date-parts": [[None]]}},
    {"title": ["No DOI, so it is skipped"]},
]}}


def test_title_search_returns_candidates_to_confirm_and_asks_politely():
    get = FakeGet(FakeResponse(CROSSREF_ANSWER))
    found, message = search_title("Flood nowcasting methods", "me@x.org", get=get)
    assert message == "" and [c["doi"] for c in found] == ["10.1/a", "10.1/b"]
    assert found[0] == {"doi": "10.1/a", "title": "Flood nowcasting methods",
                        "authors": "One, Two, Three et al.", "year": "2021",
                        "venue": "Journal of Water", "type": "journal-article"}
    assert found[1]["authors"] == "Some Organisation" and found[1]["year"] == ""
    call = get.calls[0]
    assert call["params"]["query.bibliographic"] == "Flood nowcasting methods"
    assert "mailto:me@x.org" in call["headers"]["User-Agent"]


def test_a_very_short_title_makes_no_request():
    get = FakeGet()
    found, message = search_title("flood", "me@x.org", get=get)
    assert found == [] and "at least 8" in message and get.calls == []


def test_search_failures_and_empty_results_come_back_as_messages():
    assert "Could not reach" in search_title("a long enough title", "m@x.org",
                                             get=FakeGet(requests.ConnectionError()))[1]
    found, message = search_title("a long enough title", "m@x.org",
                                  get=FakeGet(FakeResponse({"message": {"items": []}})))
    assert found == [] and "No matching" in message


def test_search_results_are_cached():
    get, cache = FakeGet(FakeResponse(CROSSREF_ANSWER)), {}
    search_title("Flood nowcasting methods", "me@x.org", get=get, cache=cache)
    search_title("  flood NOWCASTING methods ", "me@x.org", get=get, cache=cache)
    assert len(get.calls) == 1


def test_the_checker_modules_do_not_import_the_internet_code():
    import core.actions, core.bibreader, core.citecheck, core.compare, core.fields, core.tidy
    for module in (core.actions, core.bibreader, core.citecheck, core.compare, core.fields, core.tidy):
        assert not hasattr(module, "requests") and not hasattr(module, "fetch_csl")
