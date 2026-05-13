let ws;
let myNick = "";
let isLeaving = false; // flag to suppress auto-reconnect on manual leave
let leftByUser = false; // distinguish "user navigated away" from "room dissolved"
let pmHadRoundStarted = false;

function sendJson(obj) {
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

/** Home redirect; Jest has no real `location` (Sonar: handle or avoid empty catch). */
function safeNavigateHome() {
    try {
        const isJestEnv = typeof process !== 'undefined' && process?.env?.JEST_WORKER_ID;
        if (!isJestEnv) globalThis.location.href = '/';
    } catch (e) {
        console.debug('pm: home navigation skipped', e);
    }
}

// Confetti is loaded from a CDN (canvas-confetti). If the CDN is blocked
// or the library fails to load we must NOT let the game flow break --
// a missing confetti() previously crashed the letter lottery interval and
// hung every game right after drawing the letter.
function fireConfetti(opts) {
    if (typeof confetti !== 'function') return;
    try { confetti(opts); } catch (e) { console.warn('confetti failed', e); }
}

function stopCelebrationEffects() {
    if (typeof confetti === 'function' && typeof confetti.reset === 'function') {
        try {
            confetti.reset();
        } catch (e) {
            console.warn('confetti reset failed', e);
        }
    }
}

function leaveRoom() {
    leftByUser = true;
    isLeaving = true;
    globalThis.myNick = '';
    // Hide chat UI and show join UI (keeps tests stable and helps if navigation
    // is blocked by environment or user agent).
    const chatSection = document.getElementById('chat-section');
    const joinSection = document.getElementById('join-section');
    if (chatSection) chatSection.style.display = 'none';
    if (joinSection) joinSection.style.display = 'block';

    const inlineJoin = document.getElementById('room-inline-join');
    if (inlineJoin) inlineJoin.style.display = 'block';

    const btnLeave = document.getElementById('btn-leave');
    if (btnLeave) btnLeave.style.display = 'none';

    const navRoomInfo = document.getElementById('nav-room-info');
    const navHomeLink = document.getElementById('nav-home-link');
    if (navRoomInfo) navRoomInfo.style.display = 'none';
    if (navHomeLink) navHomeLink.style.display = '';

    if (ws?.readyState === WebSocket.OPEN) {
        ws.close();
    }
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

function generateRoomId() {
    const array = new Uint32Array(1);
    globalThis.crypto.getRandomValues(array);
    return (1000 + (array[0] % 9000)).toString();
}

function connect() {
    leftByUser = false;
    initAudio();
    const joinNick = document.getElementById('nickname_join')?.value.trim() || '';
    const createNick = document.getElementById('nickname')?.value.trim() || '';
    const landingNick = document.getElementById('landing_nickname')?.value.trim() || '';
    myNick = joinNick || createNick || landingNick;
    if (!myNick && typeof getResolvedNickname === 'function') {
        myNick = getResolvedNickname() || '';
    }
    if (!myNick && typeof ensureNicknameInput === 'function') {
        myNick = ensureNicknameInput() || '';
    }
    globalThis.myNick = myNick;
    if (!myNick) return alert('Nie udało się nadać nicku — odśwież stronę.');

    const pathParts = globalThis.location.pathname.split('/');
    let roomId = "";
    
    // 1. Sprawdź czy to wejście z bezpośredniego linku
    if (pathParts.length >= 3 && pathParts[1] === 'room') {
        roomId = pathParts[2];
    } else {
        // 2. Sprawdź czy wpisano kod w modalu dołączania
        roomId = document.getElementById('room_id').value.trim();
        if (!roomId) {
            roomId = document.getElementById('landing_room_code')?.value.trim() || '';
        }
    }

    // 3. Jeśli nadal brak ID, a kliknięto "STWÓRZ", generujemy nowe
    const isCreating = document.getElementById('create-modal').style.display !== 'none';
    if (!roomId && isCreating) {
        roomId = generateRoomId();
    }

    if (!roomId) return alert('Proszę podać kod pokoju lub wybrać opcję stworzenia nowego.');

    // Pobierz ustawienia (jeśli tworzymy)
    const maxRounds = document.getElementById('max_rounds').value || 5;
    const timeLimit = document.getElementById('time_limit').value || 90;

    const urlParams = new URLSearchParams(globalThis.location.search);
    let visibility = urlParams.get('visibility') === 'private' ? 'private' : 'public';
    if (isCreating) {
        const visEl = document.getElementById('room_visibility');
        const v = visEl?.value;
        if (v === 'private' || v === 'public') visibility = v;
    }

    if (typeof persistNickname === 'function') {
        persistNickname(myNick);
    } else {
        localStorage.setItem('pm_nickname', myNick);
    }

    // Landing page has no game UI; redirect to the dedicated room page,
    // which auto-joins using the stored nickname + url params.
    if (!globalThis.location.pathname.startsWith('/room/')) {
        globalThis.location.href = `/room/${roomId}?rounds=${maxRounds}&limit=${timeLimit}&visibility=${visibility}`;
        return;
    }

    globalThis.history.replaceState(
        null,
        '',
        `/room/${roomId}?rounds=${encodeURIComponent(String(maxRounds))}&limit=${encodeURIComponent(String(timeLimit))}&visibility=${encodeURIComponent(visibility)}`,
    );

    const protocol = globalThis.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const encNick = encodeURIComponent(myNick);
    let wsUrl = `${protocol}//${globalThis.location.host}/ws/${roomId}/${encNick}?rounds=${maxRounds}&limit=${timeLimit}&visibility=${visibility}`;
    
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        if (typeof hideModals === 'function') hideModals();
        document.getElementById('join-section').style.display = 'none';
        const inlineJoin = document.getElementById('room-inline-join');
        if (inlineJoin) inlineJoin.style.display = 'none';
        document.getElementById('chat-section').style.display = 'block';
        document.getElementById('btn-leave').style.display = 'inline-flex';
        document.getElementById('current-room').textContent = roomId;

        const navRoomInfo = document.getElementById('nav-room-info');
        const navRoomCode = document.getElementById('nav-room-code');
        const navHomeLink = document.getElementById('nav-home-link');
        if (navRoomCode) navRoomCode.textContent = roomId;
        if (navRoomInfo) navRoomInfo.style.display = 'inline-flex';
        if (navHomeLink) navHomeLink.style.display = 'none';

        if (typeof syncRoomLobbySettings === 'function') {
            syncRoomLobbySettings(roomId);
        }
        if (!pmHadRoundStarted && typeof setRoomPhase === 'function') {
            setRoomPhase('lobby');
        } else if (typeof setRoomPhase === 'function') {
            setRoomPhase('playing');
        }

        // Nie czyść rankingu tutaj — serwer wysyła ``score_update`` w ``_send_initial_state``.
        // Wywołanie ``updateScoreboard({}, …)`` przy reconnect powodowało wyścig z wiadomościami
        // i zerowanie punktów w UI mimo poprawnego stanu na backendzie.
    };

    ws.onclose = (e) => {
        if (e.code === 4401) {
            isLeaving = true;
            alert('Host wyrzucił Cię z pokoju.');
            safeNavigateHome();
            return;
        }
        if (e.code === 4408) {
            alert('Pokój pełny — w tym pokoju może być maksymalnie 8 graczy.');
            const inlineJoin = document.getElementById('room-inline-join');
            const chatSection = document.getElementById('chat-section');
            if (inlineJoin) inlineJoin.style.display = 'block';
            if (chatSection) chatSection.style.display = 'none';
            return;
        }
        if (e.code === 1008) {
            alert('Nick jest już zajęty lub nieprawidłowy!');
            const inlineJoin = document.getElementById('room-inline-join');
            const chatSection = document.getElementById('chat-section');
            if (inlineJoin) inlineJoin.style.display = 'block';
            if (chatSection) chatSection.style.display = 'none';
            return;
        }
        // If we initiated a manual leave, do not auto-reconnect
        if (isLeaving) {
            isLeaving = false;
            return;
        }
        // Automatic reconnect after unexpected disconnect
        addLog(`<em>Utracono połączenie. Próba wznowienia za 2 sekundy...</em>`, "system-msg");
        setTimeout(() => {
            if (document.getElementById('chat-section').style.display !== 'none') {
                connect();
            }
        }, 2000);
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        const handler = MESSAGE_HANDLERS[msg.type];
        if (handler) handler(msg);
    };

    ws.onerror = (e) => {
        console.error("WS Error:", e);
    };
}

function onSystemMessage(m) {
    addLog(`<em>${m.message}</em>`, "system-msg");
}

function onScoreUpdate(m) {
    updateScoreboard(m.scores, m.host_name, globalThis.myNick || '', m.ready_players);
}

function onChatMessage(m) {
    const container = document.createElement('div');
    const senderDiv = document.createElement('div');
    senderDiv.className = 'sender';
    senderDiv.textContent = m.sender;
    const textDiv = document.createElement('div');
    textDiv.textContent = m.text;
    container.appendChild(senderDiv);
    container.appendChild(textDiv);
    addLog(container, "");
}

function onKicked(m) {
    isLeaving = true;
    alert(m.message || 'Host wyrzucił Cię z pokoju.');
    safeNavigateHome();
}

function onKickDenied(m) {
    addLog(`<em>${m.message || 'Nie można wyrzucić gracza.'}</em>`, 'system-msg');
}

function onRoomDissolved(m) {
    // Zapobiega auto-reconnect (onclose) gdy serwer zamyka socket tuż po
    // room_dissolved — inaczej po grze często odtwarzał się „pusty” pokój.
    isLeaving = true;
    if (leftByUser) return; // user left -> do not bounce them back into /room/:id
    try {
        globalThis.sessionStorage?.setItem('pm_skip_auto_join', '1');
    } catch (e) {
        console.debug('pm: sessionStorage setItem skipped', e);
    }
    alert(m.message);
    safeNavigateHome();
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
};

function onRoundStarted(msg) {
    hideRoundResultsOverlay();
    provisionalRoundResultsMsg = null;
    globalThis.currentLetter = msg.letter;
    pmHadRoundStarted = true;
    if (typeof setRoomPhase === 'function') setRoomPhase('playing');

    if (msg.resume) {
        const letterEl = document.getElementById('current-letter');
        if (letterEl) letterEl.textContent = msg.letter;
        const btn = document.getElementById('btn-draw');
        if (btn) {
            btn.classList.remove('ready');
            btn.style.display = 'none';
        }
        addLog(
            `<em>Połączenie przywrócone. Runda ${msg.current_round}/${msg.max_rounds}, litera: <strong>${msg.letter}</strong>.</em>`,
            'system-msg',
        );
        clearInputColors();
        enableInputs();
        const rt = document.getElementById('round-timer');
        if (rt) {
            rt.style.display = 'block';
            rt.textContent = '—';
        }
        return;
    }

    const afterReveal = () => {
        const lotteryFunc = globalThis.runLetterLottery || runLetterLottery;
        lotteryFunc(msg.letter, () => {
            document.getElementById("current-letter").textContent = msg.letter;
            const btn = document.getElementById("btn-draw");
            btn.classList.remove('ready');
            btn.style.display = 'none';
            addLog(`<em>Gra rozpoczęta! Litera: <strong>${msg.letter}</strong> (Runda ${msg.current_round}/${msg.max_rounds}). Limit czasu: ${msg.time_limit}s</em>`, "system-msg");
            clearInputColors();
            enableInputs();
            let timeLeft = msg.time_limit;
            document.getElementById("round-timer").textContent = timeLeft + "s";
            document.getElementById("round-timer").style.display = "block";
            if (globalThis.globalRoundTimer) clearInterval(globalThis.globalRoundTimer);
            globalThis.globalRoundTimer = setInterval(() => {
                timeLeft--;
                if (timeLeft >= 0) document.getElementById("round-timer").textContent = timeLeft + "s";
            }, 1000);
        });
    };
    const countdownFn = globalThis.runRoundStartCountdown || runRoundStartCountdown;
    countdownFn(afterReveal);
}

function onStopRound(msg) {
    playGong();
    if (globalThis.globalRoundTimer) clearInterval(globalThis.globalRoundTimer);
    document.getElementById("round-timer").style.display = "none";
    addLog(`<em>🚨 <strong>${msg.sender} zatrzymał rundę!</strong> Oczekiwanie na przesłanie odpowiedzi... Masz 10 sekund!</em>`, "system-msg");
    const btnStop = document.getElementById('btn-stop');
    btnStop.disabled = true;
    const stickyTimer = document.getElementById('sticky-timer');
    const stickyTime = document.getElementById('sticky-time');
    if (stickyTimer) stickyTimer.style.display = 'block';
    if (stickyTime) stickyTime.innerText = '10';
    document.getElementById('current-letter').innerHTML = `<span style="color:var(--danger)">10s</span>`;
    btnStop.innerHTML = `⏳ 10s`;
    let timeLeft = 10;
    globalThis.currentCountdown = setInterval(() => {
        timeLeft--;
        if(timeLeft > 0) {
            document.getElementById('current-letter').innerHTML = `<span style="color:var(--danger)">${timeLeft}s</span>`;
            btnStop.innerHTML = `⏳ ${timeLeft}s`;
            if (stickyTime) stickyTime.innerText = timeLeft;
            playTick();
        } else {
            clearInterval(globalThis.currentCountdown);
            btnStop.innerHTML = `WYSYŁANIE...`;
            if (stickyTimer) stickyTimer.style.display = 'none';
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
        const at = scores[a] && typeof scores[a].total === "number" ? scores[a].total : 0;
        const bt = scores[b] && typeof scores[b].total === "number" ? scores[b].total : 0;
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

function buildRoundResultsHtml(msg, options = {}) {
    const variant = options.variant === "overlay" ? "overlay" : "sidebar";
    const answersRoot = msg.answers && typeof msg.answers === "object" ? msg.answers : {};
    const viewer = globalThis.myNick || myNick || "";
    const scores = msg.round_scores && typeof msg.round_scores === "object" ? msg.round_scores : {};
    const tallies = msg.veto_tallies && typeof msg.veto_tallies === "object" ? msg.veto_tallies : {};
    const isFinal = msg.final !== false;
    const players = sortRoundResultPlayers(scores, viewer);

    let html = `<div class="round-results-block round-results-block--${variant}"><div class="round-results-table-wrap"><table class="round-results-table round-results-table--players"><thead><tr><th scope="col">Gracz</th>`;
    for (const cat of ROUND_RESULT_CATEGORIES) {
        html += `<th scope="col">${escapeHtml(cat)}</th>`;
    }
    html += `<th scope="col">Suma</th></tr></thead><tbody>`;

    for (const player of players) {
        const rScore = scores[player] || { total: 0, details: {} };
        const answers = answersRoot[player] && typeof answersRoot[player] === "object" ? answersRoot[player] : {};
        const meClass = player === viewer ? " round-results-player-row--me" : "";
        html += `<tr class="round-results-player-row${meClass}"><th scope="row" class="round-results-player">${escapeHtml(player)}</th>`;
        for (const cat of ROUND_RESULT_CATEGORIES) {
            const raw = answers[cat];
            const hasAns = raw != null && String(raw).trim() !== "";
            const ptsRaw = rScore.details && rScore.details[cat];
            const pts = typeof ptsRaw === "number" ? ptsRaw : 0;
            let cell = `<div class="round-results-cell"><span class="round-results-val">${hasAns ? escapeHtml(String(raw).trim()) : "—"}</span><span class="${roundResultsPtsClass(pts)}">${pts}</span>`;
            if (cat === "Rzecz" && !isFinal && player !== viewer && hasAns) {
                const tally = tallies[player] || {};
                const tak = typeof tally.tak === "number" ? tally.tak : 0;
                const nie = typeof tally.nie === "number" ? tally.nie : 0;
                cell += `<span class="round-results-veto-tally" aria-hidden="true">${tak}·${nie}</span><div class="round-results-veto-actions" data-veto-target="${escapeHtml(player)}"><button type="button" class="round-results-veto-btn round-results-veto-btn--up" data-target="${escapeHtml(player)}" data-vote="tak" aria-label="Zatwierdź odpowiedź">👍</button><button type="button" class="round-results-veto-btn round-results-veto-btn--down" data-target="${escapeHtml(player)}" data-vote="nie" aria-label="Odrzuć odpowiedź">👎</button></div>`;
            }
            cell += "</div>";
            html += `<td class="round-results-td">${cell}</td>`;
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
    label.textContent = secondsLeft > 0 ? `Następna runda za ${secondsLeft}s` : "Następna runda…";
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
            const target = btn.getAttribute("data-target");
            const vote = btn.getAttribute("data-vote");
            if (!target || !vote) return;
            sendJson({ type: "veto_vote", target, vote });
            btn.closest(".round-results-veto-actions")
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
    showRoundResultsOverlay(buildRoundResultsHtml(provisionalRoundResultsMsg, { variant: "overlay" }), {
        gameOver: false,
        provisional: true,
        vetoEndsAt: provisionalRoundResultsMsg.veto_ends_at,
    });
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

function showRoundResultsOverlay(html, { gameOver = false, provisional = false, vetoEndsAt = null } = {}) {
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

    if (!roundResultsOverlayBound) {
        roundResultsOverlayBound = true;
        dismissBtn?.addEventListener("click", hideRoundResultsOverlay);
        backdrop?.addEventListener("click", hideRoundResultsOverlay);
    }
}

function buildGameOverResultsHtml(msg) {
    const roundScores = msg.round_scores && typeof msg.round_scores === "object" ? msg.round_scores : {};
    if (Object.keys(roundScores).length > 0) {
        return buildRoundResultsHtml(msg, { variant: "sidebar" });
    }

    const totals = msg.total_scores && typeof msg.total_scores === "object" ? msg.total_scores : {};
    const players = Object.keys(totals).sort((a, b) => {
        const av = typeof totals[a] === "number" ? totals[a] : 0;
        const bv = typeof totals[b] === "number" ? totals[b] : 0;
        return bv - av || a.localeCompare(b, "pl");
    });
    if (!players.length) return "";

    const viewer = globalThis.myNick || myNick || "";
    let html = '<div class="game-over-scoreboard"><ol class="share-score-list" aria-label="Wynik końcowy">';
    for (const player of players) {
        const pts = typeof totals[player] === "number" ? totals[player] : 0;
        const meClass = player === viewer ? " game-over-score-row--me" : "";
        html += `<li class="game-over-score-row${meClass}"><span>${escapeHtml(player)}</span><span class="share-score-pts">${pts} pkt</span></li>`;
    }
    return `${html}</ol></div>`;
}

function clearGameOverResults() {
    const panel = document.getElementById("game-over-results");
    const body = document.getElementById("game-over-results-body");
    if (body) body.innerHTML = "";
    if (panel) panel.hidden = true;
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
    if(globalThis.currentCountdown) clearInterval(globalThis.currentCountdown);
    if(globalThis.globalRoundTimer) clearInterval(globalThis.globalRoundTimer);
    document.getElementById("round-timer").style.display = "none";
    const stickyTimer = document.getElementById('sticky-timer');
    if (stickyTimer) stickyTimer.style.display = 'none';
    document.getElementById('current-letter').innerHTML = globalThis.currentLetter || '?';
    const btnStop = document.getElementById('btn-stop');
    btnStop.innerHTML = '🛑 STOP!';
    btnStop.disabled = true;

    const isFinal = msg.final !== false;
    const isGameOver = Boolean(msg.game_over);

    if (isGameOver && isFinal) {
        hideRoundResultsOverlay();
        provisionalRoundResultsMsg = null;
        clearRoundResultsCountdown();
        updateScoreboard(msg.total_scores, msg.host_name, globalThis.myNick || "");
        const viewer = globalThis.myNick || myNick || "";
        const scores = msg.round_scores && typeof msg.round_scores === "object" ? msg.round_scores : {};
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
    const scores = msg.round_scores && typeof msg.round_scores === "object" ? msg.round_scores : {};
    if (scores[viewer]) highlightMyInputs(scores[viewer]);
}

function hideGameOverShare() {
    const share = document.getElementById('game-over-share');
    if (!share) return;
    share.style.display = 'none';
    const copyBtn = document.getElementById('btn-copy-share');
    const nativeBtn = document.getElementById('btn-native-share');
    if (copyBtn) copyBtn.onclick = null;
    if (nativeBtn) {
        nativeBtn.onclick = null;
        nativeBtn.style.display = 'none';
    }
}

/**
 * Udostępnianie wyniku (Faza 4): link do /share/{room_id}, kopiowanie, Web Share API.
 */
function wireGameOverShare(roomId) {
    hideGameOverShare();
    const rid = String(roomId || '').trim();
    if (!rid) return;
    const share = document.getElementById('game-over-share');
    const anchor = document.getElementById('share-link-anchor');
    const copyBtn = document.getElementById('btn-copy-share');
    const nativeBtn = document.getElementById('btn-native-share');
    if (!share || !anchor || !copyBtn) return;

    let base = '';
    try {
        base = globalThis.location.origin || '';
    } catch (e) {
        console.debug('pm: location.origin skipped', e);
    }
    const url = `${base}/share/${encodeURIComponent(rid)}`;
    anchor.href = url;

    copyBtn.onclick = async () => {
        try {
            await globalThis.navigator.clipboard.writeText(url);
            addLog('<em>Skopiowano link do schowka.</em>', 'system-msg');
        } catch (e) {
            addLog('<em>Nie udało się skopiować — otwórz link lub zaznacz go ręcznie.</em>', 'system-msg');
            console.warn('clipboard', e);
        }
    };

    if (nativeBtn && typeof globalThis.navigator?.share === 'function') {
        nativeBtn.style.display = 'inline-block';
        nativeBtn.onclick = () => {
            globalThis.navigator
                .share({
                    title: 'Państwa-Miasta — wynik',
                    text: `Wynik pokoju ${rid}`,
                    url,
                })
                .catch(() => {});
        };
    }

    share.style.display = 'block';
}

function highlightMyInputs(rScore) {
    const inputs = document.querySelectorAll('#categories input');
    inputs.forEach(inp => {
        const cat = inp.dataset.category;
        const pts = rScore.details[cat] || 0;
        // Czyścimy stare klasy
        inp.classList.remove('pts-15', 'pts-10', 'pts-5', 'pts-0', 'success-10', 'warning-5', 'error-0');
        
        if (pts === 15) inp.classList.add('pts-15');
        else if (pts === 10) inp.classList.add('pts-10');
        else if (pts === 5) inp.classList.add('pts-5');
        else if (inp.value.trim() !== "") inp.classList.add('pts-0');
    });
}

function handleGameOver(hostName, roomId, resultsMsg = null) {
    stopCelebrationEffects();
    hideRoundResultsOverlay();
    addLog(`<div style="margin-top:1rem; font-weight:800; color:var(--pts-15); text-align:center;">🏁 KONIEC GRY!</div>`, "system-msg");

    if (typeof setRoomPhase === 'function') setRoomPhase('results');

    const chatSection = document.getElementById('chat-section');
    if (chatSection) chatSection.hidden = false;

    const gameLayout = document.getElementById('game-layout');
    if (gameLayout) gameLayout.classList.add('game-over');

    const gameMain = document.getElementById('game-main-area');
    if (gameMain) gameMain.style.display = 'none';

    const postgame = document.getElementById('room-postgame');
    if (postgame) postgame.hidden = false;

    const restartArea = document.getElementById('restart-settings');
    if (restartArea) restartArea.style.display = 'block';

    if (myNick === hostName) {
        document.getElementById('btn-restart-game').style.display = 'block';
        document.getElementById('btn-dissolve').style.display = 'block';
    }

    fireConfetti({ particleCount: 200, spread: 100, origin: { y: 0.3 } });
    setTimeout(() => fireConfetti({ particleCount: 200, spread: 120, origin: { y: 0.4 } }), 1000);

    renderGameOverResults(resultsMsg);
    wireGameOverShare(roomId);
}

function resetReadyButton() {
    const btn = document.getElementById('btn-draw');
    btn.classList.remove('ready');
    btn.innerHTML = '👍 Gotowy';
    btn.style.backgroundColor = 'var(--primary)';
    btn.style.display = 'block';
    if (typeof setRoomPhase === 'function') setRoomPhase('playing');
}

function onGameRestarted(msg) {
    hideRoundResultsOverlay();
    hideGameOverShare();
    clearGameOverResults();
    document.getElementById('game-layout')?.classList.remove('game-over');
    document.getElementById('game-main-area').style.display = 'block';
    document.getElementById('chat-sidebar')?.classList.remove('hidden');
    const postgame = document.getElementById('room-postgame');
    if (postgame) postgame.hidden = true;
    const restartArea = document.getElementById('restart-settings');
    if (restartArea) restartArea.style.display = 'none';
    if (typeof setRoomPhase === 'function') setRoomPhase('lobby');

    const btn = document.getElementById('btn-draw');
    btn.style.display = 'inline-block';
    btn.classList.remove('ready');
    btn.innerHTML = '👍 Gotowy';
    btn.style.backgroundColor = 'var(--primary)';
    document.getElementById('current-letter').innerHTML = '?';
    updateScoreboard(msg.scores, msg.host_name, globalThis.myNick || '');
    const inputs = document.querySelectorAll('#categories input');
    inputs.forEach(inp => {
        inp.value = '';
        inp.disabled = true;
        inp.classList.remove('error', 'pts-15', 'pts-10', 'pts-5', 'pts-0', 'success-10', 'warning-5', 'error-0');
    });
    addLog(`<em>Gospodarz <strong>${msg.sender}</strong> zrestartował grę z nowymi ustawieniami! Wyniki zostały wyzerowane.</em>`, "system-msg");
}

function clearInputColors() {
    const inputs = document.querySelectorAll('#categories input');
    inputs.forEach(inp => {
        inp.classList.remove('pts-15', 'pts-10', 'pts-5', 'pts-0', 'success-10', 'warning-5', 'error-0');
    });
}

/**
 * Odliczanie 3–2–1 przed animacją losowania litery (Faza 3). Przy ``prefers-reduced-motion`` pomija.
 */
function runRoundStartCountdown(onComplete) {
    if (typeof onComplete !== 'function') return;
    if (globalThis.matchMedia && globalThis.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        onComplete();
        return;
    }
    const overlay = document.getElementById('round-countdown-overlay');
    const numEl = document.getElementById('round-countdown-num');
    if (!overlay || !numEl) {
        onComplete();
        return;
    }
    overlay.removeAttribute('hidden');
    overlay.setAttribute('aria-hidden', 'false');
    const labels = ['3', '2', '1'];
    let step = 0;
    const INTER_MS = 720;
    const tick = () => {
        if (step < labels.length) {
            numEl.textContent = labels[step];
            if (typeof globalThis.playCountdownHaptic === 'function') {
                globalThis.playCountdownHaptic();
            }
            step += 1;
            globalThis.setTimeout(tick, INTER_MS);
            return;
        }
        numEl.textContent = '';
        overlay.setAttribute('hidden', '');
        overlay.setAttribute('aria-hidden', 'true');
        onComplete();
    };
    tick();
}

function runLetterLottery(targetLetter, onComplete) {
    const modal = document.getElementById('lottery-modal');
    const letterDiv = document.getElementById('lottery-letter');
    const alphabet = "ABCDEFGHIJKLMNOPRSTUWZ";
    modal.style.display = 'flex';
    let duration = 2500;
    let intervalTime = 50;
    let elapsed = 0;
    const interval = setInterval(() => {
        elapsed += intervalTime;
        const array = new Uint32Array(1);
        globalThis.crypto.getRandomValues(array);
        const randomLetter = alphabet[array[0] % alphabet.length];
        letterDiv.innerText = randomLetter;
        letterDiv.style.filter = `blur(${Math.max(0, 5 - (elapsed/duration)*5)}px)`;
        if (elapsed >= duration) {
            clearInterval(interval);
            letterDiv.innerText = targetLetter;
            letterDiv.style.filter = 'none';
            letterDiv.style.transform = 'scale(1.2)';
            letterDiv.style.color = 'var(--success)';
            playRoundStartReveal();
            if (typeof playLotteryRevealHaptic === 'function') playLotteryRevealHaptic();
            fireConfetti({ particleCount: 100, spread: 70, origin: { y: 0.6 } });
            setTimeout(() => {
                modal.style.display = 'none';
                letterDiv.style.transform = 'scale(1)';
                letterDiv.style.color = 'var(--accent)';
                if (onComplete) onComplete();
            }, 1500);
        } else {
            playLotterySpinTick(elapsed, duration);
            if (elapsed % 100 === 0 && typeof playLotterySpinHaptic === 'function') {
                playLotterySpinHaptic();
            }
        }
    }, intervalTime);
}

globalThis.stopCelebrationEffects = stopCelebrationEffects;

if (typeof module !== 'undefined') {
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
        sendJson
    };
}
