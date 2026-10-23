# ===== SECTION 1: imports =====
import re
from dataclasses import dataclass

# ===== SECTION 2: the pattern that finds the start of an entry =====
# Reads as: at the start of a line (spaces allowed), an @, the entry type
# (article, book...), an opening { or (, then the key up to the first comma.
# Because we require the @ to start the line, a commented-out entry such as
# "% @article{99," is NOT picked up.
ENTRY_RE = re.compile(
    r"^[ \t]*@(?P<type>[A-Za-z]+)[ \t]*[{(][ \t]*(?P<key>[^,\s]+)[ \t]*,",
    re.MULTILINE,
)

# These look like entries but are not references, so we skip them.
NOT_REFERENCES = {"comment", "string", "preamble"}

# ===== SECTION 3: one entry from the .bib file =====
@dataclass
class BibEntry:
    key: str     # the thing inside \cite{...}, for example "12" or "smith2020"
    type: str    # article, book, inproceedings ...
    line: int    # which line of the .bib it starts on

# ===== SECTION 4: the main function =====
def extract_bib_entries(bib_text):
    entries = []
    for match in ENTRY_RE.finditer(bib_text):
        entry_type = match.group("type").lower()
        if entry_type in NOT_REFERENCES:
            continue
        # Line number = how many line breaks come before the match, plus one.
        line = bib_text.count("\n", 0, match.start()) + 1
        entries.append(BibEntry(match.group("key"), entry_type, line))
    return entries