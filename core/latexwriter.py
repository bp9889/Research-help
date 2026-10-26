# ===== SECTION 1: imports and the result =====
import re
from dataclasses import dataclass


@dataclass
class Result:
    tex: str            # the LaTeX text
    references: list    # raw reference text, kept for the later reference step
    notes: list         # everything that needs a human look: page, kind, message


# ===== SECTION 2: escape special characters =====
# LaTeX gives these ten characters a special meaning, so they must be escaped.
# The text is changed one character at a time, so nothing is escaped twice.
SPECIAL = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
           "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
           "^": r"\textasciicircum{}"}


def escape_latex(text):
    return "".join(SPECIAL.get(ch, ch) for ch in text)


# ===== SECTION 3: headings =====
# Docling gives every heading the same level, so the level comes from the
# section number: 3 is a section, 3.1 a subsection, 3.1.2 a subsubsection.
NUMBER = re.compile(r"^\s*(\d+(?:\.\d+)*\.?)\s+(\S.*)$")
COMMANDS = ["section", "subsection", "subsubsection", "paragraph"]


def split_number(text, strict=False):
    """Return (depth, title without number). Depth 0 means no number.
    strict=True demands a dot ("1." or "1.2"), so "2023 Annual report" is not a heading."""
    match = NUMBER.match(text)
    if not match or (strict and "." not in match.group(1)):
        return 0, text.strip()
    return match.group(1).rstrip(".").count(".") + 1, match.group(2).strip()


def is_numbered_heading(text):
    """A short numbered line that Docling called plain text, like '1. INTRODUCTION'."""
    depth, rest = split_number(text, strict=True)
    return (depth > 0 and len(text) <= 90 and len(rest.split()) <= 12
            and not rest.endswith((".", ",", ";", ":")) and rest[:1].isalnum())


# ===== SECTION 4: spotting math we cannot rebuild yet =====
# Greek letters, math operators, math-italic letters and a few symbols.
MATH = re.compile("[\U0001D400-\U0001D7FF\u0370-\u03FF\u2200-\u22FF\u00D7\u00B1\u02C6]")
BODY_PARTS = {"abstract": "abstract", "keywords": "keywords", "index terms": "keywords",
              "references": "references", "bibliography": "references"}
KEYWORDS_START = re.compile(r"^(index terms|keywords)\s*[-\u2013\u2014:]*\s*", re.I)


# ===== SECTION 5: blocks -> LaTeX =====
# One pass over the blocks with a "mode": front matter, abstract, keywords,
# body, references. Anything we cannot convert yet becomes a % comment in the
# .tex file AND a row in notes, so nothing disappears silently.
def blocks_to_latex(blocks):
    title, authors, abstract, keywords = "", [], [], []
    body, references, notes, items = [], [], [], []
    mode = "front"

    def note(block, message):
        notes.append({"page": block.page, "kind": block.kind, "message": message})

    def flush_items():
        if items:
            lines = "\n".join(f"  \\item {i}" for i in items)
            body.append("\\begin{itemize}\n" + lines + "\n\\end{itemize}")
            items.clear()

    for block in blocks:
        kind, text = block.kind, block.text
        if kind == "skip" or (not text and kind not in ("formula", "table", "figure")):
            continue
        if kind == "text" and mode != "references" and is_numbered_heading(text):
            kind = "heading"
            note(block, f"Plain text looked like a heading and was promoted: {text}")
        if kind != "list_item":
            flush_items()

        # --- headings and the title ---
        if kind in ("heading", "title"):
            depth, clean = split_number(text)
            key = clean.lower()
            if not title and mode == "front" and depth == 0 and key not in BODY_PARTS:
                title = clean
            elif key in BODY_PARTS:
                mode = BODY_PARTS[key]
            else:
                mode = "body"
                command = COMMANDS[min(depth, 4) - 1] if depth else "section*"
                body.append(f"\\{command}{{{escape_latex(clean)}}}")
            continue

        # --- front matter, abstract, keywords, references ---
        if mode == "front":
            authors.append(escape_latex(text))
            continue
        if mode == "abstract":
            if KEYWORDS_START.match(text):
                keywords.append(escape_latex(KEYWORDS_START.sub("", text)))
            else:
                abstract.append(escape_latex(text))
            continue
        if mode == "keywords":
            keywords.append(escape_latex(text))
            continue
        if mode == "references":
            if kind in ("text", "list_item"):
                references.append(text)
            continue

        # --- body ---
        if kind == "text" and KEYWORDS_START.match(text) and not body:
            keywords.append(escape_latex(KEYWORDS_START.sub("", text)))
        elif kind == "text":
            body.append(escape_latex(text))
            count = len(MATH.findall(text))
            if count:
                note(block, f"{count} math symbol(s) in this paragraph; inline math is not rebuilt yet")
        elif kind == "list_item":
            items.append(escape_latex(text))
        elif kind == "caption":
            body.append(f"% CAPTION (page {block.page}): " + " ".join(text.split()))
            note(block, "Caption kept as a comment; figures and tables come in later steps")
        elif kind in ("formula", "table", "figure"):
            shown = " ".join(text.split())[:100]
            body.append(f"% {kind.upper()} (page {block.page}): not converted yet {shown}".rstrip())
            note(block, f"{kind} not converted yet")
        else:
            body.append(f"% OTHER (page {block.page}): " + " ".join(text.split())[:100])
            note(block, "Block type not supported yet: kept as a comment")
    flush_items()

    # --- assemble the file ---
    if not title:
        notes.append({"page": 0, "kind": "title", "message": "No title found"})
    head = ["% Compile with XeLaTeX or LuaLaTeX (the text is Unicode).",
            r"\documentclass[11pt]{article}", r"\usepackage{fontspec}",
            r"\usepackage[margin=2.5cm]{geometry}",
            r"\title{%s}" % escape_latex(title),
            r"\author{%s}" % " \\\\\n  ".join(authors), r"\date{}",
            r"\begin{document}", r"\maketitle"]
    parts = ["\n".join(head)]
    if abstract:
        parts.append("\\begin{abstract}\n" + "\n\n".join(abstract) + "\n\\end{abstract}")
    if keywords:
        parts.append("\\noindent\\textbf{Keywords:} " + "; ".join(keywords))
    parts += body
    parts.append("\\end{document}")
    return Result("\n\n".join(parts) + "\n", references, notes)