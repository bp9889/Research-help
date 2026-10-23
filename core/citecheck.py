# ===== SECTION 1: imports =====
import re
from bisect import bisect_left
from dataclasses import dataclass

# ===== SECTION 2: the pattern that finds citations =====
CITE_RE = re.compile(
    r"\\(?P<cmd>[A-Za-z]*cite[A-Za-z]*\*?)"   # \cite, \citep, \citet, \nocite ...
    r"\s*(?:\[[^\]]*\]\s*){0,2}"              # optional [..] arguments
    r"\{(?P<keys>[^}]*)\}"                    # the {key1, key2} part
)

# ===== SECTION 3: one found citation =====
# line/col say WHERE it is, context shows the words around it,
# file says which .tex file it came from (empty when text was pasted).
@dataclass
class Citation:
    key: str
    cmd: str
    line: int
    col: int
    context: str
    file: str = ""

# ===== SECTION 4: ignore commented-out text =====
# NEW: instead of deleting a comment we blank it with spaces of the same
# length. Now every character keeps its position, which lets us edit the
# ORIGINAL text safely at the positions we find here.
def mask_comments(tex):
    return re.sub(r"(?<!\\)%[^\n]*", lambda m: " " * len(m.group(0)), tex)

# ===== SECTION 5: find citations =====
def extract_citations(tex, filename=""):
    clean = mask_comments(tex)
    newline_positions = [m.start() for m in re.finditer("\n", clean)]
    found = []
    for match in CITE_RE.finditer(clean):
        line = bisect_left(newline_positions, match.start()) + 1
        line_start = newline_positions[line - 2] + 1 if line > 1 else 0
        col = match.start() - line_start + 1

        a = max(0, match.start() - 35)
        b = min(len(clean), match.end() + 25)
        context = " ".join(clean[a:b].split())
        if a > 0:
            context = "..." + context
        if b < len(clean):
            context = context + "..."

        for key in match.group("keys").split(","):
            key = key.strip()
            if key and not key.startswith("#"):
                found.append(Citation(key, match.group("cmd"), line, col, context, filename))
    return found

# ===== SECTION 6: change keys inside \cite{...} (NEW) =====
# mapping = {"old key": "new key"}. We find every citation exactly as in
# section 5, but instead of reading the keys we replace them in the ORIGINAL
# text, leaving spaces, commas and everything else untouched.
# Returns the new text and a log of every change.
def rewrite_keys(tex, mapping, filename=""):
    masked = mask_comments(tex)
    edits = []                                   # (start, end, new_key)
    for match in CITE_RE.finditer(masked):
        offset = match.start("keys")
        for part in match.group("keys").split(","):
            word = part.strip()
            if word in mapping:
                start = offset + part.index(word)
                edits.append((start, start + len(word), mapping[word]))
            offset += len(part) + 1              # +1 for the comma we split on

    log = []
    for start, end, new in edits:
        log.append({"file": filename, "line": tex.count("\n", 0, start) + 1,
                    "detail": f"{tex[start:end]} -> {new}"})
    for start, end, new in sorted(edits, reverse=True):   # from the end, so
        tex = tex[:start] + new + tex[end:]               # positions stay valid
    return tex, log