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
# A tiny record: which key, which command, which line.
@dataclass
class Citation:
    key: str
    cmd: str
    line: int

# ===== SECTION 4: ignore commented-out text =====
# Removes everything after an unescaped % but keeps the line breaks,
# so line numbers stay correct. "\%" (a real percent sign) is kept.
def strip_comments(tex):
    return re.sub(r"(?<!\\)%[^\n]*", "", tex)

# ===== SECTION 5: the main function =====
# Finds every citation, splits "{1, 2, 3}" into three keys, and works out
# the line number of each one from the position of the match.
def extract_citations(tex):
    clean = strip_comments(tex)
    newline_positions = [m.start() for m in re.finditer("\n", clean)]
    found = []
    for match in CITE_RE.finditer(clean):
        line = bisect_left(newline_positions, match.start()) + 1
        for key in match.group("keys").split(","):
            key = key.strip()
            if key and not key.startswith("#"):    # "#1" means a macro, not a key
                found.append(Citation(key, match.group("cmd"), line))
    return found