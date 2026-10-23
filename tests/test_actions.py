from core.actions import Plan, apply_plan, build_zip, find_duplicate_groups, make_diff

BIB = "@article{1,\n  title = {A}\n}\n\n@article{2,\n  title = {B}\n}\n"


def test_fix_case_changes_tex_only():
    r = apply_plan({"a.tex": "\\cite{Smith20}"}, {"r.bib": "@book{smith20,\n}\n"}, Plan(fix_case=True))
    assert r.tex_files["a.tex"] == "\\cite{smith20}"
    assert r.bib_files["r.bib"] == "@book{smith20,\n}\n"
    assert r.changes[0]["action"] == "fix case"


def test_original_files_are_never_modified():
    tex, bib = {"a.tex": "\\cite{1}"}, {"r.bib": BIB}
    apply_plan(tex, bib, Plan(clean_unused=True))
    assert tex == {"a.tex": "\\cite{1}"} and bib == {"r.bib": BIB}


def test_clean_unused_removes_only_uncited_entries():
    r = apply_plan({"a.tex": "\\cite{1}"}, {"r.bib": BIB}, Plan(clean_unused=True))
    assert "@article{1," in r.bib_files["r.bib"]
    assert "@article{2," not in r.bib_files["r.bib"]
    assert [x["entry"].key for x in r.removed] == ["2"]


def test_clean_unused_looks_at_every_chapter():
    tex = {"ch1.tex": "\\cite{1}", "ch2.tex": "\\cite{2}"}
    r = apply_plan(tex, {"r.bib": BIB}, Plan(clean_unused=True))
    assert r.removed == []


def test_clean_unused_does_nothing_with_nocite_star():
    r = apply_plan({"a.tex": "\\nocite{*}"}, {"r.bib": BIB}, Plan(clean_unused=True))
    assert r.removed == [] and r.bib_files["r.bib"] == BIB


def test_merge_identical_duplicates_keeps_one():
    bib = "@article{2,\n  title = {A}\n}\n@article{2,\n title = {A}\n}\n"
    assert find_duplicate_groups({"r.bib": bib})[0].identical
    r = apply_plan({"a.tex": "\\cite{2}"}, {"r.bib": bib}, Plan(merge_duplicates=True))
    assert r.bib_files["r.bib"].count("@article{2,") == 1


def test_merge_different_versions_follows_your_choice():
    bib = "@article{2,\n  year = {2019}\n}\n@article{2,\n  year = {2020}\n}\n"
    assert not find_duplicate_groups({"r.bib": bib})[0].identical
    r = apply_plan({"a.tex": "\\cite{2}"}, {"r.bib": bib}, Plan(merge_duplicates=True, keep_choice={"2": 1}))
    assert "2020" in r.bib_files["r.bib"] and "2019" not in r.bib_files["r.bib"]


def test_steps_run_in_order_merge_then_case_then_clean():
    bib = "@book{Smith20,\n}\n@book{smith20,\n}\n@book{9,\n}\n"
    r = apply_plan({"a.tex": "\\cite{smith20}"}, {"r.bib": bib},
                   Plan(merge_duplicates=True, fix_case=True, clean_unused=True))
    assert r.tex_files["a.tex"] == "\\cite{Smith20}"
    assert "@book{9," not in r.bib_files["r.bib"]


def test_diff_and_zip_contain_the_changes():
    r = apply_plan({"a.tex": "\\cite{Smith20}"}, {"r.bib": "@book{smith20,\n}\n"}, Plan(fix_case=True))
    assert "+\\cite{smith20}" in make_diff({"a.tex": "\\cite{Smith20}"}, r.tex_files)
    import io, zipfile
    names = zipfile.ZipFile(io.BytesIO(build_zip(r))).namelist()
    assert "corrected/a.tex" in names and "change_log.csv" in names