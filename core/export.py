# ===== SECTION 1: imports =====
import csv
import io

# ===== SECTION 2: all findings in one CSV =====
# findings is a dictionary: {"Missing from the .bib": [row, row], ...}
# and every row is itself a dictionary (the same rows the page shows).
# Different findings have different columns, so the CSV gets one column for
# every column name used anywhere. The first column says which finding a row
# belongs to. A cell that does not apply to a row is left empty.
def findings_to_csv(findings):
    columns = []
    for rows in findings.values():
        for row in rows:
            for name in row:
                if name not in columns:
                    columns.append(name)

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["finding"] + columns, restval="")
    writer.writeheader()
    for title, rows in findings.items():
        for row in rows:
            writer.writerow({"finding": title, **row})
    return buffer.getvalue()
