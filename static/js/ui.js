// Funkcje pomocnicze UI
const PM_NICK_KEY = 'pm_nickname';
const PM_NICK_CUSTOM_KEY = 'pm_nickname_custom';
const AUTO_NICK_RE = /^Gracz#\d{4}$/;

function showJoinModal() {
    document.getElementById('join-modal').style.display = 'flex';
    preparePlayNickname();
}

function showCreateModal() {
    document.getElementById('create-modal').style.display = 'flex';
    preparePlayNickname();
}

function hideModals() {
    document.getElementById('join-modal').style.display = 'none';
    document.getElementById('create-modal').style.display = 'none';
    document.getElementById('lottery-modal').style.display = 'none';
}

function focusStartPanel() {
    const lobby = document.getElementById('lobby');
    if (lobby) {
        lobby.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

function generatePlayerNickname() {
    const array = new Uint32Array(1);
    globalThis.crypto.getRandomValues(array);
    const number = 1000 + (array[0] % 9000);
    return `Gracz#${number}`;
}

function isCustomNickStored() {
    return localStorage.getItem(PM_NICK_CUSTOM_KEY) === '1';
}

function readStoredNickname() {
    return localStorage.getItem(PM_NICK_KEY)?.trim() || '';
}

function markNicknameCustom() {
    localStorage.setItem(PM_NICK_CUSTOM_KEY, '1');
}

function clearNicknameCustom() {
    localStorage.removeItem(PM_NICK_CUSTOM_KEY);
}

function persistNickname(nick) {
    localStorage.setItem(PM_NICK_KEY, nick);
    if (AUTO_NICK_RE.test(nick)) clearNicknameCustom();
    else markNicknameCustom();
}

function syncNicknameInputs(value) {
    const createInput = document.getElementById('nickname');
    const joinInput = document.getElementById('nickname_join');
    if (createInput) createInput.value = value;
    if (joinInput) joinInput.value = value;
}

function ensureNicknameInput() {
    const input = document.getElementById('nickname') || document.getElementById('nickname_join');
    if (!input) return null;

    const current = input.value.trim();
    if (current) return current;

    let nick;
    if (isCustomNickStored()) {
        nick = readStoredNickname();
        if (!nick) {
            nick = generatePlayerNickname();
            clearNicknameCustom();
        }
    } else {
        nick = generatePlayerNickname();
    }

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
        input.dataset.pmBound = '1';
        input.addEventListener('input', () => {
            const val = input.value.trim();
            if (!val) return;
            syncNicknameInputs(val);
            if (!AUTO_NICK_RE.test(val)) markNicknameCustom();
        });
    };
    bind(document.getElementById('nickname'));
    bind(document.getElementById('nickname_join'));
}

function preparePlayNickname() {
    ensureNicknameInput();
    bindNicknameInputs();
}

function getResolvedNickname() {
    preparePlayNickname();
    const joinInput = document.getElementById('nickname_join');
    const createInput = document.getElementById('nickname');
    const joinModalOpen = document.getElementById('join-modal')?.style.display === 'flex';
    const fromJoin = joinInput?.value.trim() || '';
    const fromCreate = createInput?.value.trim() || '';
    return joinModalOpen ? fromJoin || fromCreate : fromCreate || fromJoin;
}

function syncLandingScrollLock() {
    const body = document.body;
    if (!body.classList.contains('landing-page')) return;

    const roomsOpen =
        document.getElementById('active-rooms-section')?.style.display !== 'none';
    const marketingOpen = body.classList.contains('landing-marketing-open');

    body.classList.toggle('landing-scrollable', Boolean(roomsOpen || marketingOpen));
}

function toggleLandingMarketing(event) {
    if (event) event.preventDefault();

    const body = document.body;
    if (!body.classList.contains('landing-page')) return;

    body.classList.toggle('landing-marketing-open');
    syncLandingScrollLock();

    if (body.classList.contains('landing-marketing-open')) {
        document.getElementById('marketing')?.scrollIntoView({ behavior: 'smooth' });
    }
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
    syncLandingScrollLock();
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
    return ensureNicknameInput();
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

/** Krótka wibracja przy odliczaniu 3–2–1 przed rundą (Faza 3). */
function playCountdownHaptic() {
    if (typeof globalThis.navigator?.vibrate !== 'function') return;
    globalThis.navigator.vibrate(10);
}

globalThis.window.onload = () => {
    bindNicknameInputs();
    const isRoomRoute = globalThis.location.pathname.startsWith('/room/');
    const savedNick = isRoomRoute ? restoreNickname() : null;
    if (isRoomRoute) {
        handleRoomRouteOnLoad(savedNick);
    } else {
        loadActiveRooms();
        setInterval(loadActiveRooms, 10000);
    }
    if (document.body.classList.contains('landing-page') && location.hash === '#features') {
        document.body.classList.add('landing-marketing-open');
        syncLandingScrollLock();
    }
    bindChatEnter();
    bindCategoryEnter();
};

// Eksport dla socket.js i innych
globalThis.showJoinModal = showJoinModal;
globalThis.showCreateModal = showCreateModal;
globalThis.hideModals = hideModals;
globalThis.focusStartPanel = focusStartPanel;
globalThis.ensureNicknameInput = ensureNicknameInput;
globalThis.generatePlayerNickname = generatePlayerNickname;
globalThis.rerollPlayerNickname = rerollPlayerNickname;
globalThis.getResolvedNickname = getResolvedNickname;
globalThis.persistNickname = persistNickname;
globalThis.toggleLandingMarketing = toggleLandingMarketing;
globalThis.loadActiveRooms = loadActiveRooms;
globalThis.addLog = addLog;
globalThis.updateScoreboard = updateScoreboard;
globalThis.sendChat = sendChat;
globalThis.playLotterySpinHaptic = playLotterySpinHaptic;
globalThis.playLotteryRevealHaptic = playLotteryRevealHaptic;
globalThis.playCountdownHaptic = playCountdownHaptic;

if (typeof module !== 'undefined') {
    module.exports = {
        showJoinModal,
        showCreateModal,
        hideModals,
        focusStartPanel,
        ensureNicknameInput,
        generatePlayerNickname,
        rerollPlayerNickname,
        getResolvedNickname,
        persistNickname,
        preparePlayNickname,
        toggleLandingMarketing,
        syncLandingScrollLock,
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
        playCountdownHaptic,
    };
}
