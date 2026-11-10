#!/usr/bin/env python3
"""Copying cells puts text on the clipboard, not a picture of them (DS 9.4).

Stock ONLYOFFICE has two copy paths. Cmd/Ctrl+C goes through the browser's
copy event and writes plain text and an HTML table. The Copy item in the
right-click menu (and the toolbar button) goes through the async clipboard
API instead, and for a range of cells it also draws the selection onto a
canvas and adds that PNG to the clipboard item. Most places a person pastes
into (chat apps, mail, notes, Claude) prefer an image when one is offered, so
"select a cell, Copy, paste" landed a screenshot of the cell where its text
was wanted. Hussam, 2026-11-10: "when i select a cell and hit copy it copies
it as an image, not text".

The patch switches off that one picture: the cell-range branch of the copy
(CopyProcessor's IMAGE step) no longer runs, so both copy paths now carry the
same text and HTML. Copying a chart or a shape is a different branch and is
left as it was.

Patch sdk-all.js only: the browser loads it; sdk-all-min.js is a loader and
does not contain this code.

Idempotent: exits 0 if the marker is present. Exits 2 if the upstream anchor
is not found exactly once (a DS upgrade moved the code - re-derive the patch
instead of half-applying it to a 32 MB bundle).
"""
import sys

MARKER = "mudaber-copy-text-patch"

ANCHOR = (
    "\t\t\t\t// IMAGE\n"
    "\t\t\t\tif (_formats & AscCommon.c_oAscClipboardDataFormat.Image) {\n"
    "\t\t\t\t\tlet imageData = this.drawSelectedArea(ws, true);"
)

REPLACEMENT = (
    "\t\t\t\t// IMAGE\n"
    "\t\t\t\t// " + MARKER + ": cells copy as text and HTML only. A picture of the\n"
    "\t\t\t\t// range on the clipboard is what other apps paste instead of the text.\n"
    "\t\t\t\tif (false && (_formats & AscCommon.c_oAscClipboardDataFormat.Image)) {\n"
    "\t\t\t\t\tlet imageData = this.drawSelectedArea(ws, true);"
)

# The anchor must be the cell-range branch: after the text/selection setup of
# the cells copy, before its TEXT step.
AFTER = "ws.model.ignoreWriteFormulas(true);"
BEFORE = "//TEXT"


def main() -> int:
    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if MARKER in text:
        print("already patched")
        return 0

    if text.count(ANCHOR) != 1:
        print(f"ERROR: anchor found {text.count(ANCHOR)}x (expected 1) - DS build changed, re-derive the patch",
              file=sys.stderr)
        return 2
    at = text.index(ANCHOR)
    after_at = text.rfind(AFTER, 0, at)
    before_at = text.find(BEFORE, at)
    if after_at < 0 or at - after_at > 400 or before_at < 0 or before_at - at > 600:
        print("ERROR: anchor is not the cell-range copy's image step - DS build changed, re-derive the patch",
              file=sys.stderr)
        return 2

    text = text[:at] + REPLACEMENT + text[at + len(ANCHOR):]
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("patched (sdk copy-text: cells copy as text, not a picture)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
