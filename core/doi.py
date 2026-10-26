# ===== SECTION 1: imports =====
import html
import re
import unicodedata
from urllib.parse import quote

import requests

from .bibreader import extract_bib_entries
from .fields import check_fields
from .tidy import format_entry

# ===== SECTION 2: this file is the ONLY place that uses the internet =====
# The offline checker never imports it. Rules from CLAUDE.md:
#   - every lookup is explicit (the user presses a button),
#   - a failure never raises: you get (None, "a plain-words message"),
#   - nothing is invented: a field the server did not send is left out,
#   - results are cached in a dictionary you pass in, so the same question
#     is not asked twice.
# `get` is requests.get by default. Tests pass a fake one, so they run offline.
DOI_ORG = "https://doi.org/"
CROSSREF = "https://api.crossref.org/works"
CSL_ACCEPT = "application/vnd.citationstyles.csl+json"   # works for every DOI registry

class LookupFailed(Exception):
    pass

def user_agent(email):
    return f"CiteDesk/0.1 (mailto:{email.strip()})"

def _get_json(url, headers, params, get, timeout=15):
    get = get or requests.get
    try:
        response = get(url, headers=headers, params=params, timeout=timeout)
    except requests.RequestException as err:
        raise LookupFailed(f"Could not reach the server ({type(err).__name__}). "
                           "Check your internet connection.")
    if response.status_code == 404:
        raise LookupFailed("No record found. Check the DOI for typing mistakes.")
    if response.status_code == 429:
        raise LookupFailed("The server says there were too many requests. Wait a minute and try again.")
    if response.status_code != 200:
        raise LookupFailed(f"The server answered with error {response.status_code}.")
    try:
        data = response.json()
    except ValueError:
        raise LookupFailed("The server's answer could not be read.")
    if not isinstance(data, dict):
        raise LookupFailed("The server's answer had an unexpected shape.")
    return data

# ===== SECTION 3: find the DOI in what the user typed =====
# Accepts "10.1234/abc", "doi:10.1234/abc", "https://doi.org/10.1234/abc" and
# similar. Returns "" when no DOI is found.
_DOI = re.compile(r"10\.\d{4,9}/\S+")

def clean_doi(text):
    m = _DOI.search(text or "")
    return m.group(0).rstrip(".,;") if m else ""

# ===== SECTION 4: ask doi.org for the record (CSL-JSON) =====
# Returns (record, message). The record is None when something went wrong.
def fetch_csl(doi, email, get=None, cache=None):
    cache_key = ("doi", doi.lower())
    if cache is not None and cache_key in cache:
        return cache[cache_key], ""
    try:
        record = _get_json(DOI_ORG + quote(doi, safe="/"),
                           {"Accept": CSL_ACCEPT, "User-Agent": user_agent(email)}, None, get)
    except LookupFailed as err:
        return None, str(err)
    if cache is not None:
        cache[cache_key] = record
    return record, ""

# ===== SECTION 5: search Crossref by title =====
# Returns (candidates, message). The user must pick the right one: a title
# search can only guess. Each candidate is a small dictionary of plain text.
def search_title(title, email, rows=5, get=None, cache=None):
    title = " ".join((title or "").split())
    if len(title) < 8:
        return [], "Type more of the title (at least 8 characters)."
    cache_key = ("search", title.lower(), rows)
    if cache is not None and cache_key in cache:
        return cache[cache_key], ""
    params = {"query.bibliographic": title, "rows": rows,
              "select": "DOI,title,author,issued,container-title,type"}
    try:
        data = _get_json(CROSSREF, {"User-Agent": user_agent(email)}, params, get)
    except LookupFailed as err:
        return [], str(err)
    found = []
    for item in (data.get("message") or {}).get("items") or []:
        if not item.get("DOI"):
            continue
        names = [clean_text(a.get("family") or a.get("name")) for a in item.get("author") or []]
        names = [n for n in names if n]
        authors = ", ".join(names[:3]) + (" et al." if len(names) > 3 else "")
        found.append({"doi": item["DOI"], "title": clean_text(item.get("title")),
                      "authors": authors, "year": _date_parts(item)[0],
                      "venue": clean_text(item.get("container-title")), "type": item.get("type", "")})
    if cache is not None and found:
        cache[cache_key] = found
    return found, "" if found else "No matching papers found."

# ===== SECTION 6: cleaning text from the server =====
# Titles can hold markup like <i>, <sub> or MathML, and HTML entities like &amp;.
# We remove tag-shaped pieces, decode the entities and squeeze the spaces. Then
# (only for text fields) we escape & % # for LaTeX, without doubling a \& that
# is already escaped. A lone "<" as in "p < 0.05" is not a tag and stays.
_TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9]*(?::[A-Za-z0-9]+)?(?:\s[^<>]*)?/?>")

def _text(value):
    if isinstance(value, list):                 # Crossref sends lists for some fields
        value = value[0] if value else ""
    return "" if value is None else str(value)

def clean_text(value):
    return " ".join(html.unescape(_TAG.sub("", _text(value))).split())

def escape_latex(text):
    return re.sub(r"(?<!\\)([&%#])", r"\\\1", text)

# ===== SECTION 7: names, dates and pages =====
# "Family, Given" joined with " and ". A particle (von, van der) goes in front
# of the family name, a suffix (Jr.) in the middle. An organisation sent as
# one "literal" name gets braces so BibTeX does not split it.
def _person(a):
    if a.get("literal"):
        return "{" + escape_latex(clean_text(a["literal"])) + "}"
    family = " ".join(p for p in (clean_text(a.get("dropping-particle")),
                                  clean_text(a.get("non-dropping-particle")),
                                  clean_text(a.get("family"))) if p)
    given, suffix = clean_text(a.get("given")), clean_text(a.get("suffix"))
    parts = [p for p in (family, suffix, given) if p]
    return escape_latex(", ".join(parts)) if family else escape_latex(" ".join(parts))

def _people(value):
    names = [_person(a) for a in value or [] if isinstance(a, dict)]
    return " and ".join(n for n in names if n)

# Returns (year, month, day) as text, "" for anything the server did not send.
def _date_parts(csl):
    issued = csl.get("issued") or {}
    parts = (issued.get("date-parts") or [[]])[0] or []
    year, month, day = (str(p) if isinstance(p, int) else "" for p in (list(parts) + ["", "", ""])[:3])
    if not year:
        m = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", _text(issued.get("raw") or issued.get("literal")))
        year = m.group(1) if m else ""
    return year, month, day

_RANGE = re.compile(r"([A-Za-z0-9]+)\s*[-\u2010-\u2015]+\s*([A-Za-z0-9]+)")

def _pages(value):
    page = clean_text(value)
    m = _RANGE.fullmatch(page)
    return f"{m.group(1)}--{m.group(2)}" if m else page      # 12-20 -> 12--20

def _joined(value):                                          # ISSN and ISBN come as lists
    items = value if isinstance(value, list) else [value]
    return ", ".join(dict.fromkeys(clean_text(v) for v in items if clean_text(v)))

# ===== SECTION 8: from record to BibTeX =====
# CSL type -> BibTeX type. Anything not listed becomes misc rather than a guess.
TYPE_MAP = {
    "article-journal": "article", "article-magazine": "article", "article-newspaper": "article",
    "paper-conference": "inproceedings",
    "book": "book",
    "chapter": "incollection", "entry-encyclopedia": "incollection", "entry-dictionary": "incollection",
    "report": "techreport",
}

def bibtex_type(csl):
    kind = _text(csl.get("type"))
    if kind == "thesis":
        genre = _text(csl.get("genre")).lower()
        if "phd" in genre or "doctor" in genre:
            return "phdthesis"
        return "mastersthesis" if "master" in genre else "misc"
    return TYPE_MAP.get(kind, "misc")

CONTAINER = {"article": "journal", "inproceedings": "booktitle", "incollection": "booktitle"}
PUBLISHER_AS = {"techreport": "institution", "phdthesis": "school", "mastersthesis": "school"}
PUBLISHER_AS.update({t: "publisher" for t in ("book", "incollection", "inproceedings", "misc")})

def csl_to_bibtex(csl, key, newline="\n"):
    kind = bibtex_type(csl)
    fields = []

    def add(name, text, escape=True):
        text = text.strip()
        if text:
            fields.append((name, escape_latex(text) if escape else text, False))

    add("title", clean_text(csl.get("title")))
    add("author", _people(csl.get("author")), False)          # names are already escaped
    if kind in ("book", "incollection", "inproceedings"):
        add("editor", _people(csl.get("editor")), False)
    year, month, day = _date_parts(csl)
    add("year", year, False); add("month", month, False); add("day", day, False)
    if kind in CONTAINER:
        add(CONTAINER[kind], clean_text(csl.get("container-title")))
    if kind in PUBLISHER_AS:
        add(PUBLISHER_AS[kind], clean_text(csl.get("publisher")))
    if kind in ("book", "incollection", "inproceedings", "techreport"):
        add("address", clean_text(csl.get("publisher-place")))
    if kind in ("book", "incollection", "inproceedings"):
        add("series", clean_text(csl.get("collection-title")))
    if kind in ("article", "inproceedings", "incollection", "book"):
        add("volume", clean_text(csl.get("volume")))
    if kind in ("article", "inproceedings"):
        add("number", clean_text(csl.get("issue")))
    if kind == "techreport":
        add("number", clean_text(csl.get("number")))
    if kind in ("article", "inproceedings", "incollection"):
        add("pages", _pages(csl.get("page")))
    doi = clean_text(csl.get("DOI"))
    add("doi", doi, False)
    if kind in ("book", "incollection", "inproceedings"):
        add("isbn", _joined(csl.get("ISBN")), False)
    if kind == "article":
        add("issn", _joined(csl.get("ISSN")), False)
    url = clean_text(csl.get("URL"))
    if url and clean_doi(url).lower() != doi.lower():        # skip a plain doi.org link
        add("url", url, False)
    return format_entry(kind, key, fields, newline)

# ===== SECTION 9: keys and a check of the result =====
_BAD_KEY = re.compile(r"[\s,{}()\"#%=~\\]")

def valid_key(key):
    return bool(key) and not _BAD_KEY.search(key)

# A suggestion only: the first author's family name in plain letters plus the
# year, with a, b, c added when the key is already taken. The user can change it.
def suggest_key(csl, existing=()):
    authors = csl.get("author") or [{}]
    first = authors[0] if isinstance(authors[0], dict) else {}
    name = _text(first.get("family") or first.get("literal"))
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    base = (re.sub(r"[^A-Za-z]", "", name).lower() or "ref") + _date_parts(csl)[0]
    taken = {k.lower() for k in existing}
    for suffix in [""] + list("abcdefghijklmnopqrstuvwxyz"):
        if (base + suffix).lower() not in taken:
            return base + suffix
    return base

# Rows from the same missing-fields check the page already uses.
def missing_fields(bibtex):
    return check_fields(extract_bib_entries(bibtex))
