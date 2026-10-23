# ===== SECTION 1: imports =====
import re
from dataclasses import dataclass

# ===== SECTION 2: the pattern that finds the start of an entry =====
# At the start of a line (spaces allowed): @, the type, an opening { or (,
# then the key up to the first comma. A commented-out "% @article{99," is
# NOT matched because the line must start with the @.
ENTRY_RE = re.compile(
    r"^[ \t]*@(?P<type>[A-Za-z]+)[ \t]*(?P<open>[{(])[ \t]*(?P<key>[^,\s]+)[ \t]*,",
    re.MULTILINE,
)
NOT_REFERENCES = {"comment", "string", "preamble"}

# ===== SECTION 3: one entry from the .bib file =====
# start/end are character positions of the whole entry in the file, and raw
# is its exact text. We need them so entries can be cut out safely later.
@dataclass
class BibEntry:
    key: str
    type: str
    line: int
    start: int = 0
    end: int = 0
    raw: str = ""
    file: str = ""

# ===== SECTION 4: find where an entry ends (NEW) =====
# Count { and } until the opening brace is closed again. A backslash skips
# the next character, so \{ and \} (escaped braces) are not counted.
def _find_closing(text, open_index):
    paren = text[open_index] == "("
    depth = 0
    i = open_index + 1 if paren else open_index
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and not paren:
                return i
        elif c == ")" and paren and depth == 0:
            return i
        i += 1
    return -1

# ===== SECTION 5: the main function =====
def extract_bib_entries(bib_text, filename=""):
    matches = list(ENTRY_RE.finditer(bib_text))
    entries = []
    for i, match in enumerate(matches):
        entry_type = match.group("type").lower()
        if entry_type in NOT_REFERENCES:
            continue
        end = _find_closing(bib_text, match.start("open"))
        if end == -1:      # unbalanced braces: stop at the next entry instead
            end = matches[i + 1].start() if i + 1 < len(matches) else len(bib_text)
        else:
            end += 1
        line = bib_text.count("\n", 0, match.start()) + 1
        entries.append(BibEntry(match.group("key"), entry_type, line,
                                match.start(), end, bib_text[match.start():end], filename))
    return entries