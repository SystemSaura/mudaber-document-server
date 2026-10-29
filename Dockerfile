# Mudaber's Document Server: stock ONLYOFFICE with our chrome baked in.
#
# Why an image instead of `docker cp` onto a running container, which is how
# this used to work: those patches live only in one container's writable layer,
# so every recreation - an image pull, a reboot, a Coolify redeploy - threw
# the branding away, and the only way anyone found out was by looking at the
# editor. Baked at build time the branding is part of the artifact. A recreation
# cannot lose it, and an upgrade stops being something that happens to us: it is
# a deliberate edit to the digest below, rebuilt and re-verified on purpose.
#
# The base is pinned by DIGEST, not by a tag. `:latest` is what moved under us
# before, and even a version tag can be repushed. This digest is DS 9.4.0-129,
# the exact bytes the patches below were derived against; if it changes, the
# patch scripts exit 2 rather than half-apply, which is the behaviour we want.
#
# To upgrade: change the digest, run ./deploy.sh, and read the failures. Every
# patch script asserts its upstream block is still there, so a DS release that
# moved the ground announces itself at build time instead of in production.
FROM onlyoffice/documentserver@sha256:3ab6ebc7c605e5a32b7ae3ff19daed4925090245acc8100ce2230bd766c88212 AS ds

# ── sprite stage ─────────────────────────────────────────────────────────────
# The toolbar glyphs are PNG sprite sheets served as background-image, so no
# stylesheet or theme token can reach their colour; the pixels have to change.
# Done in a throwaway stage so Pillow never ships in the runtime image, and
# regenerated on every build so a DS upgrade re-tints the new sprites for free.
FROM python:3.12-slim AS sprites
RUN pip install --no-cache-dir pillow==11.0.0
WORKDIR /work
COPY --from=ds /var/www/onlyoffice/documentserver/web-apps/apps/spreadsheeteditor/main/resources/img ./spreadsheeteditor
COPY --from=ds /var/www/onlyoffice/documentserver/web-apps/apps/documenteditor/main/resources/img ./documenteditor
COPY --from=ds /var/www/onlyoffice/documentserver/web-apps/apps/presentationeditor/main/resources/img ./presentationeditor
COPY tint-sprites.py .
RUN python3 tint-sprites.py ./spreadsheeteditor ./documenteditor ./presentationeditor

# ── runtime ──────────────────────────────────────────────────────────────────
FROM ds

COPY --from=sprites /work/spreadsheeteditor /var/www/onlyoffice/documentserver/web-apps/apps/spreadsheeteditor/main/resources/img
COPY --from=sprites /work/documenteditor /var/www/onlyoffice/documentserver/web-apps/apps/documenteditor/main/resources/img
COPY --from=sprites /work/presentationeditor /var/www/onlyoffice/documentserver/web-apps/apps/presentationeditor/main/resources/img

# Everything we ship, staged where the build script expects it. Kept in one
# layer so a change to any single artifact rebuilds exactly one layer.
COPY theme-mudaber-pure.json theme-mudaber-carbon.json \
     patch-themes-js.py patch-ui-chrome.py patch-sdk-colors.py patch-sdk-move-insert.py \
     mudaber-chrome.css mudaber-warm-check.html \
     apply-branding.sh /opt/mudaber-branding/

RUN chmod +x /opt/mudaber-branding/apply-branding.sh \
 && /opt/mudaber-branding/apply-branding.sh

# The asset cache tag. Upstream mints a fresh one from the clock at every boot,
# which made every restart look like a brand-new editor to browsers and cost
# clients a ~12.6 MB re-download (77s on a slow link against 2.8s warm). We pin
# it to a hash of our artifacts, computed at build time by apply-branding.sh, so
# it changes when what we serve changes and at no other time. Restarts we do not
# control - reboots, crashes, the proxy - keep serving the same immutable URLs.
LABEL org.opencontainers.image.title="Mudaber Document Server" \
      org.opencontainers.image.description="ONLYOFFICE Docs 9.4.0-129 with Mudaber chrome, themes, grid palette, inked sprites, and insert-on-drop column/row moves" \
      org.opencontainers.image.vendor="Mudaber" \
      cc.mudaber.ds-version="9.4.0-129"
