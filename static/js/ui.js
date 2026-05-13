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

function syncRoomCodeInputs(value) {
    const landing = document.getElementById('landing_room_code');
    const modal = document.getElementById('room_id');
    const next = String(value ?? landing?.value ?? modal?.value ?? '').trim();
    if (landing) landing.value = next;
    if (modal) modal.value = next;
    return next;
}

function bindRoomCodeInputs() {
    const bind = (input, onEnter) => {
        if (!input || input.dataset.pmRoomBound) return;
        input.dataset.pmRoomBound = '1';
        input.addEventListener('input', () => {
            syncRoomCodeInputs(input.value);
        });
        if (onEnter) {
            input.addEventListener('keydown', (event) => {
                if (event.key !== 'Enter') return;
                event.preventDefault();
                onEnter();
            });
        }
    };
    bind(document.getElementById('landing_room_code'), connectFromLandingJoin);
    bind(document.getElementById('room_id'));
}

function connectFromLandingJoin() {
    syncRoomCodeInputs();
    const landingNick = document.getElementById('landing_nickname')?.value.trim();
    if (landingNick) syncNicknameInputs(landingNick);
    preparePlayNickname();
    if (typeof globalThis.connect === 'function') globalThis.connect();
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
    const landingInput = document.getElementById('landing_nickname');
    if (createInput) createInput.value = value;
    if (joinInput) joinInput.value = value;
    if (landingInput) landingInput.value = value;
}

function ensureNicknameInput() {
    const input =
        document.getElementById('nickname') ||
        document.getElementById('nickname_join') ||
        document.getElementById('landing_nickname');
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
    bind(document.getElementById('landing_nickname'));
}

function preparePlayNickname() {
    ensureNicknameInput();
    bindNicknameInputs();
}

function getResolvedNickname() {
    preparePlayNickname();
    const joinInput = document.getElementById('nickname_join');
    const createInput = document.getElementById('nickname');
    const landingInput = document.getElementById('landing_nickname');
    const joinModalOpen = document.getElementById('join-modal')?.style.display === 'flex';
    const fromJoin = joinInput?.value.trim() || '';
    const fromCreate = createInput?.value.trim() || '';
    const fromLanding = landingInput?.value.trim() || '';
    if (joinModalOpen) return fromJoin || fromCreate || fromLanding;
    return fromCreate || fromJoin || fromLanding;
}

function syncLandingScrollLock() {
    const body = document.body;
    if (!body.classList.contains('landing-page')) return;

    const tableWrap = document.getElementById('active-rooms-table-wrap');
    const roomsOpen = Boolean(tableWrap && !tableWrap.hidden);

    body.classList.toggle('landing-scrollable', roomsOpen);
}

function prefersReducedMotion() {
    return Boolean(globalThis.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches);
}

function initLandingGuideCarousel() {
    const root = document.querySelector('.landing-guide-carousel');
    const track = document.getElementById('landing-guide-carousel-track');
    const dotsRoot = document.getElementById('landing-guide-carousel-dots');
    const live = document.getElementById('landing-guide-carousel-live');
    if (!root || !track || !dotsRoot) return;

    const slides = Array.from(track.querySelectorAll('.landing-guide-carousel-slide'));
    if (slides.length === 0) return;

    let activeIndex = 0;

    const announce = (index) => {
        const slide = slides[index];
        if (!slide || !live) return;
        const title = slide.querySelector('.landing-guide-carousel-slide-title')?.textContent?.trim();
        if (title) live.textContent = `Slajd: ${title}`;
    };

    const setActive = (index) => {
        activeIndex = (index + slides.length) % slides.length;
        track.style.transform = `translateX(-${activeIndex * 100}%)`;
        slides.forEach((slide, i) => {
            slide.setAttribute('aria-hidden', i === activeIndex ? 'false' : 'true');
        });
        dotsRoot.querySelectorAll('[role="tab"]').forEach((dot, i) => {
            dot.setAttribute('aria-selected', i === activeIndex ? 'true' : 'false');
            dot.tabIndex = i === activeIndex ? 0 : -1;
        });
        announce(activeIndex);
    };

    dotsRoot.innerHTML = '';
    slides.forEach((slide, index) => {
        const title = slide.querySelector('.landing-guide-carousel-slide-title')?.textContent?.trim() || `Slajd ${index + 1}`;
        const dot = document.createElement('button');
        dot.type = 'button';
        dot.className = 'landing-guide-carousel-dot';
        dot.setAttribute('role', 'tab');
        dot.setAttribute('aria-label', title);
        dot.addEventListener('click', () => setActive(index));
        dotsRoot.appendChild(dot);
    });

    root.querySelectorAll('[data-carousel-dir]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const dir = btn.getAttribute('data-carousel-dir');
            setActive(activeIndex + (dir === 'prev' ? -1 : 1));
        });
    });

    root.addEventListener('keydown', (event) => {
        if (event.key === 'ArrowLeft') {
            event.preventDefault();
            setActive(activeIndex - 1);
        } else if (event.key === 'ArrowRight') {
            event.preventDefault();
            setActive(activeIndex + 1);
        }
    });

    if (!prefersReducedMotion()) {
        track.style.transition = 'transform 0.35s ease';
    }

    setActive(0);
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

function updateScoreboard(scores = {}, hostName = '', viewerNick = '', readyPlayers = null) {
    const scoreboard = document.getElementById('scoreboard');
    const lobbyRoster = document.getElementById('lobby-roster');
    const inLobby = document.body.classList.contains('room-phase-lobby');
    const readySet = Array.isArray(readyPlayers) ? new Set(readyPlayers) : null;

    if (inLobby && lobbyRoster) {
        renderLobbyRoster(scores, hostName, readySet || new Set(), viewerNick || globalThis.myNick || '');
    }

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

function renderLobbyRoster(scores = {}, hostName = '', readyPlayers = new Set(), viewerNick = '') {
    const roster = document.getElementById('lobby-roster');
    if (!roster) return;

    roster.innerHTML = '';
    const names = Object.keys(scores);
    if (names.length === 0) {
        const empty = document.createElement('p');
        empty.className = 'lobby-roster-empty';
        empty.textContent = 'Czekamy na graczy…';
        roster.appendChild(empty);
        return;
    }

    names.forEach((name) => {
        const row = document.createElement('div');
        row.className = 'lobby-roster-item';
        if (hostName && name === hostName) row.classList.add('is-host');

        const nameSpan = document.createElement('span');
        nameSpan.className = 'lobby-roster-name';
        if (name === hostName) {
            const crown = document.createElement('span');
            crown.className = 'crown';
            crown.textContent = '👑';
            nameSpan.appendChild(crown);
        }
        nameSpan.appendChild(document.createTextNode(name));

        const status = document.createElement('span');
        status.className = 'lobby-roster-status';
        status.textContent = readyPlayers.has(name) ? 'Gotowy' : 'Czeka';

        row.appendChild(nameSpan);
        row.appendChild(status);
        roster.appendChild(row);
    });
}

function setRoomPhase(phase) {
    const allowed = new Set(['lobby', 'playing', 'results']);
    const next = allowed.has(phase) ? phase : 'playing';
    document.body.classList.remove('room-phase-lobby', 'room-phase-playing', 'room-phase-results');
    document.body.classList.add(`room-phase-${next}`);

    const lobby = document.getElementById('room-lobby');
    const gameMain = document.getElementById('game-main-area');
    const readyBtn = document.getElementById('btn-draw');
    const lobbyActions = document.querySelector('.room-lobby-actions');
    const gameActions = document.querySelector('.game-actions');

    if (lobby) lobby.hidden = next !== 'lobby';
    if (gameMain) gameMain.hidden = next === 'lobby';

    if (readyBtn && lobbyActions && gameActions) {
        if (next === 'lobby') {
            lobbyActions.appendChild(readyBtn);
            readyBtn.style.display = 'inline-flex';
        } else if (!gameActions.contains(readyBtn)) {
            gameActions.insertBefore(readyBtn, gameActions.firstChild);
        }
    }
}

function readRoomSettingsFromUrl() {
    const params = new URLSearchParams(globalThis.location.search);
    const rounds = params.get('rounds') || '5';
    const limit = params.get('limit') || '90';
    const visibility = params.get('visibility') === 'private' ? 'Prywatny' : 'Publiczny';
    return { rounds, limit, visibility };
}

function syncRoomLobbySettings(roomId = '') {
    const settings = readRoomSettingsFromUrl();
    const codeEl = document.getElementById('lobby-room-code');
    const roundsEl = document.getElementById('lobby-room-rounds');
    const limitEl = document.getElementById('lobby-room-limit');
    const visEl = document.getElementById('lobby-room-visibility');
    if (codeEl) codeEl.textContent = roomId || '—';
    if (roundsEl) roundsEl.textContent = settings.rounds;
    if (limitEl) limitEl.textContent = `${settings.limit}s`;
    if (visEl) visEl.textContent = settings.visibility;
}

async function copyRoomInviteLink() {
    const roomId = document.getElementById('current-room')?.textContent?.trim() || '';
    if (!roomId) return;
    const params = new URLSearchParams(globalThis.location.search);
    const visibility = params.get('visibility') === 'private' ? 'private' : 'public';
    const url = `${globalThis.location.origin}/room/${encodeURIComponent(roomId)}?visibility=${visibility}`;
    try {
        await globalThis.navigator.clipboard.writeText(url);
        addLog('<em>Skopiowano link do pokoju.</em>', 'system-msg');
    } catch (e) {
        console.warn('clipboard', e);
        addLog('<em>Nie udało się skopiować linku.</em>', 'system-msg');
    }
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

function setActiveRoomsView(hasRooms) {
    const empty = document.getElementById('active-rooms-empty');
    const tableWrap = document.getElementById('active-rooms-table-wrap');
    if (empty) empty.hidden = hasRooms;
    if (tableWrap) tableWrap.hidden = !hasRooms;
    syncLandingScrollLock();
}

function renderActiveRooms(rooms) {
    const list = document.getElementById('rooms-list');
    const section = document.getElementById('active-rooms-section');

    const hasRooms = Array.isArray(rooms) && rooms.length > 0;
    if (section) section.hidden = false;
    setActiveRoomsView(hasRooms);
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
    syncRoomCodeInputs(roomId);
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
    bindRoomCodeInputs();
    const isRoomRoute = globalThis.location.pathname.startsWith('/room/');
    const savedNick = isRoomRoute ? restoreNickname() : null;
    if (isRoomRoute) {
        handleRoomRouteOnLoad(savedNick);
    } else {
        loadActiveRooms();
        setInterval(loadActiveRooms, 10000);
        initLandingGuideCarousel();
        preparePlayNickname();
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
globalThis.loadActiveRooms = loadActiveRooms;
globalThis.addLog = addLog;
globalThis.updateScoreboard = updateScoreboard;
globalThis.sendChat = sendChat;
globalThis.playLotterySpinHaptic = playLotterySpinHaptic;
globalThis.playLotteryRevealHaptic = playLotteryRevealHaptic;
globalThis.playCountdownHaptic = playCountdownHaptic;
globalThis.connectFromLandingJoin = connectFromLandingJoin;
globalThis.syncRoomCodeInputs = syncRoomCodeInputs;
globalThis.initLandingGuideCarousel = initLandingGuideCarousel;
globalThis.setRoomPhase = setRoomPhase;
globalThis.renderLobbyRoster = renderLobbyRoster;
globalThis.syncRoomLobbySettings = syncRoomLobbySettings;
globalThis.copyRoomInviteLink = copyRoomInviteLink;

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
        syncRoomCodeInputs,
        bindRoomCodeInputs,
        connectFromLandingJoin,
        syncLandingScrollLock,
        initLandingGuideCarousel,
        setRoomPhase,
        renderLobbyRoster,
        syncRoomLobbySettings,
        copyRoomInviteLink,
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
