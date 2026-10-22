from core.citecheck import extract_citations


def keys(tex):
    return [c.key for c in extract_citations(tex)]


def test_single_citation_with_line_number():
    result = extract_citations("Intro.\nSee \\cite{1}.")
    assert [(c.key, c.line) for c in result] == [("1", 2)]


def test_several_keys_in_one_command():
    assert keys("\\cite{1, 2,3}") == ["1", "2", "3"]


def test_commented_out_citation_is_ignored_and_lines_stay_correct():
    result = extract_citations("% \\cite{9}\nText \\cite{1}")
    assert [(c.key, c.line) for c in result] == [("1", 2)]


def test_optional_arguments():
    assert keys("\\citep[p.~3]{smith2020}") == ["smith2020"]


def test_keys_split_across_lines():
    result = extract_citations("\\cite{a,\n b}")
    assert [(c.key, c.line) for c in result] == [("a", 1), ("b", 1)]


def test_escaped_percent_is_not_a_comment():
    assert keys("50\\% done \\cite{4}") == ["4"]


def test_other_citation_commands():
    assert keys("\\citet{x} \\nocite{y}") == ["x", "y"]


def test_no_citations():
    assert extract_citations("Nothing to see here.") == []

def test_one_long_line_still_gives_different_columns():
    result = extract_citations("In~\\cite{6}, one. In~\\cite{31}, two.")
    assert [c.line for c in result] == [1, 1]
    assert result[0].col == 4
    assert result[1].col > result[0].col


def test_context_shows_words_around_the_citation():
    result = extract_citations("The authors found X in~\\cite{6}, then Y.")
    assert "found X" in result[0].context and "then Y" in result[0].context