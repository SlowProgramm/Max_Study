/*
 * Общий скрипт входа через MAX. Подключается ПЕРВЫМ на входной странице (index.html)
 * и на всех остальных:
 *   <script src="https://st.max.ru/js/max-web-app.js"></script>
 *   <script src="/static/max-auth.js"></script>
 *
 * MAX кладёт initData в #WebAppData только на входном URL.
 * Копию держим в sessionStorage + localStorage, чтобы навигация не ломала auth.
 */
(function () {
    var KEY = "max_init_data_backup";
    var KEY_LS = "max_init_data_backup_ls";
    var DIAG = "max_entry_diag";

    function ssGet(k) { try { return sessionStorage.getItem(k) || ""; } catch (e) { return ""; } }
    function ssSet(k, v) { try { sessionStorage.setItem(k, v); } catch (e) {} }
    function lsGet(k) { try { return localStorage.getItem(k) || ""; } catch (e) { return ""; } }
    function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

    function nativeInit() {
        try {
            var v = window.WebApp && window.WebApp.initData;
            return typeof v === "string" ? v : "";
        } catch (e) { return ""; }
    }

    function hashParams() {
        try { return new URLSearchParams(location.hash.replace(/^#/, "")); }
        catch (e) { return new URLSearchParams(""); }
    }

    function fromHash() { return hashParams().get("WebAppData") || ""; }

    function startParam() {
        try {
            var q = new URLSearchParams(location.search).get("WebAppStartParam");
            if (q) return q;
            var u = window.WebApp && window.WebApp.initDataUnsafe;
            return (u && u.start_param) || "";
        } catch (e) { return ""; }
    }

    function persist(v) {
        if (!v) return;
        ssSet(KEY, v);
        lsSet(KEY_LS, v);
    }

    var fresh = nativeInit() || fromHash();
    if (fresh) persist(fresh);

    // Подтянуть из localStorage, если sessionStorage пуст (новая вкладка / сброс)
    if (!ssGet(KEY) && lsGet(KEY_LS)) {
        ssSet(KEY, lsGet(KEY_LS));
    }

    if (fresh || !ssGet(DIAG)) {
        var hp = hashParams();
        var inIframe = true;
        try { inIframe = window.self !== window.top; } catch (e) {}
        ssSet(DIAG, JSON.stringify({
            page: location.pathname,
            iframe: inIframe,
            hashKeys: Array.from(hp.keys()),
            hashWebAppDataLen: (hp.get("WebAppData") || "").length,
            nativeType: typeof (window.WebApp && window.WebApp.initData),
            nativeLen: nativeInit().length,
            platform: window.WebApp ? String(window.WebApp.platform) : "no WebApp",
            queryKeys: Array.from(new URLSearchParams(location.search).keys()),
            startParam: startParam(),
            savedCopy: !!fresh
        }));
    }

    window.maxInitData = function () {
        var v = nativeInit() || fromHash() || ssGet(KEY) || lsGet(KEY_LS) || "";
        if (v) persist(v);
        return v;
    };
    window.maxStartParam = startParam;

    window.maxErrorText = function (status, body) {
        if (status === 401) {
            return "Сессия MAX потеряна. Закройте мини-приложение и откройте снова через бота.";
        }
        var d = body && (body.detail || body.error);
        if (d && typeof d === "object") d = d.message || d.code;
        if (Array.isArray(d)) d = d.map(function (x) { return x.msg || x; }).join("; ");
        return d ? String(d) : "Ошибка сервера (" + status + ")";
    };

    window.maxFetch = function (url, opts) {
        opts = opts || {};
        var headers = Object.assign({}, opts.headers || {});
        var init = window.maxInitData();
        if (init) headers["X-Max-Init-Data"] = init;
        opts.headers = headers;
        return fetch(url, opts).then(function (res) {
            // При 401 — один раз обновить initData и не ретраим бесконечно
            return res;
        });
    };

    // Надёжный переход: не теряем initData при location.href
    window.maxGo = function (path) {
        try {
            var init = window.maxInitData();
            if (init) persist(init);
        } catch (e) {}
        location.href = path;
    };

    // Подмена обычных location.href на страницах, где есть data-max-nav (опционально)
    document.addEventListener("click", function (e) {
        var a = e.target && e.target.closest && e.target.closest("a[href]");
        if (!a) return;
        var href = a.getAttribute("href") || "";
        if (href.startsWith("/") || href.startsWith(location.origin)) {
            try { persist(window.maxInitData()); } catch (err) {}
        }
    }, true);
})();
