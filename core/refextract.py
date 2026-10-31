# ===== SECTION 1: imports =====
import re
from dataclasses import dataclass

# ===== SECTION 2: what this file does (and does not do) =====
# It finds the reference list of a paper and cuts it into single references.
# Think of it as a librarian who opens the back of a book, finds the page
# headed "References" and puts a bookmark between the entries.
#
# It never uses the internet and never touches Docling: it receives the
# Blocks that core/pdfreader.py already made, or plain text. Checking the
# references against Crossref is a separate step in core/refverify.py.
#
# Rules from CLAUDE.md that apply here:
#   - nothing is invented: DOI, arXiv number and year are copied out of the
#     printed text, and when one is not there the field stays empty;
#   - a case we cannot handle is reported in `notes`, never skipped silently.
#     No reader can promise to understand every PDF, so the aim is that a
#     failure always shows up as a visible note.


@dataclass
class Reference:
    raw: str            # the text as printed, with the number [3] or 3. taken off the front
    label: str = ""     # "[3]" or "3." exactly as printed, "" when there is none
    doi: str = ""
    arxiv: str = ""
    year: str = ""
    alt_dois: tuple = ()    # other possible readings of a DOI that was broken after a full stop


# ===== SECTION 3: find the "References" heading =====
# Matches: References, REFERENCES, 7. References, VII. REFERENCES, Bibliography,
# Works Cited, Reference list, References and notes, "References:" ... and the
# same word in other languages (below), but not a sentence that merely starts
# with the word. The other-language words are a best effort from common usage,
# with and without accents; a heading that is still not known gives a note.
_HEADING_WORDS = (
    r"references?(?:\s+(?:list|cited|and\s+notes))?", r"notes\s+and\s+references",
    r"list\s+of\s+references", r"bibliography(?:\s+and\s+references)?", r"works\s+cited",
    r"literature\s+cited", r"cited\s+literature",
    # German, French, Spanish, Portuguese, Italian, Dutch
    r"literaturverzeichnis", r"literatur", r"quellenverzeichnis", r"quellen",
    r"r[e\u00e9]f[e\u00e9]rences?(?:\s+bibliographiques)?", r"bibliographie",
    r"referencias?(?:\s+bibliogr[a\u00e1]ficas)?", r"bibliograf[i\u00ed]a",
    r"refer[e\u00ea]ncias?(?:\s+bibliogr[a\u00e1]ficas)?", r"bibliografia",
    r"riferimenti(?:\s+bibliografici)?", r"referenties", r"literatuur",
    # Turkish, Indonesian and Malay
    r"kaynaklar", r"kaynak[c\u00e7]a", r"daftar\s+pustaka", r"rujukan",
    # Russian, Chinese and Japanese, Korean, Arabic, Bengali, Hindi
    r"\u0441\u043f\u0438\u0441\u043e\u043a\s+\u043b\u0438\u0442\u0435\u0440\u0430\u0442\u0443\u0440\u044b",
    r"\u043b\u0438\u0442\u0435\u0440\u0430\u0442\u0443\u0440\u0430",
    r"\u53c2\u8003\u6587\u732e", r"\ucc38\uace0\s?\ubb38\ud5cc",
    r"\u0627\u0644\u0645\u0631\u0627\u062c\u0639",
    r"\u09a4\u09a5\u09cd\u09af\u09b8\u09c2\u09a4\u09cd\u09b0", r"\u0997\u09cd\u09b0\u09a8\u09cd\u09a5\u09aa\u099e\u09cd\u099c\u09bf",
    r"\u0938\u0902\u0926\u0930\u094d\u092d",
)
_HEADING = re.compile(
    r"^\W*(?:\d+(?:\.\d+)*\.?|[IVX]+\.?)?\s*(?:" + "|".join(_HEADING_WORDS) + r")\W*$",
    re.IGNORECASE)

_HEADING_KINDS = ("heading", "title")
_REFERENCE_KINDS = ("text", "list_item", "other")

# Some PDFs make the heading a plain text block instead of a heading, so a
# SHORT text block that is nothing but the heading words also counts.
_MAX_PLAIN_HEADING = 40


def _is_reference_heading(block):
    text = block.text.strip()
    if block.kind in _HEADING_KINDS:
        return bool(_HEADING.match(text))
    return block.kind in _REFERENCE_KINDS and len(text) <= _MAX_PLAIN_HEADING \
        and bool(_HEADING.match(text))


# A block that is only a page number ("15", "Page 15 of 17") is not a reference.
# Only 1 to 3 digits count, so a year that wraps onto a line of its own ("2004.")
# is never thrown away.
_PAGE_NUMBER = re.compile(r"^\W*(?:page\s*)?\d{1,3}(?:\s*(?:of|/)\s*\d{1,4})?\W*$", re.IGNORECASE)

# A piece of a reference that the PDF reader cut off from its start: it begins
# with doi:, a link, "URL", an arXiv number or a page range, which a reference
# never does. It is glued back onto the reference before it.
_CONTINUATION = re.compile(r"^\s*(?:doi\b|https?:|url\b|arxiv[:\s]|\d{1,5}\s*[–—-]\s*\d{1,5}\s*[,.])",
                           re.IGNORECASE)


# From the Blocks of core/pdfreader.py: the text blocks between the LAST
# "References" heading and the next heading. The last one wins because the
# word can also appear in a table of contents. Returns (strings, notes).
def reference_strings(blocks):
    if not blocks:
        return [], ["This PDF gave no readable text, even with OCR (it may be a scan that is blank "
                    "or too poor to read). If you can select text in the PDF, copy the "
                    "list and use the 'Paste the list' tab."]
    start = None
    for i, block in enumerate(blocks):
        if _is_reference_heading(block):
            start = i
    if start is None:
        return [], ["No References heading was found in this PDF (the heading may be in a "
                    "language or wording that is not known). Copy the list and use the "
                    "'Paste the list' tab."]

    strings, notes, joined = [], [], 0
    for block in blocks[start + 1:]:
        text = block.text.strip()
        if block.kind in _HEADING_KINDS:
            notes.append(f"Stopped at the heading '{text[:40]}'. "
                         "If references come after it, they were not read.")
            break
        if block.kind not in _REFERENCE_KINDS or not text or _PAGE_NUMBER.match(text):
            continue
        if strings and _CONTINUATION.match(text):
            strings[-1] += " " + text
            joined += 1
        else:
            strings.append(block.text)
    if joined:
        notes.append(f"{joined} piece(s) that started with a link, DOI or page range were "
                     "joined to the reference before them. Check those references.")
    if not strings:
        notes.append("The 'References' heading was found, but no text follows it.")
    return strings, notes


# From pasted text: everything after the last "References" line. When there
# is no such line, the whole text is taken as the list (the person probably
# pasted only the list).
def text_after_heading(text):
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if _HEADING.match(line.strip()):
            start = i
    return "\n".join(lines[start + 1:] if start is not None else lines)


# In pasted text a page number sits on its own line with a blank line next to
# it. It is dropped there, and only there: a number in the middle of a wrapped
# reference has no blank line beside it and stays.
def drop_page_numbers(text):
    lines = text.splitlines()
    keep = []
    for i, line in enumerate(lines):
        before_blank = i == 0 or not lines[i - 1].strip()
        after_blank = i == len(lines) - 1 or not lines[i + 1].strip()
        if _PAGE_NUMBER.match(line.strip()) and (before_blank or after_blank):
            continue
        keep.append(line)
    return "\n".join(keep)


# A reference usually ENDS with a year, a DOI, a link or an arXiv number (and a
# full stop). When a line ends like that and the next line starts with a capital
# letter (and not with words like "In", "doi", "pages" that continue a
# reference), the next line starts a new reference. This is only a guess, so it
# comes with a warning; it is used only when there are no numbers, blank lines
# or indentation to go by.
_CLOSER = re.compile(r"(?:(?:1[89]|20)\d\d[a-z]?[.)]?|10\.\d{4,9}/\S+|https?://\S+|arxiv[:\s]*\S+)\.?$",
                     re.IGNORECASE)
_CONTINUING_WORD = re.compile(r"^\s*(?:doi\b|https?:|url\b|arxiv\b|pages?\b|pp\b|vol\b|volume\b|no\b|in\b)",
                              re.IGNORECASE)


def _split_where_references_end(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    starts = [0]
    for i in range(1, len(lines)):
        if (_CLOSER.search(lines[i - 1]) and lines[i][:1].isupper()
                and not _CONTINUING_WORD.match(lines[i])):
            starts.append(i)
    if len(starts) < 2:
        return None
    ends = starts[1:] + [len(lines)]
    return [" ".join(lines[a:b]) for a, b in zip(starts, ends)]


# ===== SECTION 4: cut one blob of text into single references =====
# Tried in this order:
#   1. several [1] [2] labels       -> split in front of each label
#   2. several lines like "3. ..."   -> split in front of each such line
#   3. blank lines between entries  -> split at the blank lines
#   4. pasted text only: a hanging indent (first line at the margin, the
#      rest of the entry indented, as in many printed lists) -> split at the margin
#   5. pasted text only: lines that END like a reference (year, DOI, link) followed
#      by a line that starts like one -> split there, with a warning
#   6. pasted text only: nothing to go on -> one reference per line, with a
#      warning (a reference that wraps over two lines is then cut in two)
#   7. otherwise                    -> one reference
_BRACKET_LABEL = re.compile(r"(?:(?<=\s)|^)(?=\[\d{1,3}\]\s)")
_DOT_LABEL = re.compile(r"(?m)^(?=\s*\d{1,3}[.)]\s)")
_LABEL_AT_START = re.compile(r"^\s*(\[\d{1,3}\]|\d{1,3}[.)])\s+")


def _squeeze(text):
    return " ".join(text.split())


def _split_by_hanging_indent(text):
    lines = [l.rstrip() for l in text.splitlines() if l.strip()]
    indents = [len(l) - len(l.lstrip()) for l in lines]
    margin = min(indents, default=0)
    starts = [i for i, n in enumerate(indents) if n == margin]
    if len(starts) < 2 or len(starts) == len(lines) or indents[0] != margin:
        return None                      # no hanging indent: every line is at the margin
    ends = starts[1:] + [len(lines)]
    return ["\n".join(lines[a:b]) for a, b in zip(starts, ends)]


def _split_blob(text, per_line=False):
    notes = []
    if len(re.findall(r"(?:(?<=\s)|^)\[\d{1,3}\]\s", text)) >= 2:
        parts = _BRACKET_LABEL.split(text)
    elif len(_DOT_LABEL.findall(text)) >= 2:
        parts = _DOT_LABEL.split(text)
    elif len(re.split(r"\n\s*\n", text.strip())) >= 2:
        parts = re.split(r"\n\s*\n", text.strip())
    elif per_line and (hung := _split_by_hanging_indent(text)):
        parts = hung
        notes.append("No numbers or blank lines were found, so the list was split where a "
                     "line starts at the left margin and the lines after it are indented. "
                     "Check the list.")
    elif per_line and (ended := _split_where_references_end(text)):
        parts = ended
        notes.append("No numbers, blank lines or indentation were found, so the list was split "
                     "where a line ends with a year, DOI or link and the next line starts with a "
                     "capital letter. This is a guess: check the list, especially references "
                     "that end without a year or link (they may be joined to the next one).")
    elif per_line and len([l for l in text.splitlines() if l.strip()]) >= 2:
        parts = text.splitlines()
        notes.append("No numbers, blank lines, indentation or line endings to go by, so every "
                     "line is treated as one reference. Check the list: a reference that wraps "
                     "over two lines will be cut in two.")
    else:
        parts = [text]
    return [_squeeze(p) for p in parts if p.strip()], notes


# ===== SECTION 5: read the useful bits out of one reference =====
# The DOI regular expression is the same shape as in core/doi.py. It is copied
# here, not imported, because doi.py is the only file allowed near the internet.
_DOI = re.compile(r"10\.\d{4,9}/[^\s\"<>]+")
_ARXIV = re.compile(r"arxiv[:\s]*(?:abs/)?(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)
_URL = re.compile(r"https?://\S+")

# PDFs break long DOIs and links over two lines, and after joining the lines a
# space is left inside. A DOI never contains a space, so a space right after
# the "10.xxxx/" prefix, or after a "-" or "/" inside it, is a line break:
#     "10.1038/ d41586-026-01551-3"  ->  "10.1038/d41586-026-01551-3"
# A break after a "." is NOT repaired: "...abc. 2019." could be a full stop.
_DOI_BREAK = re.compile(r"(10\.\d{4,9}/(?:\S*[-/])?)\s+(?=[A-Za-z0-9])")
_URL_BREAK = re.compile(r"(https?:)\s+(?=//)")


def heal_breaks(text):
    return _URL_BREAK.sub(r"\1", _DOI_BREAK.sub(r"\1", text))


def _clean_doi(text):
    m = _DOI.search(text)
    return m.group(0).rstrip(".,;:)]}>\"'") if m else ""


# A DOI that was broken after a full stop ("10.1109/CVPR.2016. 90") cannot be
# repaired safely, because the same text can be a normal sentence end. So BOTH
# readings are kept: the verifier tries the second one online and accepts it only
# when the paper's title matches the reference. A wrong guess costs one request.
_DOI_AFTER_STOP = re.compile(r"(10\.\d{4,9}/\S*\.)\s+([A-Za-z0-9][^\s\"<>]*)")


def _alternative_dois(text, doi):
    m = _DOI_AFTER_STOP.search(text)
    if not m:
        return ()
    other = (m.group(1) + m.group(2)).rstrip(".,;:)]}>\"'")
    return (other,) if other.lower() != doi.lower() else ()


# Years from 1800 to 2039. A number is NOT taken as a year when it looks like
# part of a page range or a volume (1789-1802, 35(2):1850, "pages 1990"), and
# an "Originally published ... (1942)" note is cut off, so the year of the
# edition printed in the reference wins.
_YEAR = re.compile(r"(?<![\d.])(1[89]\d\d|20[0-3]\d)(?!\d)")
_YEAR_IN_BRACKETS = re.compile(r"[(\[]\s*(1[89]\d\d|20[0-3]\d)[a-z]?\s*[)\]]")
_PAGE_WORD_BEFORE = re.compile(r"(?:pages?|pp?\.?|vol(?:ume)?\.?|no\.?|art(?:icle)?\.?|paper|"
                               r"chapter|ch\.|issue|number)\s*$", re.IGNORECASE)
_REPRINT_NOTE = re.compile(r"\b(?:originally published|first published|reprinted|reprint of|"
                           r"translated)\b", re.IGNORECASE)


def _looks_like_a_year(text, match):
    before, after = text[:match.start()], text[match.end():]
    if before[-1:] in (":", "-", "–", "—", "/") or after[:1] in (":", "-", "–", "—", "/"):
        return False
    return not _PAGE_WORD_BEFORE.search(before)


def _find_year(text):
    text = _REPRINT_NOTE.split(text)[0]
    in_brackets = _YEAR_IN_BRACKETS.findall(text)
    if in_brackets:
        return in_brackets[-1]
    years = [m.group(1) for m in _YEAR.finditer(text) if _looks_like_a_year(text, m)]
    return years[-1] if years else ""


def parse_reference(text):
    label_match = _LABEL_AT_START.match(text)
    label = label_match.group(1) if label_match else ""
    body = _squeeze(text[label_match.end():] if label_match else text)

    healed = heal_breaks(body)
    doi = _clean_doi(healed)
    arxiv_match = _ARXIV.search(healed)
    # Take links, the DOI and the arXiv number out before looking for the year,
    # so the digits inside them are not mistaken for one.
    without_ids = _URL.sub(" ", _ARXIV.sub(" ", healed.replace(doi, " ") if doi else healed))
    return Reference(body, label, doi, arxiv_match.group(1) if arxiv_match else "",
                     _find_year(without_ids), _alternative_dois(healed, doi) if doi else ())


# What we send to Crossref when there is no DOI: the printed reference
# without links and numbers, cut to a sensible length.
def search_text(ref):
    text = _URL.sub(" ", heal_breaks(ref.raw))
    if ref.doi:
        text = text.replace(ref.doi, " ")
    return _squeeze(text)[:300]


# ===== SECTION 6: warnings about the result =====
# Things that usually mean the PDF reader got it wrong. Each one is a note the
# person sees, never a silent fix.
_VERY_LONG = 700


def _where(i, ref):
    return ref.label or f"#{i}"


def check_references(refs):
    notes = []
    if refs and not any(r.label for r in refs):
        notes.append("No reference numbers were read from the list. If the paper cites by "
                     "number, like [3], the position in this list should be that number.")
    for i, ref in enumerate(refs, 1):
        dois = {d.rstrip(".,;:)]}>\"'").lower() for d in _DOI.findall(heal_breaks(ref.raw))}
        arxivs = set(_ARXIV.findall(ref.raw))
        if len(dois) + len(arxivs) >= 2:
            notes.append(f"Reference {_where(i, ref)} contains {len(dois) + len(arxivs)} different "
                         "DOIs or arXiv numbers. It may be two references joined together.")
        elif len(ref.raw) > _VERY_LONG:
            notes.append(f"Reference {_where(i, ref)} is unusually long. It may be two "
                         "references joined together.")
    return notes


# ===== SECTION 7: the two ways in =====
# from_blocks: a PDF that core/pdfreader.py already read.
# from_text:   a list the person pasted.
# Both return (references, notes).
def split_references(strings, per_line=False):
    refs, notes = [], []
    for s in strings:
        parts, more = _split_blob(s, per_line)
        notes += more
        refs += [parse_reference(p) for p in parts]
    return refs, list(dict.fromkeys(notes))


def from_blocks(blocks):
    strings, notes = reference_strings(blocks)
    refs, more = split_references(strings)
    return refs, notes + more + check_references(refs)


def from_text(text):
    refs, notes = split_references([drop_page_numbers(text_after_heading(text))], per_line=True)
    if not refs:
        notes.append("No references were found in that text.")
    return refs, notes + check_references(refs)
