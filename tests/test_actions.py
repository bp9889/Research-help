from core.actions import Plan, apply_plan, build_zip, find_duplicate_groups, make_diff
from core.bibreader import extract_bib_entries
from core.fields import find_same_paper_groups

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


# ===== merge the same paper under different keys =====
SAME = ("@article{a,\n  title = {Deep learning for power systems},\n  year = {2019}\n}\n"
        "@article{b,\n  title = {Deep Learning for {Power} Systems},\n  year = {2020}\n}\n")


def gid(bib):
    return find_same_paper_groups(extract_bib_entries(bib))[0].id


def test_same_paper_merge_removes_one_entry_and_rewrites_its_citations():
    plan = Plan(merge_same_paper=True, same_keep={gid(SAME): "a"})
    r = apply_plan({"x.tex": "\\cite{b} and \\cite{a}"}, {"r.bib": SAME}, plan)
    assert r.tex_files["x.tex"] == "\\cite{a} and \\cite{a}"
    assert "@article{a," in r.bib_files["r.bib"] and "@article{b," not in r.bib_files["r.bib"]
    assert [x["reason"] for x in r.removed] == ["same paper"]
    assert [c["action"] for c in r.changes] == ["merge same paper", "merge same paper"]


def test_same_paper_merge_keeps_the_key_you_choose():
    plan = Plan(merge_same_paper=True, same_keep={gid(SAME): "b"})
    r = apply_plan({"x.tex": "\\cite{a}"}, {"r.bib": SAME}, plan)
    assert r.tex_files["x.tex"] == "\\cite{b}"
    assert "@article{b," in r.bib_files["r.bib"] and "@article{a," not in r.bib_files["r.bib"]


def test_a_group_without_a_choice_is_left_alone():
    r = apply_plan({"x.tex": "\\cite{b}"}, {"r.bib": SAME}, Plan(merge_same_paper=True))
    assert r.bib_files["r.bib"] == SAME and r.tex_files["x.tex"] == "\\cite{b}"
    assert r.changes == [] and r.removed == []


def test_a_key_that_is_not_in_the_group_is_ignored():
    plan = Plan(merge_same_paper=True, same_keep={gid(SAME): "zzz"})
    r = apply_plan({"x.tex": "\\cite{b}"}, {"r.bib": SAME}, plan)
    assert r.bib_files["r.bib"] == SAME and r.changes == []


def test_a_citation_written_in_another_case_is_rewritten_too():
    plan = Plan(merge_same_paper=True, same_keep={gid(SAME): "a"})
    r = apply_plan({"x.tex": "\\cite{B}"}, {"r.bib": SAME}, plan)
    assert r.tex_files["x.tex"] == "\\cite{a}"


def test_three_look_alikes_collapse_into_the_chosen_one():
    bib = ("@article{a,\n  doi = {10.1/x}\n}\n"
           "@article{b,\n  doi = {10.1/X},\n  title = {Deep learning for power systems}\n}\n"
           "@article{c,\n  title = {Deep learning for power systems}\n}\n")
    groups = find_same_paper_groups(extract_bib_entries(bib))
    assert len(groups) == 1 and len(groups[0].entries) == 3
    plan = Plan(merge_same_paper=True, same_keep={groups[0].id: "b"})
    r = apply_plan({"x.tex": "\\cite{a, c}"}, {"r.bib": bib}, plan)
    assert r.tex_files["x.tex"] == "\\cite{b, b}"
    assert [e.key for e in extract_bib_entries(r.bib_files["r.bib"])] == ["b"]


def test_same_paper_merge_never_touches_the_original_files():
    tex, bib = {"x.tex": "\\cite{b}"}, {"r.bib": SAME}
    apply_plan(tex, bib, Plan(merge_same_paper=True, same_keep={gid(SAME): "a"}))
    assert tex == {"x.tex": "\\cite{b}"} and bib == {"r.bib": SAME}


def test_same_paper_runs_before_clean_unused_so_the_kept_entry_stays():
    # Only b is cited. After merging into a, the citation says a, so a is not "unused".
    plan = Plan(merge_same_paper=True, same_keep={gid(SAME): "a"}, clean_unused=True)
    r = apply_plan({"x.tex": "\\cite{b}"}, {"r.bib": SAME}, plan)
    assert [e.key for e in extract_bib_entries(r.bib_files["r.bib"])] == ["a"]
    assert [x["reason"] for x in r.removed] == ["same paper"]


def test_duplicate_keys_are_merged_first_then_the_same_paper():
    bib = SAME + "@article{a,\n  title = {Deep learning for power systems},\n  year = {2019}\n}\n"
    plan = Plan(merge_duplicates=True, merge_same_paper=True, same_keep={"a|b": "a"})
    r = apply_plan({"x.tex": "\\cite{b}"}, {"r.bib": bib}, plan)
    assert [e.key for e in extract_bib_entries(r.bib_files["r.bib"])] == ["a"]
    assert r.tex_files["x.tex"] == "\\cite{a}"
