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

  // Sprawdz czy jest niedokonczona sesja (po zamknieciu apki/przegladarki)
  var savedRoom = localStorage.getItem("pm_active_room");
  var savedNick = localStorage.getItem("pm_active_nick");
  if (savedRoom && savedNick && window.location.pathname === "/") {
    document.addEventListener("DOMContentLoaded", function () {
      setTimeout(function () {
        showReconnectDialog(savedRoom, savedNick);
      }, 500);
    });
  }
})();

function showReconnectDialog(roomId, nick) {
  var overlay = document.createElement("div");
  overlay.id = "reconnect-overlay";
  overlay.style.cssText =
    "position:fixed;inset:0;z-index:2500;display:flex;align-items:center;justify-content:center;background:rgba(2,6,23,0.82);backdrop-filter:blur(6px);padding:1rem;";

  var card = document.createElement("div");
  card.style.cssText =
    "background:#fff;border-radius:20px;padding:1.5rem;max-width:340px;width:100%;text-align:center;box-shadow:0 25px 50px -12px rgba(15,23,42,0.16);";

  card.innerHTML =
    '<h3 style="margin:0 0 .5rem;font-size:1.2rem;">Masz niedokończoną grę</h3>' +
    '<p style="margin:0 0 1rem;color:#64748b;font-size:.9rem;">Pokój <strong>' +
    roomId +
    "</strong><br>Nick: <strong>" +
    nick +
    "</strong></p>" +
    '<button id="reconnect-btn" style="width:100%;margin-bottom:.5rem;min-height:44px;border-radius:14px;border:0;background:linear-gradient(135deg,#0ea5e9,#0284c7);color:#fff;font-weight:700;font-size:1rem;cursor:pointer;">🔗 Połącz ponownie</button>' +
    '<button id="reconnect-leave-btn" style="width:100%;min-height:44px;border-radius:14px;border:1px solid #e2e8f0;background:#f8fafc;color:#64748b;font-weight:600;font-size:.9rem;cursor:pointer;">🚪 Opuść grę</button>';

  overlay.appendChild(card);
  document.body.appendChild(overlay);

  function closeOverlay() {
    localStorage.removeItem("pm_active_room");
    localStorage.removeItem("pm_active_nick");
    overlay.remove();
  }

  document.getElementById("reconnect-btn").onclick = function () {
    closeOverlay();
    window.location.href = "/room/" + roomId + "?reconnect=1";
  };

  document.getElementById("reconnect-leave-btn").onclick = function () {
    if (
      confirm(
        "Czy na pewno chcesz opuścić grę?\n\nStracisz postępy w pokoju " +
          roomId +
          ". Nie będzie można wrócić.",
      )
    ) {
      closeOverlay();
      // Opusc pokoj przez API
      fetch("/api/rooms/" + roomId + "/players/" + nick, { method: "DELETE" })
        .catch(function () {})
        .finally(function () {
          window.location.reload();
        });
    }
  };
}
