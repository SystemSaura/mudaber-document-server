# Mudaber Document Server

This is the source of the modified ONLYOFFICE Docs that powers spreadsheet, document and presentation editing in [Mudaber](https://mudaber.cc) Drive (served from `office.mudaber.cc`).

It is **ONLYOFFICE Docs Community Edition 9.4.0-129** (upstream: <https://github.com/ONLYOFFICE/DocumentServer>), licensed under the GNU Affero General Public License v3. Our modifications are published here under the same licence, as AGPL section 13 requires for software offered over a network.

## What we changed

The base image is pinned by digest in the `Dockerfile`:
`onlyoffice/documentserver@sha256:3ab6ebc7c605e5a32b7ae3ff19daed4925090245acc8100ce2230bd766c88212`. Upstream source for that exact release is at the ONLYOFFICE repositories, tag `v9.4.0.129`: `DocumentServer`, `sdkjs` and `web-apps`.

At image build time, `apply-branding.sh` applies the following to the stock files. Each patch script checks that its upstream code is still there and fails the build if it isn't, so nothing is half-applied.

| File | Change |
|---|---|
| `theme-mudaber-pure.json`, `theme-mudaber-carbon.json` | Two interface themes (light and dark). |
| `patch-themes-js.py` | Makes custom themes apply when the editor launches. In stock 9.4 they only apply when picked from the View menu. |
| `patch-ui-chrome.py` | Hides the header avatars and the right settings strip. Trims the editor preload list. |
| `mudaber-chrome.css` | Colour and type overrides appended to each editor's `app.css`. |
| `tint-sprites.py` | Recolours the toolbar icon sprites to the Mudaber accent. |
| `patch-sdk-colors.py` | Grid line, selection and fill-handle colours in the spreadsheet canvas (`sdkjs/cell/sdk-all.js`). |
| `patch-sdk-move-insert.py` | Dragging a whole column or row inserts it where you drop it, and the others shift aside, instead of overwriting. Stock ONLYOFFICE has this behaviour only while Shift is held. |
| `mudaber-sheet.js`, `mudaber-sheet.css` | The spreadsheet editor's everyday mode, loaded from `spreadsheeteditor/main/index.html`: one row of common tools (undo, redo, bold, italic, strikethrough, colours, alignment, sort, filter) with a More button that brings back the full stock ribbon, and the tab strip, left rail, name box and fx button hidden until then. It also gives each sheet the Mudaber look (Inter, roomier rows, a light header row) the first time the sheet is opened for editing, as one undo step, marked with a hidden sheet-level name so it happens once. Also a message bridge that only the editor's parent page may use, to read the open sheet and to apply cell changes a person approved in the Mudaber app; the changes go through the same command path the editor's plugins use. |
| `patch-sdk-padding.py` | Two more pixels between a cell's text and its grid lines, in drawing only; the padding used to convert column widths stays stock, so no saved width changes. |
| `fonts/` | Inter (SIL Open Font License 1.1, licence included), installed as a system font. |
| `mudaber-warm-check.html` | A small added page, beside `cache-scripts.html`, that reports which of the editor's main files the browser's cache still holds, so the Mudaber app can re-download the editor in the background when the cache has been dropped. It only reads the cache. |

The ONLYOFFICE logo and the legal notices are kept as they are; in the spreadsheet's everyday mode the logo sits at the end of the toolbar and opens About.

## Build

```sh
docker build -t mudaber-document-server .
```

## Licence

GNU AGPL v3, see `LICENSE`. ONLYOFFICE is a trademark of Ascensio System SIA, and this project is not affiliated with or endorsed by it. No trademark rights are granted. Non-code elements of the upstream product, such as illustrations, icon sets and technical writing, are licensed by Ascensio System SIA under CC BY-SA 4.0.
