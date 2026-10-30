#!/usr/bin/env python3
"""Give text in spreadsheet cells a little more room (DS 9.4).

Stock ONLYOFFICE keeps 2 px between a cell's text and its grid line (Excel's
own figure for Calibri 11), which is what makes a sheet look cramped. This
raises the drawing padding by 2 px a side. It is display only: the padding the
model uses to convert column widths between Excel's characters and pixels
(`paddingPlusBorder`) is kept at the stock value, so no file's column widths
change and Excel opens every saved file exactly as before.

Patch sdk-all.js only (the browser loads it). Idempotent through the marker;
exits 2 if the upstream line moved, so a DS upgrade fails the build loudly.
"""
import sys

MARKER = "mudaber-sdk-padding-patch"
OLD = ("t.defaults.worksheetView.cells.padding = Math.max(asc.ceil(t.maxDigitWidth / 4), 2);\n"
       "\t\t  t.model.paddingPlusBorder = 2 * t.defaults.worksheetView.cells.padding + 1;")
NEW = ("var mdbPad = Math.max(asc.ceil(t.maxDigitWidth / 4), 2); /* " + MARKER + " */\n"
       "\t\t  t.defaults.worksheetView.cells.padding = mdbPad + 2;\n"
       "\t\t  t.model.paddingPlusBorder = 2 * mdbPad + 1;")


def main() -> int:
    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if MARKER in text:
        print("already patched")
        return 0
    n = text.count(OLD)
    if n != 1:
        print(f"ERROR: cell padding block found {n} times, expected 1 - DS build changed, re-derive the patch", file=sys.stderr)
        return 2
    with open(path, "w", encoding="utf-8") as f:
        f.write(text.replace(OLD, NEW, 1))
    print("patched (cell padding +2 px a side, widths untouched)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
