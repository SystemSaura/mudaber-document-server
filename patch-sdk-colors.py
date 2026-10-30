#!/usr/bin/env python3
"""Recolour the spreadsheet grid canvas to the Mudaber palette (DS 9.4).

The cell grid is drawn on a canvas, not styled by CSS, and its colours are
hardcoded CColor literals inside sdkjs/cell/sdk-all.js. No editorConfig key
and no custom uiTheme reaches them - the theme JSONs skin the UI chrome, so
the sheet itself keeps shipping OnlyOffice green on top of the Mudaber accent.
Patching the literal is the only lever, and the file is ours.

Patch sdk-all.js only. The browser loads it (verified); the minified sibling
sdk-all-min.js does not contain these literals and must stay untouched.

  CColor(72, 121, 92)   -> accent blue     selection border + fill handle
  CColor(202, 202, 202) -> lighter grey    grid lines

The freeze line (129, 129, 129) is deliberately left alone: in this build
that triple is not uniquely a colour literal - it appears 11 times as a bare
substring, in code that has nothing to do with colours - so a replace would
risk corrupting unrelated logic. A darker freeze line is not worth that.

Only the CColor(...) forms are rewritten, never bare substrings: "202, 202,
202" occurs 5 times but only 3 of those are colour constructions.

Idempotent: exits 0 if the marker is already present. Exits 2 if any literal
count differs from what this DS build shipped (a DS upgrade moved the
ground - re-derive the counts before shipping, rather than leave a
half-patched 32 MB bundle behind).
"""
import sys

MARKER = "mudaber-sdk-colors-patch"

# Mudaber palette - edit here, nowhere else.
ACCENT_BLUE = "CColor(47, 107, 255)"     # #2F6BFF, the Aurora accent
GRIDLINE_GREY = "CColor(230, 233, 240)"  # #E6E9F0, Aurora hairline

# Stock DS 9.4.0-129 literals, written with spaces after the commas.
OO_SELECTION_GREEN = "CColor(72, 121, 92)"    # #48795C
OO_GRIDLINE_GREY = "CColor(202, 202, 202)"    # #CACACA

# (literal, replacement, exact expected count, label)
REPLACEMENTS = [
    (OO_SELECTION_GREEN, ACCENT_BLUE, 1, "selection"),
    (OO_GRIDLINE_GREY, GRIDLINE_GREY, 3, "gridline"),
]

TRAILER = "\n// " + MARKER + "\n"


def main() -> int:
    path = sys.argv[1]
    # 32 MB file: one read, string ops, one write. Never line-by-line.
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if MARKER in text:
        print("already patched")
        return 0

    counts = [(old, text.count(old), expected) for old, _, expected, _ in REPLACEMENTS]
    wrong = [(old, actual, expected) for old, actual, expected in counts if actual != expected]
    if wrong:
        for old, actual, expected in wrong:
            print(
                f"ERROR: {old} found {actual} times, expected {expected}",
                file=sys.stderr,
            )
        print(
            "ERROR: sdk-all.js colour literals changed - DS build changed, re-derive the patch",
            file=sys.stderr,
        )
        return 2

    for old, new, expected, _ in REPLACEMENTS:
        text = text.replace(old, new, expected)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + TRAILER)

    summary = ", ".join(f"{expected} {label}" for _, _, expected, label in REPLACEMENTS)
    print(f"patched (sdk colors: {summary})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
