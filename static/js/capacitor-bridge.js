// Capacitor detection — ustawia klasy CSS na <html> dla dedykowanych widokow.
// is-capacitor: apka natywna (Android WebView)
// is-mobile:  ekran < 1024px (mobile-first breakpoint)
// is-desktop: ekran >= 1024px
(function () {
  var html = document.documentElement;

  var IS_CAPACITOR =
    typeof window !== "undefined" &&
    (window.Capacitor || window._cordovaNative);

  if (IS_CAPACITOR) {
    html.classList.add("is-capacitor");
  }

  function updateBreakpoint() {
    var isDesktop = window.matchMedia("(min-width: 1024px)").matches;
    html.classList.toggle("is-desktop", isDesktop);
    html.classList.toggle("is-mobile", !isDesktop);
  }

  updateBreakpoint();
  window.addEventListener("resize", updateBreakpoint);
})();
