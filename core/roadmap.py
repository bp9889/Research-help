# status is "done", "doing" or "todo". To update the progress bar you only
# change a word here, nothing else.
ROADMAP = [
    ("Phase 1: Cite checker", [
        ("Project setup (Python, venv, Git, GitHub)", "done"),
        ("Hello page", "done"),
        ("Citation finder with line, column and context", "done"),
        (".bib reader", "done"),
        ("Compare: missing, unused, duplicates, case", "done"),
        ("Upload several .tex and .bib files", "done"),
        ("Fix, merge and clean actions with preview", "done"),
        ("Corrected text with copy button", "done"),
        ("Page layout fixes", "done"),
        ("Same paper under different keys", "done"),
        ("Citation order table", "done"),
        ("Missing-fields check", "doing"),
        ("Separate renumber tool", "doing"),
    ]),
    ("Phase 2: Reference tools", [
        ("BibTeX tidy in my style", "todo"),
        ("DOI to BibTeX import", "todo"),
        ("Paper tracker", "todo"),
    ]),
    ("Phase 3: Portfolio", [
        ("README with screenshots", "todo"),
        ("Public demo with sample data", "todo"),
        ("Short technical write-up", "todo"),
    ]),
]

ICON = {"done": "✅", "doing": "🔄", "todo": "⬜"}

# A finished item counts 1, an item in progress counts half.
def score(items):
    points = sum({"done": 1, "doing": 0.5}.get(status, 0) for _, status in items)
    return points, len(items)