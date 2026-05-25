// Funkcje pomocnicze UI
const PM_NICK_KEY = "pm_nickname";
const PM_NICK_CUSTOM_KEY = "pm_nickname_custom";
const PM_AUTO_JOIN_KEY = "pm_room_autojoin";
const PM_NICK_MAX_LENGTH = 16;
const AUTO_NICK_RE = /^Gracz#\d{4}$/;

function clampNickname(value) {
  return String(value ?? "")
    .trim()
    .slice(0, PM_NICK_MAX_LENGTH);
}

function showJoinModal() {
  document.getElementById("join-modal").style.display = "flex";
  preparePlayNickname();
}

function showCreateModal() {
  const landingNick = document.getElementById("landing_nickname")?.value.trim();
  if (landingNick) syncNicknameInputs(landingNick);
  document.getElementById("create-modal").style.display = "flex";
  preparePlayNickname();
}

function showLandingJoinCode() {
  const start = document.getElementById("landing-anon-start");
  const join = document.getElementById("landing-anon-join");
  const actions = document.getElementById("landing-anon-actions");
  if (!start || !join) return;
  const landingNick = document.getElementById("landing_nickname")?.value.trim();
  if (landingNick) syncNicknameInputs(landingNick);
  preparePlayNickname();
  start.hidden = true;
  join.hidden = false;
  if (actions) actions.hidden = true;
  document.getElementById("landing_room_code")?.focus();
}

function showLandingStartMode() {
  const start = document.getElementById("landing-anon-start");
  const join = document.getElementById("landing-anon-join");
  const actions = document.getElementById("landing-anon-actions");
  if (!start || !join) return;
  join.hidden = true;
  start.hidden = false;
  if (actions) actions.hidden = false;
}

function syncRoomCodeInputs(value) {
  const landing = document.getElementById("landing_room_code");
  const modal = document.getElementById("room_id");
  const next = String(value ?? landing?.value ?? modal?.value ?? "").trim();
  if (landing) landing.value = next;
  if (modal) modal.value = next;
  return next;
}

function bindRoomCodeInputs() {
  const bind = (input, onEnter) => {
    if (!input || input.dataset.pmRoomBound) return;
    input.dataset.pmRoomBound = "1";
    input.addEventListener("input", () => {
      syncRoomCodeInputs(input.value);
    });
    if (onEnter) {
      input.addEventListener("keydown", (event) => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        onEnter();
      });
    }
  };
  bind(document.getElementById("landing_room_code"), connectFromLandingJoin);
  bind(document.getElementById("room_id"));
}

function connectFromLandingJoin() {
  syncRoomCodeInputs();
  const landingNick = document.getElementById("landing_nickname")?.value.trim();
  if (landingNick) syncNicknameInputs(landingNick);
  preparePlayNickname();
  if (typeof globalThis.connect === "function") globalThis.connect();
}

async function quickJoinFromLanding() {
  const landingNick = document.getElementById("landing_nickname")?.value.trim();
  if (landingNick) syncNicknameInputs(landingNick);
  preparePlayNickname();
  const nick = getResolvedNickname();
  if (!nick) {
    alert("Podaj pseudonim przed szybką grą.");
    return;
  }
  persistNickname(nick);

  const requestQuickJoin = async () => {
    const resp = await fetch("/api/quick-join", { method: "POST" });
    if (!resp.ok) {
      throw new Error(`quick-join failed: ${resp.status}`);
    }
    return resp.json();
  };

  try {
    let data = await requestQuickJoin();
    const roomId = String(data.room_id || "").trim();
    if (!roomId) throw new Error("quick-join missing room_id");
    const landingCode = document.getElementById("landing_room_code");
    if (landingCode) landingCode.value = roomId;
    markRoomAutoJoinIntent();
    globalThis.location.href = `/room/${encodeURIComponent(roomId)}`;
  } catch (err) {
    console.error("quickJoinFromLanding failed:", err);
    alert("Nie udało się znaleźć pokoju. Spróbuj ponownie.");
  }
}

async function createRoomAndEnter() {
  const landingNick = document.getElementById("landing_nickname")?.value.trim();
  if (landingNick) syncNicknameInputs(landingNick);
  preparePlayNickname();
  const nick = getResolvedNickname();
  if (!nick) {
    alert("Podaj pseudonim przed utworzeniem pokoju.");
    return;
  }
  persistNickname(nick);

  try {
    const resp = await fetch("/api/rooms", { method: "POST" });
    if (!resp.ok) {
      throw new Error(`create-room failed: ${resp.status}`);
    }
    const data = await resp.json();
    const roomId = String(data.room_id || "").trim();
    if (!roomId) throw new Error("create-room missing room_id");
    hideModals();
    markRoomAutoJoinIntent();
    globalThis.location.href = `/room/${encodeURIComponent(roomId)}`;
  } catch (err) {
    console.error("createRoomAndEnter failed:", err);
    alert("Nie udało się utworzyć pokoju. Spróbuj ponownie.");
  }
}

function hideModals() {
  document.getElementById("join-modal").style.display = "none";
  document.getElementById("create-modal").style.display = "none";
  document.getElementById("lottery-modal").style.display = "none";
}

function focusStartPanel() {
  const lobby = document.getElementById("lobby");
  if (lobby) {
    lobby.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

function generatePlayerNickname() {
  const array = new Uint32Array(1);
  globalThis.crypto.getRandomValues(array);
  const number = 1000 + (array[0] % 9000);
  return `Gracz#${number}`;
}

function isCustomNickStored() {
  return localStorage.getItem(PM_NICK_CUSTOM_KEY) === "1";
}

function readStoredNickname() {
  return localStorage.getItem(PM_NICK_KEY)?.trim() || "";
}

function markNicknameCustom() {
  localStorage.setItem(PM_NICK_CUSTOM_KEY, "1");
}

function clearNicknameCustom() {
  localStorage.removeItem(PM_NICK_CUSTOM_KEY);
}

function persistNickname(nick) {
  const normalized = clampNickname(nick);
  localStorage.setItem(PM_NICK_KEY, normalized);
  if (AUTO_NICK_RE.test(normalized)) clearNicknameCustom();
  else markNicknameCustom();
  return normalized;
}

function syncNicknameInputs(value) {
  const normalized = clampNickname(value);
  const createInput = document.getElementById("nickname");
  const joinInput = document.getElementById("nickname_join");
  const landingInput = document.getElementById("landing_nickname");
  if (createInput) createInput.value = normalized;
  if (joinInput) joinInput.value = normalized;
  if (landingInput) landingInput.value = normalized;
  return normalized;
}

function ensureNicknameInput() {
  const input =
    document.getElementById("nickname") ||
    document.getElementById("nickname_join") ||
    document.getElementById("landing_nickname");
  if (!input) return readStoredNickname() || null;

  const current = clampNickname(input.value);
  if (current) {
    syncNicknameInputs(current);
    return current;
  }

  const stored = clampNickname(readStoredNickname());
  if (stored) {
    syncNicknameInputs(stored);
    return stored;
  }

  const nick = generatePlayerNickname();
  syncNicknameInputs(nick);
  return nick;
}

function rerollPlayerNickname() {
  const nick = generatePlayerNickname();
  syncNicknameInputs(nick);
  clearNicknameCustom();
  return nick;
}

function bindNicknameInputs() {
  const bind = (input) => {
    if (!input || input.dataset.pmBound) return;
    input.dataset.pmBound = "1";
    input.addEventListener("input", () => {
      const val = clampNickname(input.value);
      if (!val) return;
      syncNicknameInputs(val);
      if (!AUTO_NICK_RE.test(val)) markNicknameCustom();
    });
  };
  bind(document.getElementById("nickname"));
  bind(document.getElementById("nickname_join"));
  bind(document.getElementById("landing_nickname"));
}

function preparePlayNickname() {
  ensureNicknameInput();
  bindNicknameInputs();
}

function getResolvedNickname() {
  preparePlayNickname();
  const joinInput = document.getElementById("nickname_join");
  const createInput = document.getElementById("nickname");
  const landingInput = document.getElementById("landing_nickname");
  const joinModalOpen =
    document.getElementById("join-modal")?.style.display === "flex";
  const fromJoin = joinInput?.value.trim() || "";
  const fromCreate = createInput?.value.trim() || "";
  const fromLanding = landingInput?.value.trim() || "";
  if (joinModalOpen)
    return clampNickname(fromJoin || fromCreate || fromLanding);
  return clampNickname(fromCreate || fromJoin || fromLanding);
}

function syncLandingScrollLock() {
  const body = document.body;
  if (!body.classList.contains("landing-page")) return;

  const tableWrap = document.getElementById("active-rooms-table-wrap");
  const cardsWrap = document.getElementById("active-rooms-cards-wrap");
  const roomsOpen = Boolean(
    (tableWrap && !tableWrap.hidden) || (cardsWrap && !cardsWrap.hidden),
  );

  body.classList.toggle("landing-scrollable", roomsOpen);
}

function prefersReducedMotion() {
  return Boolean(
    globalThis.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches,
  );
}

function initLandingGuideCarousel() {
  const root = document.querySelector(".landing-guide-carousel");
  const track = document.getElementById("landing-guide-carousel-track");
  const dotsRoot = document.getElementById("landing-guide-carousel-dots");
  const live = document.getElementById("landing-guide-carousel-live");
  if (!root || !track || !dotsRoot) return;

  const slides = Array.from(
    track.querySelectorAll(".landing-guide-carousel-slide"),
  );
  if (slides.length === 0) return;

  let activeIndex = 0;

  const announce = (index) => {
    const slide = slides[index];
    if (!slide || !live) return;
    const title = slide
      .querySelector(".landing-guide-carousel-slide-title")
      ?.textContent?.trim();
    if (title) live.textContent = `Slajd: ${title}`;
  };

  const setActive = (index) => {
    activeIndex = (index + slides.length) % slides.length;
    track.style.transform = `translateX(-${activeIndex * 100}%)`;
    slides.forEach((slide, i) => {
      slide.setAttribute("aria-hidden", i === activeIndex ? "false" : "true");
    });
    dotsRoot.querySelectorAll('[role="tab"]').forEach((dot, i) => {
      dot.setAttribute("aria-selected", i === activeIndex ? "true" : "false");
      dot.tabIndex = i === activeIndex ? 0 : -1;
    });
    announce(activeIndex);
  };

  dotsRoot.innerHTML = "";
  slides.forEach((slide, index) => {
    const title =
      slide
        .querySelector(".landing-guide-carousel-slide-title")
        ?.textContent?.trim() || `Slajd ${index + 1}`;
    const dot = document.createElement("button");
    dot.type = "button";
    dot.className = "landing-guide-carousel-dot";
    dot.setAttribute("role", "tab");
    dot.setAttribute("aria-label", title);
    dot.addEventListener("click", () => setActive(index));
    dotsRoot.appendChild(dot);
  });

  root.querySelectorAll("[data-carousel-dir]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const dir = btn.dataset.carouselDir;
      setActive(activeIndex + (dir === "prev" ? -1 : 1));
    });
  });

  root.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      setActive(activeIndex - 1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      setActive(activeIndex + 1);
    }
  });

  if (!prefersReducedMotion()) {
    track.style.transition = "transform 0.35s ease";
  }

  setActive(0);
}

const LANDING_GUIDE_MOBILE_QUERY = globalThis.matchMedia?.(
  "(max-width: 1023px)",
);

function landingGuideSheetEnabled() {
  return Boolean(LANDING_GUIDE_MOBILE_QUERY?.matches);
}

function syncLandingGuideSheetState(root, openBtn, expanded) {
  document.body.classList.toggle("landing-guide-open", expanded);
  openBtn?.setAttribute("aria-expanded", expanded ? "true" : "false");
  if (landingGuideSheetEnabled()) {
    root?.setAttribute("aria-hidden", expanded ? "false" : "true");
  } else {
    root?.removeAttribute("aria-hidden");
  }
}

function initLandingGuideMobileSheet() {
  const openBtn = document.getElementById("landing-guide-open");
  const closeBtn = document.querySelector(".landing-guide-close");
  const root =
    document.getElementById("guide") ||
    document.querySelector(".landing-guide-carousel");
  if (!openBtn || !root) return;

  const applyLayoutMode = () => {
    if (landingGuideSheetEnabled()) {
      const expanded = document.body.classList.contains("landing-guide-open");
      syncLandingGuideSheetState(root, openBtn, expanded);
    } else {
      syncLandingGuideSheetState(root, openBtn, false);
    }
  };

  const openGuide = () => {
    if (!landingGuideSheetEnabled()) return;
    syncLandingGuideSheetState(root, openBtn, true);
    closeBtn?.focus();
  };

  const closeGuide = () => {
    if (!landingGuideSheetEnabled()) return;
    syncLandingGuideSheetState(root, openBtn, false);
    openBtn.focus();
  };

  openBtn.addEventListener("click", openGuide);
  closeBtn?.addEventListener("click", closeGuide);

  root.addEventListener("click", (event) => {
    if (!landingGuideSheetEnabled() || event.target !== root) return;
    closeGuide();
  });

  root.addEventListener("keydown", (event) => {
    if (
      !landingGuideSheetEnabled() ||
      !document.body.classList.contains("landing-guide-open")
    )
      return;
    if (event.key === "Escape") {
      event.preventDefault();
      closeGuide();
    }
  });

  LANDING_GUIDE_MOBILE_QUERY?.addEventListener?.("change", applyLayoutMode);
  applyLayoutMode();
}

function addLog(content, className = "") {
  const logs = document.getElementById("logs");
  if (!logs) return;

  const entry = document.createElement("div");
  entry.className = `log-entry ${className || ""}`.trim();

  if (content instanceof HTMLElement) {
    entry.appendChild(content);
  } else {
    entry.innerHTML = String(content ?? "");
  }

  logs.appendChild(entry);
  logs.scrollTop = logs.scrollHeight;
}

let lastLobbyRosterState = {
  scores: {},
  hostName: "",
  readyPlayers: new Set(),
  viewerNick: "",
  connectedPlayers: null,
  disconnectedPlayers: new Set(),
};

function resetLobbyRosterState() {
  lastLobbyRosterState = {
    scores: {},
    hostName: "",
    readyPlayers: new Set(),
    viewerNick: "",
    connectedPlayers: null,
    disconnectedPlayers: new Set(),
  };
}

function renderLobbyState(m) {
  if (!m || !Array.isArray(m.ready_players)) return;
  const { scores, hostName, viewerNick } = lastLobbyRosterState;
  const readySet = new Set(m.ready_players);
  const connectedSet = Array.isArray(m.connected_players)
    ? new Set(m.connected_players)
    : null;
  const disconnectedSet = Array.isArray(m.disconnected_players)
    ? new Set(m.disconnected_players)
    : new Set();
  lastLobbyRosterState.disconnectedPlayers = disconnectedSet;
  renderLobbyRoster(
    scores,
    hostName,
    readySet,
    viewerNick,
    connectedSet,
    disconnectedSet,
  );
}

function updateScoreboard(
  scores = {},
  hostName = "",
  viewerNick = "",
  readyPlayers = null,
  connectedPlayers = null,
  disconnectedPlayers = null,
) {
  const scoreboard = document.getElementById("scoreboard");
  const lobbyRoster = document.getElementById("lobby-roster");
  const readySet = Array.isArray(readyPlayers)
    ? new Set(readyPlayers)
    : new Set();
  const connectedSet = Array.isArray(connectedPlayers)
    ? new Set(connectedPlayers)
    : null;
  const resolvedViewer = viewerNick || globalThis.myNick || "";
  // disconnectedPlayers nie przychodzi z score_update — uzyj ostatniego
  // znanego stanu z lobby_state (#7-ui-player-status)
  let discoSet;
  if (disconnectedPlayers === null) {
    discoSet = lastLobbyRosterState.disconnectedPlayers;
  } else {
    discoSet = Array.isArray(disconnectedPlayers)
      ? new Set(disconnectedPlayers)
      : new Set();
  }

  lastLobbyRosterState = {
    scores,
    hostName,
    readyPlayers: readySet,
    viewerNick: resolvedViewer,
    connectedPlayers: connectedSet,
    disconnectedPlayers: discoSet,
  };

  if (lobbyRoster && document.body.classList.contains("room-phase-lobby")) {
    renderLobbyRoster(
      scores,
      hostName,
      readySet,
      resolvedViewer,
      connectedSet,
      discoSet,
    );
  }

  if (!scoreboard) return;

  const viewer = viewerNick || globalThis.myNick || "";

  scoreboard.innerHTML = "";

  const entries = Object.entries(scores).sort(
    (a, b) => Number(b[1]) - Number(a[1]),
  );

  if (entries.length === 0) {
    const empty = document.createElement("div");
    empty.className = "score-item";
    empty.style.opacity = "0.6";
    empty.innerHTML = "<span>Czekamy na graczy…</span><strong>—</strong>";
    scoreboard.appendChild(empty);
    return;
  }

  entries.forEach(([name, points]) => {
    const row = document.createElement("div");
    row.className = "score-item";
    if (hostName && name === hostName) row.classList.add("is-host");

    const left = document.createElement("div");
    left.className = "score-item-left";

    const nameSpan = document.createElement("span");
    if (name === hostName) {
      const crown = document.createElement("span");
      crown.className = "crown";
      crown.textContent = "👑";
      nameSpan.appendChild(crown);
    }
    nameSpan.appendChild(document.createTextNode(name));

    left.appendChild(nameSpan);

    const canKick =
      hostName &&
      viewer &&
      viewer === hostName &&
      name !== viewer &&
      typeof sendJson === "function";
    if (canKick) {
      const kickBtn = document.createElement("button");
      kickBtn.type = "button";
      kickBtn.className = "btn-kick";
      kickBtn.setAttribute("aria-label", `Wyrzuć gracza ${name} z pokoju`);
      kickBtn.textContent = "Wyrzuć";
      kickBtn.addEventListener("click", () => {
        if (!globalThis.confirm(`Wyrzucić ${name} z pokoju?`)) return;
        sendJson({ type: "kick_player", target: name });
      });
      left.appendChild(kickBtn);
    }

    const pts = document.createElement("strong");
    pts.textContent = `${Number(points) || 0} pkt`;

    row.appendChild(left);
    row.appendChild(pts);
    scoreboard.appendChild(row);
  });
}

function createLobbyAvatar(name, viewerNick = "") {
  const el = document.createElement("span");
  el.className = "lobby-roster-avatar";
  el.textContent = ((name && name.trim()[0]) || "?").toUpperCase();
  return el;
}

const MAX_LOBBY_SLOTS = 8;

function renderLobbyRoster(
  scores = {},
  hostName = "",
  readyPlayers = new Set(),
  viewerNick = "",
  connectedPlayers = null,
  disconnectedPlayers = new Set(),
) {
  const roster = document.getElementById("lobby-roster");
  if (!roster) return;

  roster.innerHTML = "";
  const rosterNames = connectedPlayers
    ? [...connectedPlayers].filter((name) => Object.hasOwn(scores, name))
    : Object.keys(scores);
  const countEl = document.getElementById("lobby-player-count");
  if (countEl) {
    if (rosterNames.length === 0) {
      countEl.textContent = `0/${MAX_LOBBY_SLOTS}`;
    } else {
      const readyCount = rosterNames.filter((name) =>
        readyPlayers.has(name),
      ).length;
      const disconnectedCount = [...disconnectedPlayers].filter((name) =>
        rosterNames.includes(name),
      ).length;
      const discoSuffix =
        disconnectedCount > 0 ? ` · ${disconnectedCount} rozłączonych` : "";
      countEl.textContent = `${rosterNames.length}/${MAX_LOBBY_SLOTS} · ${readyCount} gotowych${discoSuffix}`;
    }
  }

  const allNames = [
    ...new Set([...rosterNames, ...disconnectedPlayers]),
  ].filter((name) => Object.hasOwn(scores, name));

  const slots = Array.from(
    { length: MAX_LOBBY_SLOTS },
    (_, index) => allNames[index] || null,
  );
  slots.forEach((name) => {
    const row = document.createElement("div");
    row.className = "lobby-roster-item";
    if (!name) {
      row.classList.add("lobby-roster-item--empty");
      const placeholder = document.createElement("span");
      placeholder.className = "lobby-roster-empty-slot";
      placeholder.textContent = "Wolne";
      row.appendChild(placeholder);
      roster.appendChild(row);
      return;
    }

    if (hostName && name === hostName) row.classList.add("is-host");
    if (disconnectedPlayers.has(name)) row.classList.add("is-disconnected");

    const nameSpan = document.createElement("span");
    nameSpan.className = "lobby-roster-name";
    if (name === hostName) {
      const crown = document.createElement("span");
      crown.className = "crown";
      crown.textContent = "👑";
      nameSpan.appendChild(crown);
    }
    nameSpan.appendChild(document.createTextNode(name));
    nameSpan.title = name;

    const identity = document.createElement("div");
    identity.className = "lobby-roster-identity";
    identity.appendChild(createLobbyAvatar(name, viewerNick));
    identity.appendChild(nameSpan);

    const status = document.createElement("span");
    status.className = "lobby-roster-status";
    if (readyPlayers.has(name)) status.classList.add("is-ready");
    if (disconnectedPlayers.has(name)) {
      status.textContent = "Rozłączony";
      status.classList.add("is-disconnected");
    } else {
      status.textContent = readyPlayers.has(name) ? "Gotowy" : "Czeka";
    }

    row.appendChild(identity);
    row.appendChild(status);
    roster.appendChild(row);
  });
}

function setRoomPhase(phase) {
  const allowed = new Set(["lobby", "playing", "results", "round_results"]);
  const next = allowed.has(phase) ? phase : "playing";
  document.body.classList.remove(
    "room-phase-lobby",
    "room-phase-playing",
    "room-phase-results",
    "room-phase-round_results",
  );
  document.body.classList.add(`room-phase-${next}`);

  const lobby = document.getElementById("room-lobby");
  const gameMain = document.getElementById("game-main-area");
  const readyBtn = document.getElementById("btn-draw");
  const lobbyActions = document.querySelector(".room-lobby-actions");
  const gameActions = document.querySelector(".game-actions");
  const chatSection = document.getElementById("chat-section");

  if (lobby) lobby.hidden = next !== "lobby";
  if (gameMain) gameMain.hidden = next === "lobby" || next === "round_results";
  if (chatSection) chatSection.hidden = next === "round_results";

  const gameLayout = document.getElementById("game-layout");
  const postgame = document.getElementById("room-postgame");
  if (gameLayout)
    gameLayout.hidden = next === "lobby" || next === "round_results";
  if (postgame && next !== "results") postgame.hidden = true;

  if (readyBtn && lobbyActions && gameActions) {
    if (next === "lobby") {
      lobbyActions.appendChild(readyBtn);
      readyBtn.style.display = "inline-flex";
    } else if (!gameActions.contains(readyBtn)) {
      gameActions.insertBefore(readyBtn, gameActions.firstChild);
    }
  }

  if (next === "lobby") {
    const { scores, hostName, readyPlayers, viewerNick, connectedPlayers } =
      lastLobbyRosterState;
    renderLobbyRoster(
      scores,
      hostName,
      readyPlayers,
      viewerNick,
      connectedPlayers,
    );

    // Host vs non-host panel visibility
    const configPanel = document.getElementById("lobby-config-panel");
    const configInfo = document.getElementById("lobby-config-info");
    const startBtn = document.getElementById("lobby-start-game");
    const isHost = globalThis.myNick === hostName;
    if (configPanel) configPanel.style.display = isHost ? "" : "none";
    if (configInfo) configInfo.style.display = isHost ? "none" : "";
    if (startBtn) startBtn.style.display = isHost ? "" : "none";

    // Swap chat send button to use lobby chat
    const sendBtn = document.querySelector(".game-chat-send");
    if (sendBtn) {
      sendBtn.onclick = sendLobbyChat;
    }
  } else {
    // Restore game chat send
    const sendBtn = document.querySelector(".game-chat-send");
    if (sendBtn) {
      sendBtn.onclick = sendChat;
    }
  }
}

function readRoomSettingsFromUrl() {
  // Deprecated: settings are no longer passed via URL
  return { rounds: "5", limit: "90", visibility: "Publiczny" };
}

function syncRoomLobbySettings(roomId = "") {
  const codeEl = document.getElementById("lobby-room-code");
  const roundsEl = document.getElementById("lobby-room-rounds");
  const limitEl = document.getElementById("lobby-room-limit");
  const visEl = document.getElementById("lobby-room-visibility");
  if (codeEl) codeEl.textContent = roomId || "—";
  if (roundsEl) roundsEl.textContent = "5";
  if (limitEl) limitEl.textContent = "90s";
  if (visEl) visEl.textContent = "Publiczny";
  if (typeof bindLobbyConfigEvents === "function") {
    bindLobbyConfigEvents();
  }
}

function updateLobbyConfig() {
  const rounds = Number(document.getElementById("lobby_rounds")?.value || 5);
  const limit = Number(
    document.getElementById("lobby_time_limit")?.value || 90,
  );
  const visibility =
    document.getElementById("lobby_visibility")?.value || "public";
  const stopEnabled =
    document.getElementById("lobby_stop_mechanism")?.checked || false;

  if (typeof sendJson === "function") {
    sendJson({
      type: "lobby_config_update",
      rounds,
      limit,
      visibility,
      stop_mechanism: stopEnabled,
    });
    addLog("<em>Ustawienia zapisane.</em>", "system-msg");
  }
}

function updateLobbyConfigUI(data) {
  const roundsEl = document.getElementById("lobby_rounds");
  const limitEl = document.getElementById("lobby_time_limit");
  const visibilityEl = document.getElementById("lobby_visibility");
  const stopEl = document.getElementById("lobby_stop_mechanism");
  const roundsDetail = document.getElementById("lobby-room-rounds");
  const limitDetail = document.getElementById("lobby-room-limit");
  const visDetail = document.getElementById("lobby-room-visibility");

  if (roundsEl) roundsEl.value = String(data.rounds ?? 5);
  if (limitEl) limitEl.value = String(data.limit ?? 90);
  if (visibilityEl) visibilityEl.value = data.visibility ?? "public";
  if (stopEl) stopEl.checked = data.stop_mechanism ?? true;

  if (roundsDetail) roundsDetail.textContent = String(data.rounds ?? 5);
  if (limitDetail) limitDetail.textContent = `${data.limit ?? 90}s`;
  if (visDetail)
    visDetail.textContent =
      data.visibility === "private" ? "Prywatny" : "Publiczny";

  // Host vs non-host panel visibility
  const configPanel = document.getElementById("lobby-config-panel");
  const configInfo = document.getElementById("lobby-config-info");
  const isHost = globalThis.myNick === lastLobbyRosterState.hostName;
  if (configPanel) configPanel.style.display = isHost ? "" : "none";
  if (configInfo) configInfo.style.display = isHost ? "none" : "";
}

async function copyRoomInviteLink() {
  const roomId =
    document.getElementById("current-room")?.textContent?.trim() || "";
  if (!roomId) return;
  const url = `${globalThis.location.origin}/room/${encodeURIComponent(roomId)}`;
  try {
    await globalThis.navigator.clipboard.writeText(url);
    addLog("<em>Skopiowano link do pokoju.</em>", "system-msg");
  } catch (e) {
    console.warn("clipboard", e);
    addLog("<em>Nie udało się skopiować linku.</em>", "system-msg");
  }
}

function sendChat() {
  const input = document.getElementById("message-input");
  if (!input) return;

  const text = input.value.trim();
  if (!text) return;

  if (typeof sendJson === "function") {
    sendJson({ type: "chat", text });
    input.value = "";
    if (
      typeof globalThis.stopCelebrationEffects === "function" &&
      (document.body.classList.contains("room-phase-results") ||
        document.body.classList.contains("room-phase-round_results"))
    ) {
      globalThis.stopCelebrationEffects();
    }
  }
}

function sendLobbyChat() {
  const input = document.getElementById("message-input");
  if (!input) return;
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  if (typeof sendJson === "function") {
    sendJson({ type: "lobby_chat_msg", text });
  }
}

function appendChatMessage(sender, text) {
  const container = document.createElement("div");
  const senderDiv = document.createElement("div");
  senderDiv.className = "sender";
  senderDiv.textContent = sender;
  const textDiv = document.createElement("div");
  textDiv.textContent = text;
  container.appendChild(senderDiv);
  container.appendChild(textDiv);
  addLog(container, "");
}

function escapeLandingText(text) {
  if (text == null || text === "") return "";
  const node = document.createElement("div");
  node.textContent = String(text);
  return node.innerHTML;
}

function roomVisibilityLabel(room) {
  return (
    room.visibility_label ||
    (room.visibility === "private" ? "Prywatny" : "Publiczny")
  );
}

function buildRoomRow(room) {
  const visLabel = roomVisibilityLabel(room);
  const tr = document.createElement("tr");
  tr.innerHTML = `
        <td style="font-weight:800; color:var(--accent);">${escapeLandingText(room.id)}</td>
        <td>${escapeLandingText(room.host || "Anonim")}</td>
        <td><span class="badge badge-rules">${escapeLandingText(room.players)} graczy</span></td>
        <td>${escapeLandingText(room.current_round)}/${escapeLandingText(room.max_rounds)}</td>
        <td><span class="badge badge-rules">${escapeLandingText(room.time_limit)}s</span></td>
        <td><span class="badge badge-mode">${escapeLandingText(visLabel)}</span></td>
        <td>
            <button type="button" class="btn-join-small" data-room-id="${escapeLandingText(room.id)}">DOŁĄCZ</button>
        </td>
    `;
  tr.querySelector(".btn-join-small")?.addEventListener("click", () => {
    globalThis.joinRoom(room.id);
  });
  return tr;
}

function buildRoomCard(room) {
  const visLabel = roomVisibilityLabel(room);
  const li = document.createElement("li");
  li.className = "active-rooms-card";
  li.innerHTML = `
        <div class="active-rooms-card-head">
            <span class="active-rooms-card-code">${escapeLandingText(room.id)}</span>
            <span class="active-rooms-card-host">${escapeLandingText(room.host || "Anonim")}</span>
        </div>
        <div class="active-rooms-card-meta">
            <span class="badge badge-rules">${escapeLandingText(room.players)} graczy</span>
            <span class="badge badge-rules">${escapeLandingText(room.current_round)}/${escapeLandingText(room.max_rounds)} rund</span>
            <span class="badge badge-rules">${escapeLandingText(room.time_limit)}s</span>
            <span class="badge badge-mode">${escapeLandingText(visLabel)}</span>
        </div>
        <button type="button" class="btn-join-small active-rooms-card-join" data-room-id="${escapeLandingText(room.id)}">Dołącz</button>
    `;
  li.querySelector(".active-rooms-card-join")?.addEventListener("click", () => {
    globalThis.joinRoom(room.id);
  });
  return li;
}

function setActiveRoomsView(hasRooms) {
  const empty = document.getElementById("active-rooms-empty");
  const tableWrap = document.getElementById("active-rooms-table-wrap");
  const cardsWrap = document.getElementById("active-rooms-cards-wrap");
  if (empty) empty.hidden = hasRooms;
  if (tableWrap) tableWrap.hidden = !hasRooms;
  if (cardsWrap) cardsWrap.hidden = !hasRooms;
  syncLandingScrollLock();
}

function renderActiveRooms(rooms) {
  const list = document.getElementById("rooms-list");
  const cards = document.getElementById("active-rooms-cards-wrap");
  const section = document.getElementById("active-rooms-section");

  const hasRooms = Array.isArray(rooms) && rooms.length > 0;
  if (section) section.hidden = false;
  setActiveRoomsView(hasRooms);
  if (!hasRooms) {
    if (list) list.innerHTML = "";
    if (cards) cards.innerHTML = "";
    return;
  }

  if (list) {
    list.innerHTML = "";
    rooms.forEach((room) => list.appendChild(buildRoomRow(room)));
  }
  if (cards) {
    cards.innerHTML = "";
    rooms.forEach((room) => cards.appendChild(buildRoomCard(room)));
  }
}

async function loadActiveRooms() {
  try {
    const resp = await fetch("/api/active-rooms");
    const rooms = await resp.json();
    renderActiveRooms(rooms);
  } catch (err) {
    console.error("Błąd podczas ładowania pokoi:", err);
  }
}

// Globalna funkcja dołączania z tabeli
globalThis.joinRoom = (roomId) => {
  syncRoomCodeInputs(roomId);
  showJoinModal();
};

function restoreNickname() {
  return ensureNicknameInput();
}

function applyRoomSettingsFromUrl() {
  // No-op: settings are no longer passed via URL
}

function shouldSkipRoomAutoJoin() {
  try {
    if (globalThis.sessionStorage?.getItem("pm_skip_auto_join") === "1") {
      globalThis.sessionStorage.removeItem("pm_skip_auto_join");
      return true;
    }
  } catch (e) {
    console.debug("pm: sessionStorage read skipped", e);
  }
  return false;
}

function markRoomAutoJoinIntent() {
  try {
    globalThis.sessionStorage?.setItem(PM_AUTO_JOIN_KEY, "1");
  } catch (e) {
    console.debug("pm: sessionStorage setItem skipped", e);
  }
}

function consumeRoomAutoJoinIntent() {
  try {
    if (globalThis.sessionStorage?.getItem(PM_AUTO_JOIN_KEY) === "1") {
      globalThis.sessionStorage.removeItem(PM_AUTO_JOIN_KEY);
      return true;
    }
  } catch (e) {
    console.debug("pm: sessionStorage read skipped", e);
  }
  return false;
}

function prepareRoomInviteNickname(allowAutoJoin) {
  if (allowAutoJoin) {
    preparePlayNickname();
    return;
  }
  if (isCustomNickStored()) {
    preparePlayNickname();
    return;
  }
  rerollPlayerNickname();
  bindNicknameInputs();
}

function setRoomJoinVisible(visible) {
  const inlineJoin = document.getElementById("room-inline-join");
  const chatSection = document.getElementById("chat-section");
  if (inlineJoin) inlineJoin.style.display = visible ? "block" : "none";
  if (chatSection && visible) chatSection.style.display = "none";
}

function prepareRoomReconnectUi() {
  setRoomJoinVisible(false);
  const chatSection = document.getElementById("chat-section");
  if (chatSection) chatSection.style.display = "block";
  if (typeof setRoomPhase === "function") setRoomPhase("lobby");
}

function tryAutoJoin(savedNick, roomId) {
  if (!savedNick?.trim()) return false;
  if (shouldSkipRoomAutoJoin()) return false;
  prepareRoomReconnectUi();
  console.log("Auto-joining room:", roomId);
  if (typeof connect === "function") connect();
  return true;
}

function handleRoomRouteOnLoad(savedNick) {
  const isRoomRoute = globalThis.location.pathname.startsWith("/room/");
  const pathParts = globalThis.location.pathname.split("/");
  if (pathParts.length < 3 || pathParts[1] !== "room") return isRoomRoute;

  const roomId = pathParts[2];
  const roomInlineLabel = document.getElementById("room-inline-label");
  if (roomInlineLabel) roomInlineLabel.textContent = `Pokój: ${roomId}`;

  const roomIdInput = document.getElementById("room_id");
  if (roomIdInput) {
    roomIdInput.value = roomId;
    if (!isRoomRoute || !document.getElementById("room-inline-join")) {
      showJoinModal();
    }
  }

  applyRoomSettingsFromUrl();
  const allowAutoJoin = consumeRoomAutoJoinIntent();
  prepareRoomInviteNickname(allowAutoJoin);
  const autoJoined = allowAutoJoin && tryAutoJoin(savedNick, roomId);
  if (!autoJoined) setRoomJoinVisible(true);
  return isRoomRoute;
}

function bindChatEnter() {
  const msgInput = document.getElementById("message-input");
  if (!msgInput) return;
  msgInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter" && typeof sendChat === "function") sendChat();
  });
}

function bindCategoryEnter() {
  const catInputs = document.querySelectorAll("#categories input");
  catInputs.forEach((inp, i) => {
    inp.addEventListener("keypress", (e) => {
      if (e.key !== "Enter") return;
      if (i < catInputs.length - 1) {
        catInputs[i + 1].focus();
        return;
      }
      const stopBtn = document.getElementById("btn-stop");
      if (stopBtn && !stopBtn.disabled && typeof stopGame === "function") {
        stopGame();
      }
    });
  });
}

function bindLobbyConfigEvents() {
  const saveBtn = document.getElementById("lobby-save-config");
  if (saveBtn) {
    saveBtn.addEventListener("click", updateLobbyConfig);
  }
  const startBtn = document.getElementById("lobby-start-game");
  if (startBtn) {
    startBtn.addEventListener("click", () => {
      if (typeof sendJson === "function") {
        sendJson({ type: "start_game" });
      }
    });
  }
  const chatSendBtn = document.getElementById("btn-chat-send");
  if (chatSendBtn) {
    chatSendBtn.addEventListener("click", sendLobbyChat);
  }
}

globalThis.updateLobbyConfig = updateLobbyConfig;
globalThis.updateLobbyConfigUI = updateLobbyConfigUI;
globalThis.sendLobbyChat = sendLobbyChat;
globalThis.bindLobbyConfigEvents = bindLobbyConfigEvents;
globalThis.sendChat = sendChat;
globalThis.appendChatMessage = appendChatMessage;

function playLotterySpinHaptic() {
  if (typeof globalThis.navigator?.vibrate !== "function") return;
  globalThis.navigator.vibrate(12);
}

function playLotteryRevealHaptic() {
  if (typeof globalThis.navigator?.vibrate !== "function") return;
  globalThis.navigator.vibrate([22, 48, 28]);
}

/** Krótka wibracja przy odliczaniu 3–2–1 przed rundą (Faza 3). */
function playCountdownHaptic() {
  if (typeof globalThis.navigator?.vibrate !== "function") return;
  globalThis.navigator.vibrate(10);
}

globalThis.window.onload = () => {
  bindNicknameInputs();
  bindRoomCodeInputs();
  const isRoomRoute = globalThis.location.pathname.startsWith("/room/");
  const savedNick = isRoomRoute ? restoreNickname() : null;
  if (isRoomRoute) {
    handleRoomRouteOnLoad(savedNick);
  } else {
    loadActiveRooms();
    setInterval(loadActiveRooms, 10000);
    initLandingGuideCarousel();
    initLandingGuideMobileSheet();
    preparePlayNickname();
  }
  bindChatEnter();
  bindCategoryEnter();
  bindLobbyConfigEvents();
};

// Eksport dla socket.js i innych
globalThis.showJoinModal = showJoinModal;
globalThis.showCreateModal = showCreateModal;
globalThis.createRoomAndEnter = createRoomAndEnter;
globalThis.hideModals = hideModals;
globalThis.focusStartPanel = focusStartPanel;
globalThis.ensureNicknameInput = ensureNicknameInput;
globalThis.generatePlayerNickname = generatePlayerNickname;
globalThis.rerollPlayerNickname = rerollPlayerNickname;
globalThis.getResolvedNickname = getResolvedNickname;
globalThis.persistNickname = persistNickname;
globalThis.loadActiveRooms = loadActiveRooms;
globalThis.addLog = addLog;
globalThis.updateScoreboard = updateScoreboard;
globalThis.sendChat = sendChat;
globalThis.playLotterySpinHaptic = playLotterySpinHaptic;
globalThis.playLotteryRevealHaptic = playLotteryRevealHaptic;
globalThis.playCountdownHaptic = playCountdownHaptic;
globalThis.showLandingJoinCode = showLandingJoinCode;
globalThis.showLandingStartMode = showLandingStartMode;
globalThis.connectFromLandingJoin = connectFromLandingJoin;
globalThis.quickJoinFromLanding = quickJoinFromLanding;
globalThis.syncRoomCodeInputs = syncRoomCodeInputs;
globalThis.initLandingGuideCarousel = initLandingGuideCarousel;
globalThis.initLandingGuideMobileSheet = initLandingGuideMobileSheet;
globalThis.setRoomPhase = setRoomPhase;
globalThis.renderLobbyRoster = renderLobbyRoster;
globalThis.renderLobbyState = renderLobbyState;
globalThis.clampNickname = clampNickname;
globalThis.syncRoomLobbySettings = syncRoomLobbySettings;
globalThis.copyRoomInviteLink = copyRoomInviteLink;
globalThis.markRoomAutoJoinIntent = markRoomAutoJoinIntent;
globalThis.updateLobbyConfigUI = updateLobbyConfigUI;
globalThis.updateLobbyConfig = updateLobbyConfig;

if (typeof module !== "undefined") {
  module.exports = {
    showJoinModal,
    showCreateModal,
    createRoomAndEnter,
    showLandingJoinCode,
    showLandingStartMode,
    hideModals,
    focusStartPanel,
    ensureNicknameInput,
    generatePlayerNickname,
    rerollPlayerNickname,
    getResolvedNickname,
    persistNickname,
    preparePlayNickname,
    syncRoomCodeInputs,
    bindRoomCodeInputs,
    connectFromLandingJoin,
    quickJoinFromLanding,
    syncLandingScrollLock,
    initLandingGuideCarousel,
    initLandingGuideMobileSheet,
    setRoomPhase,
    renderLobbyRoster,
    resetLobbyRosterState,
    syncRoomLobbySettings,
    copyRoomInviteLink,
    PM_NICK_MAX_LENGTH,
    clampNickname,
    addLog,
    updateScoreboard,
    sendChat,
    buildRoomRow,
    buildRoomCard,
    renderActiveRooms,
    loadActiveRooms,
    restoreNickname,
    applyRoomSettingsFromUrl,
    tryAutoJoin,
    markRoomAutoJoinIntent,
    consumeRoomAutoJoinIntent,
    prepareRoomInviteNickname,
    handleRoomRouteOnLoad,
    bindChatEnter,
    bindCategoryEnter,
    playLotterySpinHaptic,
    playLotteryRevealHaptic,
    playCountdownHaptic,
    updateLobbyConfig,
    updateLobbyConfigUI,
    bindLobbyConfigEvents,
  };
}
