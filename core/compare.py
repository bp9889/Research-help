# ===== SECTION 1: imports =====
import difflib
from dataclasses import dataclass, field

# ===== SECTION 2: the report =====
@dataclass
class Report:
    missing: list = field(default_factory=list)        # cited, but not in the .bib
    unused: list = field(default_factory=list)         # in the .bib, never cited
    duplicates: list = field(default_factory=list)     # same key twice in the .bib
    case_mismatch: list = field(default_factory=list)  # Smith20 vs smith20
    nocite_all: bool = False                           # \nocite{*} was used

# ===== SECTION 3: helper - where was a key cited? =====
# With uploaded files the place also names the file: "ch2.tex: line 4, col 9".
def _where_cited(citations):
    places = {}
    for c in citations:
        prefix = f"{c.file}: " if c.file else ""
        places.setdefault(c.key, []).append(f"{prefix}line {c.line}, col {c.col}")
    return places

def _place(e):
    return f"{e.file}:{e.line}" if e.file else str(e.line)

# ===== SECTION 4: the main comparison =====
def compare(citations, entries):
    report = Report()
    cited_at = _where_cited(citations)

    report.nocite_all = "*" in cited_at
    cited_at.pop("*", None)

    entries_by_lower = {}
    for e in entries:
        entries_by_lower.setdefault(e.key.lower(), []).append(e)
    exact_keys = {e.key for e in entries}

    # 4a. Duplicates
    for lower_key, group in entries_by_lower.items():
        if len(group) > 1:
            report.duplicates.append({
                "key": group[0].key,
                "lines in .bib": ", ".join(_place(e) for e in group),
            })

    # 4b. Missing and case mismatch
    for key, places in cited_at.items():
        if key in exact_keys:
            continue
        if key.lower() in entries_by_lower:
            report.case_mismatch.append({
                "cited as": key,
                "entry is": entries_by_lower[key.lower()][0].key,
                "where": "; ".join(places),
            })
        else:
            suggestion = ""
            if not key.isdigit():
                close = difflib.get_close_matches(key, list(exact_keys), n=3, cutoff=0.6)
                suggestion = ", ".join(close)
            report.missing.append({
                "key": key,
                "where": "; ".join(places),
                "did you mean": suggestion,
            })

    # 4c. Unused
    if not report.nocite_all:
        cited_lower = {k.lower() for k in cited_at}
        seen = set()
        for e in entries:
            if e.key.lower() not in cited_lower and e.key.lower() not in seen:
                seen.add(e.key.lower())
                report.unused.append({"key": e.key,
                                      "line in .bib": _place(e) if e.file else e.line})

    return report

# ===== SECTION 5: citation order =====
# With an unsorted style (unsrt, IEEEtran) the number in your PDF follows the
# order of FIRST citation. Keys missing from the .bib show as [?] and use up
# no number. The order across files follows the order you uploaded them in.
def citation_order(citations, entries):
    in_bib = {e.key.lower() for e in entries}
    seen, rows, number = set(), [], 0
    for c in citations:
        low = c.key.lower()
        if c.key == "*" or low in seen:
            continue
        seen.add(low)
        found = low in in_bib
        if found:
            number += 1
        prefix = f"{c.file}: " if c.file else ""
        rows.append({"number": str(number) if found else "[?]", "key": c.key,
                     "first cited at": f"{prefix}line {c.line}, col {c.col}",
                     "in .bib": "yes" if found else "NO"})
    return rows