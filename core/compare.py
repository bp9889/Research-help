# ===== SECTION 1: imports =====
import difflib
from dataclasses import dataclass, field

# ===== SECTION 2: the report =====
# Four lists, one per kind of finding. Each item is a small dictionary
# so it can be shown directly as a table row later.
@dataclass
class Report:
    missing: list = field(default_factory=list)        # cited, but not in the .bib
    unused: list = field(default_factory=list)         # in the .bib, never cited
    duplicates: list = field(default_factory=list)     # same key twice in the .bib
    case_mismatch: list = field(default_factory=list)  # Smith20 vs smith20
    nocite_all: bool = False                           # \nocite{*} was used

# ===== SECTION 3: helper - where was a key cited? =====
def _where_cited(citations):
    places = {}
    for c in citations:
        places.setdefault(c.key, []).append(f"line {c.line}, col {c.col}")
    return places

# ===== SECTION 4: the main comparison =====
def compare(citations, entries):
    report = Report()
    cited_at = _where_cited(citations)

    # \nocite{*} means "list every entry", so nothing can be "unused".
    report.nocite_all = "*" in cited_at
    cited_at.pop("*", None)

    # BibTeX ignores upper/lower case in keys, so we compare lowercase too.
    entries_by_lower = {}
    for e in entries:
        entries_by_lower.setdefault(e.key.lower(), []).append(e)
    exact_keys = {e.key for e in entries}

    # 4a. Duplicates: the same key (ignoring case) on more than one entry.
    for lower_key, group in entries_by_lower.items():
        if len(group) > 1:
            report.duplicates.append({
                "key": group[0].key,
                "lines in .bib": ", ".join(str(e.line) for e in group),
            })

    # 4b. Missing and case mismatch: go through every cited key.
    for key, places in cited_at.items():
        if key in exact_keys:
            continue                                   # perfect match
        if key.lower() in entries_by_lower:
            report.case_mismatch.append({
                "cited as": key,
                "entry is": entries_by_lower[key.lower()][0].key,
                "where": "; ".join(places),
            })
        else:
            # Suggest similar keys for typos. For numbers like 12 a "similar"
            # key is meaningless, so we only suggest for non-numeric keys.
            suggestion = ""
            if not key.isdigit():
                close = difflib.get_close_matches(key, list(exact_keys), n=3, cutoff=0.6)
                suggestion = ", ".join(close)
            report.missing.append({
                "key": key,
                "where": "; ".join(places),
                "did you mean": suggestion,
            })

    # 4c. Unused: entries whose key is never cited.
    if not report.nocite_all:
        cited_lower = {k.lower() for k in cited_at}
        seen = set()
        for e in entries:
            if e.key.lower() not in cited_lower and e.key.lower() not in seen:
                seen.add(e.key.lower())
                report.unused.append({"key": e.key, "line in .bib": e.line})

    return report