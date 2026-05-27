function toggleReady() {
  const btn = document.getElementById("btn-draw");
  if (btn.classList.contains("ready")) {
    btn.classList.remove("ready");
    btn.innerHTML = "👍 Gotowy";
    btn.style.backgroundColor = "var(--primary)";
    sendJson({ type: "not_ready" });
  } else {
    btn.classList.add("ready");
    btn.innerHTML = "⏳ Czekamy na resztę...";
    btn.style.backgroundColor = "var(--accent)";
    sendJson({ type: "ready" });
  }
}

function stopGame() {
  const stopBtn = document.getElementById("btn-stop");
  stopBtn.dataset.stopped = "true";
  stopBtn.disabled = true;

  // Natychmiastowe wysłanie swoich wyników jak się wciśnie STOP
  sendJson({ type: "stop" });
  disableAndSubmit();
}

function requestRestart() {
  var rounds = 5;
  var limit = 90;
  var sel = document.getElementById("restart-rounds");
  if (sel) {
    rounds = Number.parseInt(sel.value) || 5;
  }
  var sel2 = document.getElementById("restart-limit");
  if (sel2) {
    limit = Number.parseInt(sel2.value) || 90;
  }
  sendJson({
    type: "restart_game",
    rounds: rounds,
    limit: limit,
  });
  var rs = document.getElementById("restart-settings");
  if (rs) rs.style.display = "none";
}

function dissolveRoom() {
  if (
    confirm("Czy na pewno chcesz rozwiązać pokój? Wszyscy zostaną rozłączeni!")
  ) {
    sendJson({ type: "dissolve_room" });
  }
}

function enableInputs() {
  if (globalThis.currentCountdown) clearInterval(globalThis.currentCountdown);

  var activeCats = globalThis.pmRoundCategories;
  var activeCustomCats = globalThis.pmRoundCustomCategories;

  var inputs = document.querySelectorAll("#categories input");
  inputs.forEach(function (inp) {
    var cat = inp.getAttribute("data-category") || "";
    var field = inp.closest(".game-field");
    // Aktywne jesli: brak danych = wszystkie wlaczone (fallback),
    // albo kategoria jest w liscie z backendu, albo custom kategoria
    var isActive =
      globalThis.currentLetter === undefined ||
      !activeCats ||
      activeCats.indexOf(cat) !== -1 ||
      (activeCustomCats && activeCustomCats[cat] !== undefined);

    if (isActive) {
      inp.disabled = false;
      inp.value = "";
      inp.classList.remove("error", "success-10", "warning-5", "error-0");
      inp.style.borderColor = "";
      if (field) {
        field.classList.remove("cat-inactive");
        field.classList.add("cat-active");
        field.hidden = false;
      }
    } else {
      inp.disabled = true;
      inp.value = "";
      if (field) {
        field.classList.add("cat-inactive");
        field.classList.remove("cat-active");
        field.hidden = true;
      }
    }
  });

  // Ponownie lap eventy (cloneNode usuwa listenery)
  const newInputs = document.querySelectorAll(
    "#categories input:not([disabled])",
  );
  newInputs.forEach(function (inp, i) {
    var clone = inp.cloneNode(true);
    inp.parentNode.replaceChild(clone, inp);
  });
  const finalInputs = document.querySelectorAll(
    "#categories input:not([disabled])",
  );
  finalInputs.forEach(function (inp, i) {
    inp.addEventListener("input", function (e) {
      checkAllFilled();
      validateFirstLetter(e.target);
    });
    inp.addEventListener("keypress", function (e) {
      if (e.key === "Enter") {
        var sibs = document.querySelectorAll(
          "#categories input:not([disabled])",
        );
        if (i < sibs.length - 1) sibs[i + 1].focus();
        else {
          var stopBtn = document.getElementById("btn-stop");
          if (!stopBtn.disabled) stopGame();
        }
      }
    });
  });

  var btnStop = document.getElementById("btn-stop");
  btnStop.disabled = true;
  delete btnStop.dataset.stopped;
  btnStop.innerHTML = "🛑 STOP!";

  if (globalThis.currentLetter) {
    document.getElementById("current-letter").innerHTML =
      globalThis.currentLetter;
  }
}

function checkAllFilled() {
  var inputs = document.querySelectorAll("#categories input:not([disabled])");
  var allFilled = true;
  inputs.forEach(function (inp) {
    if (inp.value.trim().length === 0) allFilled = false;
  });
  var stopBtn = document.getElementById("btn-stop");

  if (allFilled && !("stopped" in stopBtn.dataset)) {
    stopBtn.disabled = false;
  } else {
    stopBtn.disabled = true;
  }
}

/** Pierwsza litera odpowiedzi → mała ASCII (jak ``fold_polish_diacritics`` w backendzie). */
function _foldPolishAsciiChar(ch) {
  const map = {
    ą: "a",
    ć: "c",
    ę: "e",
    ł: "l",
    ń: "n",
    ó: "o",
    ś: "s",
    ź: "z",
    ż: "z",
    Ą: "a",
    Ć: "c",
    Ę: "e",
    Ł: "l",
    Ń: "n",
    Ó: "o",
    Ś: "s",
    Ź: "z",
    Ż: "z",
  };
  const c = map[ch];
  if (c) return c;
  return ch.toLowerCase();
}

function validateFirstLetter(inp) {
  if (!globalThis.currentLetter) return;
  const val = inp.value.trim();
  if (val.length === 0) {
    inp.style.borderColor = "";
    return;
  }
  const target = globalThis.currentLetter.toLowerCase();
  const first = val[0];
  const folded = _foldPolishAsciiChar(first);
  if (folded === target) {
    inp.style.borderColor = "";
  } else {
    inp.style.borderColor = "var(--danger)";
  }
}

function disableAndSubmit() {
  var inputs = document.querySelectorAll("#categories input:not([disabled])");
  var answers = {};
  inputs.forEach(function (inp) {
    answers[inp.dataset.category] = inp.value.trim();
    inp.disabled = true;
  });

  document.getElementById("btn-stop").disabled = true;
  sendJson({ type: "answers", answers: answers });
}


/**
 * Udostępnianie linku do pokoju z poziomu lobby.
 * Mobile (pointer:coarse): Web Share API → native share sheet.
 * Desktop (pointer:fine): clipboard.writeText → skopiowanie linku.
 */
function shareLobbyRoom() {
  const rid = (function () {
    try {
      const parts = globalThis.location.pathname.split("/");
      if (parts.length >= 3 && parts[1] === "room") return parts[2];
    } catch (e) {
      // ignore
    }
    const el = document.getElementById("lobby-room-code");
    return el ? el.textContent.trim().replace(/^—$/, "") : "";
  })();

  if (!rid) return;

  let base = "";
  try {
    base = globalThis.location.origin || "";
  } catch (e) {
    // ignore
  }
  const url = `${base}/room/${encodeURIComponent(rid)}`;

  // Web Share API — jeśli dostępna, użyj (działa w Android WebView / Capacitor)
  if (typeof globalThis.navigator?.share === "function") {
    globalThis.navigator
      .share({
        title: "Państwa-Miasta — dołącz do pokoju!",
        text: `Dołącz do pokoju ${rid} 🎮`,
        url,
      })
      .catch(() => {});
    return;
  }

  // Desktop / fallback: clipboard
  if (typeof globalThis.navigator?.clipboard?.writeText === "function") {
    globalThis.navigator.clipboard
      .writeText(url)
      .then(() => {
        if (typeof addLog === "function") {
          addLog("<em>Skopiowano link do schowka.</em>", "system-msg");
        }
      })
      .catch(() => {
        if (typeof addLog === "function") {
          addLog("<em>Nie udało się skopiować — skopiuj link ręcznie.</em>", "system-msg");
        }
      });
    return;
  }

  // Last-resort fallback
  try {
    globalThis.prompt("Skopiuj link do pokoju:", url);
  } catch (e) {
    // ignore
  }
}

if (typeof module !== "undefined") {
  module.exports = {
    toggleReady,
    stopGame,
    requestRestart,
    dissolveRoom,
    enableInputs,
    checkAllFilled,
    validateFirstLetter,
    disableAndSubmit,
    shareLobbyRoom,
  };
}
