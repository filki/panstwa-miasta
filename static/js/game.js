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

  // Category filter: use last known config from lobby
  var config = globalThis.pmLastConfig || {};
  var activeCats = Array.isArray(config.categories) ? config.categories : [];
  var customCats = config.custom_categories || {};

  var catContainer = document.getElementById("categories");
  if (!catContainer) return;

  // Show/hide built-in category fields
  var fields = catContainer.querySelectorAll(".game-field");
  fields.forEach(function (field) {
    var inp = field.querySelector("input");
    if (!inp) return;
    var cat = inp.getAttribute("data-category") || "";
    if (activeCats.indexOf(cat) !== -1) {
      field.style.display = "";
      inp.disabled = false;
      inp.value = "";
      inp.classList.remove("error", "success-10", "warning-5", "error-0");
      inp.style.borderColor = "";
    } else {
      field.style.display = "none";
      inp.disabled = true;
    }
  });

  // Remove old custom fields
  catContainer.querySelectorAll(".game-field--custom").forEach(function (el) {
    el.remove();
  });

  // Add custom category fields
  Object.keys(customCats).forEach(function (name) {
    var div = document.createElement("div");
    div.className = "form-group game-field game-field--custom";
    var label = document.createElement("label");
    label.setAttribute("for", "cat-custom-" + name);
    label.textContent = "🔶 " + name;
    var input = document.createElement("input");
    input.type = "text";
    input.className = "game-input";
    input.id = "cat-custom-" + name;
    input.setAttribute("data-category", name);
    input.disabled = false;
    input.value = "";
    div.appendChild(label);
    div.appendChild(input);
    catContainer.appendChild(div);
  });

  // Attach event listeners to all enabled inputs
  var allInputs = catContainer.querySelectorAll("input:not([disabled])");
  allInputs.forEach(function (inp, i) {
    ["input", "keydown"].forEach(function (evt) {
      inp.removeEventListener(evt, inp._pmHandler);
    });
    var handler = function (e) {
      if (e.type === "input") {
        checkAllFilled();
        validateFirstLetter(e.target);
      } else if (e.key === "Enter") {
        var siblings = catContainer.querySelectorAll("input:not([disabled])");
        var idx = Array.prototype.indexOf.call(siblings, e.target);
        if (idx < siblings.length - 1) {
          siblings[idx + 1].focus();
        } else {
          var stopBtn = document.getElementById("btn-stop");
          if (!stopBtn.disabled) stopGame();
        }
      }
    };
    inp._pmHandler = handler;
    inp.addEventListener("input", handler);
    inp.addEventListener("keydown", handler);
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
  const inputs = Array.from(document.querySelectorAll("#categories input"));
  const allFilled = inputs.every((inp) => inp.value.trim().length > 0);
  const stopBtn = document.getElementById("btn-stop");

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
  const inputs = document.querySelectorAll("#categories input");
  let answers = {};
  inputs.forEach((inp) => {
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
