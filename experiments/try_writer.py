# ===== SECTION 1: PDF -> blocks -> .tex, and a summary of what needs a look =====
# Run from the project folder:  python -m experiments.try_writer local_data/one.pdf
import sys
from collections import Counter

from core.latexwriter import blocks_to_latex
from core.pdfreader import read_pdf


def main():
    blocks = read_pdf(sys.argv[1])
    result = blocks_to_latex(blocks)
    with open(sys.argv[1] + ".tex", "w", encoding="utf-8") as f:
        f.write(result.tex)
    print(f"{len(blocks)} blocks read, {len(result.references)} reference block(s) set aside")
    print("Needs a look:", dict(Counter(n["kind"] for n in result.notes)))
    for n in result.notes:
        if n["kind"] == "formula":
            print(f"page {n['page']}: {n['message']}")


if __name__ == "__main__":
    main()