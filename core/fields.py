# ===== SECTION 1: imports =====
import re

from .bibreader import _find_closing

# ===== SECTION 2: which fields each entry type needs =====
# Each item is a tuple of alternatives: ("author", "editor") means either one.
_YEAR = ("year", "date")
REQUIRED = {
    "article": [("author",), ("title",), ("journal", "journaltitle"), _YEAR],
    "inproceedings": [("author",), ("title",), ("booktitle",), _YEAR],
    "incollection": [("author",), ("title",), ("booktitle",), ("publisher",), _YEAR],
    "book": [("author", "editor"), ("title",), ("publisher",), _YEAR],
    "techreport": [("author",), ("title",), ("institution",), _YEAR],
    "phdthesis": [("author",), ("title",), ("school",), _YEAR],
    "mastersthesis": [("author",), ("title",), ("school",), _YEAR],
}

# ===== SECTION 3: read the fields of one entry =====
# Returns {"title": "...", "year": "2020", ...}. Values are skipped over as a
# whole, so a word like "year = 2020" written INSIDE a title is not mistaken
# for a field.
_NAME_EQ = re.compile(r"\s*([A-Za-z][A-Za-z0-9_-]*)\s*=\s*")

def parse_fields(raw):
    fields = {}
    i = raw.find(",") + 1              # start after the key
    n = len(raw)
    while i < n:
        m = _NAME_EQ.match(raw, i)
        if not m:
            i += 1
            continue
        j = m.end()
        if j >= n:
            break
        if raw[j] == "{":
            end = _find_closing(raw, j)
            end = n - 1 if end == -1 else end
            value, i = raw[j + 1:end], end + 1
        elif raw[j] == '"':
            k = j + 1
            while k < n and raw[k] != '"':
                k += 2 if raw[k] == "\\" else 1
            value, i = raw[j + 1:k], k + 1
        else:                           # a bare number or macro, e.g. year = 2020
            m2 = re.compile(r"[^,}\s]+").match(raw, j)
            value = m2.group(0) if m2 else ""
            i = j + len(value)
        fields[m.group(1).lower()] = value
    return fields

def _place(e):
    return f"{e.file}:{e.line}" if e.file else e.line

# ===== SECTION 4: missing-fields check =====
def check_fields(entries):
    rows = []
    for e in entries:
        have = parse_fields(e.raw)
        missing = [" or ".join(alts) for alts in REQUIRED.get(e.type, [])
                   if not any(have.get(a, "").strip() for a in alts)]
        if missing:
            rows.append({"key": e.key, "type": e.type, "where": _place(e),
                         "missing": ", ".join(missing)})
    return rows

# ===== SECTION 5: same paper under different keys =====
def _norm_doi(d):
    d = d.strip().lower()
    return re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", d)

def _norm_title(t):
    t = re.sub(r"\\[A-Za-z]+|[{}$\\]", "", t.lower())
    return re.sub(r"[^a-z0-9]+", " ", t).strip()

def find_same_paper(entries):
    parent = list(range(len(entries)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    seen, links = {}, []
    for i, e in enumerate(entries):
        f = parse_fields(e.raw)
        sigs = []
        doi = _norm_doi(f.get("doi", ""))
        if doi:
            sigs.append(("same DOI", doi))
        title = _norm_title(f.get("title", ""))
        if len(title) >= 15:            # very short titles match too easily
            sigs.append(("same title", title))
        for sig in sigs:
            if sig not in seen:
                seen[sig] = i
            elif entries[seen[sig]].key.lower() != e.key.lower():
                parent[find(i)] = find(seen[sig])
                links.append((i, sig[0]))

    groups = {}
    for i in range(len(entries)):
        groups.setdefault(find(i), []).append(i)
    rows = []
    for root, idx in groups.items():
        if len(idx) > 1:
            es = [entries[i] for i in idx]
            rows.append({
                "keys": ", ".join(dict.fromkeys(e.key for e in es)),
                "why": ", ".join(sorted({r for i, r in links if find(i) == root})),
                "years": ", ".join(parse_fields(e.raw).get("year", "?") for e in es),
                "where": ", ".join(str(_place(e)) for e in es),
            })
    return rows