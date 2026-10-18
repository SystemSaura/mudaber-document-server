#!/usr/bin/env python3
"""Patch OnlyOffice web-apps Themes.js so a CUSTOM uiTheme fully applies at
editor launch (DS 9.4). Upstream's check_launched_custom_theme only fixes the
body classes: it never writes the theme's CSS variables (write_theme_css is
called only from the View-menu picker path), it never re-skins the canvas
(asc_setSkin), and its class swap regex misspells "light" as "ligth" so the
stale theme-type-light class survives. Result: uiTheme:"theme-mudaber-carbon"
launches as default-light with our id class dangling.

Idempotent: exits 0 if the marker is already present. Exits 2 if neither the
marker nor the expected upstream block is found (a DS upgrade changed the
file — re-derive the patch before shipping).
"""
import sys

MARKER = "mudaber-launch-theme-patch"

UPSTREAM = """\
        const check_launched_custom_theme = function () {
            let theme_id = window.uitheme.id;
            if ( themes_map[theme_id] ) {
                if ( themes_map[theme_id].source != 'static') {
                    const m = document.body.className.match('theme-type-' + themes_map[theme_id].type);
                    if ( !m )
                        document.body.classList.add('theme-type-' + themes_map[theme_id].type);
                    else if ( m.length )
                        document.body.className = document.body.className.replace(/theme-type-(?:dark|ligth)/i, 'theme-type-' + themes_map[theme_id].type);
                }
            } else {
"""

PATCHED = """\
        const check_launched_custom_theme = function () {
            // """ + MARKER + """: a custom uiTheme launched via the config must
            // get its CSS written and the canvas re-skinned, exactly like the
            // View-menu picker path (apply_theme) does.
            let theme_id = window.uitheme.id;
            if ( themes_map[theme_id] ) {
                if ( !!themes_map[theme_id].src ) {
                    let t = themes_map[theme_id];
                    write_theme_css(t.src.id, create_colors_css(t.src.id, t.src.colors));
                    normalize_theme_icons(t);
                    delete t.src;

                    try {
                        // Dark app theme means dark cells too, unless the user
                        // explicitly chose otherwise in View > Dark Document.
                        // (Common.localStorage.getItem returns undefined for a
                        // missing key, never null.)
                        if ( themes_map[theme_id].type == 'dark' && !Common.localStorage.getItem('content-theme') )
                            window.uitheme.iscontentdark = true;

                        const _themes = Common.UI.Themes;
                        if ( _themes && _themes.api ) {
                            if ( _themes.api.asc_setContentDarkMode ) {
                                _themes.api.asc_setContentDarkMode(themes_map[theme_id].type == 'dark' && _themes.isContentThemeDark());
                                Common.NotificationCenter.trigger('contenttheme:dark', _themes.isContentThemeDark());
                            }
                            if ( _themes.api.asc_setSkin )
                                _themes.api.asc_setSkin(_themes.getThemeColors());
                        }
                    } catch (e) {}
                }
                if ( themes_map[theme_id].source != 'static') {
                    document.body.className = document.body.className.replace(/theme-type-[\\w-]+\\s?/gi, '').trim();
                    document.body.classList.add('theme-type-' + themes_map[theme_id].type);
                }
            } else {
"""


def main() -> int:
    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if MARKER in text:
        print("already patched")
        return 0
    if UPSTREAM not in text:
        print("ERROR: upstream check_launched_custom_theme block not found — DS build changed, re-derive the patch", file=sys.stderr)
        return 2
    with open(path, "w", encoding="utf-8") as f:
        f.write(text.replace(UPSTREAM, PATCHED, 1))
    print("patched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
