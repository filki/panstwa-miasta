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
  const rounds =
    Number.parseInt(document.getElementById("restart-rounds").value) || 5;
  const limit =
    Number.parseInt(document.getElementById("restart-limit").value) || 90;
  sendJson({
    type: "restart_game",
    rounds: rounds,
    limit: limit,
  });
  document.getElementById("restart-settings").style.display = "none";
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

  // Ktore kategorie sa aktywne? (z configu lobby)
  // null = brak configu (reconnect) → wszystkie wlaczone
  var config = globalThis.pmLastConfig;
  var activeCats =
    config && Array.isArray(config.categories) && config.categories.length > 0
      ? config.categories
      : null;

  var inputs = document.querySelectorAll("#categories input");
  inputs.forEach(function (inp) {
    var cat = inp.getAttribute("data-category") || "";
    var field = inp.closest(".game-field");
    var isActive = activeCats === null || activeCats.indexOf(cat) !== -1;

    if (isActive) {
      inp.disabled = false;
      inp.value = "";
      inp.classList.remove("error", "success-10", "warning-5", "error-0");
      inp.style.borderColor = "";
      if (field) {
        field.classList.remove("cat-inactive");
        field.classList.add("cat-active");
      }
      var label = field ? field.querySelector("label") : null;
      if (label) {
        label.textContent = label.textContent.replace(/\s*\(wyłączona\)$/, "");
      }
    } else {
      inp.disabled = true;
      inp.value = "";
      if (field) {
        field.classList.add("cat-inactive");
        field.classList.remove("cat-active");
      }
      var label = field ? field.querySelector("label") : null;
      if (label && label.textContent.indexOf("(wyłączona)") === -1) {
        label.textContent = label.textContent + " (wyłączona)";
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
  };
}
