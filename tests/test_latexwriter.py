from core.latexwriter import (blocks_to_latex, escape_latex, is_numbered_heading,
                              split_number)
from core.pdfreader import Block


def make(*pairs):
    return [Block(kind, text, 1) for kind, text in pairs]


def test_escape_all_special_characters_once():
    assert escape_latex("50% of R&D_x #1 {a} ~ ^ $") == (
        r"50\% of R\&D\_x \#1 \{a\} \textasciitilde{} \textasciicircum{} \$")
    assert escape_latex("\\") == r"\textbackslash{}"


def test_split_number_depth():
    assert split_number("3. Methods") == (1, "Methods")
    assert split_number("3.1. Setup") == (2, "Setup")
    assert split_number("3.1.2 Details") == (3, "Details")
    assert split_number("Methods") == (0, "Methods")


def test_strict_needs_a_dot():
    assert not is_numbered_heading("2023 Annual report")
    assert is_numbered_heading("1. INTRODUCTION")
    assert not is_numbered_heading("1. This is a full sentence that ends here.")


def test_heading_levels_come_from_numbers():
    tex = blocks_to_latex(make(("title", "My Paper"), ("heading", "3. Methods"),
                               ("heading", "3.1. Setup"), ("heading", "3.1.2 More"))).tex
    assert "\\section{Methods}" in tex
    assert "\\subsection{Setup}" in tex
    assert "\\subsubsection{More}" in tex


def test_plain_text_heading_is_promoted_and_noted():
    result = blocks_to_latex(make(("title", "T"), ("text", "1. INTRODUCTION"),
                                  ("text", "Body text.")))
    assert "\\section{INTRODUCTION}" in result.tex
    assert any("promoted" in n["message"] for n in result.notes)


def test_title_abstract_keywords_and_authors():
    result = blocks_to_latex(make(
        ("heading", "A Great Paper"), ("text", "Ann Lee, Bo Chen"),
        ("heading", "ABSTRACT"), ("text", "We study 100% of cases."),
        ("heading", "KEYWORDS"), ("text", "Control, MPC"), ("heading", "1. Intro")))
    assert "\\title{A Great Paper}" in result.tex
    assert "\\author{Ann Lee, Bo Chen}" in result.tex
    assert "\\begin{abstract}\nWe study 100\\% of cases.\n\\end{abstract}" in result.tex
    assert "\\textbf{Keywords:} Control, MPC" in result.tex


def test_index_terms_line_is_split_off():
    result = blocks_to_latex(make(("heading", "T"), ("heading", "ABSTRACT"),
                                  ("text", "Short abstract."),
                                  ("text", "Index Terms- Spatial Audio, Coding")))
    assert "\\textbf{Keywords:} Spatial Audio, Coding" in result.tex


def test_references_are_collected_not_typeset():
    result = blocks_to_latex(make(("heading", "T"), ("heading", "1. Intro"), ("text", "Hello."),
                                  ("heading", "6. REFERENCES"), ("list_item", "[1] A. B."),
                                  ("text", "[2] C. D.")))
    assert result.references == ["[1] A. B.", "[2] C. D."]
    assert "A. B." not in result.tex


def test_list_items_become_itemize():
    tex = blocks_to_latex(make(("heading", "T"), ("heading", "1. Intro"),
                               ("list_item", "one"), ("list_item", "two"), ("text", "after"))).tex
    assert "\\begin{itemize}\n  \\item one\n  \\item two\n\\end{itemize}" in tex
    assert tex.index("\\end{itemize}") < tex.index("after")


def test_unsupported_blocks_are_visible():
    result = blocks_to_latex(make(("heading", "T"), ("heading", "1. Intro"),
                                  ("formula", ""), ("figure", ""), ("table", ""),
                                  ("caption", "Fig. 1. A plot"), ("other", "weird")))
    assert "% FORMULA (page 1)" in result.tex
    assert "% FIGURE (page 1)" in result.tex
    assert "% CAPTION (page 1): Fig. 1. A plot" in result.tex
    assert len(result.notes) == 5


def test_math_symbols_are_flagged():
    result = blocks_to_latex(make(("heading", "T"), ("heading", "1. Intro"),
                                  ("text", "The power 𝐶𝑝 depends on β and A ∈ R.")))
    assert any("math symbol" in n["message"] for n in result.notes)


def test_skip_blocks_disappear():
    tex = blocks_to_latex(make(("heading", "T"), ("skip", "Page 3"), ("heading", "1. A"))).tex
    assert "Page 3" not in tex