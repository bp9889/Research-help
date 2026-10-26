# ===== SECTION 1: convert one PDF =====
import sys
from docling.document_converter import DocumentConverter

result = DocumentConverter().convert(sys.argv[1])
doc = result.document

# ===== SECTION 2: list every block Docling found, with its type =====
for item, level in doc.iterate_items():
    label = str(getattr(item, "label", "?"))
    text = getattr(item, "text", "")[:70]
    print(f"{label:28} {text}")

# ===== SECTION 3: save the markdown version to read it =====
with open(sys.argv[1] + ".md", "w", encoding="utf-8") as f:
    f.write(doc.export_to_markdown())