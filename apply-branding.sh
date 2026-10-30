#!/usr/bin/env bash
#
# Applies the Mudaber look to a pristine ONLYOFFICE Document Server. Runs once,
# at image build time, from the Dockerfile.
#
# The old runtime version of this had to keep .orig copies of every file it
# touched, so that re-running it patched pristine source instead of stacking a
# second patch on top of the first. At build time that whole problem is gone:
# the base image IS the pristine copy, every build starts from the same digest,
# and the result is immutable. That is the main reason this moved.
#
# Every patch script exits 2 if the upstream block it expects is missing, and
# `set -e` turns that into a failed build. A DS upgrade therefore breaks the
# build, loudly, on the machine doing the building - never silently in prod.
set -euo pipefail

STAGE=/opt/mudaber-branding
DS=/var/www/onlyoffice/documentserver
WEBAPPS="$DS/web-apps"
THEMES_DIR="$WEBAPPS/apps/common/main/resources/themes"
SDK_CELL="$DS/sdkjs/cell/sdk-all.js"
FLUSH=/usr/bin/documentserver-flush-cache.sh

echo "==> Installing Mudaber interface themes"
install -m 0644 "$STAGE/theme-mudaber-pure.json"   "$THEMES_DIR/theme-mudaber-pure.json"
install -m 0644 "$STAGE/theme-mudaber-carbon.json" "$THEMES_DIR/theme-mudaber-carbon.json"

# themes.json is the aggregate the editor actually reads. Built here rather than
# shipped, so it can never drift from the two theme files beside it.
python3 - "$THEMES_DIR" <<'PY'
import json, sys
d = sys.argv[1]
themes = [json.load(open(f"{d}/theme-mudaber-{n}.json", encoding="utf-8")) for n in ("pure", "carbon")]
with open(f"{d}/themes.json", "w", encoding="utf-8") as f:
    json.dump({"themes": themes}, f, indent=4)
PY

# nginx serves a precompressed twin in preference to the plain file, so a .gz
# left stale silently undoes the patch beside it. -n keeps the output
# byte-identical between builds (no mtime in the header), which keeps image
# layers cacheable and makes "did anything actually change" answerable.
gzip -9 -n -c "$THEMES_DIR/themes.json" > "$THEMES_DIR/themes.json.gz"

echo "==> Patching the editor"
# path|patcher|mode ("-" for patchers that take no mode)
# Themes.js and Header.js live in common/ and so cover all three editors at
# once; the right settings strip and the stylesheet are per editor.
PATCHES="
$WEBAPPS/apps/common/main/lib/controller/Themes.js|patch-themes-js.py|-
$WEBAPPS/apps/common/main/lib/view/Header.js|patch-ui-chrome.py|--header
$WEBAPPS/apps/spreadsheeteditor/main/app/view/RightMenu.js|patch-ui-chrome.py|--rightmenu
$WEBAPPS/apps/presentationeditor/main/app/view/RightMenu.js|patch-ui-chrome.py|--rightmenu
$WEBAPPS/apps/documenteditor/main/app/view/RightMenu.js|patch-ui-chrome.py|--rightmenu-de
$WEBAPPS/apps/spreadsheeteditor/main/resources/css/app.css|patch-ui-chrome.py|--appcss
$WEBAPPS/apps/presentationeditor/main/resources/css/app.css|patch-ui-chrome.py|--appcss
$WEBAPPS/apps/documenteditor/main/resources/css/app.css|patch-ui-chrome.py|--appcss
$WEBAPPS/apps/api/documents/cache-scripts.html|patch-ui-chrome.py|--cachescripts
$SDK_CELL|patch-sdk-colors.py|-
$SDK_CELL|patch-sdk-move-insert.py|-
$SDK_CELL|patch-sdk-padding.py|-
"

echo "$PATCHES" | while IFS='|' read -r path patcher mode; do
    [ -n "$path" ] || continue
    [ -f "$path" ] || { echo "!! missing upstream file: $path" >&2; exit 2; }
    if [ "$mode" = "-" ]; then
        python3 "$STAGE/$patcher" "$path"
    else
        python3 "$STAGE/$patcher" "$mode" "$path"
    fi
    # Regenerate the precompressed twin only where upstream ships one.
    [ -f "$path.gz" ] && gzip -9 -n -c "$path" > "$path.gz"
done

# The Mudaber palette and type over the ribbon. Appended rather than patched
# into a rule, because app.css is 630 KB of upstream and a later override is
# both simpler to reason about and survives upstream reshuffling its selectors.
# The same sheet goes onto all three editors: it is written against the shell
# they share (#toolbar, the tab strip, buttons, inputs, menus), and the few
# spreadsheet-only selectors in it simply match nothing in the other two.
echo "==> Applying the Mudaber chrome stylesheet"
for app in spreadsheeteditor documenteditor presentationeditor; do
    APPCSS="$WEBAPPS/apps/$app/main/resources/css/app.css"
    [ -f "$APPCSS" ] || { echo "!! missing upstream file: $APPCSS" >&2; exit 2; }
    if grep -q "mudaber-chrome-css" "$APPCSS"; then
        echo "    $app: already applied"
    else
        cat "$STAGE/mudaber-chrome.css" >> "$APPCSS"
        [ -f "$APPCSS.gz" ] && gzip -9 -n -c "$APPCSS" > "$APPCSS.gz"
        echo "    $app: appended $(wc -c < "$STAGE/mudaber-chrome.css") bytes"
    fi
done

echo "==> Installing the sheet's everyday toolbar and Dabbour bridge"
# mudaber-sheet.js picks the toolbar mode before the editor lays itself out,
# so it must load ahead of the app: the editor's own index.html includes it,
# with its stylesheet after app.css. Spreadsheets only.
SSE="$WEBAPPS/apps/spreadsheeteditor/main"
install -d -m 0755 "$SSE/resources/mudaber"
install -m 0644 "$STAGE/mudaber-sheet.js"  "$SSE/resources/mudaber/sheet.js"
install -m 0644 "$STAGE/mudaber-sheet.css" "$SSE/resources/mudaber/sheet.css"
python3 - "$SSE/index.html" <<'PY'
import sys, re
path = sys.argv[1]
src = open(path, encoding="utf-8").read()
if "mudaber-sheet" in src:
    print("    index.html already includes it")
    sys.exit(0)
assert src.count("</head>") == 1, "upstream spreadsheet index.html changed - re-check where the sheet script goes"
first = re.search(r"<script\b", src)
assert first, "upstream spreadsheet index.html has no script - re-check"
tag = '<!-- mudaber-sheet --><script src="resources/mudaber/sheet.js"></script>\n'
src = src[:first.start()] + tag + src[first.start():]
src = src.replace("</head>", '<link rel="stylesheet" type="text/css" href="resources/mudaber/sheet.css"></head>', 1)
open(path, "w", encoding="utf-8").write(src)
print("    index.html includes the sheet script and stylesheet")
PY
[ -f "$SSE/index.html.gz" ] && gzip -9 -n -c "$SSE/index.html" > "$SSE/index.html.gz"

echo "==> Installing Inter"
# The font the Mudaber look sets on a sheet. The server regenerates its font
# list at every boot, which is when Inter joins it.
install -d -m 0755 /usr/share/fonts/truetype/inter
install -m 0644 "$STAGE"/Inter-*.ttf /usr/share/fonts/truetype/inter/
install -m 0644 "$STAGE/Inter-LICENSE.txt" /usr/share/fonts/truetype/inter/LICENSE.txt

echo "==> Installing the editor cache check"
# The app frames this page to ask whether the editor is still in this machine's
# cache, and re-downloads it in the background when it is not (see the page).
# It sits beside cache-scripts.html so the server's /web-apps/ redirect hands it
# the versioned path the editor is cached under.
install -m 0644 "$STAGE/mudaber-warm-check.html" "$WEBAPPS/apps/api/documents/mudaber-warm-check.html"

echo "==> Pinning the asset cache tag"
# Three things mint a tag - boot, the font regeneration that also runs at every
# boot, and the plugin manager - and all three funnel through this one script,
# so the pin goes here rather than at any call site. An explicit --hash still
# wins; the pin file is only the default.
python3 - "$FLUSH" <<'PY'
import sys
path = sys.argv[1]
src = open(path).read()
old = 'HASH=${HASH:-$(date'
new = 'HASH=${HASH:-$(cat /etc/onlyoffice-cache-tag 2>/dev/null)}\n' + old
if 'onlyoffice-cache-tag' in src:
    print("    flush-cache already pinned")
else:
    assert src.count(old) == 1, "upstream flush-cache changed - re-check the hash default"
    open(path, "w").write(src.replace(old, new))
    print("    flush-cache pinned")
PY
chmod +x "$FLUSH"

# Derived from what we ship, so the tag moves when the look moves and stays put
# across every restart that changes nothing.
# Hash EVERY staged artifact, not a hand-listed subset. tint-sprites.py was
# missing from the old list because it is not named patch-*, which meant a
# sprite-only change recoloured the icons on the server and then served them
# under the unchanged tag - immutable for a year, so no client would ever have
# seen it. Whatever we add next is covered automatically.
TAG="$(cat $(find "$STAGE" -maxdepth 1 -type f | sort) | md5sum | awk '{print $1}')"
printf '%s' "$TAG" > /etc/onlyoffice-cache-tag
echo "    cache tag $TAG"

echo "==> Branding baked in"
