// W Capacitor WebView (natywna apka) laczymy sie z serwerem produkcyjnym.
// W przegladarce laczymy sie z tym samym originem (bez zmian).
(function () {
  var IS_CAPACITOR =
    typeof window !== "undefined" &&
    (window.Capacitor || window._cordovaNative);
  if (!IS_CAPACITOR) return;

  var SERVER = "https://panstwamiasta.com.pl";
  window.PM_API_BASE = SERVER;
  window.PM_WS_BASE = SERVER.replace(/^https?:/, "wss:");

  // Monkey-patch fetch: prefix relative URLs with server
  var _fetch = window.fetch;
  window.fetch = function (url, opts) {
    if (typeof url === "string" && url.startsWith("/")) {
      url = SERVER + url;
    }
    return _fetch.call(window, url, opts);
  };
})();
