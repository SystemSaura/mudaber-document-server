#!/usr/bin/env python3
"""Strip the OnlyOffice chrome Mudaber replaces with its own (DS 9.4).

Unconditional by design: this document server exists only for the Mudaber
app, whose OfficeEditor renders its own top bar (file name, saved state,
share). Patched here, not via editorConfig, because branding options are
license-gated at runtime while the files are ours:

  --header    web-apps/apps/common/main/lib/view/Header.js
              hides the co-editing users box and the current-user avatars
  --rightmenu web-apps/apps/{spreadsheet,presentation}editor/.../RightMenu.js
              removes the right settings strip (cell/shape/image/... icons);
              hideRightMenu in the config only collapses it, the 40px strip
              always renders otherwise
  --rightmenu-de
              the same for web-apps/apps/documenteditor/.../RightMenu.js,
              which opens its render() differently (no local `el`, and the
              render:before trigger comes first) and so needs its own anchor
  --cachescripts
              web-apps/apps/api/documents/cache-scripts.html
              drops the Visio preloads. The app loads this page in a hidden
              frame at startup to pull the editors down before anyone opens a
              document; Visio is the one editor Drive cannot open, and its two
              bundles are ~7 MB - minutes of someone's link, spent on nothing
  --appcss    web-apps/apps/*/main/resources/css/app.css
              belt-and-braces for the strip: a stored "panel open" state
              (sse/de/pe-hide-right-settings=false) makes the controller
              re-show the el after render's hide(), so the view-level hide is
              not durable - display:none !important beats any jQuery .show(),
              and the box layout still skips it (:visible is computed)

The ONLYOFFICE logo is deliberately NOT touched. The Community licence terms
require the original branding and copyright notices to be retained, and the
ONLYOFFICE trademark policy permits modifying the code and restyling the UI
but not removing the logo. An earlier revision of this script hid
#header-logo; that replacement was removed for licence compliance and must
not be reintroduced. Hiding the co-editing users box and the current-user
avatars is UI we replace with our own, not branding, so it stays.

Idempotent per file (marker checks). Exits 2 if an expected upstream block
is missing - a DS upgrade changed the file, re-derive before shipping.
"""
import sys

PATCHES = {
    "--header": [
        # No #header-logo entry: the ONLYOFFICE logo must stay (see module
        # docstring - Community licence / trademark policy).
        (
            "'<section id=\"tlb-box-users\" class=\"box-cousers dropdown\">' +",
            "'<section id=\"tlb-box-users\" class=\"box-cousers dropdown\" style=\"display:none\">' +",
        ),
        # The current-user avatar (shown by removeClass('hidden'), which an
        # inline style survives). Each appears twice: edit + view layouts.
        (
            "'<button type=\"button\" class=\"btn btn-header slot-btn-user-name hidden\">'",
            "'<button type=\"button\" class=\"btn btn-header slot-btn-user-name hidden\" style=\"display:none\">'",
        ),
        (
            "'<button type=\"button\" class=\"btn btn-header slot-btn-user-name hidden\">'",
            "'<button type=\"button\" class=\"btn btn-header slot-btn-user-name hidden\" style=\"display:none\">'",
        ),
        (
            "'<div class=\"btn-current-user hidden\">'",
            "'<div class=\"btn-current-user hidden\" style=\"display:none\">'",
        ),
        (
            "'<div class=\"btn-current-user hidden\">'",
            "'<div class=\"btn-current-user hidden\" style=\"display:none\">'",
        ),
    ],
    "--rightmenu": [
        (
            "        render: function (mode) {\n"
            "            var el = $(this.el);\n"
            "\n"
            "            this.trigger('render:before', this);\n",
            "        render: function (mode) {\n"
            "            var el = $(this.el);\n"
            "\n"
            "            // mudaber-ui-chrome-patch: Mudaber draws its own chrome; the\n"
            "            // settings strip never shows. Hiding is enough - the viewport\n"
            "            // box layout skips panels that are :hidden, so the sheet takes\n"
            "            // the full width. (Do NOT trigger layout:changed here: render\n"
            "            // runs before the viewport layout exists and the app dies.)\n"
            "            el.hide();\n"
            "\n"
            "            this.trigger('render:before', this);\n",
        ),
    ],
    # The document editor's render() has no local `el` and triggers
    # render:before on its first line, so the spreadsheet anchor above does not
    # exist there. Same hide, same reasons, through the Backbone view's own
    # element.
    "--rightmenu-de": [
        (
            "        render: function (mode) {\n"
            "            this.trigger('render:before', this);\n",
            "        render: function (mode) {\n"
            "            // mudaber-ui-chrome-patch: Mudaber draws its own chrome; the\n"
            "            // settings strip never shows. Hiding is enough - the viewport\n"
            "            // box layout skips panels that are :hidden, so the page takes\n"
            "            // the full width. (Do NOT trigger layout:changed here: render\n"
            "            // runs before the viewport layout exists and the app dies.)\n"
            "            this.$el.hide();\n"
            "\n"
            "            this.trigger('render:before', this);\n",
        ),
    ],
}

APPCSS_RULE = "\n/* mudaber-ui-chrome-patch */\n#right-menu{display:none !important;}\n"

CACHE_SCRIPTS_MARKER = "<!-- mudaber-ui-chrome-patch: visio preloads removed -->"

MARKERS = {
    "--header": 'id="tlb-box-users" class="box-cousers dropdown" style="display:none"',
    "--rightmenu": "mudaber-ui-chrome-patch",
    "--rightmenu-de": "mudaber-ui-chrome-patch",
    "--appcss": "mudaber-ui-chrome-patch",
    "--cachescripts": "mudaber-ui-chrome-patch",
}


def main() -> int:
    mode, path = sys.argv[1], sys.argv[2]
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if MARKERS[mode] in text:
        print(f"already patched ({mode})")
        return 0
    if mode == "--appcss":
        with open(path, "a", encoding="utf-8") as f:
            f.write(APPCSS_RULE)
        print(f"patched ({mode})")
        return 0
    if mode == "--cachescripts":
        # Line-wise rather than an exact-block match: upstream reorders this
        # list between releases, and "every line that preloads Visio" survives
        # that where a literal four-line match would not.
        kept = [line for line in text.splitlines(keepends=True) if "visio" not in line.lower()]
        dropped = len(text.splitlines()) - len(kept)
        if dropped < 2:
            print(
                f"ERROR: expected Visio preloads in {path}, found {dropped} - re-derive the patch",
                file=sys.stderr,
            )
            return 2
        with open(path, "w", encoding="utf-8") as f:
            f.write("".join(kept) + CACHE_SCRIPTS_MARKER + "\n")
        print(f"patched ({mode}: {dropped} Visio preloads dropped)")
        return 0
    for old, new in PATCHES[mode]:
        if old not in text:
            print(f"ERROR: upstream block not found for {mode} - DS build changed, re-derive the patch", file=sys.stderr)
            return 2
        text = text.replace(old, new, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"patched ({mode})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
