let ws;
let myNick = "";
let isLeaving = false; // flag to suppress auto-reconnect on manual leave

function sendJson(obj) {
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

// Funkcja wyjścia z pokoju – zamyka WebSocket, czyści UI i usuwa parametr pokoju z URL
function leaveRoom() {
    // Flag to suppress auto-reconnect
    isLeaving = true;
    // Hide chat UI and show join UI
    document.getElementById('chat-section').style.display = 'none';
    document.getElementById('join-section').style.display = 'block';
    document.getElementById('btn-leave').style.display = 'none';
    // Remove room param from URL
    globalThis.history.replaceState(null, '', globalThis.location.pathname);
    // Close WebSocket if open
    if (ws?.readyState === WebSocket.OPEN) {
        ws.close();
    }
    // Clear timers
    if (globalThis.globalRoundTimer) {
        clearInterval(globalThis.globalRoundTimer);
        globalThis.globalRoundTimer = null;
    }
    if (globalThis.currentCountdown) {
        clearInterval(globalThis.currentCountdown);
        globalThis.currentCountdown = null;
    }
}

function connect() {
    initAudio();
    myNick = document.getElementById('nickname').value.trim();
    const roomId = document.getElementById('room_id').value.trim();

    if (!myNick || !roomId) return alert('Proszę podać nick i upewnić się, że masz ID pokoju.');

    // Zapisz na przyszłość
    localStorage.setItem('pm_nickname', myNick);
    
    // Podmień URL żeby łatwo było go skopiować i wysłać znajomym!
    globalThis.history.replaceState(null, '', `?room=${roomId}`);

    const protocol = globalThis.location.protocol === 'https:' ? 'wss:' : 'ws:';
    let wsUrl = `${protocol}//${globalThis.location.host}/ws/${roomId}/${myNick}`;
    
    if (globalThis.roomRounds && globalThis.roomLimit) {
        wsUrl += `?rounds=${globalThis.roomRounds}&limit=${globalThis.roomLimit}`;
    }
    
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        document.getElementById('join-section').style.display = 'none';
        document.getElementById('chat-section').style.display = 'block';
        document.getElementById('btn-leave').style.display = 'block';
        document.getElementById('current-room').textContent = roomId;
    };

    ws.onclose = (e) => {
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
        const handlers = {
            system: (m) => addLog(`<em>${m.message}</em>`, "system-msg"),
            score_update: (m) => updateScoreboard(m.scores, m.host_name),
            chat: (m) => {
                const container = document.createElement('div');
                const senderDiv = document.createElement('div');
                senderDiv.className = 'sender';
                senderDiv.textContent = m.sender;
                const textDiv = document.createElement('div');
                textDiv.textContent = m.text;
                container.appendChild(senderDiv);
                container.appendChild(textDiv);
                addLog(container, "");
            },
            round_started: onRoundStarted,
            stop_round: onStopRound,
            round_results: onRoundResults,
            game_restarted: onGameRestarted,
            room_dissolved: (m) => {
                alert(m.message);
                globalThis.location.href = globalThis.location.pathname;
            }
        };

        if (handlers[msg.type]) {
            handlers[msg.type](msg);
        }
    };

    ws.onerror = (e) => {
        console.error("WS Error:", e);
    };
}

function onRoundStarted(msg) {
    globalThis.currentLetter = msg.letter;
    const lotteryFunc = globalThis.runLetterLottery || runLetterLottery;
    lotteryFunc(msg.letter, () => {
        document.getElementById("current-letter").textContent = msg.letter;
        const btn = document.getElementById("btn-draw");
        btn.classList.remove('ready');
        btn.style.display = 'none';
        addLog(`<em>Gra rozpoczęta! Litera: <strong>${msg.letter}</strong> (Runda ${msg.current_round}/${msg.max_rounds}). Limit czasu: ${msg.time_limit}s</em>`, "system-msg");
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
    if (pts === 10) return "var(--accent)";
    if (pts === 5) return "var(--warning)";
    return "var(--danger)";
}

function buildPlayerResultHtml(player, rScore, pAnswers) {
    let html = `<div style="margin-bottom: 0.5rem"><strong>${player}: +${rScore.total} pkt</strong><br>`;
    for (const [cat, val] of Object.entries(pAnswers)) {
        if(val) {
            const pts = rScore.details[cat] || 0;
            const color = getScoreColor(pts);
            html += `<span style="font-size:0.8em; color:${color};">${cat}:</span> ${val} `;
        }
    }
    html += `</div>`;
    return html;
}

function buildRoundResultsHtml(msg) {
    let html = `<div class="sender">Wyniki Rundy:</div>`;
    for (const [player, rScore] of Object.entries(msg.round_scores)) {
        const pAnswers = msg.answers[player] || {};
        html += buildPlayerResultHtml(player, rScore, pAnswers);
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
    updateScoreboard(msg.total_scores, msg.host_name);
    if (msg.game_over) handleGameOver(msg.host_name);
    else resetReadyButton();
}

function highlightMyInputs(rScore) {
    const inputs = document.querySelectorAll('#categories input');
    inputs.forEach(inp => {
        const cat = inp.dataset.category;
        const pts = rScore.details[cat];
        inp.classList.remove('success-10', 'warning-5', 'error-0');
        if(pts === 10) inp.classList.add('success-10');
        else if(pts === 5) inp.classList.add('warning-5');
        else inp.classList.add('error-0');
    });
}

function handleGameOver(hostName) {
    addLog(`<div style="margin-top:1rem; font-weight:800; color:var(--danger); text-align:center;">🏁 Koniec Gry! Zwycięzca został wyłoniony!</div>`, "system-msg");
    document.getElementById('btn-draw').style.display = 'none';
    document.getElementById('restart-settings').style.display = 'block';
    if (myNick === hostName) {
        document.getElementById('btn-restart-game').style.display = 'block';
        document.getElementById('btn-dissolve').style.display = 'block';
    }
    confetti({ particleCount: 150, spread: 100, origin: { y: 0.3 } });
    setTimeout(() => confetti({ particleCount: 150, spread: 120, origin: { y: 0.4 } }), 1000);
}

function resetReadyButton() {
    const btn = document.getElementById('btn-draw');
    btn.classList.remove('ready');
    btn.innerHTML = '👍 Gotowy do rundy';
    btn.style.backgroundColor = 'var(--primary)';
    btn.style.display = 'block';
}

function onGameRestarted(msg) {
    document.getElementById('restart-settings').style.display = 'none';
    const btn = document.getElementById('btn-draw');
    btn.style.display = 'inline-block';
    btn.classList.remove('ready');
    btn.innerHTML = '👍 Gotowy do rundy';
    btn.style.backgroundColor = 'var(--primary)';
    document.getElementById('current-letter').innerHTML = '?';
    updateScoreboard(msg.scores, msg.host_name);
    const inputs = document.querySelectorAll('#categories input');
    inputs.forEach(inp => {
        inp.value = '';
        inp.disabled = true;
        inp.classList.remove('error', 'success-10', 'warning-5', 'error-0');
    });
    addLog(`<em>Gospodarz <strong>${msg.sender}</strong> zrestartował grę z nowymi ustawieniami! Wyniki zostały wyzerowane.</em>`, "system-msg");
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
            confetti({ particleCount: 100, spread: 70, origin: { y: 0.6 } });
            setTimeout(() => {
                modal.style.display = 'none';
                letterDiv.style.transform = 'scale(1)';
                letterDiv.style.color = 'var(--accent)';
                if (onComplete) onComplete();
            }, 1500);
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
