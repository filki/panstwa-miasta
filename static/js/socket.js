let ws;
let myNick = "";
let isLeaving = false; // flag to suppress auto-reconnect on manual leave
let leftByUser = false; // distinguish "user navigated away" from "room dissolved"
let pmHadRoundStarted = false;
let pmWsGeneration = 0;
let PM_SERVER_ORIGIN =
  globalThis.Capacitor || globalThis._cordovaNative
    ? "https://panstwamiasta.com.pl"
    : null;

function sendJson(obj) {
  if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}
globalThis.sendJson = sendJson;

function clearClientRoundTimers() {
  if (globalThis.globalRoundTimer) {
    clearInterval(globalThis.globalRoundTimer);
    globalThis.globalRoundTimer = null;
  }
  if (globalThis.currentCountdown) {
    clearInterval(globalThis.currentCountdown);
    globalThis.currentCountdown = null;
  }
}

function startRoundTimer(timeLeft) {
  const rt = document.getElementById("round-timer");
  if (!rt) return;
  let remaining = timeLeft;
  rt.style.display = "block";
  rt.textContent = `${remaining}s`;
  clearClientRoundTimers();
  globalThis.globalRoundTimer = setInterval(() => {
    remaining--;
    if (remaining >= 0) rt.textContent = `${remaining}s`;
  }, 1000);
}

function lockSubmittedAnswers() {
  document.querySelectorAll("#categories input").forEach((inp) => {
    inp.disabled = true;
  });
  const btnStop = document.getElementById("btn-stop");
  if (!btnStop) return;
  btnStop.disabled = true;
  delete btnStop.dataset.stopped;
  btnStop.innerHTML = "Oczekiwanie na resztę…";
}

/** Home redirect; Jest has no real `location` (Sonar: handle or avoid empty catch). */
function safeNavigateHome() {
  try {
    const isJestEnv =
      typeof process !== "undefined" && process?.env?.JEST_WORKER_ID;
    if (!isJestEnv) globalThis.location.href = "/";
  } catch (e) {
    console.debug("pm: home navigation skipped", e);
  }
}

// Confetti is loaded from a CDN (canvas-confetti). If the CDN is blocked
// or the library fails to load we must NOT let the game flow break --
// a missing confetti() previously crashed the letter lottery interval and
// hung every game right after drawing the letter.
function fireConfetti(opts) {
  if (typeof confetti !== "function") return;
  try {
    confetti(opts);
  } catch (e) {
    console.warn("confetti failed", e);
  }
}

function stopCelebrationEffects() {
  if (typeof confetti === "function" && typeof confetti.reset === "function") {
    try {
      confetti.reset();
    } catch (e) {
      console.warn("confetti reset failed", e);
    }
  }
}

function leaveRoom() {
  // Jesli gra sie nie zaczela — wychodzimy bez pytania
  if (!pmHadRoundStarted) {
    doLeaveRoom();
    return;
  }
  showLeaveConfirmModal();
}

function showLeaveConfirmModal() {
  let existing = document.getElementById("leave-confirm-overlay");
  if (existing) existing.remove();

  let overlay = document.createElement("div");
  overlay.id = "leave-confirm-overlay";
  overlay.style.cssText =
    "position:fixed;inset:0;z-index:2500;display:flex;align-items:center;justify-content:center;background:rgba(2,6,23,0.82);-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);padding:1rem;";

  let card = document.createElement("div");
  card.style.cssText =
    "background:#fff;border-radius:20px;padding:1.5rem;max-width:320px;width:100%;text-align:center;box-shadow:0 25px 50px -12px rgba(0,0,0,0.18);font-family:Inter,system-ui,sans-serif;";

  card.innerHTML =
    '<h3 style="margin:0 0 .35rem;font-size:1.15rem;font-weight:800;color:#1a0a06;">Opuścić grę?</h3>' +
    '<p style="margin:0 0 1.25rem;color:#7a5540;font-size:.875rem;line-height:1.45;">Grasz albo wszystko tracisz. Po wyjściu nie ma powrotu — pokój i postępy zostaną usunięte.</p>' +
    '<button id="leave-confirm-stay" style="width:100%;margin-bottom:.5rem;min-height:44px;border-radius:12px;border:0;background:linear-gradient(135deg,#d58f23,#74371f);color:#fff;font-weight:700;font-size:1rem;cursor:pointer;">🔗 Zostań w grze</button>' +
    '<button id="leave-confirm-leave" style="width:100%;min-height:44px;border-radius:12px;border:1px solid #3e140f29;background:#f7f0de;color:#3e140f;font-weight:600;font-size:.9rem;cursor:pointer;">🚪 Opuść grę</button>';

  overlay.appendChild(card);
  document.body.appendChild(overlay);

  document.getElementById("leave-confirm-stay").onclick = function () {
    overlay.remove();
  };

  document.getElementById("leave-confirm-leave").onclick = function () {
    overlay.remove();
    doLeaveRoom();
  };
}

function doLeaveRoom() {
  // Wyslij dissolve_room do serwera — usunie pokoj z RAM i DB.
  // Nie zamykamy WS recznie — serwer zamknie socket po dissolve.
  // Jesli nie jestesmy hostem, serwer odrzuci dissolve, a my i tak
  // juz nawigujemy na /, co zamknie WS po stronie przegladarki.
  if (ws?.readyState === WebSocket.OPEN) {
    sendJson({ type: "dissolve_room" });
  }
  leftByUser = true;
  isLeaving = true;
  globalThis.myNick = "";
  // Wyczysc sesje
  localStorage.removeItem("pm_active_room");
  localStorage.removeItem("pm_active_nick");
  // Nawiguj na / — to zamknie WS, serwer dostanie disconnect
  safeNavigateHome();
  if (globalThis.globalRoundTimer) {
    clearInterval(globalThis.globalRoundTimer);
    globalThis.globalRoundTimer = null;
  }
  if (globalThis.currentCountdown) {
    clearInterval(globalThis.currentCountdown);
    globalThis.currentCountdown = null;
  }
  // Przenieś użytkownika na stronę główną (landing)
  // In jsdom tests navigation is not implemented, so we must not crash.
  safeNavigateHome();
}

function handleCloseCode(code) {
  if (code === 4401) {
    isLeaving = true;
    alert("Host wyrzucił Cię z pokoju.");
    safeNavigateHome();
    return true;
  }
  if (code === 4408) {
    isLeaving = true;
    alert(
      "Pokój jest pełny (maksymalnie 8 graczy).\n\nSpróbuj za chwilę lub stwórz własny pokój na stronie głównej.",
    );
    safeNavigateHome();
    return true;
  }
  if (code === 4409) {
    isLeaving = true;
    alert(
      "Gra w tym pokoju już trwa. Nie można dołączyć w trakcie rundy.\n\nWróć na stronę główną i znajdź inny pokój lub stwórz własny.",
    );
    safeNavigateHome();
    return true;
  }
  if (code === 1008) {
    isLeaving = true;
    alert(
      "Ten nick jest już zajęty lub nieprawidłowy.\n\nZmień go i spróbuj ponownie.",
    );
    const ij = document.getElementById("room-inline-join");
    const cs = document.getElementById("chat-section");
    if (ij) ij.style.display = "block";
    if (cs) cs.style.display = "none";
    return true;
  }
  return false;
}

function _resolveNickname() {
  const joinNick = document.getElementById("nickname_join")?.value.trim() || "";
  const createNick = document.getElementById("nickname")?.value.trim() || "";
  const landingNick =
    document.getElementById("landing_nickname")?.value.trim() || "";
  let nick = (
    globalThis.clampNickname ||
    ((value) =>
      String(value ?? "")
        .trim()
        .slice(0, 16))
  )(joinNick || createNick || landingNick);
  if (!nick && typeof getResolvedNickname === "function") {
    nick = getResolvedNickname() || "";
  }
  if (!nick && typeof ensureNicknameInput === "function") {
    nick = ensureNicknameInput() || "";
  }
  globalThis.myNick = nick;
  return nick;
}

function _detectRoomId() {
  const pathParts = globalThis.location.pathname.split("/");
  if (pathParts.length >= 3 && pathParts[1] === "room") {
    return pathParts[2];
  }
  const roomId = document.getElementById("room_id").value.trim();
  if (roomId) return roomId;
  return document.getElementById("landing_room_code")?.value.trim() || "";
}

function _resolveConnectionSettings() {
  const roomId = _detectRoomId();
  if (!roomId) {
    if (document.getElementById("create-modal").style.display !== "none") {
      alert("Najpierw utwórz pokój przyciskiem „Stwórz i wejdź”.");
      return null;
    }
    alert("Proszę podać kod pokoju lub wybrać opcję stworzenia nowego.");
    return null;
  }
  return { roomId };
}

function _buildWsUrl(roomId) {
  let baseHost = globalThis.location.host;
  let protocol = globalThis.location.protocol === "https:" ? "wss:" : "ws:";
  // W Capacitor WebView laczymy sie z serwerem produkcyjnym
  if (globalThis.PM_WS_BASE !== undefined) {
    let url = new URL(globalThis.PM_WS_BASE);
    baseHost = url.host;
  }
  const encNick = encodeURIComponent(myNick);
  return `${protocol}//${baseHost}/ws/${roomId}/${encNick}`;
}

function _teardownPrevSocket() {
  if (!ws) return;
  ws.onclose = null;
  ws.onerror = null;
  ws.onmessage = null;
  try {
    if (
      ws.readyState === WebSocket.OPEN ||
      ws.readyState === WebSocket.CONNECTING
    ) {
      ws.close();
    }
  } catch (e) {
    console.debug("pm: prior websocket close skipped", e);
  }
}

function connect() {
  leftByUser = false;
  initAudio();
  myNick = _resolveNickname();
  globalThis.myNick = myNick;
  if (!myNick) return alert("Nie udało się nadać nicku — odśwież stronę.");

  const settings = _resolveConnectionSettings();
  if (!settings) return;
  const { roomId } = settings;

  if (typeof persistNickname === "function") {
    persistNickname(myNick);
  } else {
    localStorage.setItem("pm_nickname", myNick);
  }

  if (!globalThis.location.pathname.startsWith("/room/")) {
    if (typeof markRoomAutoJoinIntent === "function") {
      markRoomAutoJoinIntent();
    }
    globalThis.location.href = `/room/${roomId}`;
    return;
  }

  globalThis.history.replaceState(null, "", `/room/${roomId}`);

  const wsUrl = _buildWsUrl(roomId);

  pmWsGeneration += 1;
  const socketGeneration = pmWsGeneration;
  _teardownPrevSocket();

  const socket = new WebSocket(wsUrl);
  ws = socket;

  socket.onopen = () => {
    if (socketGeneration !== pmWsGeneration) return;
    // Zapis sesji dla reconnect po zamknieciu apki/przegladarki
    let activeRoom = _detectRoomId();
    if (activeRoom) {
      localStorage.setItem("pm_active_room", activeRoom);
      localStorage.setItem("pm_active_nick", myNick);
    }
    if (typeof hideModals === "function") hideModals();
    document.getElementById("join-section").style.display = "none";
    const inlineJoin = document.getElementById("room-inline-join");
    if (inlineJoin) inlineJoin.style.display = "none";
    document.getElementById("chat-section").style.display = "block";
    document.getElementById("btn-leave").style.display = "inline-flex";
    document.getElementById("current-room").textContent = roomId;

    const navRoomInfo = document.getElementById("nav-room-info");
    const navRoomCode = document.getElementById("nav-room-code");
    const navHomeLink = document.getElementById("nav-home-link");
    if (navRoomCode) navRoomCode.textContent = roomId;
    if (navRoomInfo) navRoomInfo.style.display = "inline-flex";
    if (navHomeLink) navHomeLink.style.display = "none";

    if (typeof syncRoomLobbySettings === "function") {
      syncRoomLobbySettings(roomId);
    }
    if (!pmHadRoundStarted && typeof setRoomPhase === "function") {
      setRoomPhase("lobby");
    } else if (typeof setRoomPhase === "function") {
      setRoomPhase("playing");
    }

    // Nie czyść rankingu tutaj — serwer wysyła ``score_update`` w ``_send_initial_state``.
    // Wywołanie ``updateScoreboard({}, …)`` przy reconnect powodowało wyścig z wiadomościami
    // i zerowanie punktów w UI mimo poprawnego stanu na backendzie.
  };

  socket.onclose = (e) => {
    if (socketGeneration !== pmWsGeneration) return;
    if (handleCloseCode(e.code)) return;
    // If we initiated a manual leave, do not auto-reconnect
    if (isLeaving) {
      isLeaving = false;
      return;
    }
    // Unexpected disconnect — try to reconnect
    addLog(
      `<em>Utracono połączenie z serwerem. Próba wznowienia za 3 sekundy...</em>`,
      "system-msg",
    );
    setTimeout(() => {
      const chatVisible =
        document.getElementById("chat-section")?.style.display !== "none";
      if (chatVisible) {
        addLog(`<em>Próba ponownego połączenia...</em>`, "system-msg");
        connect();
      }
    }, 3000);
  };

  socket.onmessage = (event) => {
    if (socketGeneration !== pmWsGeneration) return;
    const msg = JSON.parse(event.data);
    const handler = MESSAGE_HANDLERS[msg.type];
    if (handler) handler(msg);
  };

  socket.onerror = (e) => {
    if (socketGeneration !== pmWsGeneration) return;
    addLog(
      `<em>Błąd połączenia. Sprawdź swoje połączenie internetowe i odśwież stronę.</em>`,
      "system-msg",
    );
    console.error("WS Error:", e);
  };
}

function onSystemMessage(m) {
  addLog(`<em>${m.message}</em>`, "system-msg");
}

function onScoreUpdate(m) {
  updateScoreboard(
    m.scores,
    m.host_name,
    globalThis.myNick || "",
    m.ready_players,
    m.connected_players,
  );
}

function onChatMessage(m) {
  const container = document.createElement("div");
  const senderDiv = document.createElement("div");
  senderDiv.className = "sender";
  senderDiv.textContent = m.sender;
  const textDiv = document.createElement("div");
  textDiv.textContent = m.text;
  container.appendChild(senderDiv);
  container.appendChild(textDiv);
  addLog(container, "");
}

function onKicked(m) {
  isLeaving = true;
  alert(m.message || "Host wyrzucił Cię z pokoju.");
  safeNavigateHome();
}

function onKickDenied(m) {
  addLog(`<em>${m.message || "Nie można wyrzucić gracza."}</em>`, "system-msg");
}

function onRoomDissolved(m) {
  // Zapobiega auto-reconnect (onclose) gdy serwer zamyka socket tuż po
  // room_dissolved — inaczej po grze często odtwarzał się „pusty” pokój.
  isLeaving = true;
  if (leftByUser) return; // user left -> do not bounce them back into /room/:id
  try {
    globalThis.sessionStorage?.setItem("pm_skip_auto_join", "1");
  } catch (e) {
    console.debug("pm: sessionStorage setItem skipped", e);
  }
  alert(m.message);
  safeNavigateHome();
}

function onLobbyState(m) {
  if (typeof renderLobbyState === "function") {
    renderLobbyState(m);
  }
}

let pmAppealToken = "";

function onAppealToken(msg) {
  if (msg && typeof msg.token === "string" && msg.token) {
    pmAppealToken = msg.token;
  }
}

const MESSAGE_HANDLERS = {
  system: onSystemMessage,
  score_update: onScoreUpdate,
  chat: onChatMessage,
  round_started: onRoundStarted,
  stop_round: onStopRound,
  round_results: onRoundResults,
  veto_update: onVetoUpdate,
  game_restarted: onGameRestarted,
  room_dissolved: onRoomDissolved,
  kicked: onKicked,
  kick_denied: onKickDenied,
  appeal_token: onAppealToken,
  lobby_state: onLobbyState,
  lobby_config_update: (data) => {
    if (typeof updateLobbyConfigUI === "function") {
      updateLobbyConfigUI(data);
    }
  },
  lobby_chat: (data) => {
    if (typeof appendChatMessage === "function") {
      appendChatMessage(data.from, data.text);
    }
  },
};

function onRoundStartedResume(msg) {
  injectCustomCategoryFields();
  const letterEl = document.getElementById("current-letter");
  if (letterEl) letterEl.textContent = msg.letter;
  const btn = document.getElementById("btn-draw");
  if (btn) {
    btn.classList.remove("ready");
    btn.style.display = "none";
  }
  addLog(
    `<em>Połączenie przywrócone. Runda ${msg.current_round}/${msg.max_rounds}, litera: <strong>${msg.letter}</strong>.</em>`,
    "system-msg",
  );
  clearClientRoundTimers();
  if (msg.answer_submitted) {
    lockSubmittedAnswers();
  } else {
    clearInputColors();
    enableInputs();
  }
  if (msg.stop_triggered) {
    onStopRound({
      sender: "Serwer (Wznowienie)",
      time_left:
        typeof msg.stop_seconds_left === "number" ? msg.stop_seconds_left : 10,
      resume: true,
    });
    return;
  }
  if (typeof msg.seconds_left === "number") {
    startRoundTimer(msg.seconds_left);
  } else {
    const rt = document.getElementById("round-timer");
    if (rt) {
      rt.style.display = "block";
      rt.textContent = "—";
    }
  }
}

function injectCustomCategoryFields() {
  let config = globalThis.pmLastConfig;
  if (!config?.custom_categories) return;
  let names = Object.keys(config.custom_categories);
  if (names.length === 0) return;
  let container = document.getElementById("categories");
  if (!container) return;
  names.forEach(function (name) {
    let safe = name
      .replace(/[^a-zA-Z0-9\u00C0-\u024f\u0400-\u04FF]+/g, "-")
      .toLowerCase();
    let existing = document.getElementById("cat-custom-" + safe);
    if (existing) return;
    let div = document.createElement("div");
    div.className = "form-group game-field";
    let label = document.createElement("label");
    label.textContent = "\u2728 " + name;
    label.htmlFor = "cat-custom-" + safe;
    div.appendChild(label);
    let inp = document.createElement("input");
    inp.type = "text";
    inp.className = "game-input";
    inp.id = "cat-custom-" + safe;
    inp.dataset.category = name;
    inp.disabled = true;
    div.appendChild(inp);
    container.appendChild(div);
  });
}

function cleanupCustomCategoryFields() {
  document.querySelectorAll("#categories .game-field").forEach(function (el) {
    let inp = el.querySelector("input");
    if (
      inp?.dataset?.category &&
      globalThis.pmLastConfig?.custom_categories
    ) {
      if (
        globalThis.pmLastConfig.custom_categories[inp.dataset.category] !==
        undefined
      ) {
        el.remove();
      }
    }
  });
}

function onRoundStartedFresh(msg) {
  cleanupCustomCategoryFields();
  injectCustomCategoryFields();
  const afterReveal = () => {
    const lotteryFunc = globalThis.runLetterLottery || runLetterLottery;
    lotteryFunc(msg.letter, () => {
      document.getElementById("current-letter").textContent = msg.letter;
      const btn = document.getElementById("btn-draw");
      btn.classList.remove("ready");
      btn.style.display = "none";
      addLog(
        `<em>Gra rozpoczęta! Litera: <strong>${msg.letter}</strong> (Runda ${msg.current_round}/${msg.max_rounds}). Limit czasu: ${msg.time_limit}s</em>`,
        "system-msg",
      );
      clearInputColors();
      enableInputs();
      let timeLeft = msg.time_limit;
      document.getElementById("round-timer").textContent = timeLeft + "s";
      document.getElementById("round-timer").style.display = "block";
      startRoundTimer(timeLeft);
    });
  };
  const countdownFn =
    globalThis.runRoundStartCountdown || runRoundStartCountdown;
  countdownFn(afterReveal);
}

function onRoundStarted(msg) {
  hideRoundResultsOverlay();
  provisionalRoundResultsMsg = null;
  globalThis.currentLetter = msg.letter;
  globalThis.pmRoundCategories = msg.categories || null;
  globalThis.pmRoundCustomCategories = msg.custom_categories || null;
  pmHadRoundStarted = true;
  if (typeof setRoomPhase === "function") setRoomPhase("playing");
  if (msg.resume) {
    onRoundStartedResume(msg);
    return;
  }
  onRoundStartedFresh(msg);
}

function onStopRound(msg) {
  playGong();
  clearClientRoundTimers();
  document.getElementById("round-timer").style.display = "none";
  if (!msg.resume) {
    addLog(
      `<em>🚨 <strong>${msg.sender} zatrzymał rundę!</strong> Oczekiwanie na przesłanie odpowiedzi... Masz 10 sekund!</em>`,
      "system-msg",
    );
  }
  const btnStop = document.getElementById("btn-stop");
  btnStop.disabled = true;
  const stickyTimer = document.getElementById("sticky-timer");
  const stickyTime = document.getElementById("sticky-time");
  if (stickyTimer) stickyTimer.style.display = "block";
  let timeLeft = typeof msg.time_left === "number" ? msg.time_left : 10;
  if (stickyTime) stickyTime.innerText = String(timeLeft);
  document.getElementById("current-letter").innerHTML =
    `<span style="color:var(--danger)">${timeLeft}s</span>`;
  btnStop.innerHTML = `⏳ ${timeLeft}s`;
  if (timeLeft <= 0) {
    btnStop.innerHTML = `WYSYŁANIE...`;
    if (stickyTimer) stickyTimer.style.display = "none";
    disableAndSubmit();
    return;
  }
  globalThis.currentCountdown = setInterval(() => {
    timeLeft--;
    if (timeLeft > 0) {
      document.getElementById("current-letter").innerHTML =
        `<span style="color:var(--danger)">${timeLeft}s</span>`;
      btnStop.innerHTML = `⏳ ${timeLeft}s`;
      if (stickyTime) stickyTime.innerText = String(timeLeft);
      playTick();
    } else {
      clearInterval(globalThis.currentCountdown);
      globalThis.currentCountdown = null;
      btnStop.innerHTML = `WYSYŁANIE...`;
      if (stickyTimer) stickyTimer.style.display = "none";
      disableAndSubmit();
    }
  }, 1000);
}

function getScoreColor(pts) {
  if (pts === 15) return "var(--pts-15)";
  if (pts === 10) return "var(--pts-10)";
  if (pts === 5) return "var(--pts-5)";
  return "var(--danger)";
}

/** Kolejność jak w backendzie ``GAME_CATEGORIES`` — spójna tabela wyników. */
const ROUND_RESULT_CATEGORIES = [
  "Państwo",
  "Miasto",
  "Rzecz",
  "Zwierzę",
  "Roślina",
  "Imię",
  "Zawód",
];

function escapeHtml(text) {
  if (text == null || text === "") return "";
  const d = document.createElement("div");
  d.textContent = String(text);
  return d.innerHTML;
}

function isWideRoundResultsLayout() {
  return false;
}

function roundResultsPtsClass(pts) {
  if (pts === 15) return "round-results-pts round-results-pts--15";
  if (pts === 10) return "round-results-pts round-results-pts--10";
  if (pts === 5) return "round-results-pts round-results-pts--5";
  return "round-results-pts round-results-pts--0";
}

function sortRoundResultPlayers(scores, viewer) {
  return Object.keys(scores).sort((a, b) => {
    const aw = a === viewer ? 1 : 0;
    const bw = b === viewer ? 1 : 0;
    if (aw !== bw) return bw - aw;
    const at =
      scores[a] && typeof scores[a].total === "number" ? scores[a].total : 0;
    const bt =
      scores[b] && typeof scores[b].total === "number" ? scores[b].total : 0;
    return bt - at || a.localeCompare(b, "pl");
  });
}

function buildPlayerResultHtml(player, rScore, pAnswers, viewerNick) {
  return buildRoundResultsHtml(
    {
      round_scores: { [player]: rScore },
      answers: { [player]: pAnswers },
      final: true,
    },
    { variant: "sidebar" },
  );
}

function _buildVetoHtml(cat, player, viewer, isFinal, hasAns, tallies) {
  if (cat === "Rzecz" && !isFinal && player !== viewer && hasAns) {
    const tally = tallies[player] || {};
    const tak = typeof tally.tak === "number" ? tally.tak : 0;
    const nie = typeof tally.nie === "number" ? tally.nie : 0;
    return `<span class="round-results-veto-tally" aria-hidden="true">${tak}·${nie}</span><div class="round-results-veto-actions" data-veto-target="${escapeHtml(player)}"><button type="button" class="round-results-veto-btn round-results-veto-btn--up" data-target="${escapeHtml(player)}" data-vote="tak" aria-label="Zatwierdź odpowiedź">👍</button><button type="button" class="round-results-veto-btn round-results-veto-btn--down" data-target="${escapeHtml(player)}" data-vote="nie" aria-label="Odrzuć odpowiedź">👎</button></div>`;
  }
  return "";
}

function _buildCustomCatVetoHtml(vetoKey, tallies, isFinal, player, viewer, hasAns, cat) {
  if (
    !ROUND_RESULT_CATEGORIES.includes(cat) &&
    !isFinal &&
    player !== viewer &&
    hasAns
  ) {
    const ctally = tallies[vetoKey] || {};
    const cTak = typeof ctally.tak === "number" ? ctally.tak : 0;
    const cNie = typeof ctally.nie === "number" ? ctally.nie : 0;
    return `<span class="round-results-veto-tally" aria-hidden="true">${cTak}·${cNie}</span><div class="round-results-veto-actions"><button type="button" class="round-results-veto-btn round-results-veto-btn--up" data-target="${escapeHtml(player)}" data-cat="${escapeHtml(cat)}" data-vote="tak" aria-label="Zatwierdź">👍</button><button type="button" class="round-results-veto-btn round-results-veto-btn--down" data-target="${escapeHtml(player)}" data-cat="${escapeHtml(cat)}" data-vote="nie" aria-label="Odrzuć">👎</button></div>`;
  }
  return "";
}

function _buildAppealHtml(allowAppeals, player, viewer, pts, roundNumber, roomId, cat) {
  if (allowAppeals && player === viewer && pts === 0 && roundNumber > 0 && roomId) {
    return `<button type="button" class="postgame-appeal-btn" data-room-id="${escapeHtml(roomId)}" data-round="${roundNumber}" data-category="${escapeHtml(cat)}">Wyjaśnij</button><div class="postgame-appeal-result" hidden></div>`;
  }
  return "";
}

function _buildWordReportHtml(allowAppeals, player, viewer, pts, hasAns, roundLetter, cat, raw) {
  if (allowAppeals && player === viewer && pts === 0 && hasAns && roundLetter.length === 1) {
    const wordText = String(raw).trim();
    return `<button type="button" class="postgame-word-report-btn" data-word="${escapeHtml(wordText)}" data-category="${escapeHtml(cat)}" data-letter="${escapeHtml(roundLetter)}">Zapisz do słownika</button><div class="postgame-word-report-result" hidden></div>`;
  }
  return "";
}

function buildResultCell(
  cat,
  hasAns,
  raw,
  pts,
  player,
  viewer,
  isFinal,
  tallies,
  allowAppeals,
  roundNumber,
  roomId,
  roundLetter,
) {
  const vetoKey =
    !ROUND_RESULT_CATEGORIES.includes(cat) ? player + "::" + cat : player;
  let cell = `<div class="round-results-cell"><span class="round-results-val">${hasAns ? escapeHtml(String(raw).trim()) : "—"}</span><span class="${roundResultsPtsClass(pts)}">${pts}</span>`;
  cell += _buildVetoHtml(cat, player, viewer, isFinal, hasAns, tallies);
  cell += _buildCustomCatVetoHtml(vetoKey, tallies, isFinal, player, viewer, hasAns, cat);
  cell += _buildAppealHtml(allowAppeals, player, viewer, pts, roundNumber, roomId, cat);
  cell += _buildWordReportHtml(allowAppeals, player, viewer, pts, hasAns, roundLetter, cat, raw);
  cell += "</div>";
  return cell;
}

function buildRoundResultsHtml(msg, options = {}) {
  const variant = options.variant === "overlay" ? "overlay" : "sidebar";
  // Active standard categories — fall back to full list if not provided
  let activeCats =
    msg.categories &&
    Array.isArray(msg.categories) &&
    msg.categories.length > 0
      ? msg.categories
      : ROUND_RESULT_CATEGORIES;
  const answersRoot =
    msg.answers && typeof msg.answers === "object" ? msg.answers : {};
  const viewer = globalThis.myNick || myNick || "";
  const scores =
    msg.round_scores && typeof msg.round_scores === "object"
      ? msg.round_scores
      : {};
  const tallies =
    msg.veto_tallies && typeof msg.veto_tallies === "object"
      ? msg.veto_tallies
      : {};
  const isFinal = msg.final !== false;
  const allowAppeals = Boolean(options.allowAppeals);
  const roundNumber = Number(options.roundNumber) || 0;
  const roomId = String(options.roomId || "");
  const roundLetter = String(
    options.roundLetter || globalThis.currentLetter || "",
  )
    .trim()
    .toLowerCase();
  const players = sortRoundResultPlayers(scores, viewer);

  // Detect custom categories from score details
  let customCats = [];
  for (const player of players) {
    let pdet = scores[player]?.details;
    if (pdet) {
      let keys = Object.keys(pdet);
      for (const key of keys) {
        if (
          !ROUND_RESULT_CATEGORIES.includes(key) &&
          !customCats.includes(key)
        ) {
          customCats.push(key);
        }
      }
    }
  }

  let html = `<div class="round-results-block round-results-block--${variant}"><div class="round-results-table-wrap"><table class="round-results-table round-results-table--players"><thead><tr><th scope="col">Gracz</th>`;
  for (const cat of activeCats) {
    html += `<th scope="col">${escapeHtml(cat)}</th>`;
  }
  for (const cat of customCats) {
    html += `<th scope="col">${escapeHtml(cat)}</th>`;
  }
  html += `<th scope="col">Suma</th></tr></thead><tbody>`;

  for (const player of players) {
    const rScore = scores[player] || { total: 0, details: {} };
    const answers =
      answersRoot[player] && typeof answersRoot[player] === "object"
        ? answersRoot[player]
        : {};
    const meClass = player === viewer ? " round-results-player-row--me" : "";
    html += `<tr class="round-results-player-row${meClass}"><th scope="row" class="round-results-player">${escapeHtml(player)}</th>`;
    for (const cat of activeCats) {
      const raw = answers[cat];
      const hasAns = raw != null && String(raw).trim() !== "";
      const ptsRaw = rScore.details?.[cat];
      const pts = typeof ptsRaw === "number" ? ptsRaw : 0;
      const cell = buildResultCell(
        cat,
        hasAns,
        raw,
        pts,
        player,
        viewer,
        isFinal,
        tallies,
        allowAppeals,
        roundNumber,
        roomId,
        roundLetter,
      );
      html += `<td class="round-results-td">${cell}</td>`;
    }
    // Custom category columns
    for (const ccat of customCats) {
      let craw = answers[ccat];
      let chasAns = craw != null && String(craw).trim() !== "";
      let cptsRaw = rScore.details?.[ccat];
      let cpts = typeof cptsRaw === "number" ? cptsRaw : 0;
      let ccell = buildResultCell(
        ccat,
        chasAns,
        craw,
        cpts,
        player,
        viewer,
        isFinal,
        tallies,
        allowAppeals,
        roundNumber,
        roomId,
        roundLetter,
      );
      html += `<td class="round-results-td">${ccell}</td>`;
    }
    const total = typeof rScore.total === "number" ? rScore.total : 0;
    html += `<td class="round-results-td round-results-td--total"><span class="round-results-player-total">+${total} pkt</span></td></tr>`;
  }

  html += "</tbody></table></div></div>";
  return html;
}

let roundResultsOverlayBound = false;
let provisionalRoundResultsMsg = null;
let roundResultsCountdownTimer = null;

function clearRoundResultsCountdown() {
  if (roundResultsCountdownTimer) {
    clearInterval(roundResultsCountdownTimer);
    roundResultsCountdownTimer = null;
  }
}

function updateRoundResultsCountdownLabel(secondsLeft) {
  const label = document.getElementById("round-results-countdown");
  if (!label) return;
  label.textContent =
    secondsLeft > 0 ? `Następna runda za ${secondsLeft}s` : "Następna runda…";
  label.hidden = false;
}

function startRoundResultsCountdown(vetoEndsAt) {
  clearRoundResultsCountdown();
  if (!vetoEndsAt) return;
  const tick = () => {
    const left = Math.max(0, Math.ceil((vetoEndsAt - Date.now()) / 1000));
    updateRoundResultsCountdownLabel(left);
    if (left <= 0) clearRoundResultsCountdown();
  };
  tick();
  roundResultsCountdownTimer = setInterval(tick, 250);
}

function bindRoundResultsVeto(root) {
  if (!root) return;
  root.querySelectorAll(".round-results-veto-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.target;
      const vote = btn.dataset.vote;
      const cat = btn.dataset.cat || "";
      if (!target || !vote) return;
      let payload = { type: "veto_vote", target: target, vote: vote };
      if (cat) payload.cat = cat;
      sendJson(payload);
      btn
        .closest(".round-results-veto-actions")
        ?.querySelectorAll(".round-results-veto-btn")
        .forEach((peer) => {
          peer.classList.toggle("is-active", peer === btn);
          peer.disabled = peer === btn;
        });
    });
  });
}

function refreshProvisionalRoundResultsOverlay() {
  if (!provisionalRoundResultsMsg) return;
  showRoundResultsOverlay(
    buildRoundResultsHtml(provisionalRoundResultsMsg, { variant: "overlay" }),
    {
      gameOver: false,
      provisional: true,
      vetoEndsAt: provisionalRoundResultsMsg.veto_ends_at,
    },
  );
}

function hideRoundResultsOverlay() {
  const overlay = document.getElementById("round-results-overlay");
  if (!overlay) return;
  overlay.hidden = true;
  overlay.setAttribute("aria-hidden", "true");
  document.body.classList.remove("room-results-open");
  provisionalRoundResultsMsg = null;
  clearRoundResultsCountdown();
  const countdown = document.getElementById("round-results-countdown");
  if (countdown) countdown.hidden = true;
  const chatSection = document.getElementById("chat-section");
  if (chatSection) chatSection.hidden = false;
}

function showRoundResultsOverlay(
  html,
  { gameOver = false, provisional = false, vetoEndsAt = null } = {},
) {
  const overlay = document.getElementById("round-results-overlay");
  const body = document.getElementById("round-results-modal-body");
  if (!overlay || !body) return;

  if (!gameOver) {
    stopCelebrationEffects();
    if (typeof setRoomPhase === "function") setRoomPhase("round_results");
  }

  body.innerHTML = html;
  bindRoundResultsVeto(body);
  overlay.hidden = false;
  overlay.setAttribute("aria-hidden", "false");
  document.body.classList.add("room-results-open");

  _configureResultsOverlayControls(overlay, gameOver, provisional, vetoEndsAt);

  if (!roundResultsOverlayBound) {
    roundResultsOverlayBound = true;
    const dismissBtn = document.getElementById("btn-round-results-dismiss");
    const backdrop = overlay.querySelector(".round-results-overlay-backdrop");
    dismissBtn?.addEventListener("click", hideRoundResultsOverlay);
    backdrop?.addEventListener("click", hideRoundResultsOverlay);
  }
}

function _configureResultsOverlayControls(
  overlay,
  gameOver,
  provisional,
  vetoEndsAt,
) {
  const dismissBtn = document.getElementById("btn-round-results-dismiss");
  const backdrop = overlay.querySelector(".round-results-overlay-backdrop");
  const countdown = document.getElementById("round-results-countdown");
  const vetoHint = overlay.querySelector(".round-results-veto-hint");
  if (dismissBtn) {
    dismissBtn.hidden = provisional;
    dismissBtn.style.display = provisional ? "none" : "";
    dismissBtn.textContent = gameOver ? "Zobacz koniec gry" : "Dalej";
    if (!provisional) dismissBtn.focus();
  }
  if (backdrop) backdrop.style.pointerEvents = provisional ? "none" : "";
  if (countdown) countdown.hidden = !provisional;
  if (vetoHint) vetoHint.hidden = !provisional;

  if (provisional) startRoundResultsCountdown(vetoEndsAt);
  else clearRoundResultsCountdown();
}

function buildGameOverScoreboardHtml(msg) {
  const totals =
    msg.total_scores && typeof msg.total_scores === "object"
      ? msg.total_scores
      : {};
  const players = Object.keys(totals).sort((a, b) => {
    const av = typeof totals[a] === "number" ? totals[a] : 0;
    const bv = typeof totals[b] === "number" ? totals[b] : 0;
    return bv - av || a.localeCompare(b, "pl");
  });
  if (!players.length) return "";

  const viewer = globalThis.myNick || myNick || "";
  let html =
    '<div class="game-over-scoreboard"><ol class="share-score-list" aria-label="Tabela wyników końcowych">';
  for (const player of players) {
    const pts = typeof totals[player] === "number" ? totals[player] : 0;
    const meClass = player === viewer ? " game-over-score-row--me" : "";
    html += `<li class="game-over-score-row${meClass}"><span>${escapeHtml(player)}</span><span class="share-score-pts">${pts} pkt</span></li>`;
  }
  return `${html}</ol></div>`;
}

function buildGameOverRoundBreakdownHtml(msg) {
  const history = Array.isArray(msg.round_history) ? msg.round_history : [];
  const roomId = msg.room_id || "";
  let roundsHtml = "";

  if (history.length > 0) {
    roundsHtml = history
      .map((round) => {
        const roundNo = Number(round.round) || 0;
        const letter = String(round.letter || "?");
        const head = `<p class="game-over-round-title">Runda ${roundNo} · ${escapeHtml(letter)}</p>`;
        return `${head}${buildRoundResultsHtml(
          {
            answers: round.answers,
            round_scores: round.round_scores,
            veto_tallies: round.veto_tallies,
            categories: round.categories,
            custom_categories: round.custom_categories,
            final: true,
          },
          {
            variant: "sidebar",
            allowAppeals: true,
            roundNumber: roundNo,
            roomId,
            roundLetter: letter,
          },
        )}`;
      })
      .join("");
  } else {
    const roundScores =
      msg.round_scores && typeof msg.round_scores === "object"
        ? msg.round_scores
        : {};
    if (Object.keys(roundScores).length > 0) {
      roundsHtml = buildRoundResultsHtml(msg, {
        variant: "sidebar",
        allowAppeals: true,
        roundNumber: msg.current_round || 0,
        roomId,
      });
    }
  }

  if (!roundsHtml) return "";
  return `<section class="game-over-details" aria-labelledby="game-over-details-title"><h4 id="game-over-details-title" class="game-over-details-title">Szczegóły rund i wyjaśnienia</h4>${roundsHtml}</section>`;
}

function buildGameOverResultsHtml(msg) {
  const scoreboard = buildGameOverScoreboardHtml(msg);
  const details = buildGameOverRoundBreakdownHtml(msg);
  if (scoreboard && details) return `${scoreboard}${details}`;
  return scoreboard || details;
}

function clearGameOverResults() {
  const panel = document.getElementById("game-over-results");
  const body = document.getElementById("game-over-results-body");
  if (body) body.innerHTML = "";
  if (panel) panel.hidden = true;
}

async function requestPostgameAppeal(button) {
  const roomId = button.dataset.roomId || "";
  const roundNo = Number(button.dataset.round || "0");
  const category = button.dataset.category || "";
  const playerName = globalThis.myNick || myNick || "";
  const resultBox = button.parentElement?.querySelector(
    ".postgame-appeal-result",
  );
  if (!roomId || !roundNo || !category || !playerName) return;
  button.disabled = true;
  if (resultBox) {
    resultBox.hidden = false;
    resultBox.textContent = "Ładowanie wyjaśnienia…";
  }
  try {
    const headers = { "Content-Type": "application/json" };
    if (pmAppealToken) {
      headers.Authorization = `Bearer ${pmAppealToken}`;
    }
    const resp = await fetch(
      `/api/rooms/${encodeURIComponent(roomId)}/appeals`,
      {
        method: "POST",
        headers,
        body: JSON.stringify({
          player_name: playerName,
          round: roundNo,
          category,
        }),
      },
    );
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const detail = data?.detail
        ? String(data.detail)
        : "Nie udało się pobrać wyjaśnienia.";
      if (resultBox) resultBox.textContent = detail;
      return;
    }
    if (resultBox)
      resultBox.textContent = data.message_pl || "Brak wyjaśnienia.";
  } catch (err) {
    if (resultBox) resultBox.textContent = "Błąd połączenia z serwerem.";
    console.error("requestPostgameAppeal failed:", err);
  } finally {
    button.disabled = false;
  }
}

function wirePostgameAppealButtons(root) {
  if (!root) return;
  root.querySelectorAll(".postgame-appeal-btn").forEach((button) => {
    if (button.dataset.appealBound === "1") return;
    button.dataset.appealBound = "1";
    button.addEventListener("click", () => {
      requestPostgameAppeal(button);
    });
  });
}

function renderGameOverResults(msg) {
  if (!msg) return;
  const panel = document.getElementById("game-over-results");
  const body = document.getElementById("game-over-results-body");
  if (!panel || !body) return;
  const html = buildGameOverResultsHtml(msg);
  if (!html) {
    clearGameOverResults();
    return;
  }
  body.innerHTML = html;
  wirePostgameAppealButtons(body);
  if (typeof globalThis.wirePostgameWordReportButtons === "function") {
    globalThis.wirePostgameWordReportButtons(body);
  }
  panel.hidden = false;
}

function onVetoUpdate(msg) {
  if (!provisionalRoundResultsMsg || msg.final) return;
  provisionalRoundResultsMsg = {
    ...provisionalRoundResultsMsg,
    veto_tallies: msg.veto_tallies || provisionalRoundResultsMsg.veto_tallies,
  };
  refreshProvisionalRoundResultsOverlay();
}

function onRoundResults(msg) {
  clearClientRoundTimers();
  document.getElementById("round-timer").style.display = "none";
  const stickyTimer = document.getElementById("sticky-timer");
  if (stickyTimer) stickyTimer.style.display = "none";
  document.getElementById("current-letter").innerHTML =
    globalThis.currentLetter || "?";
  const btnStop = document.getElementById("btn-stop");
  btnStop.innerHTML = "🛑 STOP!";
  btnStop.disabled = true;

  const isFinal = msg.final !== false;
  const isGameOver = Boolean(msg.game_over);

  if (isGameOver && isFinal) {
    hideRoundResultsOverlay();
    provisionalRoundResultsMsg = null;
    clearRoundResultsCountdown();
    updateScoreboard(msg.total_scores, msg.host_name, globalThis.myNick || "");
    const viewer = globalThis.myNick || myNick || "";
    const scores =
      msg.round_scores && typeof msg.round_scores === "object"
        ? msg.round_scores
        : {};
    if (scores[viewer]) highlightMyInputs(scores[viewer]);
    handleGameOver(msg.host_name, msg.room_id, msg);
    return;
  }

  showRoundResultsOverlay(buildRoundResultsHtml(msg, { variant: "overlay" }), {
    gameOver: false,
    provisional: !isFinal,
    vetoEndsAt: msg.veto_ends_at,
  });

  if (!isFinal) {
    provisionalRoundResultsMsg = { ...msg, final: false };
    updateScoreboard(msg.total_scores, msg.host_name, globalThis.myNick || "");
    return;
  }

  provisionalRoundResultsMsg = null;
  clearRoundResultsCountdown();
  updateScoreboard(msg.total_scores, msg.host_name, globalThis.myNick || "");
  const viewer = globalThis.myNick || myNick || "";
  const scores =
    msg.round_scores && typeof msg.round_scores === "object"
      ? msg.round_scores
      : {};
  if (scores[viewer]) highlightMyInputs(scores[viewer]);
}

function hideGameOverShare() {
  const share = document.getElementById("game-over-share");
  if (!share) return;
  share.style.display = "none";
  const copyBtn = document.getElementById("btn-copy-share");
  const nativeBtn = document.getElementById("btn-native-share");
  if (copyBtn) copyBtn.onclick = null;
  if (nativeBtn) {
    nativeBtn.onclick = null;
    nativeBtn.style.display = "none";
  }
}

/**
 * Udostępnianie wyniku (Faza 4): link do /share/{room_id}, kopiowanie, Web Share API.
 */
function wireGameOverShare(roomId) {
  hideGameOverShare();
  const rid = String(roomId || "").trim();
  if (!rid) return;
  const share = document.getElementById("game-over-share");
  const anchor = document.getElementById("share-link-anchor");
  const copyBtn = document.getElementById("btn-copy-share");
  const nativeBtn = document.getElementById("btn-native-share");
  if (!share || !anchor || !copyBtn) return;

  let base = "";
  try {
    base = globalThis.location.origin || "";
  } catch (e) {
    console.debug("pm: location.origin skipped", e);
  }
  const url = `${base}/share/${encodeURIComponent(rid)}`;
  anchor.href = url;

  copyBtn.onclick = async () => {
    try {
      await globalThis.navigator.clipboard.writeText(url);
      addLog("<em>Skopiowano link do schowka.</em>", "system-msg");
    } catch (e) {
      addLog(
        "<em>Nie udało się skopiować — otwórz link lub zaznacz go ręcznie.</em>",
        "system-msg",
      );
      console.warn("clipboard", e);
    }
  };

  if (nativeBtn && typeof globalThis.navigator?.share === "function") {
    nativeBtn.style.display = "inline-block";
    nativeBtn.onclick = () => {
      globalThis.navigator
        .share({
          title: "Państwa-Miasta — wynik",
          text: `Wynik pokoju ${rid}`,
          url,
        })
        .catch(() => {});
    };
  }

  share.style.display = "block";
}

function highlightMyInputs(rScore) {
  const inputs = document.querySelectorAll("#categories input");
  inputs.forEach((inp) => {
    const cat = inp.dataset.category;
    const pts = rScore.details[cat] || 0;
    // Czyścimy stare klasy
    inp.classList.remove(
      "pts-15",
      "pts-10",
      "pts-5",
      "pts-0",
      "success-10",
      "warning-5",
      "error-0",
    );

    if (pts === 15) inp.classList.add("pts-15");
    else if (pts === 10) inp.classList.add("pts-10");
    else if (pts === 5) inp.classList.add("pts-5");
    else if (inp.value.trim() !== "") inp.classList.add("pts-0");
  });
}

function handleGameOver(hostName, roomId, resultsMsg = null) {
  stopCelebrationEffects();
  hideRoundResultsOverlay();
  addLog(
    `<div style="margin-top:1rem; font-weight:800; color:var(--pts-15); text-align:center;">🏁 KONIEC GRY!</div>`,
    "system-msg",
  );

  if (typeof setRoomPhase === "function") setRoomPhase("results");

  const chatSection = document.getElementById("chat-section");
  if (chatSection) chatSection.hidden = false;

  const gameLayout = document.getElementById("game-layout");
  if (gameLayout) gameLayout.classList.add("game-over");

  const gameMain = document.getElementById("game-main-area");
  if (gameMain) gameMain.style.display = "none";

  const postgame = document.getElementById("room-postgame");
  if (postgame) postgame.hidden = false;

  const restartArea = document.getElementById("restart-settings");
  if (restartArea) restartArea.style.display = "block";

  if (myNick === hostName) {
    document.getElementById("btn-restart-game").style.display = "block";
    document.getElementById("btn-restart-defaults").style.display = "block";
  }
  // Wyjdz z pokoju always visible for everyone

  fireConfetti({ particleCount: 200, spread: 100, origin: { y: 0.3 } });
  setTimeout(
    () => fireConfetti({ particleCount: 200, spread: 120, origin: { y: 0.4 } }),
    1000,
  );

  renderGameOverResults(resultsMsg);
  wireGameOverShare(roomId);
}

function resetReadyButton() {
  const btn = document.getElementById("btn-draw");
  btn.classList.remove("ready");
  btn.innerHTML = "👍 Gotowy";
  btn.style.backgroundColor = "var(--primary)";
  btn.style.display = "block";
  if (typeof setRoomPhase === "function") setRoomPhase("playing");
}

function onGameRestarted(msg) {
  hideGameOverShare();
  hideRoundResultsOverlay();
  clearGameOverResults();
  document.getElementById("game-layout")?.classList.remove("game-over");
  document.getElementById("game-main-area").style.display = "block";
  document.getElementById("chat-sidebar")?.classList.remove("hidden");
  const postgame = document.getElementById("room-postgame");
  if (postgame) postgame.hidden = true;
  const restartArea = document.getElementById("restart-settings");
  if (restartArea) restartArea.style.display = "none";
  if (typeof setRoomPhase === "function") setRoomPhase("lobby");

  const btn = document.getElementById("btn-draw");
  btn.style.display = "inline-block";
  btn.classList.remove("ready");
  btn.innerHTML = "👍 Gotowy";
  btn.style.backgroundColor = "var(--primary)";
  document.getElementById("current-letter").innerHTML = "?";
  updateScoreboard(msg.scores, msg.host_name, globalThis.myNick || "");
  const inputs = document.querySelectorAll("#categories input");
  inputs.forEach((inp) => {
    inp.value = "";
    inp.disabled = true;
    inp.classList.remove(
      "error",
      "pts-15",
      "pts-10",
      "pts-5",
      "pts-0",
      "success-10",
      "warning-5",
      "error-0",
    );
  });
  cleanupCustomCategoryFields();
  addLog(
    `<em>Gospodarz <strong>${msg.sender}</strong> zrestartował grę z nowymi ustawieniami! Wyniki zostały wyzerowane.</em>`,
    "system-msg",
  );
}

function clearInputColors() {
  const inputs = document.querySelectorAll("#categories input");
  inputs.forEach((inp) => {
    inp.classList.remove(
      "pts-15",
      "pts-10",
      "pts-5",
      "pts-0",
      "success-10",
      "warning-5",
      "error-0",
    );
  });
}

/**
 * Odliczanie 3–2–1 przed animacją losowania litery (Faza 3). Przy ``prefers-reduced-motion`` pomija.
 */
function runRoundStartCountdown(onComplete) {
  if (typeof onComplete !== "function") return;
  if (globalThis.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches) {
    onComplete();
    return;
  }
  const overlay = document.getElementById("round-countdown-overlay");
  const numEl = document.getElementById("round-countdown-num");
  if (!overlay || !numEl) {
    onComplete();
    return;
  }
  overlay.removeAttribute("hidden");
  overlay.setAttribute("aria-hidden", "false");
  const labels = ["3", "2", "1"];
  let step = 0;
  const INTER_MS = 720;
  const tick = () => {
    if (step < labels.length) {
      numEl.textContent = labels[step];
      if (typeof globalThis.playCountdownHaptic === "function") {
        globalThis.playCountdownHaptic();
      }
      step += 1;
      globalThis.setTimeout(tick, INTER_MS);
      return;
    }
    numEl.textContent = "";
    overlay.setAttribute("hidden", "");
    overlay.setAttribute("aria-hidden", "true");
    onComplete();
  };
  tick();
}

function runLetterLottery(targetLetter, onComplete) {
  const modal = document.getElementById("lottery-modal");
  const letterDiv = document.getElementById("lottery-letter");
  const alphabet = "ABCDEFGHIJKLMNOPRSTUWZ";
  modal.style.display = "flex";
  let duration = 2500;
  let intervalTime = 50;
  let elapsed = 0;
  const interval = setInterval(() => {
    elapsed += intervalTime;
    const array = new Uint32Array(1);
    globalThis.crypto.getRandomValues(array);
    const randomLetter = alphabet[array[0] % alphabet.length];
    letterDiv.innerText = randomLetter;
    letterDiv.style.filter = `blur(${Math.max(0, 5 - (elapsed / duration) * 5)}px)`;
    if (elapsed >= duration) {
      clearInterval(interval);
      letterDiv.innerText = targetLetter;
      letterDiv.style.filter = "none";
      letterDiv.style.transform = "scale(1.2)";
      letterDiv.style.color = "var(--success)";
      playRoundStartReveal();
      if (typeof playLotteryRevealHaptic === "function")
        playLotteryRevealHaptic();
      fireConfetti({ particleCount: 100, spread: 70, origin: { y: 0.6 } });
      setTimeout(() => {
        modal.style.display = "none";
        letterDiv.style.transform = "scale(1)";
        letterDiv.style.color = "var(--accent)";
        if (onComplete) onComplete();
      }, 1500);
    } else {
      playLotterySpinTick(elapsed, duration);
      if (elapsed % 100 === 0 && typeof playLotterySpinHaptic === "function") {
        playLotterySpinHaptic();
      }
    }
  }, intervalTime);
}

globalThis.stopCelebrationEffects = stopCelebrationEffects;

if (typeof module !== "undefined") {
  module.exports = {
    leaveRoom,
    connect,
    onRoundStarted,
    onStopRound,
    getScoreColor,
    escapeHtml,
    isWideRoundResultsLayout,
    buildPlayerResultHtml,
    buildRoundResultsHtml,
    buildGameOverResultsHtml,
    renderGameOverResults,
    clearGameOverResults,
    showRoundResultsOverlay,
    hideRoundResultsOverlay,
    onRoundResults,
    highlightMyInputs,
    handleGameOver,
    hideGameOverShare,
    wireGameOverShare,
    resetReadyButton,
    onGameRestarted,
    runRoundStartCountdown,
    runLetterLottery,
    sendJson,
  };
}
