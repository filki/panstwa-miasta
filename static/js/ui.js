// Funkcje pomocnicze UI
function showJoinModal() {
    document.getElementById('join-modal').style.display = 'flex';
}

function showCreateModal() {
    document.getElementById('create-modal').style.display = 'flex';
}

function hideModals() {
    document.getElementById('join-modal').style.display = 'none';
    document.getElementById('create-modal').style.display = 'none';
    document.getElementById('lottery-modal').style.display = 'none';
}

function addLog(content, className = '') {
    const logs = document.getElementById('logs');
    if (!logs) return;

    const entry = document.createElement('div');
    entry.className = `log-entry ${className || ''}`.trim();

    if (content instanceof HTMLElement) {
        entry.appendChild(content);
    } else {
        entry.innerHTML = String(content ?? '');
    }

    logs.appendChild(entry);
    logs.scrollTop = logs.scrollHeight;
}

function updateScoreboard(scores = {}, hostName = '') {
    const scoreboard = document.getElementById('scoreboard');
    if (!scoreboard) return;

    scoreboard.innerHTML = '';

    const entries = Object.entries(scores).sort((a, b) => Number(b[1]) - Number(a[1]));

    if (entries.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'score-item';
        empty.style.opacity = '0.6';
        empty.innerHTML = '<span>Czekamy na graczy…</span><strong>—</strong>';
        scoreboard.appendChild(empty);
        return;
    }

    entries.forEach(([name, points]) => {
        const row = document.createElement('div');
        row.className = 'score-item';
        if (hostName && name === hostName) row.classList.add('is-host');

        const safePoints = Number(points) || 0;
        row.innerHTML = `
            <span>${name === hostName ? '<span class="crown">👑</span>' : ''}${name}</span>
            <strong>${safePoints} pkt</strong>
        `;
        scoreboard.appendChild(row);
    });
}

function sendChat() {
    const input = document.getElementById('message-input');
    if (!input) return;

    const text = input.value.trim();
    if (!text) return;

    if (typeof sendJson === 'function') {
        sendJson({ type: 'chat', text });
        input.value = '';
    }
}

// Funkcja ładowania aktywnych pokoi
async function loadActiveRooms() {
    try {
        const resp = await fetch('/api/active-rooms');
        const rooms = await resp.json();
        
        const list = document.getElementById('rooms-list');
        const section = document.getElementById('active-rooms-section');

        if (!rooms || rooms.length === 0) {
            if (section) section.style.display = 'none';
            return;
        }

        if (section) section.style.display = 'block';
        if (list) {
            list.innerHTML = '';
            rooms.forEach(room => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="font-weight:800; color:var(--accent);">${room.id}</td>
                    <td>${room.host || 'Anonim'}</td>
                    <td><span class="badge badge-rules">${room.players} graczy</span></td>
                    <td>${room.current_round}/${room.max_rounds}</td>
                    <td><span class="badge badge-rules">${room.time_limit}s</span></td>
                    <td><span class="badge badge-mode">${room.mode}</span></td>
                    <td>
                        <button class="btn-join-small" onclick="joinRoom('${room.id}')">DOŁĄCZ</button>
                    </td>
                `;
                list.appendChild(tr);
            });
        }
    } catch (err) {
        console.error("Błąd podczas ładowania pokoi:", err);
    }
}

// Globalna funkcja dołączania z tabeli
globalThis.joinRoom = (roomId) => {
    const roomIdInput = document.getElementById('room_id');
    if (roomIdInput) roomIdInput.value = roomId;
    showJoinModal();
};

// Inicjalizacja przy załadowaniu strony
globalThis.window.onload = () => {
    const isRoomRoute = globalThis.location.pathname.startsWith('/room/');
    const roomInlineLabel = document.getElementById('room-inline-label');

    // 1. Załaduj nick z localStorage
    const savedNick = localStorage.getItem('pm_nickname');
    if (savedNick && document.getElementById('nickname')) {
        document.getElementById('nickname').value = savedNick;
    }

    // 2. Obsługa wejścia bezpośrednio przez link /room/ID
    const pathParts = globalThis.location.pathname.split('/');
    if (pathParts.length >= 3 && pathParts[1] === 'room') {
        const roomId = pathParts[2];
        if (roomInlineLabel) roomInlineLabel.textContent = `Pokój: ${roomId}`;
        const roomIdInput = document.getElementById('room_id');
        if (roomIdInput) {
            roomIdInput.value = roomId;
            if (!isRoomRoute || !document.getElementById('room-inline-join')) {
                showJoinModal();
            }
        }
        
        // AUTO-JOIN: Jeśli mamy nick, próbujemy połączyć od razu
        if (savedNick && savedNick.trim() !== "") {
            console.log("Auto-joining room:", roomId);
            setTimeout(() => {
                if (typeof connect === 'function') connect();
            }, 500);
        }
    }

    // 3. Załaduj pokoje i ustaw interwał
    if (!isRoomRoute) {
        loadActiveRooms();
        setInterval(loadActiveRooms, 10000);
    }

    // 4. Obsługa klawisza Enter na czacie
    const msgInput = document.getElementById('message-input');
    if (msgInput) {
        msgInput.addEventListener('keypress', e => {
            if (e.key === 'Enter') {
                if (typeof sendChat === 'function') sendChat();
            }
        });
    }

    // 5. Obsługa Enter na inputach kategorii (przechodzenie do następnego)
    const catInputs = document.querySelectorAll('#categories input');
    catInputs.forEach((inp, i) => {
        inp.addEventListener('keypress', e => {
            if (e.key === 'Enter') {
                if (i < catInputs.length - 1) {
                    catInputs[i + 1].focus();
                } else {
                    const stopBtn = document.getElementById('btn-stop');
                    if (stopBtn && !stopBtn.disabled) {
                        if (typeof stopGame === 'function') stopGame();
                    }
                }
            }
        });
    });
};

// Eksport dla socket.js i innych
globalThis.showJoinModal = showJoinModal;
globalThis.showCreateModal = showCreateModal;
globalThis.hideModals = hideModals;
globalThis.loadActiveRooms = loadActiveRooms;
globalThis.addLog = addLog;
globalThis.updateScoreboard = updateScoreboard;
globalThis.sendChat = sendChat;
