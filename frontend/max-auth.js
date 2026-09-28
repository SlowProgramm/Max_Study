/*
 * Общий скрипт входа через MAX. Подключается ПЕРВЫМ на входной странице (index.html)
 * и на всех остальных:
 *   <script src="https://st.max.ru/js/max-web-app.js"></script>
 *   <script src="/static/max-auth.js"></script>
 *
 * Зачем: MAX кладёт данные запуска в #WebAppData только во входной URL.
 * После перехода на другую страницу (location.href) фрагмент теряется,
 * поэтому копию initData сохраняем в sessionStorage на входе.
 */
(function () {
    var KEY = "max_init_data_backup";
    var DIAG = "max_entry_diag";

    function store(k) { try { return sessionStorage.getItem(k) || ""; } catch (e) { return ""; } }
    function save(k, v) { try { sessionStorage.setItem(k, v); } catch (e) {} }

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

    var fresh = nativeInit() || fromHash();
    if (fresh) save(KEY, fresh);

    // Запись «что увидела страница» — только если нашли данные или записи ещё нет,
    // чтобы последующие страницы без данных не затирали запись входной.
    if (fresh || !store(DIAG)) {
        var hp = hashParams();
        var inIframe = true;
        try { inIframe = window.self !== window.top; } catch (e) {}
        save(DIAG, JSON.stringify({
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

    window.maxInitData = function () { return nativeInit() || fromHash() || store(KEY); };
    window.maxStartParam = startParam;

    // Текст ошибки для пользователя по ответу сервера
    window.maxErrorText = function (status, body) {
        if (status === 401) {
            return "Не удалось определить ваш аккаунт MAX. Закройте приложение и откройте его снова через бота.";
        }
        var d = body && (body.detail || body.error);
        if (d && typeof d === "object") d = d.message;
        return d ? String(d) : "Ошибка сервера (" + status + ")";
    };

    // fetch, который сам добавляет заголовок с initData
    window.maxFetch = function (url, opts) {
        opts = opts || {};
        opts.headers = Object.assign({}, opts.headers, { "X-Max-Init-Data": window.maxInitData() });
        return fetch(url, opts);
    };
})();
