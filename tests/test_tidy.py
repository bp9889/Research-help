from core.actions import Plan, apply_plan
from core.bibreader import extract_bib_entries
from core.tidy import format_entry, parse_entry, same_wording, tidy_bib, tidy_entry

MESSY = (
    "% my references\n"
    "\n"
    "@Article{ Key1,\n"
    '  Title = "Deep {learning} for power systems",\n'
    "  AUTHOR={Li, A and Wu, B},\n"
    "  year = {2020},\n"
    "  journal = Nature,\n"
    "  month = jan,\n"
    "  volume = 12,\n"
    "  pages = {1--10},\n"
    "}\n"
    "\n\n"
    "@book{k2,\n"
    "  publisher = {P}, title={Intro\n      duction}, year=2019\n"
    "}\n"
)

TIDY = (
    "% my references\n"
    "@Article{Key1,\n"
    "\ttitle        = {Deep {learning} for power systems},\n"
    "\tauthor       = {Li, A and Wu, B},\n"
    "\tyear         = 2020,\n"
    "\tmonth        = jan,\n"
    "\tjournal      = Nature,\n"
    "\tvolume       = 12,\n"
    "\tpages        = {1--10}\n"
    "}\n"
    "@book{k2,\n"
    "\ttitle        = {Intro duction},\n"
    "\tyear         = 2019,\n"
    "\tpublisher    = {P}\n"
    "}\n"
)


def test_messy_file_becomes_the_owners_style():
    text, log = tidy_bib(MESSY, "r.bib")
    assert text == TIDY
    assert [r["action"] for r in log] == ["tidy", "tidy"]


def test_tidy_is_idempotent_and_reports_nothing_the_second_time():
    text, _ = tidy_bib(MESSY)
    again, log = tidy_bib(text)
    assert again == text and log == []


def test_numbers_are_bare_macros_stay_bare_and_other_values_get_braces():
    raw = '@misc{k,\n year = {2020}, month = jan, note = "text", pages = 5\n}'
    new, reason = tidy_entry(raw)
    assert reason == ""
    assert "year         = 2020" in new and "month        = jan" in new
    assert "note         = {text}" in new and "pages        = 5" in new


def test_unknown_fields_go_after_the_listed_ones_in_written_order():
    raw = "@misc{k,\n zzz = {1x}, abstract = {A}, title = {T}\n}"
    new, _ = tidy_entry(raw)
    names = [line.split("=")[0].strip() for line in new.splitlines()[1:-1]]
    assert names == ["title", "zzz", "abstract"]


def test_long_field_names_still_get_a_space_before_the_equals_sign():
    new = format_entry("misc", "k", [("averyveryverylongname", "x", False)])
    assert "\taveryveryverylongname = {x}" in new


def test_no_trailing_comma_and_no_blank_lines_between_entries():
    text, _ = tidy_bib("@a{x,\n title={T},\n}\n\n\n\n@a{y,\n title={U},\n}\n")
    assert ",\n}" not in text and "\n\n" not in text


def test_comments_string_and_comment_blocks_are_kept():
    src = ('@string{jan = "January"}\n\n@a{x,\n title={T}\n}\n\n% between\n'
           '@comment{keep me}\n@a{y,\n title={U}\n}\n')
    text, _ = tidy_bib(src)
    assert '@string{jan = "January"}' in text and "% between" in text
    assert "@comment{keep me}" in text
    assert [e.key for e in extract_bib_entries(text)] == ["x", "y"]


def test_entries_are_never_sorted_or_removed():
    src = "@a{z,\n title={T}\n}\n@a{z,\n title={T}\n}\n@a{b,\n title={U}\n}\n"
    text, _ = tidy_bib(src)
    assert [e.key for e in extract_bib_entries(text)] == ["z", "z", "b"]


def test_windows_line_endings_are_kept():
    text, _ = tidy_bib("@a{x,\r\n  title={T}\r\n}\r\n")
    assert text == "@a{x,\r\n\ttitle        = {T}\r\n}\r\n"


def test_round_brackets_become_braces_and_quotes_with_accents_work():
    raw = '@a(x,\n author = "M{\\"u}ller, A"\n)'
    new, reason = tidy_entry(raw)
    assert reason == "" and new == '@a{x,\n\tauthor       = {M{\\"u}ller, A}\n}'


def test_an_entry_it_cannot_read_exactly_is_left_unchanged_and_reported():
    src = '@a{x,\n title = "Part one" # " and two"\n}\n@a{y,\n title = {U}\n}\n'
    text, log = tidy_bib(src)
    assert '"Part one" # " and two"' in text            # untouched
    assert "title        = {U}" in text                 # the next entry is still tidied
    assert [r["action"] for r in log] == ["tidy skipped", "tidy"]
    assert "#" in log[0]["detail"]


def test_comment_inside_an_entry_is_reported_not_guessed():
    _, reason = tidy_entry("@a{x,\n title = {T}, % hmm\n year = 2020\n}")
    assert reason != ""


def test_unbalanced_braces_are_reported():
    _, reason = tidy_entry("@a{x,\n title = {T\n}")
    assert reason != ""


def test_wording_guard_accepts_layout_changes_and_rejects_word_changes():
    old = "@a{k,\n title = {Deep learning},\n year = 2020\n}"
    assert same_wording(old, "@a{k,\n\tyear = {2020},\n\ttitle = {Deep   learning}\n}")
    assert not same_wording(old, "@a{k,\n title = {Deep learnin},\n year = 2020\n}")   # a letter lost
    assert not same_wording(old, "@a{k,\n title = {Deep Learning},\n year = 2020\n}")  # case changed
    assert not same_wording(old, "@a{k,\n title = {Deep learning}\n}")                 # field dropped
    assert not same_wording(old, "@a{j,\n title = {Deep learning},\n year = 2020\n}")  # key changed


def test_every_tidied_entry_passes_the_guard_against_its_original():
    for old, new in zip(extract_bib_entries(MESSY), extract_bib_entries(tidy_bib(MESSY)[0])):
        assert same_wording(old.raw, new.raw)


def test_parse_entry_keeps_duplicate_fields():
    p = parse_entry("@a{x,\n note = {1}, note = {2}\n}")
    assert [f[1] for f in p.fields] == ["1", "2"]


def test_tidy_can_be_part_of_a_plan_and_runs_last():
    bib = "@a{1,\n title = {A}\n}\n@a{2,\n title = {B}\n}\n"
    r = apply_plan({"x.tex": "\\cite{1}"}, {"r.bib": bib}, Plan(clean_unused=True, tidy=True))
    assert r.bib_files["r.bib"] == "@a{1,\n\ttitle        = {A}\n}\n"
    assert [c["action"] for c in r.changes] == ["remove unused", "tidy"]


def test_tidy_never_modifies_the_original_files():
    bib = {"r.bib": MESSY}
    apply_plan({"x.tex": "\\cite{Key1}"}, bib, Plan(tidy=True))
    assert bib == {"r.bib": MESSY}
