# ===== SECTION 1: imports =====
import csv
import io
import re
import statistics
from dataclasses import dataclass, field

from .fields import _norm_doi, parse_fields

# ===== SECTION 2: what this file does =====
# It turns the findings the checker already has into ONE score from 0 to 100,
# with the reasons next to it. Think of a school report card: one grade on top,
# and under it every subject with the marks that were lost.
#
# This file is offline. The checks that need the internet (do the DOIs exist?)
# are done in core/refverify.py; their rows are simply handed in here, and a
# check that was not run is left out of the score instead of counting as good.
#
# How the score works, in plain words:
#   - every kind of problem has a MAXIMUM number of points it can cost;
#   - the more of the items are affected, the closer it gets to that maximum
#     (it is reached when a quarter of the items are affected; for retracted
#     papers, which matter far more, when 2% of the DOIs are affected);
#   - any problem at all costs at least 15% of its maximum, so a single broken
#     citation is never hidden inside a big bibliography.

FULL_AT = 0.25          # share of items affected at which the maximum is reached
RETRACTED_FULL_AT = 0.02
AT_LEAST = 0.15         # share of the maximum that any single problem costs


@dataclass
class HealthItem:
    check: str          # name of the problem
    affected: int       # how many items have it
    out_of: int         # how many items were looked at
    penalty: float      # points lost
    advice: str         # what to do, in one sentence


@dataclass
class Health:
    score: int
    label: str
    items: list = field(default_factory=list)       # HealthItem, worst first
    profile: dict = field(default_factory=dict)
    not_run: list = field(default_factory=list)     # checks that were not done


def _penalty(cap, affected, out_of, full_at=FULL_AT):
    if affected <= 0:
        return 0.0
    share = affected / max(out_of, 1)
    return round(max(cap * min(1.0, share / full_at), cap * AT_LEAST), 1)


def _label(score):
    return "Healthy" if score >= 90 else "Needs attention" if score >= 70 else "Needs work"


# ===== SECTION 3: the old-papers profile =====
# Facts, not judgements: how old the references are and how many have a DOI.
def reference_profile(entries, this_year):
    years, with_doi = [], 0
    for e in entries:
        f = parse_fields(e.raw)
        year = f.get("year", "").strip()
        if year.isdigit() and len(year) == 4:
            years.append(int(year))
        if f.get("doi", "").strip():
            with_doi += 1
    profile = {"entries": len(entries), "with a DOI": with_doi}
    if years:
        profile.update({"oldest year": min(years), "newest year": max(years),
                        "median year": int(statistics.median(years)),
                        "older than 10 years": sum(y < this_year - 10 for y in years)})
    return profile


# ===== SECTION 4: the retraction list (optional file you download yourself) =====
# Crossref publishes the Retraction Watch data as a CSV file. The columns used
# are OriginalPaperDOI and RetractionDOI (RetractionNature is used when it is
# there). The file is read here on your computer, so no DOI is sent anywhere.
# Returns (table, message): table maps a lower-case DOI to what is known.
def _plain(name):
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


# Column names are matched loosely (capitals, spaces and underscores do not
# matter), because the exact header could not be checked against the real file.
def _find_column(names, wanted):
    for name in names:
        if _plain(name) == wanted:
            return name
    for name in names:                       # last resort: the name contains it
        if wanted in _plain(name):
            return name
    return None


def load_retraction_list(csv_text):
    reader = csv.DictReader(io.StringIO(csv_text))
    names = reader.fieldnames or []
    original = _find_column(names, "originalpaperdoi")
    if original is None:
        shown = ", ".join(names[:8]) or "(no columns found)"
        return {}, ("This does not look like the Retraction Watch file: there is no "
                    f"OriginalPaperDOI column. The columns in this file start with: {shown}.")
    notice = _find_column(names, "retractiondoi")
    nature = _find_column(names, "retractionnature")
    table = {}
    for row in reader:
        doi = _norm_doi(row.get(original) or "")
        if doi.startswith("10."):
            kind = (row.get(nature) or "").strip() if nature else ""
            link = (row.get(notice) or "").strip() if notice else ""
            table.setdefault(doi, {"nature": kind or "listed", "notice": link})
    return table, ""


def find_retracted(entries, table):
    rows = []
    for e in entries:
        doi = _norm_doi(parse_fields(e.raw).get("doi", ""))
        if doi in table:
            rows.append({"key": e.key, "doi": doi, "listed as": table[doi]["nature"],
                         "notice": table[doi]["notice"]})
    return rows


# ===== SECTION 5: the report card =====
# report      the Report from core/compare.py
# entries     BibEntry objects from the .bib files
# field_rows  rows from core/fields.check_fields
# same_groups groups from core/fields.find_same_paper_groups
# doi_rows    rows from core/refverify.check_bib_dois, or None if not run
# doi_checked how many DOIs that check looked at
# retracted   rows from find_retracted, or None if no list was given
def build_health(report, citations, entries, field_rows, same_groups, this_year,
                 doi_rows=None, doi_checked=0, retracted=None):
    cited = {c.key.lower() for c in citations if c.key != "*"}
    unique_keys = {e.key.lower() for e in entries}
    in_groups = sum(len(g.entries) for g in same_groups)

    # (name, how many affected, out of how many, most points it can cost, advice,
    #  share of items at which the maximum is reached)
    checks = [
        ("Cited but missing from the .bib", len(report.missing), len(cited), 40,
         "These break the bibliography. Add the entries or fix the keys.", FULL_AT),
        ("Case mismatches", len(report.case_mismatch), len(cited), 10,
         "Use the 'Fix case mismatches' action below.", FULL_AT),
        ("Duplicate keys", len(report.duplicates), len(unique_keys), 15,
         "Use the 'Merge duplicate keys' action below.", FULL_AT),
        ("Entries with missing fields", len(field_rows), len(entries), 20,
         "Add the missing fields, or fetch the entry again from its DOI.", FULL_AT),
        ("Same paper under different keys", in_groups, len(entries), 10,
         "Use the 'Merge the same paper' action below.", FULL_AT),
    ]
    not_run = []
    if report.nocite_all:
        not_run.append("Unused entries (\\nocite{*} includes everything)")
    else:
        checks.append(("Unused entries", len(report.unused), len(entries), 10,
                       "Use the 'Remove unused entries' action below.", FULL_AT))
    if doi_rows is None:
        not_run.append("DOIs that do not exist or point to another paper (needs internet)")
    else:
        checks.append(("DOI problems", len(doi_rows), doi_checked, 20,
                       "Look up the right DOI, or remove the wrong one.", FULL_AT))
    if retracted is None:
        not_run.append("Retracted or corrected papers (needs the Retraction Watch file)")
    else:
        with_doi = sum(1 for e in entries if parse_fields(e.raw).get("doi", "").strip())
        checks.append(("Retracted or corrected papers", len(retracted), with_doi, 30,
                       "Read the notice. Cite a retracted paper only on purpose, and say so.",
                       RETRACTED_FULL_AT))

    items = [HealthItem(name, n, total, _penalty(cap, n, total, full_at), advice)
             for name, n, total, cap, advice, full_at in checks]
    score = max(0, round(100 - sum(i.penalty for i in items)))
    items.sort(key=lambda i: i.penalty, reverse=True)
    return Health(score, _label(score), items, reference_profile(entries, this_year), not_run)
