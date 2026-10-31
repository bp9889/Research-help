# ===== SECTION 1: imports =====
import re
import unicodedata
from dataclasses import dataclass, field

from .doi import clean_text, csl_to_bibtex, escape_latex, fetch_csl, search_title, suggest_key
from .fields import parse_fields
from .refextract import search_text
from .tidy import format_entry

# ===== SECTION 2: what this file does =====
# It takes the references that core/refextract.py cut out and asks Crossref
# "is this a real paper?". Think of a customs officer: every reference gets
# stamped, and the stamp says how sure we are.
#
#   confirmed   the printed DOI resolves and its title matches the reference
#   likely      no DOI, but the best Crossref hit agrees on title and year
#   check       something was found, but it does not clearly match: you choose
#   not found   nothing matched
#   not checked the internet was not reachable
#
# This file does not touch the internet itself. It only calls the functions
# in core/doi.py, which is the one file allowed to. Rules kept from CLAUDE.md:
# a failure never raises, nothing is invented, and a title search can only
# guess, so a weak match is shown for you to choose and is never trusted.
# `get` and `cache` are passed straight through, so tests run offline.
CONFIRMED, LIKELY, CHECK = "confirmed", "likely", "check"
NOT_FOUND, NOT_CHECKED = "not found", "not checked"

# doi.py answers with plain-words messages. These three mean "there is simply no
# such paper"; any other message (no connection, too many requests, server
# error) is a problem with the server, and must never be read as "not found".
_NO_SUCH_PAPER = ("No record found", "No matching papers", "Type more of the title")


def _server_trouble(message):
    return bool(message) and not message.startswith(_NO_SUCH_PAPER)


@dataclass
class Checked:
    ref: object                                   # a core.refextract.Reference
    status: str
    why: str                                      # one plain sentence for the table
    record: dict = None                           # CSL-JSON, for confirmed and likely
    candidates: list = field(default_factory=list)  # a few guesses, for "check"


# ===== SECTION 3: do the title and the printed reference agree? =====
# Words are compared in plain lower-case letters and digits (accents folded),
# and short words like "of" are ignored. At least 80% of the title's words must
# appear in the reference, and the title needs three words or more, because a
# one-word title would match almost anything. (That is for a search guess. When
# the reference PRINTS the DOI or arXiv number and it resolves, a title of even
# one real word is enough, because the identifier itself is strong evidence.)
def _words(text):
    folded = unicodedata.normalize("NFKD", clean_text(text)).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z0-9]+", folded.lower())


def title_in_reference(title, raw, min_words=3):
    wanted = [w for w in _words(title) if len(w) > 2]
    if len(wanted) < min_words:
        return False
    present = set(_words(raw))
    return sum(w in present for w in wanted) / len(wanted) >= 0.8


def _record_year(record):
    parts = ((record.get("issued") or {}).get("date-parts") or [[]])[0] or []
    return str(parts[0]) if parts and isinstance(parts[0], int) else ""


def _candidate(record):
    return {"doi": clean_text(record.get("DOI")), "title": clean_text(record.get("title")),
            "authors": "", "year": _record_year(record),
            "venue": clean_text(record.get("container-title")), "type": record.get("type", "")}


# ===== SECTION 4: check one reference =====
# Order of attempts:
#   1. the printed DOI;
#   2. the arXiv number, through its own DOI (10.48550/arXiv.<number>), which
#      doi.org resolves like any other DOI. This is much stronger than a title
#      search, and it is how a reference that only prints an arXiv number is checked;
#   3. a title search, which can only guess.
# A resolved identifier whose title does not match is never trusted, but the next
# attempt still runs, so a wrong printed DOI does not hide a right arXiv number.
# Each identifier is (what it is, the DOI to ask for, quiet). A "quiet" one is a
# second reading of a DOI that was broken after a full stop; if it does not
# resolve that is not worth a note, because it was only a guess.
def _identifiers(ref):
    found = []
    if ref.doi:
        found.append(("printed DOI", ref.doi, False))
    for other in ref.alt_dois:
        found.append(("printed DOI with the line break closed", other, True))
    if ref.arxiv:
        found.append(("arXiv number", f"10.48550/arXiv.{ref.arxiv}", False))
    return found


def verify_reference(ref, email, get=None, cache=None):
    notes, wrong = [], []
    for kind, doi, quiet in _identifiers(ref):
        record, message = fetch_csl(doi, email, get=get, cache=cache)
        if record:
            title = clean_text(record.get("title"))
            if title_in_reference(title, ref.raw, min_words=1):
                return Checked(ref, CONFIRMED,
                               f"The {kind} resolves and its title matches the reference.", record)
            wrong.append((kind, title, record))
        elif _server_trouble(message):
            return Checked(ref, NOT_CHECKED, message)
        elif not quiet:
            notes.append(f"The {kind} did not resolve.")
    if wrong:
        kind, title, _ = wrong[0]
        return Checked(ref, CHECK,
                       f"The {kind} points to \"{title[:70]}\", which does not clearly match "
                       "this reference.", candidates=[_candidate(r) for _, _, r in wrong])
    note = " ".join(notes) + (" " if notes else "")

    query = search_text(ref)
    found, message = search_title(query, email, get=get, cache=cache)
    if not found:
        if _server_trouble(message):
            return Checked(ref, NOT_CHECKED, message)
        return Checked(ref, NOT_FOUND, note + (message or "No matching paper found."))

    top = found[0]
    same_year = not ref.year or not top["year"] or ref.year == top["year"]
    if title_in_reference(top["title"], ref.raw) and same_year:
        record, _ = fetch_csl(top["doi"], email, get=get, cache=cache)
        if record:
            return Checked(ref, LIKELY, note + "Best Crossref match agrees on title and year. "
                           "Still compare it with the PDF.", record)
    return Checked(ref, CHECK, note + "Crossref found papers, but none clearly matches. "
                   "Compare the guesses with the PDF.", candidates=found[:3])


# ===== SECTION 5: check a whole list =====
# progress(done, total) is called after each reference, so the page can show
# a progress bar. If the connection fails three times in a row we stop and mark
# the rest "not checked", instead of waiting for dozens of time-outs.
def verify_all(refs, email, get=None, cache=None, progress=None):
    results, failures = [], 0
    for i, ref in enumerate(refs):
        if failures >= 3:
            results.append(Checked(ref, NOT_CHECKED,
                                   "Skipped: the internet connection failed three times in a row."))
        else:
            checked = verify_reference(ref, email, get=get, cache=cache)
            failures = failures + 1 if checked.status == NOT_CHECKED else 0
            results.append(checked)
        if progress:
            progress(i + 1, len(refs))
    return results


# ===== SECTION 6: write the results as a .bib draft and as a table =====
# confirmed and likely  -> a full entry made from the Crossref record
# everything else       -> an @misc with the printed text in `note`, so the
#                          reference is kept and no metadata is made up.
# Braces and & % # in the printed text are escaped so the file stays valid.
def _note_text(raw):
    text = " ".join(raw.split()).replace("\\", "").replace("{", "\\{").replace("}", "\\}")
    return escape_latex(text)


def _unused_key(base, taken):
    key, n = base, 2
    while key.lower() in taken:
        key, n = f"{base}_{n}", n + 1
    return key


def build_bib(results, existing_keys=()):
    taken = {k.lower() for k in existing_keys}
    blocks, rows = [], []
    for n, c in enumerate(results, 1):
        if c.record and c.status in (CONFIRMED, LIKELY):
            key = suggest_key(c.record, taken)
            entry = csl_to_bibtex(c.record, key)
            if c.status == LIKELY:
                entry = "% likely match: compare with the PDF before using\n" + entry
        else:
            number = re.sub(r"\D", "", c.ref.label) or str(n)
            key = _unused_key(f"ref{number}", taken)
            entry = format_entry("misc", key, [("note", _note_text(c.ref.raw), False)])
            lines = [f"% {c.status}: {c.why}"]
            lines += [f"% guess: {g['doi']}  {g['title'][:70]} ({g['year']})" for g in c.candidates]
            entry = "\n".join(lines) + "\n" + entry
        taken.add(key.lower())
        blocks.append(entry)
        rows.append({"#": c.ref.label or str(n), "status": c.status, "key": key,
                     "why": c.why, "reference": c.ref.raw[:90]})
    return "\n".join(blocks) + ("\n" if blocks else ""), rows


# ===== SECTION 7: check the DOIs already inside a .bib =====
# Two common mistakes: a DOI that does not exist (a typo) and a DOI that
# belongs to a different paper. Returns (rows, how_many_checked, message).
# Only problems become rows. On a connection failure it stops and says so.
def check_bib_dois(entries, email, get=None, cache=None, progress=None):
    rows, checked, failures = [], 0, 0
    with_doi = [(e, parse_fields(e.raw)) for e in entries]
    with_doi = [(e, f) for e, f in with_doi if f.get("doi", "").strip()]
    for i, (entry, fields) in enumerate(with_doi):
        doi = fields["doi"].strip()
        record, message = fetch_csl(doi, email, get=get, cache=cache)
        if record:
            failures, checked = 0, checked + 1
            theirs, mine = clean_text(record.get("title")), fields.get("title", "")
            # Either title may be the shorter one (a subtitle is often dropped).
            if mine and not (title_in_reference(theirs, mine) or title_in_reference(mine, theirs)):
                rows.append({"key": entry.key, "doi": doi,
                             "problem": "DOI points to a different paper",
                             "the DOI's title": theirs[:80]})
        elif _server_trouble(message):
            failures += 1
            if failures >= 3:
                return rows, checked, f"Stopped after three server problems in a row: {message}"
        else:
            failures, checked = 0, checked + 1
            rows.append({"key": entry.key, "doi": doi, "problem": "DOI does not exist",
                         "the DOI's title": ""})
        if progress:
            progress(i + 1, len(with_doi))
    return rows, checked, ""


# ===== SECTION 8: is the internet part working on this computer? =====
# One lookup each for the two services this tool uses, with a paper that is
# known to exist. Nothing is changed or saved. Returns a list of
# (service, worked, message), so the page can show a plain answer instead of a
# mystery when a check later says "not checked".
TEST_DOI = "10.1109/cvpr.2016.90"
TEST_TITLE = "Deep residual learning for image recognition"


def check_connection(email, get=None):
    results = []
    record, message = fetch_csl(TEST_DOI, email, get=get)
    if record and "residual learning" in clean_text(record.get("title")).lower():
        results.append(("doi.org (DOI lookup)", True, "Answered correctly."))
    elif record:
        results.append(("doi.org (DOI lookup)", False,
                        "It answered, but with an unexpected paper. Tell the developer."))
    else:
        results.append(("doi.org (DOI lookup)", False, message))

    found, message = search_title(TEST_TITLE, email, rows=5, get=get)
    if any(item["doi"].lower() == TEST_DOI for item in found):
        results.append(("Crossref (title search)", True, "Answered correctly."))
    elif found:
        results.append(("Crossref (title search)", False,
                        "It answered, but the expected paper was not in the results. Tell the developer."))
    else:
        results.append(("Crossref (title search)", False, message))
    return results
