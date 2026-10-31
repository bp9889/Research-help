import pytest

from core.pdfreader import Block
from core.refextract import (from_blocks, from_text, parse_reference, reference_strings,
                             search_text, split_references, text_after_heading)


def heading(text):
    return Block("heading", text)


def text(t):
    return Block("text", t)


# ===== finding the heading =====
@pytest.mark.parametrize("title", ["References", "REFERENCES", "7. References", "VII. REFERENCES",
                                   "Bibliography", "Works Cited", "References:"])
def test_common_reference_headings_are_found(title):
    strings, notes = reference_strings([heading("Intro"), text("body"), heading(title),
                                        text("[1] A. One. A paper. 2020.")])
    assert strings == ["[1] A. One. A paper. 2020."] and notes == []


def test_the_last_references_heading_wins():
    blocks = [heading("Contents"), heading("References"), text("page 9"),
              heading("1. Intro"), text("body"),
              heading("References"), text("[1] Real one.")]
    assert reference_strings(blocks)[0] == ["[1] Real one."]


def test_a_sentence_that_starts_with_the_word_is_not_a_heading():
    blocks = [heading("References to earlier work in this field"), text("body")]
    strings, notes = reference_strings(blocks)
    assert strings == [] and "No References heading" in notes[0]


def test_reading_stops_at_the_next_heading_and_says_so():
    blocks = [heading("References"), text("[1] First."), heading("Appendix A"), text("proof")]
    strings, notes = reference_strings(blocks)
    assert strings == ["[1] First."]
    assert "Appendix A" in notes[0]


def test_page_furniture_and_figures_between_references_are_ignored():
    blocks = [heading("References"), text("[1] First."), Block("skip", "Journal 2026"),
              Block("figure", ""), text("[2] Second.")]
    assert reference_strings(blocks)[0] == ["[1] First.", "[2] Second."]


def test_a_heading_with_nothing_after_it_is_reported():
    strings, notes = reference_strings([heading("References")])
    assert strings == [] and "no text follows" in notes[0]


# ===== pasted text =====
def test_pasted_text_is_cut_after_the_last_heading():
    pasted = "Body.\nReferences\n[1] A. One. 2020.\n[2] B. Two. 2021."
    assert text_after_heading(pasted) == "[1] A. One. 2020.\n[2] B. Two. 2021."


def test_pasted_text_without_a_heading_is_taken_whole():
    assert text_after_heading("[1] A.\n[2] B.") == "[1] A.\n[2] B."


# ===== cutting one blob into references =====
def test_bracket_numbers_split_a_one_line_blob():
    refs, _ = split_references(["[1] A. One. Alpha. 2020. [2] B. Two. Beta. 2021."])
    assert [r.label for r in refs] == ["[1]", "[2]"]
    assert refs[1].raw == "B. Two. Beta. 2021."


def test_bracket_numbers_split_a_wrapped_multi_line_blob():
    blob = "[1] A. One. A long title that\nwraps over lines. 2020.\n[2] B. Two. Beta. 2021."
    refs, _ = split_references([blob])
    assert [r.raw for r in refs] == ["A. One. A long title that wraps over lines. 2020.",
                                     "B. Two. Beta. 2021."]


def test_numbered_lines_with_dots_split():
    refs, _ = split_references(["1. A. One. Alpha. 2020.\n2. B. Two. Beta. 2021."])
    assert [r.label for r in refs] == ["1.", "2."]


def test_blank_lines_split():
    refs, _ = split_references(["A. One. Alpha. 2020.\n\nB. Two. Beta. 2021."])
    assert len(refs) == 2


def test_one_wrapped_reference_in_a_block_stays_one():
    refs, notes = split_references(["A. One. A long title that\nwraps over lines. 2020."])
    assert len(refs) == 1 and notes == []


def test_pasted_lines_that_end_with_a_year_are_split_where_the_references_end_with_a_warning():
    refs, notes = from_text("A. One. Alpha. 2020.\nB. Two. Beta. 2021.")
    assert [r.year for r in refs] == ["2020", "2021"]
    assert "where a line ends with a year, DOI or link" in notes[0]


def test_pasted_lines_with_nothing_to_go_on_are_split_per_line_with_a_warning():
    refs, notes = from_text("Alpha by One\nBeta by Two")
    assert len(refs) == 2
    assert "every line is treated as one reference" in notes[0]


def test_empty_paste_says_nothing_was_found():
    refs, notes = from_text("   \n  ")
    assert refs == [] and "No references were found" in notes[-1]


def test_from_blocks_gives_one_reference_per_block():
    refs, notes = from_blocks([heading("References"),
                               text("[1] A. One. Alpha. 2020."),
                               text("[2] B. Two. Beta. 2021.")])
    assert [r.label for r in refs] == ["[1]", "[2]"] and notes == []


# ===== reading the useful bits =====
def test_label_is_taken_off_and_kept_separately():
    ref = parse_reference("[12]   K. He.  Deep   learning. 2016.")
    assert (ref.label, ref.raw) == ("[12]", "K. He. Deep learning. 2016.")


@pytest.mark.parametrize("printed", [
    "A title. doi:10.1109/CVPR.2016.90.",
    "A title. https://doi.org/10.1109/CVPR.2016.90",
    "A title. DOI 10.1109/CVPR.2016.90, pp. 1-9",
    "A title (10.1109/CVPR.2016.90)",
])
def test_doi_is_found_and_trailing_punctuation_is_dropped(printed):
    assert parse_reference(printed).doi == "10.1109/CVPR.2016.90"


def test_arxiv_number_is_found():
    assert parse_reference("A. One. A title. arXiv:2301.01234v2, 2023.").arxiv == "2301.01234"


def test_a_year_in_brackets_wins_over_other_numbers():
    ref = parse_reference("A. One. Title. Journal 1998, vol 3 (2019), pp 1998-2004.")
    assert ref.year == "2019"


def test_the_last_year_is_used_when_there_are_no_brackets():
    assert parse_reference("A. One. Title. Journal, 2018.").year == "2018"


def test_digits_inside_a_doi_are_not_taken_as_the_year():
    ref = parse_reference("A. One. A title without a year. https://doi.org/10.1000/2019.55")
    assert ref.year == "" and ref.doi == "10.1000/2019.55"


def test_nothing_is_invented_when_the_reference_has_no_ids():
    ref = parse_reference("A. One. A title.")
    assert (ref.doi, ref.arxiv, ref.year) == ("", "", "")


def test_search_text_has_no_links_or_doi():
    ref = parse_reference("A. One. A title. 2020. https://example.org/x doi:10.1000/abc")
    assert search_text(ref) == "A. One. A title. 2020. doi:"


def test_search_text_is_cut_to_a_sensible_length():
    assert len(search_text(parse_reference("word " * 200))) <= 300


# ===== the problems found on the first real paper =====
def test_a_doi_broken_over_two_lines_is_repaired_but_the_printed_text_is_kept():
    ref = parse_reference("[21] Why things happen. Nature, 653(8115):650, 2026. doi: 10.1038/ d41586-026-01551-3.")
    assert ref.doi == "10.1038/d41586-026-01551-3"
    assert "10.1038/ d41586" in ref.raw                       # raw is exactly as printed


def test_a_doi_broken_after_a_hyphen_is_repaired():
    assert parse_reference("A. One. Title. 2023. doi: 10.1038/s41586-023- 06734-w.").doi == "10.1038/s41586-023-06734-w"


def test_a_break_after_a_full_stop_is_not_guessed():
    # "...2016. 90" could be the end of a sentence, so only the safe part is kept.
    assert parse_reference("A. One. Title. doi:10.1109/CVPR.2016. 90").doi == "10.1109/CVPR.2016"


def test_text_after_a_finished_doi_is_never_glued_to_it():
    assert parse_reference("A. One. Title. doi:10.1000/abc. Next sentence here.").doi == "10.1000/abc"


def test_a_link_broken_after_the_colon_is_removed_from_the_search_text():
    ref = parse_reference("A. One. A title here. URL https: //openreview.net/forum?id=X1. arXiv:2310.01798.")
    assert "openreview" not in search_text(ref) and ref.arxiv == "2310.01798"


# ===== years =====
def test_years_before_1950_are_found():
    assert parse_reference("R. Fisher. The design of experiments. Oliver and Boyd, 1935.").year == "1935"
    assert parse_reference("A. Einstein (1905). On the electrodynamics of moving bodies.").year == "1905"


def test_numbers_inside_page_ranges_and_volumes_are_not_years():
    assert parse_reference("A. One. Title. J. Phys., 35(2):1850, 2004.").year == "2004"
    assert parse_reference("A. One. Title. Journal, pages 1789-1802, 1999.").year == "1999"
    assert parse_reference("A. One. Title. Journal, vol. 1850, no. 3.").year == ""


def test_the_edition_year_wins_over_an_originally_published_note():
    ref = parse_reference("R. Merton. The normative structure of science. University of Chicago "
                          "Press, 1973. Originally published as “A Note”, J. Legal Soc. 1 (1942).")
    assert ref.year == "1973"


# ===== finding the heading =====
@pytest.mark.parametrize("title", ["Reference list", "References and Notes", "Notes and References",
                                   "Literature Cited", "List of References", "Bibliography and References",
                                   "Cited literature"])
def test_more_heading_wordings_are_found(title):
    assert reference_strings([heading(title), text("[1] A. One. A paper. 2020.")])[0] == ["[1] A. One. A paper. 2020."]


def test_a_heading_the_pdf_reader_made_a_plain_text_block_is_still_found():
    blocks = [text("Intro body"), text("References"), text("[1] A. One. Alpha. 2020.")]
    assert reference_strings(blocks)[0] == ["[1] A. One. Alpha. 2020."]


def test_a_long_text_block_that_starts_with_the_word_is_not_a_heading():
    long_text = "References to earlier work are collected in the long paragraph below this line."
    assert reference_strings([text(long_text), text("body")])[0] == []


def test_no_heading_tells_you_about_the_paste_tab():
    _, notes = reference_strings([heading("Intro"), text("body")])
    assert "Paste the list" in notes[0]


def test_a_pdf_with_no_text_is_reported_as_a_possible_scan():
    refs, notes = from_blocks([])
    assert refs == [] and "scan" in notes[0] and "OCR" in notes[0]


# ===== pieces of the PDF that are not references =====
def test_page_numbers_between_references_are_ignored():
    blocks = [heading("References"), text("[1] A. One. Alpha. 2020."), text("15"),
              text("Page 16 of 17"), text("[2] B. Two. Beta. 2021.")]
    assert reference_strings(blocks)[0] == ["[1] A. One. Alpha. 2020.", "[2] B. Two. Beta. 2021."]


def test_a_piece_that_starts_with_a_page_range_or_doi_or_link_is_joined_back():
    blocks = [heading("References"),
              text("[1] A. One. A long title. Nature, 651(8107):"),
              text("914–919, 2026. doi: 10.1038/s41586-026-10265-5."),
              text("[2] B. Two. Beta paper. arXiv:2301.01234, 2023."),
              text("URL https://arxiv.org/abs/2301.01234.")]
    strings, notes = reference_strings(blocks)
    assert len(strings) == 2
    assert strings[0].endswith("doi: 10.1038/s41586-026-10265-5.")
    assert "2 piece(s)" in notes[0]


def test_a_normal_reference_is_never_joined_to_the_one_before():
    blocks = [heading("References"), text("A. One. Alpha. 2020."), text("van der Waals, J. Beta. 1910."),
              text("2020 Annual Report of the Society. Gamma. 2021.")]
    assert len(reference_strings(blocks)[0]) == 3


# ===== warnings about the result =====
def test_a_list_without_numbers_says_so_and_how_to_read_it():
    refs, notes = from_blocks([heading("References"), text("A. One. Alpha. 2020."), text("B. Two. Beta. 2021.")])
    assert len(refs) == 2 and "position in this list" in notes[0]


def test_a_numbered_list_gets_no_missing_numbers_warning():
    _, notes = from_blocks([heading("References"), text("[1] A. One. Alpha. 2020.")])
    assert notes == []


def test_a_block_with_two_dois_is_flagged_as_possibly_joined():
    joined = "A. One. Alpha. doi:10.1000/aaa. B. Two. Beta. doi:10.1000/bbb."
    _, notes = from_blocks([heading("References"), text("[1] Fine. Ref. 2020. doi:10.1000/ccc."), text(joined)])
    assert any("#2" in n and "two references joined" in n for n in notes)


def test_the_same_doi_written_twice_is_not_a_warning():
    _, notes = from_blocks([heading("References"),
                            text("[1] A. One. Alpha. doi:10.1000/aaa. https://doi.org/10.1000/AAA")])
    assert not any("joined" in n for n in notes)


def test_an_unusually_long_reference_is_flagged():
    _, notes = from_blocks([heading("References"), text("[1] " + "word " * 200)])
    assert any("unusually long" in n for n in notes)


# ===== pasted lists without numbers =====
def test_a_hanging_indent_splits_a_pasted_list():
    pasted = ("Smith, J. A long title that wraps\n"
              "    over a second line. Journal, 2020.\n"
              "Jones, K. Another title that also\n"
              "    wraps. Journal, 2021.\n")
    refs, notes = from_text(pasted)
    assert [r.year for r in refs] == ["2020", "2021"]
    assert "indented" in notes[0]


def test_a_list_flush_at_the_margin_with_wrapped_references_is_still_split():
    pasted = ("A. One. A long title that wraps\nover a second line. Journal, 2020.\n"
              "B. Two. Another title that\nwraps too. Journal, 2021.")
    refs, _ = from_text(pasted)
    assert [r.year for r in refs] == ["2020", "2021"]
    assert refs[0].raw == "A. One. A long title that wraps over a second line. Journal, 2020."


# ===== a whole invented list that copies the quirks of a real PDF =====
# Made up on purpose: real papers must not be committed (see CLAUDE.md).
INVENTED = """\
References
 [1] Ada Example, Bo Sample, Cy Placeholder, Di Testcase, Ed Fixture, Flo Mockup, Gus Stub,
     and Hal Dummy. A long made-up title about nothing in particular. Journal of Tests,
     427(6971):247–252, 2004. doi: 10.1000/test.0001.

 [2] Ida Example, Jo Sample, et al. Another made-up paper with a wrapped link. Journal of
     Tests, 324(5923):85–89, 2009. doi: 10.1000/
     test.0002.

 [3] Kai Example. A book about invented things. In Lou Editor, editor, The Book of Made-Up
     Things, pages 267–278. Press, City, 1973. Originally published in Journal of Tests 1,
     115–126 (1942).

                                                  15
 [4] Moe Example. Preprint without a DOI. arXiv:2607.00001v1, 2026. URL
     https://arxiv.org/abs/2607.00001.

 [5] Why made-up things happen. Journal of Tests, 653(8115):650, 2026. doi: 10.1000/
     d00005-026-00005-3.

 [6] Ned Example and Oz Sample. Large models on invented tasks. In International Conference
     on Tests (ICT 2024), 2024. URL https:
     //example.org/forum?id=ABC123. arXiv:2310.00002.
"""


def test_an_invented_list_with_all_the_real_quirks_is_read_correctly():
    refs, notes = from_text(INVENTED)
    assert [r.label for r in refs] == ["[1]", "[2]", "[3]", "[4]", "[5]", "[6]"]
    assert [r.doi for r in refs] == ["10.1000/test.0001", "10.1000/test.0002", "", "",
                                     "10.1000/d00005-026-00005-3", ""]
    assert [r.arxiv for r in refs] == ["", "", "", "2607.00001", "", "2310.00002"]
    assert [r.year for r in refs] == ["2004", "2009", "1973", "2026", "2026", "2024"]
    assert notes == []


def test_a_page_number_in_pasted_text_is_not_glued_to_the_reference_before_it():
    refs, _ = from_text(INVENTED)
    assert not refs[2].raw.endswith("15") and refs[2].raw.endswith("(1942).")


def test_a_year_alone_on_a_wrapped_line_is_never_thrown_away():
    pasted = "[1] A. One. A title that wraps\n2004.\n[2] B. Two. Another title. 2005."
    refs, _ = from_text(pasted)
    assert refs[0].year == "2004"


def test_a_block_starting_with_a_year_is_kept_not_thrown_away_as_a_page_number():
    # It is not glued to the reference before it either: a reference may
    # genuinely start with a year. It stays visible as its own entry.
    blocks = [heading("References"), text("[1] A. One. Alpha."), text("2004. doi: 10.1000/aaa.")]
    assert reference_strings(blocks)[0] == ["[1] A. One. Alpha.", "2004. doi: 10.1000/aaa."]


# ===== stricter versions: these fail if the protection is removed =====
def test_a_page_range_or_volume_that_looks_like_a_year_is_not_taken_even_when_it_comes_last():
    assert parse_reference("A. One. Title. Journal, 2004, pages 1789-1802.").year == "2004"
    assert parse_reference("A. One. Title. J. Phys. 2004;35(2):1850.").year == "2004"
    assert parse_reference("A. One. Title. Journal 2004, 1850–1862").year == "2004"
    assert parse_reference("A. One. Title. J. Phys. 35(2):1850.").year == ""


def test_a_year_alone_on_a_line_beside_a_blank_line_is_not_taken_for_a_page_number():
    pasted = "[1] A. One. A title that wraps\n\n2004.\n\n[2] B. Two. Another title. 2005."
    refs, _ = from_text(pasted)
    assert refs[0].year == "2004"


# ===== headings in other languages =====
@pytest.mark.parametrize("title", [
    "Literaturverzeichnis", "LITERATUR", "Références", "Bibliographie", "Références bibliographiques",
    "Referencias", "Bibliografía", "Referencias bibliográficas", "Referências", "Bibliografia",
    "Riferimenti bibliografici", "Referenties", "Literatuur", "Kaynaklar", "Kaynakça", "Daftar Pustaka",
    "Rujukan", "Список литературы", "Литература",
    "参考文献", "참고문헌", "참고 문헌", "المراجع",
    "তথ্যসূত্র", "গ্রন্থপঞ্জি", "संदर्भ",
    "7. Literaturverzeichnis", "5 RÉFÉRENCES",
])
def test_headings_in_other_languages_are_found(title):
    strings, notes = reference_strings([heading("Intro"), heading(title), text("[1] A. One. A paper. 2020.")])
    assert strings == ["[1] A. One. A paper. 2020."] and notes == []


def test_an_ordinary_word_that_only_contains_a_heading_word_is_not_a_heading():
    for sentence in ("Literature review", "Referencing styles", "Quellen of error in the model"):
        assert reference_strings([heading(sentence), text("body")])[0] == []


# ===== a DOI broken after a full stop =====
def test_both_readings_of_a_doi_broken_after_a_full_stop_are_kept():
    ref = parse_reference("[1] A. One. A title here. CVPR, 2016. doi: 10.1109/CVPR.2016. 90")
    assert ref.doi == "10.1109/CVPR.2016" and ref.alt_dois == ("10.1109/CVPR.2016.90",)


def test_an_ordinary_sentence_after_a_doi_gives_a_harmless_second_reading():
    ref = parse_reference("A. One. Title. doi:10.1000/abc. Next sentence here.")
    assert ref.doi == "10.1000/abc" and ref.alt_dois == ("10.1000/abc.Next",)


def test_a_reference_without_a_broken_doi_has_no_second_reading():
    assert parse_reference("A. One. Title. doi:10.1000/abc.").alt_dois == ()
    assert parse_reference("A. One. Title. 2020.").alt_dois == ()


# ===== unnumbered lists: split where a reference ends =====
UNNUMBERED = """\
Ross King, Ken Whelan, and Stephen Oliver. Functional genomic hypothesis generation by a
robot scientist. Nature, 427(6971):247–252,
2004. doi: 10.1038/nature02236.
Nathan Szymanski, Bernardus Rendy, et al. An autonomous laboratory for the synthesis of
inorganic materials. Nature, 624(7990):86–91, 2023. doi:
10.1038/s41586-023-06734-w.
Jie Huang, Xinyun Chen, and Denny Zhou. Large language models cannot self-correct reasoning
yet. In ICLR 2024, 2024. URL https:
//openreview.net/forum?id=IkmD3fKBPQ. arXiv:2310.01798.
Chenglei Si, Diyi Yang, and Tatsunori Hashimoto. Can LLMs generate novel research ideas? In
ICLR 2025, 2025. arXiv:2409.04109.
"""


def test_an_unnumbered_wrapped_list_is_split_into_the_right_references():
    refs, notes = from_text(UNNUMBERED)
    assert len(refs) == 4
    assert [r.year for r in refs] == ["2004", "2023", "2024", "2025"]
    assert [r.doi or r.arxiv for r in refs] == ["10.1038/nature02236", "10.1038/s41586-023-06734-w",
                                                  "2310.01798", "2409.04109"]
    assert any("where a line ends with a year, DOI or link" in n for n in notes)


def test_a_line_that_starts_with_in_doi_or_pages_continues_the_reference_before_it():
    pasted = ("A. One. A title here. Journal, 2020.\nIn Proceedings of the Society, pages 5-10, 2020.\n"
              "B. Two. Another title. Journal, 2021.\nDOI 10.1000/abc\nC. Three. Third. 2022.")
    refs, _ = from_text(pasted)
    assert len(refs) == 3 and "In Proceedings" in refs[0].raw and refs[1].doi == "10.1000/abc"


def test_a_reference_that_ends_without_a_year_or_link_is_joined_to_the_next_and_the_warning_says_so():
    # The documented limit of this guess: the first line gives no sign that it ends.
    pasted = ("A. One. A book about things. Press, City.\n"
              "B. Two. Beta paper. Journal, 2021.\n"
              "C. Three. Gamma paper. Journal, 2022.")
    refs, notes = from_text(pasted)
    assert len(refs) == 2 and "A book about things" in refs[0].raw and "Beta paper" in refs[0].raw
    assert "may be joined to the next one" in notes[0]


def test_two_lines_with_no_ending_cue_fall_back_to_one_per_line():
    refs, notes = from_text("A. One. A book about things. Press, City.\nB. Two. Beta paper. Journal, 2021.")
    assert len(refs) == 2 and "every line is treated as one reference" in notes[0]
