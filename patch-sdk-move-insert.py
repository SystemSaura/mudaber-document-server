#!/usr/bin/env python3
"""Dragging whole columns or rows inserts them where you drop them (DS 9.4).

Stock ONLYOFFICE overwrites: grab column K by its header, drop it on E, and
K's contents replace E's (after a "replace?" prompt). Excel and Google Sheets
users expect the column to slide in between instead, with everything else
shifting aside. ONLYOFFICE already ships that behaviour - its "insert between"
move, with the insertion line, the cut-and-shift and a single undo step - but
only while Shift is held at the moment you start dragging, which nobody finds.

The patch makes that the default for whole-column and whole-row selections,
whichever way the drag starts (from the header, or from the selection border).
Ctrl/Cmd still copies; with this patch the copy is inserted too, so a drag of
a whole column or row can no longer overwrite anything. Partial ranges (a few
cells) keep stock behaviour, which already asks before replacing data.

One injection point: the first call of
WorksheetView.prototype.changeSelectionMoveRangeHandle, where the drag stores
its column/row move options. Upstream reads options.shiftKey from there on
(drawing the insertion line, computing the target, and doing the insert-move
in applyMoveRangeHandle), so forcing shiftKey on for RangeCol/RangeRow is the
whole change.

Patch sdk-all.js only: the browser loads it; sdk-all-min.js is a loader and
does not contain this code (verified: 0 occurrences).

Idempotent: exits 0 if the marker is present. Exits 2 if the upstream anchor
is not found exactly once (a DS upgrade moved the code - re-derive the patch
instead of half-applying it to a 32 MB bundle).
"""
import sys

MARKER = "mudaber-move-insert-patch"

ANCHOR = (
    "\t\t\t//added new options for move all colls/rows\n"
    "\t\t\tif (colRowMoveProps) {\n"
    "\t\t\t\tthis.startCellMoveRange.colRowMoveProps = colRowMoveProps;\n"
    "\t\t\t}\n"
)

INJECT = (
    "\t\t\t// " + MARKER + ": a whole column or row you drag is inserted where you drop it,\n"
    "\t\t\t// shifting the others aside, instead of overwriting the column/row underneath.\n"
    "\t\t\t// Upstream does this only while Shift is held; Mudaber makes it the default.\n"
    "\t\t\tif (type === c_oAscSelectionType.RangeCol || type === c_oAscSelectionType.RangeRow) {\n"
    "\t\t\t\tcolRowMoveProps = colRowMoveProps || {ctrlKey: false};\n"
    "\t\t\t\tcolRowMoveProps.shiftKey = true;\n"
    "\t\t\t}\n"
)

# The anchor must sit inside changeSelectionMoveRangeHandle, after `type` is set.
FUNC_HEAD = "WorksheetView.prototype.changeSelectionMoveRangeHandle = function (x, y, colRowMoveProps) {"
TYPE_DECL = "var type = selectionRange.getType();"


def main() -> int:
    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if MARKER in text:
        print("already patched")
        return 0

    if text.count(ANCHOR) != 1 or text.count(FUNC_HEAD) != 1:
        print(f"ERROR: anchor found {text.count(ANCHOR)}x, function head {text.count(FUNC_HEAD)}x "
              "(expected 1 each) - DS build changed, re-derive the patch", file=sys.stderr)
        return 2
    head_at, anchor_at = text.index(FUNC_HEAD), text.index(ANCHOR)
    type_at = text.find(TYPE_DECL, head_at)
    next_func = text.find("WorksheetView.prototype.", head_at + len(FUNC_HEAD))
    if not (head_at < type_at < anchor_at < next_func):
        print("ERROR: anchor is not inside changeSelectionMoveRangeHandle after `type` is declared "
              "- DS build changed, re-derive the patch", file=sys.stderr)
        return 2

    text = text[:anchor_at] + INJECT + text[anchor_at:]
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("patched (sdk move-insert: whole columns/rows insert on drop)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
