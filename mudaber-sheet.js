/* mudaber-sheet-js: Mudaber's spreadsheet editor, in the editor's own frame.
 *
 * Loaded by the patched spreadsheeteditor/main/index.html ahead of the app, so
 * the first thing it does (pick the toolbar mode) lands before the layout is
 * measured. Two jobs:
 *
 * 1. Everyday tools. The ribbon's ten tabs and ~150 buttons are what most
 *    people never touch, so by default ("simple") the sheet shows one row:
 *    undo, redo, bold, italic, strikethrough, colours, alignment, sort and
 *    filter, plus More, Find and the ONLYOFFICE mark. More brings the whole
 *    ribbon back, untouched; "Fewer tools" returns. The choice is remembered
 *    on this device. The look of both modes lives in mudaber-sheet.css.
 *
 * 2. The Mudaber look, on its own. The first time a sheet opens here in edit
 *    mode (and any tab added later, the moment it is shown), it gets Inter 10,
 *    roomy rows with text centred, a light header row, and a quiet numbering
 *    column, applied through the same command path as everything below, so
 *    it is one undo step and saves like anything typed. A hidden sheet-level
 *    name (MudaberLook) marks a sheet as done, so it happens once per sheet,
 *    on every device, and never fights choices made after it. The app is told
 *    (mudaber-sheet-look) so it can offer Undo.
 *
 * 3. A bridge for Dabbour. Mudaber's own page (this frame's parent, and only
 *    it) can ask for a snapshot of the open sheet and apply the cell changes a
 *    person approved on a Dabbour card. Writes go through the same path the
 *    editor's plugins use (_beforeEvalCommand / builder API / History), so
 *    they co-edit, save and undo like anything typed by hand.
 */
(function () {
    'use strict';
    var KEY = 'mudaber.sheet.tools';
    var root = document.documentElement;
    var mode = 'simple';
    try { if (window.localStorage.getItem(KEY) === 'full') mode = 'full'; } catch (e) { /* private mode */ }
    root.classList.add(mode === 'full' ? 'mdb-full' : 'mdb-simple');

    var ICON = {
        more: '<svg viewBox="0 0 256 256" aria-hidden="true"><path fill="currentColor" d="M144 128a16 16 0 1 1-16-16 16 16 0 0 1 16 16Zm-84-16a16 16 0 1 0 16 16 16 16 0 0 0-16-16Zm136 0a16 16 0 1 0 16 16 16 16 0 0 0-16-16Z"/></svg>',
        find: '<svg viewBox="0 0 256 256" aria-hidden="true"><path fill="currentColor" d="M229.66 218.34 179.6 168.28a88.21 88.21 0 1 0-11.32 11.31l50.06 50.07a8 8 0 0 0 11.32-11.32ZM40 112a72 72 0 1 1 72 72 72.08 72.08 0 0 1-72-72Z"/></svg>',
        less: '<svg viewBox="0 0 256 256" aria-hidden="true"><path fill="currentColor" d="M213.66 165.66a8 8 0 0 1-11.32 0L128 91.31l-74.34 74.35a8 8 0 0 1-11.32-11.32l80-80a8 8 0 0 1 11.32 0l80 80a8 8 0 0 1 0 11.32Z"/></svg>'
    };

    function app() { return window.SSE && typeof window.SSE.getController === 'function' ? window.SSE : null; }
    /* The viewport stacks its rows by fixed heights it keeps in script (tab
       strip + controls), not by what CSS draws, so hiding the tab strip alone
       would leave an empty band. The toolbar row's height becomes a getter:
       our one-row height in simple mode, whatever the editor last set in full
       mode (it still sets it on theme and compact changes; we keep the value). */
    var SIMPLE_H = 50;
    function hookHeight() {
        try {
            var vl = app().getController('Viewport').viewport.vlayout;
            var item = vl.getItem('toolbar');
            if (!item || item.__mdb) return !!item;
            var stock = item.height;
            Object.defineProperty(item, 'height', {
                configurable: true,
                get: function () { return mode === 'simple' ? SIMPLE_H : stock; },
                set: function (v) { stock = v; }
            });
            item.__mdb = true;
            return true;
        } catch (e) { return false; }
    }
    function relayout() {
        try { app().getController('Viewport').viewport.vlayout.doLayout(); } catch (e) { /* app not up yet */ }
        try { window.Common.NotificationCenter.trigger('layout:changed', 'toolbar'); } catch (e) { /* same */ }
        try { window.Common.NotificationCenter.trigger('layout:changed', 'leftmenu'); } catch (e) { /* same */ }
        // The grid is a canvas sized when drawn: tell it the box moved.
        try { var api = window.g_asc_plugins && window.g_asc_plugins.api; if (api && api.asc_Resize) api.asc_Resize(); } catch (e) { /* same */ }
    }
    function toHome() {
        try {
            var tb = app().getController('Toolbar').toolbar;
            if (tb && typeof tb.setTab === 'function') tb.setTab('home');
        } catch (e) { /* the simple row still shows the home slots */ }
    }
    function setMode(next) {
        mode = next;
        root.classList.toggle('mdb-simple', next === 'simple');
        root.classList.toggle('mdb-full', next === 'full');
        try { window.localStorage.setItem(KEY, next); } catch (e) { /* not remembered */ }
        if (next === 'simple') toHome();
        relayout();
        // The canvas measures itself on resize; one more pass after the
        // layout has settled keeps the grid from drawing under the toolbar.
        setTimeout(relayout, 60);
        tellParent({ type: 'mudaber-sheet-mode', mode: next });
    }
    function find() {
        try { app().getController('LeftMenu').onShortcut('search'); return; } catch (e) { /* fall through */ }
        try { window.Common.NotificationCenter.trigger('search:show'); } catch (e) { /* nothing to open */ }
    }
    function about() {
        if (mode !== 'full') setMode('full');
        setTimeout(function () {
            var b = document.getElementById('left-btn-about');
            if (b) b.click();
        }, 120);
    }

    function button(cls, html, title, onClick) {
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'mdb-btn ' + cls;
        b.innerHTML = html;
        if (title) b.setAttribute('data-mdb-tip', title);
        b.setAttribute('aria-label', title || b.textContent);
        b.addEventListener('click', function (e) { e.preventDefault(); onClick(); });
        // The editor takes focus on mousedown everywhere; keep the grid's.
        b.addEventListener('mousedown', function (e) { e.preventDefault(); });
        return b;
    }

    function mount() {
        var controls = document.querySelector('#toolbar .box-controls');
        var tabsRight = document.querySelector('#toolbar .box-tabs .extra.right');
        if (!controls || !tabsRight || !app() || !hookHeight()) return false;
        if (controls.querySelector('.mdb-tail')) return true;

        var more = button('mdb-more', ICON.more + '<span>More</span>', 'Every other tool', function () { setMode('full'); });
        var tail = document.createElement('div');
        tail.className = 'mdb-tail';
        var find1 = button('mdb-find', ICON.find, 'Find (⌘F)', find);
        var mark = button('mdb-oo', '<i></i>', 'ONLYOFFICE Docs, the editor inside Mudaber', about);
        tail.appendChild(find1);
        tail.appendChild(mark);
        var moreBox = document.createElement('div');
        moreBox.className = 'mdb-morebox';
        moreBox.appendChild(more);
        controls.appendChild(moreBox);
        controls.appendChild(tail);

        var less = button('mdb-less', ICON.less + '<span>Fewer tools</span>', 'Back to the everyday tools', function () { setMode('simple'); });
        tabsRight.appendChild(less);

        if (mode === 'simple') toHome();
        relayout();
        return true;
    }
    (function wait(n) {
        if (mount() || n > 600) return;
        setTimeout(function () { wait(n + 1); }, 100);
    })(0);

    // ── the bridge ──────────────────────────────────────────────────────────
    var parentOrigin = '*';
    function tellParent(msg) {
        try { window.parent.postMessage(msg, parentOrigin); } catch (e) { /* no parent */ }
    }
    function sdk() {
        var api = window.g_asc_plugins && window.g_asc_plugins.api;
        if (!api || typeof api.getJsApi !== 'function') throw new Error('The sheet is still opening.');
        return { api: api, Api: api.getJsApi() };
    }
    function text(v) { return v === null || v === undefined ? '' : String(v); }

    var MAX_ROWS = 400, MAX_COLS = 30;
    /* "B2:F52" (or "C7") to zero-based corners */
    function parseA1(a) {
        var col = function (s) { var n = 0; for (var i = 0; i < s.length; i++) n = n * 26 + s.charCodeAt(i) - 64; return n - 1; };
        var parts = text(a).replace(/\$/g, '').split(':');
        var p = function (s) { var m = /^([A-Z]+)(\d+)$/i.exec(s); return m ? { c: col(m[1].toUpperCase()), r: +m[2] - 1 } : { c: 0, r: 0 }; };
        var a1 = p(parts[0]), a2 = p(parts[1] || parts[0]);
        return { r1: a1.r, c1: a1.c, r2: a2.r, c2: a2.c };
    }
    function snapshot(opts) {
        var s = sdk(), Api = s.Api;
        var ws = Api.GetActiveSheet();
        var used = ws.GetUsedRange();
        var rows = [], truncated = false;
        var span = parseA1(used.GetAddress(false, false, 'xlA1', false));
        var r1 = span.r1, c1 = span.c1, nr = span.r2 - span.r1 + 1, nc = span.c2 - span.c1 + 1;
        var maxR = Math.min(nr, (opts && opts.maxRows) || MAX_ROWS), maxC = Math.min(nc, MAX_COLS);
        if (nr > maxR || nc > maxC) truncated = true;
        for (var r = 0; r < maxR; r++) {
            var row = [];
            for (var c = 0; c < maxC; c++) row.push(text(ws.GetRangeByNumber(r1 + r, c1 + c).GetText()));
            rows.push(row);
        }
        // Trailing empty rows say nothing and cost tokens.
        while (rows.length && rows[rows.length - 1].every(function (x) { return x === ''; })) rows.pop();
        var sel = '';
        try { sel = Api.GetSelection().GetAddress(false, false, 'xlA1', false); } catch (e) { /* no selection */ }
        var font = '';
        try {
            // A data cell, not the header: the header is often styled on its own.
            var f = ws.GetRangeByNumber(Math.min(r1 + 1, r1 + Math.max(0, nr - 1)), c1).GetCharacters(1, 1).GetFont();
            font = text(f.GetName()) + ' ' + text(f.GetSize());
        } catch (e) { /* an empty cell has no characters: unknown */ }
        return {
            sheet: ws.GetName(),
            sheets: Api.GetSheets().map(function (x) { return x.GetName(); }),
            origin: { row: r1 + 1, col: c1 + 1 },
            used: used.GetAddress(false, false, 'xlA1', false),
            selection: sel,
            font: font.trim(),
            rows: rows,
            totalRows: nr,
            totalCols: nc,
            truncated: truncated
        };
    }
    function rgb(hex) {
        var m = /^#?([0-9a-f]{6})$/i.exec(text(hex));
        if (!m) throw new Error('Not a colour: ' + hex);
        var n = parseInt(m[1], 16);
        return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
    }
    function apply(changes, sheetName, done) {
        var s = sdk(), api = s.api, Api = s.Api;
        if (!Array.isArray(changes) || !changes.length) throw new Error('Nothing to change.');
        if (api.isLongAction && api.isLongAction()) throw new Error('The sheet is busy. Try again in a moment.');
        if (api.canRunBuilderScript && !api.canRunBuilderScript()) throw new Error('This sheet cannot be edited right now (read-only, or a dialog is open).');
        var ws = sheetName ? Api.GetSheet(sheetName) : Api.GetActiveSheet();
        if (!ws) throw new Error('There is no sheet called ' + sheetName + '.');
        var applied = 0, error = null;
        api._beforeEvalCommand();
        try {
            for (var i = 0; i < changes.length; i++) {
                var ch = changes[i] || {};
                var rg = ws.GetRange(text(ch.range || ch.cell));
                if (!rg) throw new Error('Not a cell or range: ' + (ch.range || ch.cell));
                if (Object.prototype.hasOwnProperty.call(ch, 'value')) {
                    // A column that keeps dates or codes as typed text (2026-07-01)
                    // gets text, not a date the locale then reformats.
                    if (ch.asText) rg.SetNumberFormat('@');
                    rg.SetValue(text(ch.value));
                }
                if (ch.fill) { var f = rgb(ch.fill); rg.SetFillColor(Api.CreateColorFromRGB(f[0], f[1], f[2])); }
                if (ch.fill === null) rg.SetFillColor('No Fill');
                if (ch.color) { var k = rgb(ch.color); rg.SetFontColor(Api.CreateColorFromRGB(k[0], k[1], k[2])); }
                if (ch.font) rg.SetFontName(text(ch.font));
                if (typeof ch.size === 'number' && ch.size >= 6 && ch.size <= 72) rg.SetFontSize(ch.size);
                if (typeof ch.rowHeight === 'number' && ch.rowHeight >= 8 && ch.rowHeight <= 200) rg.SetRowHeight(ch.rowHeight);
                if (ch.valign === 'top' || ch.valign === 'center' || ch.valign === 'bottom') rg.SetAlignVertical(ch.valign);
                if (typeof ch.bold === 'boolean') rg.SetBold(ch.bold);
                if (typeof ch.italic === 'boolean') rg.SetItalic(ch.italic);
                if (typeof ch.strike === 'boolean') rg.SetStrikeout(ch.strike);
                applied++;
            }
        } catch (e) {
            error = e && e.message ? e.message : String(e);
        }
        var finish = function () {
            api.evalCommand = false;
            var end = function () { done(error ? { applied: applied, error: error } : { applied: applied }); };
            if (typeof api.onEndBuilderScript === 'function') api.onEndBuilderScript(end); else end();
        };
        var H = window.AscCommon && window.AscCommon.History;
        if (H && typeof H.Is_LastPointEmpty === 'function' && !H.Is_LastPointEmpty()) api._afterEvalCommand(finish);
        else finish();
    }
    // ── the Mudaber look ────────────────────────────────────────────────────
    var LOOK = 'MudaberLook';
    var INK = [42, 49, 80], HEAD = [242, 245, 252], MUTED = [165, 170, 192];
    function colLetter(i) { var s = ''; i += 1; while (i > 0) { var m = (i - 1) % 26; s = String.fromCharCode(65 + m) + s; i = Math.floor((i - m - 1) / 26); } return s; }
    function marked(ws) {
        try { return ws.GetDefNames().some(function (n) { return n.GetName() === LOOK; }); } catch (e) { return true; }
    }
    function editable() {
        try {
            var main = app() && app().getController('Main');
            if (main && main.appOptions && !main.appOptions.isEdit) return false;
            var api = sdk().api;
            return !(api.isLongAction && api.isLongAction()) && !(api.canRunBuilderScript && !api.canRunBuilderScript());
        } catch (e) { return false; }
    }
    /* Row 1 reads as a header when it holds two or more words and no numbers,
       and there is data under it. */
    function headerRow(ws, span) {
        if (span.r2 <= span.r1) return false;
        var words = 0;
        for (var c = span.c1; c <= span.c2; c++) {
            var v = text(ws.GetRangeByNumber(span.r1, c).GetText()).trim();
            if (!v) continue;
            if (/^-?[\d.,%$]+$/.test(v)) return false;
            words++;
        }
        return words >= 2;
    }
    function lookSheet(ws, Api) {
        var span = parseA1(ws.GetUsedRange().GetAddress(false, false, 'xlA1', false));
        var lastCol = Math.max(span.c2 + 4, 25), lastRow = Math.max(span.r2 + 200, 200);
        // Whole columns, so cells typed later inherit the look too.
        var all = ws.GetRange('A:' + colLetter(lastCol));
        all.SetFontName('Inter');
        all.SetFontSize(10);
        all.SetAlignVertical('center');
        ws.GetRange('1:' + (lastRow + 1)).SetRowHeight(22.5);
        if (headerRow(ws, span)) {
            var h = ws.GetRange(colLetter(span.c1) + (span.r1 + 1) + ':' + colLetter(span.c2) + (span.r1 + 1));
            h.SetBold(true);
            h.SetFontColor(Api.CreateColorFromRGB(INK[0], INK[1], INK[2]));
            h.SetFillColor(Api.CreateColorFromRGB(HEAD[0], HEAD[1], HEAD[2]));
            h.SetRowHeight(25.5);
            // A numbering column ("#") recedes.
            if (text(ws.GetRangeByNumber(span.r1, span.c1).GetText()).trim() === '#' && span.r2 > span.r1) {
                ws.GetRange(colLetter(span.c1) + (span.r1 + 2) + ':' + colLetter(span.c1) + (span.r2 + 1)).SetFontColor(Api.CreateColorFromRGB(MUTED[0], MUTED[1], MUTED[2]));
            }
        }
        // Inter is wider than Calibri: a column whose longest text would no
        // longer fit grows to fit it; none ever shrinks (an empty column is
        // wide on purpose). Widths are written in the stored unit (Excel
        // characters, padding included) the file already uses; the builder's
        // own getter and setter disagree on units, so the model is used here.
        try {
            var model = ws.worksheet;
            var defW = window.AscCommonExcel && window.AscCommonExcel.oDefaultMetrics ? window.AscCommonExcel.oDefaultMetrics.ColWidthChars : 8.43;
            var lastR = Math.min(span.r2, span.r1 + 500);
            for (var c = span.c1; c <= span.c2; c++) {
                var longest = 0;
                for (var r = span.r1; r <= lastR; r++) {
                    var len = text(ws.GetRangeByNumber(r, c).GetText()).length;
                    if (len > longest) longest = len;
                }
                if (!longest) continue;
                var need = Math.min(longest * 1.3 + 1.4, 80);
                var have = model.getColWidth(c);
                if (!(have > 0)) have = defW;
                if (need > have) model.setColWidth(need, c, c);
            }
        } catch (e) { /* widths stay as they were */ }
        ws.AddDefName(LOOK, "'" + ws.GetName().replace(/'/g, "''") + "'!$A$1", true);
        return span;
    }
    /* Runs one builder command the way plugins do (one undo step). */
    function command(fn, done) {
        var s = sdk(), api = s.api;
        var error = null;
        api._beforeEvalCommand();
        try { fn(s.Api); } catch (e) { error = e && e.message ? e.message : String(e); }
        var finish = function () {
            api.evalCommand = false;
            var end = function () { done && done(error); };
            if (typeof api.onEndBuilderScript === 'function') api.onEndBuilderScript(end); else end();
        };
        var H = window.AscCommon && window.AscCommon.History;
        if (H && typeof H.Is_LastPointEmpty === 'function' && !H.Is_LastPointEmpty()) api._afterEvalCommand(finish);
        else finish();
    }
    var lastLook = null, docReady = false;
    function isReady() {
        if (docReady) return true;
        try { return !!app().getController('Main')._isDocReady; } catch (e) { return false; }
    }
    function autoLook() {
        // Never before the whole workbook is in: a half-loaded model has no
        // sheets to judge, and a mark set there would be wrong.
        if (!isReady() || !editable()) return;
        var ws;
        try { ws = sdk().Api.GetActiveSheet(); } catch (e) { return; }
        if (!ws || marked(ws)) return;
        var name = ws.GetName();
        command(function (Api) { lookSheet(ws, Api); }, function (error) {
            if (error) return;
            lastLook = { sheet: name, at: Date.now() };
            tellParent({ type: 'mudaber-sheet-look', sheet: name });
        });
    }
    /* "Undo" on the app's notice: put the sheet back, keep it marked so it is not done again. */
    function unlook() {
        var api = sdk().api;
        if (!lastLook || Date.now() - lastLook.at > 60000) throw new Error('Too late to undo here; use the undo button.');
        var name = lastLook.sheet;
        lastLook = null;
        api.asc_Undo();
        command(function (Api) {
            var ws = Api.GetSheet(name);
            if (ws && !marked(ws)) ws.AddDefName(LOOK, "'" + name.replace(/'/g, "''") + "'!$A$1", true);
        });
    }
    var lookTimer = 0;
    function lookSoon() { clearTimeout(lookTimer); lookTimer = setTimeout(function () { try { autoLook(); } catch (e) { /* never break the editor */ } }, 400); }
    (function hook(n) {
        var ok = false;
        try {
            if (window.Common && window.Common.NotificationCenter && app()) {
                window.Common.NotificationCenter.on('document:ready', function () { docReady = true; lookSoon(); });
                var api = sdk().api;
                api.asc_registerCallback('asc_onActiveSheetChanged', lookSoon);
                api.asc_registerCallback('asc_onSheetsChanged', lookSoon);
                ok = true;
            }
        } catch (e) { ok = false; }
        if (!ok && n < 600) setTimeout(function () { hook(n + 1); }, 100);
        else if (ok) lookSoon(); // in case the document was already in before we hooked on
    })(0);

    function show(where) {
        var s = sdk();
        var rg = s.Api.GetActiveSheet().GetRange(text(where));
        if (rg) rg.Select();
    }

    window.addEventListener('message', function (e) {
        if (e.source !== window.parent) return;
        var d = e.data;
        if (!d || typeof d !== 'object' || d.type !== 'mudaber-sheet') return;
        parentOrigin = e.origin && e.origin !== 'null' ? e.origin : '*';
        var reply = function (body) { tellParent(Object.assign({ type: 'mudaber-sheet-reply', id: d.id }, body)); };
        try {
            if (d.op === 'snapshot') reply({ ok: true, result: snapshot(d) });
            else if (d.op === 'apply') apply(d.changes, d.sheet, function (r) { reply({ ok: !r.error, result: r, error: r.error }); });
            else if (d.op === 'show') { show(d.where); reply({ ok: true }); }
            else if (d.op === 'unlook') { unlook(); reply({ ok: true }); }
            else if (d.op === 'mode') { if (d.mode === 'simple' || d.mode === 'full') setMode(d.mode); reply({ ok: true, result: { mode: mode } }); }
            else if (d.op === 'ping') reply({ ok: true, result: { mode: mode, ready: !!(window.g_asc_plugins && window.g_asc_plugins.api) } });
            else reply({ ok: false, error: 'Unknown request.' });
        } catch (err) {
            reply({ ok: false, error: err && err.message ? err.message : String(err) });
        }
    });
})();
