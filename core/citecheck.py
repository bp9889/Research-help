# ===== SECTION 1: imports =====
import re
from bisect import bisect_left
from dataclasses import dataclass

# ===== SECTION 2: the pattern that finds citations =====
# Reads as: a backslash, a command containing "cite", optional [..] arguments,
# then {key1, key2} captured as "keys".
CITE_RE = re.compile(
    r"\\(?P<cmd>[A-Za-z]*cite[A-Za-z]*\*?)"   # \cite, \citep, \citet, \nocite ...
    r"\s*(?:\[[^\]]*\]\s*){0,2}"              # optional [..] arguments
    r"\{(?P<keys>[^}]*)\}"                    # the {key1, key2} part
)

# ===== SECTION 3: one found citation =====
# A small record: which key, which command, and WHERE it is.
# line = which line, col = how far along that line (1 = first character),
# context = a few words around it, so you can press Ctrl+F in VS Code.
@dataclass
class Citation:
    key: str
    cmd: str
    line: int
    col: int
    context: str

# ===== SECTION 4: ignore commented-out text =====
# Removes everything after an unescaped % but keeps the line breaks,
# so line numbers stay correct. "\%" (a real percent sign) is kept.
def strip_comments(tex):
    return re.sub(r"(?<!\\)%[^\n]*", "", tex)

# ===== SECTION 5: the main function =====
def extract_citations(tex):
    clean = strip_comments(tex)
    newline_positions = [m.start() for m in re.finditer("\n", clean)]
    found = []
    for match in CITE_RE.finditer(clean):
        # Line number = how many line breaks come before the match, plus one.
        line = bisect_left(newline_positions, match.start()) + 1

        # Column = distance from the start of that line to the match.
        line_start = newline_positions[line - 2] + 1 if line > 1 else 0
        col = match.start() - line_start + 1

        # Context = about 35 characters before and 25 after, on one line.
        a = max(0, match.start() - 35)
        b = min(len(clean), match.end() + 25)
        context = " ".join(clean[a:b].split())
        if a > 0:
            context = "..." + context
        if b < len(clean):
            context = context + "..."

        # "{1, 2, 3}" becomes three separate citations.
        for key in match.group("keys").split(","):
            key = key.strip()
            if key and not key.startswith("#"):
                found.append(Citation(key, match.group("cmd"), line, col, context))
    return found