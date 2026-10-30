#!/usr/bin/env python3
"""Recolour the editor's icon sprites to the Mudaber palette (DS 9.4).

The toolbar glyphs are not inline SVG and not CSS-maskable: they are PNG sprite
sheets pulled in as `background-image`, so no theme token, no `uiTheme` and no
stylesheet can reach their colour. The only way to move them off stock is to
recolour the pixels, which is what this does at image build time.

Takes one or more img directories - the three editors ship their own sheets.

DS 9.4 ships two generations of sprite side by side. The older sheets are
entirely monochrome. The `v2/` sheets are not: they carry ONLYOFFICE's accent
blue (around #446ECA with a #92B7F0 highlight) and a few semantic reds. So the
transform is per pixel rather than per file:

  grey and dark   -> Mudaber ink. These are the ordinary glyphs.
  grey and light  -> left alone. Each sheet carries a white "inverse" twin of
                     every glyph, the one `.toolbar__icon.icon--inverse` reaches
                     with `background-position-x:-20px` for dark surfaces;
                     inking those would make them vanish.
  ONLYOFFICE blue -> rotated onto the Mudaber accent hue (Aurora blue), keeping its own
                     saturation and lightness so shading and antialiasing
                     survive. This is what stops the icons reading as theirs.
  anything else   -> left alone. Reds and greens are semantic (delete, error,
                     validation) and are not ours to reinterpret.

Antialiasing lives in the alpha channel, which is passed through untouched.

Exits 2 if a sprite is unreadable and too large to be one of DS's empty
placeholders - that means an upgrade changed the format, so look before shipping.
"""
import colorsys
import sys
from pathlib import Path

from PIL import Image, UnidentifiedImageError

# Matches `icon-normal` in theme-mudaber-pure.json: rgba(26,26,30,.62) over
# white. Keeping the two in step is the point - the sprite glyphs and the
# themeable icons have to read as one set.
INK = (113, 113, 116)  # #717174

# Mudaber accent #2F6BFF (Aurora). Only the hue is taken; each pixel keeps its own
# saturation and lightness so the icons stay shaded rather than going flat.
ACCENT_HUE = colorsys.rgb_to_hls(0x2F / 255, 0x6B / 255, 0xFF / 255)[0]

# Above this a neutral pixel belongs to the white inverse twin.
DARK_CUTOFF = 128
# Channels within this spread count as neutral.
NEUTRAL_TOLERANCE = 16
# ONLYOFFICE's accent blue sits near 220 degrees; this window is wide enough to
# catch its highlight and shadow steps without reaching cyan or violet.
BLUE_HUE_RANGE = (200 / 360, 245 / 360)
MIN_SATURATION = 0.15


def recolour(px, x, y):
    r, g, b, a = px[x, y]
    if a == 0:
        return None
    if max(r, g, b) - min(r, g, b) <= NEUTRAL_TOLERANCE:
        return (INK[0], INK[1], INK[2], a) if r < DARK_CUTOFF else None
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    if s < MIN_SATURATION or not (BLUE_HUE_RANGE[0] <= h <= BLUE_HUE_RANGE[1]):
        return None
    nr, ng, nb = colorsys.hls_to_rgb(ACCENT_HUE, l, s)
    return (round(nr * 255), round(ng * 255), round(nb * 255), a)


def tint(path: Path) -> tuple[int, int, int]:
    img = Image.open(path).convert("RGBA")
    px = img.load()
    w, h = img.size
    inked = accented = untouched = 0
    for y in range(h):
        for x in range(w):
            new = recolour(px, x, y)
            if new is None:
                untouched += 1
                continue
            if new[:3] == INK:
                inked += 1
            else:
                accented += 1
            px[x, y] = new
    img.save(path, "PNG", optimize=True)
    return inked, accented, untouched


def main() -> int:
    # One argument per editor's img dir - each has its own sprite sheets.
    for img_dir in sys.argv[1:]:
        rc = tint_dir(Path(img_dir))
        if rc != 0:
            return rc
    return 0


def tint_dir(img_dir: Path) -> int:
    print(f"==> {img_dir}")
    sprites = sorted(p for p in img_dir.rglob("icons*.png"))
    if not sprites:
        print(f"ERROR: no icon sprites under {img_dir}", file=sys.stderr)
        return 2
    total = [0, 0]
    for p in sprites:
        try:
            inked, accented, _ = tint(p)
        except UnidentifiedImageError:
            # DS ships empty placeholders (the iconshuge set is 0 bytes).
            # Skipping those is right; a real sprite failing to decode is not,
            # so size is the guard.
            size = p.stat().st_size
            if size < 2048:
                print(f"    {p.relative_to(img_dir)}: skipped, {size} byte placeholder")
                continue
            print(f"ERROR: {p} ({size} bytes) will not decode and is too big to be a placeholder",
                  file=sys.stderr)
            return 2
        total[0] += inked
        total[1] += accented
        print(f"    {p.relative_to(img_dir)}: {inked} inked, {accented} moved to the accent hue")
    print(f"    {len(sprites)} sheets: {total[0]} px to #{INK[0]:02x}{INK[1]:02x}{INK[2]:02x}, "
          f"{total[1]} px rotated onto the Mudaber accent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
