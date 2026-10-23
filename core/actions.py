# ===== SECTION 1: imports =====
import csv
import difflib
import io
import zipfile
from dataclasses import dataclass, field

from .bibreader import extract_bib_entries
from .citecheck import extract_citations, rewrite_keys
from .compare import compare

# ===== SECTION 2: helpers that read many files at once =====
# tex_files and bib_files are dictionaries: {"chapter1.tex": "text...", ...}
def read_citations(tex_files):
    found = []
    for name, text in tex_files.items():
        found += extract_citations(text, name)
    return found

def read_entries(bib_files):
    found = []
    for name, text in bib_files.items():
        found += extract_bib_entries(text, name)
    return found

# ===== SECTION 3: cutting entries out of a .bib =====
# Works from the end of the file backwards so earlier positions stay valid.
# Also removes the spaces and the line break after the entry.
def remove_entries(bib_files, entries):
    new = dict(bib_files)
    by_file = {}
    for e in entries:
        by_file.setdefault(e.file, []).append(e)
    for name, items in by_file.items():
        text = new[name]
        for e in sorted(items, key=lambda x: x.start, reverse=True):
            end = e.end
            while end < len(text) and text[end] in " \t":
                end += 1
            if text[end:end + 2] == "\r\n":
                end += 2
            elif text[end:end + 1] == "\n":
                end += 1
            text = text[:e.start] + text[end:]
        new[name] = text
    return new

# ===== SECTION 4: finding duplicate keys =====
@dataclass
class DuplicateGroup:
    key: str
    versions: list      # BibEntry objects sharing the key
    identical: bool     # True when the copies are the same apart from spacing

def find_duplicate_groups(bib_files):
    groups = {}
    for e in read_entries(bib_files):
        groups.setdefault(e.key.lower(), []).append(e)
    result = []
    for versions in groups.values():
        if len(versions) > 1:
            same = len({" ".join(v.raw.split()) for v in versions}) == 1
            result.append(DuplicateGroup(versions[0].key, versions, same))
    return result

# ===== SECTION 5: the plan and the result =====
@dataclass
class Plan:
    merge_duplicates: bool = False
    keep_choice: dict = field(default_factory=dict)   # lowercase key -> version to keep
    fix_case: bool = False
    clean_unused: bool = False

@dataclass
class Result:
    tex_files: dict
    bib_files: dict
    removed: list = field(default_factory=list)   # {"reason", "entry"}
    changes: list = field(default_factory=list)   # {"action","file","line","detail"}

# ===== SECTION 6: apply the plan =====
# Order matters: merge duplicates first, then fix case, then remove unused.
# After each step the files are read again, so each step sees the result
# of the one before. Your original texts are never modified: we work on copies.
def apply_plan(tex_files, bib_files, plan):
    tex, bib = dict(tex_files), dict(bib_files)
    result = Result(tex, bib)

    if plan.merge_duplicates:
        drop = []
        for g in find_duplicate_groups(bib):
            keep = plan.keep_choice.get(g.key.lower(), 0)
            for i, v in enumerate(g.versions):
                if i != keep:
                    drop.append(v)
                    result.removed.append({"reason": "duplicate key", "entry": v})
                    result.changes.append({"action": "merge duplicate", "file": v.file,
                                           "line": v.line, "detail": f"removed extra copy of {v.key}"})
        bib = remove_entries(bib, drop)

    if plan.fix_case:
        report = compare(read_citations(tex), read_entries(bib))
        mapping = {m["cited as"]: m["entry is"] for m in report.case_mismatch}
        if mapping:
            for name, text in list(tex.items()):
                tex[name], log = rewrite_keys(text, mapping, name)
                result.changes += [{"action": "fix case", **row} for row in log]

    if plan.clean_unused:
        citations = read_citations(tex)
        if not any(c.key == "*" for c in citations):          # \nocite{*}: keep all
            cited = {c.key.lower() for c in citations}
            drop = [e for e in read_entries(bib) if e.key.lower() not in cited]
            for e in drop:
                result.removed.append({"reason": "unused", "entry": e})
                result.changes.append({"action": "remove unused", "file": e.file,
                                       "line": e.line, "detail": f"removed entry {e.key}"})
            bib = remove_entries(bib, drop)

    result.tex_files, result.bib_files = tex, bib
    return result

# ===== SECTION 7: preview and download =====
def make_diff(old_files, new_files):
    parts = []
    for name, new_text in new_files.items():
        if old_files.get(name) != new_text:
            parts += difflib.unified_diff(
                old_files[name].splitlines(), new_text.splitlines(),
                fromfile=f"original/{name}", tofile=f"corrected/{name}", lineterm="")
    return "\n".join(parts)

def build_zip(result):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in {**result.tex_files, **result.bib_files}.items():
            z.writestr(f"corrected/{name}", text.encode("utf-8"))
        if result.removed:
            blocks = [f"% removed ({r['reason']}) from {r['entry'].file}:{r['entry'].line}\n{r['entry'].raw}\n"
                      for r in result.removed]
            z.writestr("removed_entries.bib", "\n".join(blocks).encode("utf-8"))
        log = io.StringIO()
        writer = csv.DictWriter(log, fieldnames=["action", "file", "line", "detail"])
        writer.writeheader()
        writer.writerows(result.changes)
        z.writestr("change_log.csv", log.getvalue().encode("utf-8"))
    return buffer.getvalue()