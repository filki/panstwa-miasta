/**
 * @jest-environment jsdom
 */

global.sendJson = jest.fn();
global.connect = jest.fn();
global.scrollTo = jest.fn();
global.alert = jest.fn();

const {
    showJoinModal,
    showCreateModal,
    hideModals,
    focusStartPanel,
    syncLandingScrollLock,
    syncRoomCodeInputs,
    initLandingGuideCarousel,
    connectFromLandingJoin,
    preparePlayNickname,
    setRoomPhase,
    renderLobbyRoster,
    addLog,
    updateScoreboard,
    sendChat,
    buildRoomRow,
    buildRoomCard,
    renderActiveRooms,
    loadActiveRooms,
    ensureNicknameInput,
    generatePlayerNickname,
    restoreNickname,
    handleRoomRouteOnLoad,
    applyRoomSettingsFromUrl,
    tryAutoJoin,
    playLotterySpinHaptic,
    playLotteryRevealHaptic,
    playCountdownHaptic,
} = require('../static/js/ui.js');

const baseDom = () => `
    <div id="logs"></div>
    <div id="scoreboard"></div>
    <div id="join-modal" style="display: none;"></div>
    <div id="create-modal" style="display: none;"></div>
    <div id="lottery-modal" style="display: none;"></div>
    <input id="nickname" />
    <input id="nickname_join" />
    <input id="room_id" />
    <input id="landing_room_code" />
    <input id="landing_nickname" />
    <select id="max_rounds"><option value="3">3</option><option value="5">5</option><option value="10">10</option><option value="22">22</option></select>
    <select id="time_limit"><option value="60">60</option><option value="90">90</option><option value="120">120</option></select>
    <select id="room_visibility"><option value="public">public</option><option value="private">private</option></select>
    <input id="message-input" />
    <div id="active-rooms-section">
        <div id="active-rooms-empty"></div>
        <div id="active-rooms-table-wrap" hidden>
            <table><tbody id="rooms-list"></tbody></table>
        </div>
        <ul id="active-rooms-cards-wrap" class="active-rooms-cards" hidden></ul>
    </div>
`;

beforeEach(() => {
    document.body.innerHTML = baseDom();
    jest.clearAllMocks();
    globalThis.sendJson = global.sendJson;
    globalThis.myNick = '';
});

describe('addLog', () => {
    test('renders raw HTML when content is string', () => {
        addLog('<b>Bold</b>', 'system-msg');
        const logs = document.getElementById('logs');
        expect(logs.innerHTML).toContain('<b>Bold</b>');
        expect(logs.querySelector('.log-entry')).not.toBeNull();
        expect(logs.querySelector('.system-msg')).not.toBeNull();
    });

    test('appends HTMLElement nodes as-is', () => {
        const span = document.createElement('span');
        span.textContent = 'Span Content';
        addLog(span, 'chat-msg');
        const logs = document.getElementById('logs');
        expect(logs.textContent).toContain('Span Content');
        expect(logs.querySelector('span')).not.toBeNull();
    });

    test('returns early when logs div is missing', () => {
        document.body.innerHTML = '';
        expect(() => addLog('safe', 'system-msg')).not.toThrow();
    });

    test('coerces nullish content to empty string', () => {
        addLog(null, 'system-msg');
        const entry = document.getElementById('logs').querySelector('.log-entry');
        expect(entry).not.toBeNull();
        expect(entry.innerHTML).toBe('');
    });
});

describe('updateScoreboard', () => {
    test('renders scores sorted descending and marks host with crown', () => {
        updateScoreboard({ Alice: 10, Bob: 30, Carol: 20 }, 'Bob');
        const sb = document.getElementById('scoreboard');
        expect(sb.innerHTML).toContain('30 pkt');
        expect(sb.innerHTML).toContain('20 pkt');
        expect(sb.innerHTML).toContain('10 pkt');
        expect(sb.querySelector('.is-host')).not.toBeNull();
        expect(sb.innerHTML).toContain('👑');
        const items = sb.querySelectorAll('.score-item');
        expect(items[0].textContent).toContain('Bob');
        expect(items[1].textContent).toContain('Carol');
        expect(items[2].textContent).toContain('Alice');
    });

    test('host sees kick buttons for other players', () => {
        globalThis.myNick = 'Bob';
        global.sendJson = jest.fn();
        globalThis.sendJson = global.sendJson;
        globalThis.confirm = jest.fn(() => true);
        updateScoreboard({ Alice: 10, Bob: 30, Carol: 20 }, 'Bob', 'Bob');
        const kicks = document.querySelectorAll('.btn-kick');
        expect(kicks).toHaveLength(2);
        kicks[0].click();
        expect(global.sendJson).toHaveBeenCalledWith({ type: 'kick_player', target: 'Carol' });
    });

    test('non-host does not see kick buttons', () => {
        globalThis.myNick = 'Alice';
        updateScoreboard({ Alice: 10, Bob: 30 }, 'Bob', 'Alice');
        expect(document.querySelectorAll('.btn-kick')).toHaveLength(0);
    });

    test('shows placeholder when there are no scores', () => {
        updateScoreboard({}, '');
        const sb = document.getElementById('scoreboard');
        expect(sb.innerHTML).toContain('Czekamy na graczy');
    });

    test('returns early when scoreboard is missing', () => {
        document.body.innerHTML = '';
        expect(() => updateScoreboard({ Foo: 1 }, 'Foo')).not.toThrow();
    });
});

describe('modal helpers', () => {
    test('showJoinModal displays the join modal', () => {
        showJoinModal();
        expect(document.getElementById('join-modal').style.display).toBe('flex');
    });

    test('showCreateModal displays the create modal', () => {
        showCreateModal();
        expect(document.getElementById('create-modal').style.display).toBe('flex');
    });

    test('hideModals hides every known modal', () => {
        document.getElementById('join-modal').style.display = 'flex';
        document.getElementById('create-modal').style.display = 'flex';
        document.getElementById('lottery-modal').style.display = 'flex';
        hideModals();
        expect(document.getElementById('join-modal').style.display).toBe('none');
        expect(document.getElementById('create-modal').style.display).toBe('none');
        expect(document.getElementById('lottery-modal').style.display).toBe('none');
    });

    test('focusStartPanel scrolls to lobby', () => {
        document.body.innerHTML = '<section id="lobby"></section>';
        const lobby = document.getElementById('lobby');
        lobby.scrollIntoView = jest.fn();
        focusStartPanel();
        expect(lobby.scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'nearest' });
    });

    test('syncLandingScrollLock enables scroll when active rooms table is visible', () => {
        document.body.className = 'landing-page';
        document.body.innerHTML = '<div id="active-rooms-table-wrap"></div>';
        document.getElementById('active-rooms-table-wrap').hidden = false;
        syncLandingScrollLock();
        expect(document.body.classList.contains('landing-scrollable')).toBe(true);
    });
});

describe('sendChat', () => {
    test('sends trimmed message and clears the input', () => {
        const input = document.getElementById('message-input');
        input.value = '  Hello world  ';
        sendChat();
        expect(globalThis.sendJson).toHaveBeenCalledWith({ type: 'chat', text: 'Hello world' });
        expect(input.value).toBe('');
    });

    test('does nothing when the message is empty/whitespace', () => {
        const input = document.getElementById('message-input');
        input.value = '   ';
        sendChat();
        expect(globalThis.sendJson).not.toHaveBeenCalled();
    });

    test('returns early when input is missing', () => {
        document.body.innerHTML = '';
        expect(() => sendChat()).not.toThrow();
        expect(globalThis.sendJson).not.toHaveBeenCalled();
    });
});

describe('buildRoomRow', () => {
    test('renders a <tr> with the room id, host and a join button', () => {
        const tr = buildRoomRow({
            id: '1234',
            host: 'Filip',
            players: 3,
            current_round: 2,
            max_rounds: 5,
            time_limit: 90,
            visibility: 'public',
            visibility_label: 'Publiczny',
        });
        expect(tr.tagName).toBe('TR');
        expect(tr.innerHTML).toContain('1234');
        expect(tr.innerHTML).toContain('Filip');
        expect(tr.innerHTML).toContain('3 graczy');
        expect(tr.innerHTML).toContain('2/5');
        expect(tr.innerHTML).toContain('90s');
        expect(tr.innerHTML).toContain('Publiczny');
        expect(tr.querySelector('button.btn-join-small')).not.toBeNull();
    });

    test('falls back to "Anonim" when host is missing', () => {
        const tr = buildRoomRow({
            id: '9999',
            players: 1,
            current_round: 0,
            max_rounds: 3,
            time_limit: 60,
            visibility: 'private',
            visibility_label: 'Prywatny',
        });
        expect(tr.innerHTML).toContain('Anonim');
    });
});

describe('buildRoomCard', () => {
    test('renders a card with room metadata and join button', () => {
        const card = buildRoomCard({
            id: '1234',
            host: 'Filip',
            players: 3,
            current_round: 2,
            max_rounds: 5,
            time_limit: 90,
            visibility: 'public',
            visibility_label: 'Publiczny',
        });
        expect(card.tagName).toBe('LI');
        expect(card.className).toBe('active-rooms-card');
        expect(card.textContent).toContain('1234');
        expect(card.textContent).toContain('Filip');
        expect(card.textContent).toContain('3 graczy');
        expect(card.textContent).toContain('2/5 rund');
        expect(card.querySelector('button.active-rooms-card-join')).not.toBeNull();
    });
});

describe('renderActiveRooms', () => {
    test('shows the section and appends a row per room', () => {
        document.body.className = 'landing-page';
        renderActiveRooms([
            {
                id: '1',
                host: 'A',
                players: 1,
                current_round: 0,
                max_rounds: 5,
                time_limit: 60,
                visibility_label: 'Publiczny',
            },
            {
                id: '2',
                host: 'B',
                players: 2,
                current_round: 1,
                max_rounds: 5,
                time_limit: 90,
                visibility_label: 'Publiczny',
            },
        ]);
        expect(document.getElementById('active-rooms-section').hidden).toBe(false);
        expect(document.getElementById('active-rooms-table-wrap').hidden).toBe(false);
        expect(document.getElementById('active-rooms-cards-wrap').hidden).toBe(false);
        expect(document.getElementById('active-rooms-empty').hidden).toBe(true);
        expect(document.body.classList.contains('landing-scrollable')).toBe(true);
        const rows = document.querySelectorAll('#rooms-list tr');
        expect(rows).toHaveLength(2);
        const cards = document.querySelectorAll('#active-rooms-cards-wrap .active-rooms-card');
        expect(cards).toHaveLength(2);
    });

    test('shows empty state when there are no rooms', () => {
        renderActiveRooms([]);
        expect(document.getElementById('active-rooms-section').hidden).toBe(false);
        expect(document.getElementById('active-rooms-empty').hidden).toBe(false);
        expect(document.getElementById('active-rooms-table-wrap').hidden).toBe(true);
        expect(document.getElementById('active-rooms-cards-wrap').hidden).toBe(true);
        expect(document.body.classList.contains('landing-scrollable')).toBe(false);
    });

    test('shows empty state when input is null/undefined', () => {
        renderActiveRooms(null);
        expect(document.getElementById('active-rooms-empty').hidden).toBe(false);
        renderActiveRooms(undefined);
        expect(document.getElementById('active-rooms-table-wrap').hidden).toBe(true);
    });
});

describe('loadActiveRooms', () => {
    test('fetches /api/active-rooms and renders results', async () => {
        global.fetch = jest.fn(() =>
            Promise.resolve({
                json: () =>
                    Promise.resolve([
                        {
                            id: '1234',
                            host: 'Host1',
                            players: 2,
                            current_round: 1,
                            max_rounds: 5,
                            time_limit: 90,
                            visibility: 'public',
                            visibility_label: 'Publiczny',
                        },
                    ]),
            }),
        );
        await loadActiveRooms();
        expect(global.fetch).toHaveBeenCalledWith('/api/active-rooms');
        expect(document.getElementById('rooms-list').innerHTML).toContain('1234');
        expect(document.getElementById('active-rooms-table-wrap').hidden).toBe(false);
        expect(document.getElementById('active-rooms-empty').hidden).toBe(true);
    });

    test('shows empty state when the API returns an empty list', async () => {
        global.fetch = jest.fn(() => Promise.resolve({ json: () => Promise.resolve([]) }));
        await loadActiveRooms();
        expect(document.getElementById('active-rooms-empty').hidden).toBe(false);
        expect(document.getElementById('active-rooms-table-wrap').hidden).toBe(true);
    });

    test('logs an error and does not throw on fetch failure', async () => {
        const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
        global.fetch = jest.fn(() => Promise.reject(new Error('boom')));
        await expect(loadActiveRooms()).resolves.toBeUndefined();
        expect(spy).toHaveBeenCalledWith('Błąd podczas ładowania pokoi:', expect.any(Error));
        spy.mockRestore();
    });
});

describe('landing guide carousel', () => {
    const carouselDom = () => `
        ${baseDom()}
        <section class="landing-guide-carousel">
            <div class="landing-guide-carousel-track" id="landing-guide-carousel-track">
                <article class="landing-guide-carousel-slide">
                    <h3 class="landing-guide-carousel-slide-title">Kroki</h3>
                </article>
                <article class="landing-guide-carousel-slide">
                    <h3 class="landing-guide-carousel-slide-title">Kategorie</h3>
                </article>
            </div>
            <div class="landing-guide-carousel-dots" id="landing-guide-carousel-dots"></div>
            <p id="landing-guide-carousel-live" class="visually-hidden"></p>
            <button type="button" data-carousel-dir="next">next</button>
        </section>
    `;

    test('initLandingGuideCarousel activates the first slide and dots', () => {
        document.body.innerHTML = carouselDom();
        initLandingGuideCarousel();
        const track = document.getElementById('landing-guide-carousel-track');
        expect(track.style.transform).toBe('translateX(-0%)');
        const dots = document.querySelectorAll('.landing-guide-carousel-dot');
        expect(dots).toHaveLength(2);
        expect(dots[0].getAttribute('aria-selected')).toBe('true');
    });

    test('carousel next button advances slides', () => {
        document.body.innerHTML = carouselDom();
        initLandingGuideCarousel();
        document.querySelector('[data-carousel-dir="next"]').click();
        expect(document.getElementById('landing-guide-carousel-track').style.transform).toBe('translateX(-100%)');
    });
});

describe('landing quick join nickname', () => {
    test('connectFromLandingJoin prepares nickname before connect', () => {
        globalThis.connect = jest.fn();
        document.getElementById('landing_nickname').value = 'Zosia';
        document.getElementById('landing_room_code').value = '4821';
        connectFromLandingJoin();
        expect(document.getElementById('nickname').value).toBe('Zosia');
        expect(globalThis.connect).toHaveBeenCalled();
    });

    test('showLandingJoinCode reveals room code step', () => {
        document.body.innerHTML = `
            <div id="landing-anon-start"></motion>
            <div id="landing-anon-join" hidden></div>
            <input id="landing_nickname" />
            <input id="nickname" />
            <input id="nickname_join" />
        `;
        showLandingJoinCode();
        expect(document.getElementById('landing-anon-start').hidden).toBe(true);
        expect(document.getElementById('landing-anon-join').hidden).toBe(false);
    });
});

describe('room phase helpers', () => {
    test('setRoomPhase toggles lobby visibility', () => {
        document.body.innerHTML = `
            <section id="room-lobby"></section>
            <div id="game-layout"></div>
            <main id="game-main-area"></main>
            <div class="room-lobby-actions"></div>
            <div class="game-actions"><button id="btn-draw"></button></div>
        `;
        setRoomPhase('lobby');
        expect(document.body.classList.contains('room-phase-lobby')).toBe(true);
        expect(document.getElementById('room-lobby').hidden).toBe(false);
        expect(document.getElementById('game-main-area').hidden).toBe(true);
        expect(document.getElementById('game-layout').hidden).toBe(true);
    });

    test('renderLobbyRoster shows ready badges and eight slots', () => {
        document.body.innerHTML = '<div id="lobby-roster"></div><span id="lobby-player-count"></span>';
        renderLobbyRoster({ Anna: 0, Bob: 0 }, 'Anna', new Set(['Bob']), 'Anna');
        const roster = document.getElementById('lobby-roster');
        expect(roster.textContent).toContain('Anna');
        expect(roster.textContent).toContain('Gotowy');
        expect(roster.textContent).toContain('Czeka');
        expect(roster.querySelectorAll('.lobby-roster-item').length).toBe(8);
        expect(roster.querySelectorAll('.lobby-roster-item--empty').length).toBe(6);
        expect(document.getElementById('lobby-player-count').textContent).toContain('2/8');
    });
});

describe('landing room code sync', () => {
    test('syncRoomCodeInputs mirrors landing and modal fields', () => {
        const landing = document.getElementById('landing_room_code');
        const modal = document.getElementById('room_id');
        landing.value = ' 4821 ';
        expect(syncRoomCodeInputs()).toBe('4821');
        expect(modal.value).toBe('4821');
        expect(syncRoomCodeInputs('9012')).toBe('9012');
        expect(landing.value).toBe('9012');
        expect(modal.value).toBe('9012');
    });
});

describe('joinRoom global', () => {
    test('sets room_id input and opens the join modal', () => {
        globalThis.joinRoom('5678');
        expect(document.getElementById('room_id').value).toBe('5678');
        expect(document.getElementById('landing_room_code').value).toBe('5678');
        expect(document.getElementById('join-modal').style.display).toBe('flex');
    });
});

describe('restoreNickname', () => {
    test('restores custom nickname from localStorage', () => {
        localStorage.setItem('pm_nickname', 'Filip');
        localStorage.setItem('pm_nickname_custom', '1');
        const restored = restoreNickname();
        expect(restored).toBe('Filip');
        expect(document.getElementById('nickname').value).toBe('Filip');
        localStorage.removeItem('pm_nickname');
        localStorage.removeItem('pm_nickname_custom');
    });

    test('restores generated Gracz# nick from localStorage', () => {
        localStorage.setItem('pm_nickname', 'Gracz#2289');
        localStorage.removeItem('pm_nickname_custom');
        const restored = restoreNickname();
        expect(restored).toBe('Gracz#2289');
        expect(document.getElementById('nickname').value).toBe('Gracz#2289');
        localStorage.removeItem('pm_nickname');
    });

    test('assigns a generated Gracz# nick when no nick saved', () => {
        localStorage.removeItem('pm_nickname');
        localStorage.removeItem('pm_nickname_custom');
        const restored = restoreNickname();
        expect(restored).toMatch(/^Gracz#\d{4}$/);
        expect(document.getElementById('nickname').value).toBe(restored);
        expect(localStorage.getItem('pm_nickname')).toBeNull();
    });
});

describe('generatePlayerNickname', () => {
    test('returns Gracz# plus a four-digit number', () => {
        const nick = generatePlayerNickname();
        expect(nick).toMatch(/^Gracz#\d{4}$/);
        const number = Number(nick.slice(6));
        expect(number).toBeGreaterThanOrEqual(1000);
        expect(number).toBeLessThanOrEqual(9999);
    });
});

describe('tryAutoJoin', () => {
    test('hides inline join, shows lobby shell and connects immediately', () => {
        document.body.innerHTML = `
            <section id="room-inline-join" style="display: block;"></section>
            <div id="chat-section" style="display: none;">
                <section id="room-lobby" hidden></section>
                <main id="game-main-area" hidden></main>
            </div>
            <input id="nickname" value="Gracz#1234" />
        `;
        global.connect.mockClear();
        expect(tryAutoJoin('Gracz#1234', '4624')).toBe(true);
        expect(document.getElementById('room-inline-join').style.display).toBe('none');
        expect(document.getElementById('chat-section').style.display).toBe('block');
        expect(global.connect).toHaveBeenCalledTimes(1);
    });

    test('shows join form when auto-join is skipped after dissolve', () => {
        sessionStorage.setItem('pm_skip_auto_join', '1');
        window.history.replaceState({}, '', '/room/4624');
        document.body.innerHTML = `
            <section id="room-inline-join" style="display: none;"></section>
            <div id="chat-section" style="display: block;"></div>
            <input id="nickname" value="Gracz#1234" />
            <input id="room_id" />
            <p id="room-inline-label"></p>
            <select id="max_rounds"><option value="5" selected>5</option></select>
            <select id="time_limit"><option value="90" selected>90</option></select>
            <select id="room_visibility"><option value="public" selected>public</option></select>
        `;
        global.connect.mockClear();
        handleRoomRouteOnLoad('Gracz#1234');
        expect(document.getElementById('room-inline-join').style.display).toBe('block');
        expect(document.getElementById('chat-section').style.display).toBe('none');
        expect(global.connect).not.toHaveBeenCalled();
    });
});

describe('applyRoomSettingsFromUrl', () => {
    afterEach(() => {
        window.history.replaceState({}, '', '/');
    });

    test('applies rounds and limit from URL search params to selects', () => {
        window.history.replaceState({}, '', '/room/1234?rounds=10&limit=60');
        applyRoomSettingsFromUrl();
        expect(document.getElementById('max_rounds').value).toBe('10');
        expect(document.getElementById('time_limit').value).toBe('60');
    });

    test('applies rounds, limit and visibility from URL search params', () => {
        window.history.replaceState(
            {},
            '',
            'http://localhost/room/1234?rounds=3&limit=90&visibility=private',
        );
        applyRoomSettingsFromUrl();
        expect(document.getElementById('max_rounds').value).toBe('3');
        expect(document.getElementById('time_limit').value).toBe('90');
        expect(document.getElementById('room_visibility').value).toBe('private');
    });

    test('no-op when params are absent', () => {
        window.history.replaceState({}, '', '/');
        const roundsSel = document.getElementById('max_rounds');
        const limitSel = document.getElementById('time_limit');
        roundsSel.value = '5';
        limitSel.value = '90';
        applyRoomSettingsFromUrl();
        expect(roundsSel.value).toBe('5');
        expect(limitSel.value).toBe('90');
    });
});

describe('lottery haptics', () => {
    test('playLotterySpinHaptic calls a short pulse when vibrate exists', () => {
        const vibrate = jest.fn();
        globalThis.navigator.vibrate = vibrate;
        playLotterySpinHaptic();
        expect(vibrate).toHaveBeenCalledWith(12);
    });

    test('playLotteryRevealHaptic uses a gap pattern', () => {
        const vibrate = jest.fn();
        globalThis.navigator.vibrate = vibrate;
        playLotteryRevealHaptic();
        expect(vibrate).toHaveBeenCalledWith([22, 48, 28]);
    });

    test('playCountdownHaptic uses a short pulse', () => {
        const vibrate = jest.fn();
        globalThis.navigator.vibrate = vibrate;
        playCountdownHaptic();
        expect(vibrate).toHaveBeenCalledWith(10);
    });

    test('does not throw when vibrate is missing', () => {
        const saved = globalThis.navigator.vibrate;
        try {
            delete globalThis.navigator.vibrate;
        } catch {
            // jsdom may refuse delete; ignore
        }
        expect(() => {
            playLotterySpinHaptic();
            playLotteryRevealHaptic();
            playCountdownHaptic();
        }).not.toThrow();
        if (saved !== undefined) globalThis.navigator.vibrate = saved;
    });
});
