# ===== SECTION 1: what this script is for =====
# Docling has several optional steps, and each one loads its own model and
# costs time. This script converts the same PDF once per setting and prints
# how long each took, so the settings are chosen from numbers, not a guess.
#
# Think of Docling as a kitchen. Every chef you hire turns up for the shift
# even when there is nothing on their station. This script hires them one at
# a time and times the meal.
#
# Run from the repository root:
#     python -m experiments.time_docling local_data/one.pdf
#     python -m experiments.time_docling local_data/one.pdf 2       (first 2 pages)
#     python -m experiments.time_docling local_data/one.pdf 2 8     (and 8 threads)
#
# The very first run also downloads about 1 GB of models, so run it twice and
# trust the second set of numbers.

import sys
import time


# ===== SECTION 2: the settings to compare =====
# Each row is a name and the switches to turn ON. Everything else stays off.
SETTINGS = [
    ("text only", {}),
    ("+ tables", {"do_table_structure": True}),
    ("+ OCR", {"do_ocr": True}),
    ("+ formulas", {"do_formula_enrichment": True}),
    ("everything on", {"do_table_structure": True, "do_ocr": True,
                       "do_formula_enrichment": True}),
]

# Steps that are on by default in Docling and that we want off at the start.
OPTIONAL_STEPS = ("do_ocr", "do_table_structure", "do_formula_enrichment",
                  "do_code_enrichment", "do_picture_classification",
                  "do_picture_description")


# ===== SECTION 3: build a converter with every optional step off =====
# set_if_present is used because Docling renames and adds these switches
# between releases. A switch this version does not have is simply skipped
# instead of crashing the whole comparison.
def set_if_present(options, name, value):
    if hasattr(options, name):
        setattr(options, name, value)
        return True
    return False


def build_converter(switches, threads):
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions()
    for step in OPTIONAL_STEPS:
        set_if_present(options, step, False)
    for name, value in switches.items():
        if not set_if_present(options, name, value):
            print(f"   (this Docling has no {name}, skipping that switch)")

    # More threads is the one free speed-up on a CPU. Docling's default is 4.
    try:
        from docling.datamodel.pipeline_options import AcceleratorOptions
        options.accelerator_options = AcceleratorOptions(num_threads=threads)
    except Exception:
        pass        # an older Docling sets threads elsewhere; not worth failing over

    return DocumentConverter(format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=options)})


# ===== SECTION 4: time one conversion =====
# Two numbers are measured separately, because they have different cures:
#   build   - loading the models. Cure: build the converter once and reuse it.
#   convert - reading this PDF. Cure: turn a step off, or convert fewer pages.
def time_once(path, switches, threads, page_limit):
    start = time.perf_counter()
    converter = build_converter(switches, threads)
    built = time.perf_counter()

    if page_limit:
        try:
            result = converter.convert(path, page_range=(1, page_limit))
        except TypeError:
            print("   (this Docling has no page_range, converting every page)")
            result = converter.convert(path)
    else:
        result = converter.convert(path)

    done = time.perf_counter()
    blocks = sum(1 for _ in result.document.iterate_items())
    return built - start, done - built, blocks


# ===== SECTION 5: run every setting and print a table =====
def main():
    if len(sys.argv) < 2:
        print("usage: python -m experiments.time_docling <pdf> [pages] [threads]")
        return

    path = sys.argv[1]
    page_limit = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    threads = int(sys.argv[3]) if len(sys.argv) > 3 else 4

    print(f"{path}   pages={page_limit or 'all'}   threads={threads}")
    print(f"{'setting':15} {'build':>8} {'convert':>9} {'blocks':>7}")

    for name, switches in SETTINGS:
        try:
            build, convert, blocks = time_once(path, switches, threads, page_limit)
            print(f"{name:15} {build:7.1f}s {convert:8.1f}s {blocks:7}")
        except Exception as error:
            # One bad setting must not stop the rest of the comparison.
            print(f"{name:15} failed: {type(error).__name__}: {error}")


if __name__ == "__main__":
    main()
