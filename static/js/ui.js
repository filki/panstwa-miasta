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

function updateScoreboard(scores = {}, hostName = '', viewerNick = '') {
    const scoreboard = document.getElementById('scoreboard');
    if (!scoreboard) return;

    const viewer = viewerNick || globalThis.myNick || '';

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

        const left = document.createElement('div');
        left.className = 'score-item-left';

        const nameSpan = document.createElement('span');
        if (name === hostName) {
            const crown = document.createElement('span');
            crown.className = 'crown';
            crown.textContent = '👑';
            nameSpan.appendChild(crown);
        }
        nameSpan.appendChild(document.createTextNode(name));

        left.appendChild(nameSpan);

        const canKick =
            hostName &&
            viewer &&
            viewer === hostName &&
            name !== viewer &&
            typeof sendJson === 'function';
        if (canKick) {
            const kickBtn = document.createElement('button');
            kickBtn.type = 'button';
            kickBtn.className = 'btn-kick';
            kickBtn.setAttribute('aria-label', `Wyrzuć gracza ${name} z pokoju`);
            kickBtn.textContent = 'Wyrzuć';
            kickBtn.addEventListener('click', () => {
                if (!globalThis.confirm(`Wyrzucić ${name} z pokoju?`)) return;
                sendJson({ type: 'kick_player', target: name });
            });
            left.appendChild(kickBtn);
        }

        const pts = document.createElement('strong');
        pts.textContent = `${Number(points) || 0} pkt`;

        row.appendChild(left);
        row.appendChild(pts);
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

function buildRoomRow(room) {
    const visLabel =
        room.visibility_label ||
        (room.visibility === 'private' ? 'Prywatny' : 'Publiczny');
    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td style="font-weight:800; color:var(--accent);">${room.id}</td>
        <td>${room.host || 'Anonim'}</td>
        <td><span class="badge badge-rules">${room.players} graczy</span></td>
        <td>${room.current_round}/${room.max_rounds}</td>
        <td><span class="badge badge-rules">${room.time_limit}s</span></td>
        <td><span class="badge badge-mode">${visLabel}</span></td>
        <td>
            <button class="btn-join-small" onclick="joinRoom('${room.id}')">DOŁĄCZ</button>
        </td>
    `;
    return tr;
}

function renderActiveRooms(rooms) {
    const list = document.getElementById('rooms-list');
    const section = document.getElementById('active-rooms-section');

    const hasRooms = Array.isArray(rooms) && rooms.length > 0;
    if (section) section.style.display = hasRooms ? 'block' : 'none';
    if (!hasRooms || !list) return;

    list.innerHTML = '';
    rooms.forEach((room) => list.appendChild(buildRoomRow(room)));
}

async function loadActiveRooms() {
    try {
        const resp = await fetch('/api/active-rooms');
        const rooms = await resp.json();
        renderActiveRooms(rooms);
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

function restoreNickname() {
    const savedNick = localStorage.getItem('pm_nickname');
    const input = document.getElementById('nickname');
    if (savedNick && input) input.value = savedNick;
    return savedNick;
}

function applyRoomSettingsFromUrl() {
    const params = new URLSearchParams(globalThis.location.search);
    const rounds = params.get('rounds');
    const limit = params.get('limit');
    const roundsSel = document.getElementById('max_rounds');
    const limitSel = document.getElementById('time_limit');
    if (rounds && roundsSel) roundsSel.value = rounds;
    if (limit && limitSel) limitSel.value = limit;
    const vis = params.get('visibility');
    const visSel = document.getElementById('room_visibility');
    if (visSel && (vis === 'public' || vis === 'private')) visSel.value = vis;
}

function tryAutoJoin(savedNick, roomId) {
    if (!savedNick?.trim()) return;
    // After a host "dissolves room" we redirect players to landing,
    // but some browsers may briefly reload the room page. Avoid auto-join
    // back into a dissolved room in that case.
    try {
        if (globalThis.sessionStorage?.getItem('pm_skip_auto_join') === '1') {
            globalThis.sessionStorage.removeItem('pm_skip_auto_join');
            return;
        }
    } catch (e) {
        console.debug('pm: sessionStorage read skipped', e);
    }
    console.log("Auto-joining room:", roomId);
    setTimeout(() => {
        if (typeof connect === 'function') connect();
    }, 500);
}

function handleRoomRouteOnLoad(savedNick) {
    const isRoomRoute = globalThis.location.pathname.startsWith('/room/');
    const pathParts = globalThis.location.pathname.split('/');
    if (pathParts.length < 3 || pathParts[1] !== 'room') return isRoomRoute;

    const roomId = pathParts[2];
    const roomInlineLabel = document.getElementById('room-inline-label');
    if (roomInlineLabel) roomInlineLabel.textContent = `Pokój: ${roomId}`;

    const roomIdInput = document.getElementById('room_id');
    if (roomIdInput) {
        roomIdInput.value = roomId;
        if (!isRoomRoute || !document.getElementById('room-inline-join')) {
            showJoinModal();
        }
    }

    applyRoomSettingsFromUrl();
    tryAutoJoin(savedNick, roomId);
    return isRoomRoute;
}

function bindChatEnter() {
    const msgInput = document.getElementById('message-input');
    if (!msgInput) return;
    msgInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && typeof sendChat === 'function') sendChat();
    });
}

function bindCategoryEnter() {
    const catInputs = document.querySelectorAll('#categories input');
    catInputs.forEach((inp, i) => {
        inp.addEventListener('keypress', (e) => {
            if (e.key !== 'Enter') return;
            if (i < catInputs.length - 1) {
                catInputs[i + 1].focus();
                return;
            }
            const stopBtn = document.getElementById('btn-stop');
            if (stopBtn && !stopBtn.disabled && typeof stopGame === 'function') {
                stopGame();
            }
        });
    });
}

function playLotterySpinHaptic() {
    if (typeof globalThis.navigator?.vibrate !== 'function') return;
    globalThis.navigator.vibrate(12);
}

function playLotteryRevealHaptic() {
    if (typeof globalThis.navigator?.vibrate !== 'function') return;
    globalThis.navigator.vibrate([22, 48, 28]);
}

globalThis.window.onload = () => {
    const savedNick = restoreNickname();
    const isRoomRoute = handleRoomRouteOnLoad(savedNick);
    if (!isRoomRoute) {
        loadActiveRooms();
        setInterval(loadActiveRooms, 10000);
    }
    bindChatEnter();
    bindCategoryEnter();
};

// Eksport dla socket.js i innych
globalThis.showJoinModal = showJoinModal;
globalThis.showCreateModal = showCreateModal;
globalThis.hideModals = hideModals;
globalThis.loadActiveRooms = loadActiveRooms;
globalThis.addLog = addLog;
globalThis.updateScoreboard = updateScoreboard;
globalThis.sendChat = sendChat;
globalThis.playLotterySpinHaptic = playLotterySpinHaptic;
globalThis.playLotteryRevealHaptic = playLotteryRevealHaptic;

if (typeof module !== 'undefined') {
    module.exports = {
        showJoinModal,
        showCreateModal,
        hideModals,
        addLog,
        updateScoreboard,
        sendChat,
        buildRoomRow,
        renderActiveRooms,
        loadActiveRooms,
        restoreNickname,
        applyRoomSettingsFromUrl,
        tryAutoJoin,
        handleRoomRouteOnLoad,
        bindChatEnter,
        bindCategoryEnter,
        playLotterySpinHaptic,
        playLotteryRevealHaptic,
    };
}
