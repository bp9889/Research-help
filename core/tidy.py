# ===== SECTION 1: imports =====
import re
from collections import Counter
from dataclasses import dataclass

from .bibreader import ENTRY_RE, _find_closing, extract_bib_entries

# ===== SECTION 2: the owner's style =====
# Fields come in this order. A field that is not in the list goes after the
# listed ones, in the order it was written. The name is padded to 13 characters
# (or one more than its length when it is longer) and then comes "= ".
FIELD_ORDER = [
    "title", "shorttitle", "author", "year", "month", "day", "journal",
    "booktitle", "location", "on", "publisher", "address", "series", "volume",
    "number", "pages", "doi", "isbn", "issn", "url", "urldate", "copyright",
    "category", "note", "metadata",
]
NAME_WIDTH = 13
_DIGITS = re.compile(r"[0-9]+")

# ===== SECTION 3: reading one entry strictly =====
# The parser in fields.py is forgiving, which is fine for checking. For
# rewriting we need to be sure, so this one raises TidyError for anything it
# does not fully understand, and the entry is then left exactly as it was.
class TidyError(Exception):
    pass

@dataclass
class ParsedEntry:
    type: str
    key: str
    fields: list        # (name in lowercase, text, is_macro)

_NAME_EQ = re.compile(r"\s*([A-Za-z][A-Za-z0-9_:-]*)\s*=\s*")
_BARE = re.compile(r"[^\s,{}()\"#=]+")

def parse_entry(raw):
    m = ENTRY_RE.match(raw)
    if not m or raw[-1] not in "})":
        raise TidyError("could not read the start or end of the entry")
    last = len(raw) - 1                    # position of the closing } or )
    i, fields = m.end(), []
    while True:
        while i < last and raw[i].isspace():
            i += 1
        if i >= last:
            break
        nm = _NAME_EQ.match(raw, i)
        if not nm or nm.end() >= last:
            raise TidyError(f"unexpected text near {raw[i:i + 20]!r}")
        j, name = nm.end(), nm.group(1).lower()

        if raw[j] == "{":
            end = _find_closing(raw, j)
            if end == -1 or end >= last:
                raise TidyError(f"unbalanced braces in {name}")
            text, macro, i = raw[j + 1:end], False, end + 1
        elif raw[j] == '"':
            k, depth = j + 1, 0
            while k < last:
                ch = raw[k]
                if ch == "\\" and depth == 0 and raw[k + 1:k + 2] == '"':
                    raise TidyError(f'a backslash before " in {name} is unclear')
                if ch == "\\":
                    k += 2
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth < 0:
                        raise TidyError(f"unbalanced braces in {name}")
                elif ch == '"' and depth == 0:
                    break
                k += 1
            if k >= last:
                raise TidyError(f"quote not closed in {name}")
            text, macro, i = raw[j + 1:k], False, k + 1
        else:
            b = _BARE.match(raw, j)
            if not b:
                raise TidyError(f"could not read the value of {name}")
            text, i = b.group(0), b.end()
            macro = not _DIGITS.fullmatch(text)      # year = 2020 is a number, jan is a macro

        while i < last and raw[i].isspace():
            i += 1
        if i < last and raw[i] == "#":
            raise TidyError(f"{name} joins strings with #")
        if i < last and raw[i] == ",":
            i += 1
        elif i < last:
            raise TidyError(f"unexpected text after {name}")
        fields.append((name, text if macro else " ".join(text.split()), macro))
    return ParsedEntry(m.group("type"), m.group("key"), fields)

# ===== SECTION 4: writing one entry in the owner's style =====
def _rank(name):
    return FIELD_ORDER.index(name) if name in FIELD_ORDER else len(FIELD_ORDER)

# fields = list of (name, text, is_macro). A number or a macro is written bare,
# everything else in curly braces. This is also used by the DOI import.
def format_entry(entry_type, key, fields, newline="\n"):
    ordered = sorted(fields, key=lambda f: _rank(f[0]))      # stable: ties keep their order
    lines = [f"@{entry_type}{{{key},"]
    for n, (name, text, macro) in enumerate(ordered):
        bare = macro or _DIGITS.fullmatch(text)
        value = text if bare else "{" + text + "}"
        comma = "," if n < len(ordered) - 1 else ""
        lines.append(f"\t{name.ljust(max(NAME_WIDTH, len(name) + 1))}= {value}{comma}")
    lines.append("}")
    return newline.join(lines)

# ===== SECTION 5: the guard that proves the wording did not change =====
# Two independent checks. Both must pass, or the entry is left as it was.
#   1. Field by field: same type, same key, same fields with the same text
#      (order, spacing and the braces/quotes around a value do not count).
#   2. A safety net: every letter and digit in the whole entry is counted
#      (ignoring upper/lower case), and the counts must be equal.
def _signature(raw):
    p = parse_entry(raw)
    return p.type.lower(), p.key, sorted(p.fields)

def _letters(raw):
    return Counter(re.sub(r"[^a-z0-9]", "", raw.lower()))

def same_wording(old_raw, new_raw):
    try:
        return _signature(old_raw) == _signature(new_raw) and _letters(old_raw) == _letters(new_raw)
    except TidyError:
        return False

# ===== SECTION 6: tidy one entry =====
# Returns (new text, reason). The reason is empty when all went well.
def tidy_entry(raw, newline="\n"):
    try:
        p = parse_entry(raw)
    except TidyError as err:
        return raw, str(err)
    new = format_entry(p.type, p.key, p.fields, newline)
    if not same_wording(raw, new):
        return raw, "the wording check failed"
    return new, ""

# ===== SECTION 7: tidy a whole .bib file =====
# Text between entries (comments, @string, @comment, @preamble) is kept. Only
# blank lines around it are removed, so there are none between entries.
# Entries are never sorted, merged or removed. Returns (new text, change log).
def _block(gap):
    lines = gap.replace("\r\n", "\n").split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines

def tidy_bib(text, filename=""):
    entries = extract_bib_entries(text, filename)
    if not entries:
        return text, []
    newline = "\r\n" if "\r\n" in text else "\n"
    blocks, log, pos = [], [], 0
    for e in entries:
        blocks += _block(text[pos:e.start])
        new, reason = tidy_entry(e.raw, newline)
        blocks.append(new)
        if reason:
            log.append({"action": "tidy skipped", "file": filename, "line": e.line,
                        "detail": f"left {e.key} unchanged: {reason}"})
        elif new != e.raw:
            log.append({"action": "tidy", "file": filename, "line": e.line,
                        "detail": f"reformatted entry {e.key}"})
        pos = e.end
    blocks += _block(text[pos:])
    return newline.join(blocks) + newline, log
