let ws;
let myNick = "";
let isLeaving = false; // flag to suppress auto-reconnect on manual leave
let leftByUser = false; // distinguish "user navigated away" from "room dissolved"

function sendJson(obj) {
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

// Confetti is loaded from a CDN (canvas-confetti). If the CDN is blocked
// or the library fails to load we must NOT let the game flow break --
// a missing confetti() previously crashed the letter lottery interval and
// hung every game right after drawing the letter.
function fireConfetti(opts) {
    if (typeof confetti !== 'function') return;
    try { confetti(opts); } catch (e) { console.warn('confetti failed', e); }
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
    try {
        const isJestEnv = typeof process !== 'undefined' && process?.env?.JEST_WORKER_ID;
        if (!isJestEnv) globalThis.location.href = "/";
    } catch (e) {
        // noop (test environment)
    }
}

function generateRoomId() {
    const array = new Uint32Array(1);
    globalThis.crypto.getRandomValues(array);
    return (1000 + (array[0] % 9000)).toString();
}

function connect() {
    leftByUser = false;
    initAudio();
    myNick = document.getElementById('nickname').value.trim();
    globalThis.myNick = myNick;
    if (!myNick) return alert('Proszę najpierw podać swój nickname!');

    const pathParts = globalThis.location.pathname.split('/');
    let roomId = "";
    
    // 1. Sprawdź czy to wejście z bezpośredniego linku
    if (pathParts.length >= 3 && pathParts[1] === 'room') {
        roomId = pathParts[2];
    } else {
        // 2. Sprawdź czy wpisano kod w modalu dołączania
        roomId = document.getElementById('room_id').value.trim();
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
        const v = visEl && visEl.value;
        if (v === 'private' || v === 'public') visibility = v;
    }

    localStorage.setItem('pm_nickname', myNick);

    // Landing page has no game UI; redirect to the dedicated room page,
    // which auto-joins using the stored nickname + url params.
    if (!globalThis.location.pathname.startsWith('/room/')) {
        globalThis.location.href = `/room/${roomId}?rounds=${maxRounds}&limit=${timeLimit}&visibility=${visibility}`;
        return;
    }

    globalThis.history.replaceState(null, '', `/room/${roomId}`);

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

        if (typeof updateScoreboard === 'function') updateScoreboard({}, '', globalThis.myNick || '');
    };

    ws.onclose = (e) => {
        if (e.code === 4401) {
            isLeaving = true;
            alert('Host wyrzucił Cię z pokoju.');
            try {
                const isJestEnv = typeof process !== 'undefined' && process?.env?.JEST_WORKER_ID;
                if (!isJestEnv) globalThis.location.href = '/';
            } catch (err) {
                // noop
            }
            return;
        }
        if (e.code === 1008) {
            alert('Nick jest już zajęty lub nieprawidłowy!');
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
    updateScoreboard(m.scores, m.host_name, globalThis.myNick || '');
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
    try {
        const isJestEnv = typeof process !== 'undefined' && process?.env?.JEST_WORKER_ID;
        if (!isJestEnv) globalThis.location.href = '/';
    } catch (e) {
        // noop
    }
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
        // noop (private mode / disabled storage)
    }
    alert(m.message);
    try {
        const isJestEnv = typeof process !== 'undefined' && process?.env?.JEST_WORKER_ID;
        if (!isJestEnv) globalThis.location.href = '/';
    } catch (e) {
        // noop (test environment)
    }
}

const MESSAGE_HANDLERS = {
    system: onSystemMessage,
    score_update: onScoreUpdate,
    chat: onChatMessage,
    round_started: onRoundStarted,
    stop_round: onStopRound,
    round_results: onRoundResults,
    game_restarted: onGameRestarted,
    room_dissolved: onRoomDissolved,
    kicked: onKicked,
    kick_denied: onKickDenied,
};

function onRoundStarted(msg) {
    globalThis.currentLetter = msg.letter;
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

function buildPlayerResultHtml(player, rScore, pAnswers) {
    // Uproszczony log: tylko kto ile punktów dostał w sumie, bez detali kategorii (kolory są na inputach)
    return `<div style="margin-bottom: 0.5rem"><strong>${player}: +${rScore.total} pkt</strong></div>`;
}

function buildRoundResultsHtml(msg) {
    let html = `<div class="sender">Podsumowanie Rundy:</div>`;
    for (const [player, rScore] of Object.entries(msg.round_scores)) {
        html += buildPlayerResultHtml(player, rScore, {});
        if (player === myNick) highlightMyInputs(rScore);
    }
    return html;
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

    const html = buildRoundResultsHtml(msg);
    addLog(html, "results-msg");
    updateScoreboard(msg.total_scores, msg.host_name, globalThis.myNick || '');

    if (msg.game_over) handleGameOver(msg.host_name);
    else resetReadyButton();
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

function handleGameOver(hostName) {
    addLog(`<div style="margin-top:1rem; font-weight:800; color:var(--pts-15); text-align:center;">🏁 KONIEC GRY!</div>`, "system-msg");
    
    // Pokaż ranking jako główny element
    document.getElementById('game-layout').classList.add('game-over');
    document.getElementById('scoreboard-sidebar').classList.remove('hidden');
    document.getElementById('game-main-area').style.display = 'none';
    document.getElementById('chat-sidebar').classList.add('hidden');
    
    // Przenieś przyciski restartu do sidebar'a rankingu lub wyświetl pod rankingiem
    const restartArea = document.getElementById('restart-settings');
    restartArea.style.display = 'block';
    document.getElementById('scoreboard-sidebar').appendChild(restartArea);
    
    if (myNick === hostName) {
        document.getElementById('btn-restart-game').style.display = 'block';
        document.getElementById('btn-dissolve').style.display = 'block';
    }
    
    fireConfetti({ particleCount: 200, spread: 100, origin: { y: 0.3 } });
    setTimeout(() => fireConfetti({ particleCount: 200, spread: 120, origin: { y: 0.4 } }), 1000);
}

function resetReadyButton() {
    const btn = document.getElementById('btn-draw');
    btn.classList.remove('ready');
    btn.innerHTML = '👍 Gotowy do rundy';
    btn.style.backgroundColor = 'var(--primary)';
    btn.style.display = 'block';
}

function onGameRestarted(msg) {
    // Przywracamy obszary gry
    document.getElementById('game-layout').classList.remove('game-over');
    document.getElementById('game-main-area').style.display = 'block';
    document.getElementById('chat-sidebar').classList.remove('hidden');
    document.getElementById('scoreboard-sidebar').classList.remove('hidden');
    
    // Przywracamy panel restartu na jego miejsce w main-area (jeśli był przeniesiony)
    const restartArea = document.getElementById('restart-settings');
    restartArea.style.display = 'none';
    document.getElementById('game-main-area').appendChild(restartArea);

    const btn = document.getElementById('btn-draw');
    btn.style.display = 'inline-block';
    btn.classList.remove('ready');
    btn.innerHTML = '👍 Gotowy do rundy';
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

if (typeof module !== 'undefined') {
    module.exports = {
        leaveRoom,
        connect,
        onRoundStarted,
        onStopRound,
        getScoreColor,
        buildPlayerResultHtml,
        buildRoundResultsHtml,
        onRoundResults,
        highlightMyInputs,
        handleGameOver,
        resetReadyButton,
        onGameRestarted,
        runLetterLottery,
        sendJson
    };
}
