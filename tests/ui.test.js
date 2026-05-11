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
    addLog,
    updateScoreboard,
    sendChat,
    buildRoomRow,
    renderActiveRooms,
    loadActiveRooms,
    restoreNickname,
    applyRoomSettingsFromUrl,
} = require('../static/js/ui.js');

const baseDom = () => `
    <div id="logs"></div>
    <div id="scoreboard"></div>
    <div id="join-modal" style="display: none;"></div>
    <div id="create-modal" style="display: none;"></div>
    <div id="lottery-modal" style="display: none;"></div>
    <input id="nickname" />
    <input id="room_id" />
    <select id="max_rounds"><option value="5">5</option><option value="10">10</option></select>
    <select id="time_limit"><option value="60">60</option><option value="90">90</option></select>
    <input id="message-input" />
    <div id="active-rooms-section"></div>
    <table><tbody id="rooms-list"></tbody></table>
`;

beforeEach(() => {
    document.body.innerHTML = baseDom();
    jest.clearAllMocks();
    globalThis.sendJson = global.sendJson;
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
            mode: 'public',
        });
        expect(tr.tagName).toBe('TR');
        expect(tr.innerHTML).toContain('1234');
        expect(tr.innerHTML).toContain('Filip');
        expect(tr.innerHTML).toContain('3 graczy');
        expect(tr.innerHTML).toContain('2/5');
        expect(tr.innerHTML).toContain('90s');
        expect(tr.innerHTML).toContain('public');
        expect(tr.querySelector('button.btn-join-small')).not.toBeNull();
    });

    test('falls back to "Anonim" when host is missing', () => {
        const tr = buildRoomRow({
            id: '9999',
            players: 1,
            current_round: 0,
            max_rounds: 3,
            time_limit: 60,
            mode: 'private',
        });
        expect(tr.innerHTML).toContain('Anonim');
    });
});

describe('renderActiveRooms', () => {
    test('shows the section and appends a row per room', () => {
        renderActiveRooms([
            { id: '1', host: 'A', players: 1, current_round: 0, max_rounds: 5, time_limit: 60, mode: 'public' },
            { id: '2', host: 'B', players: 2, current_round: 1, max_rounds: 5, time_limit: 90, mode: 'private' },
        ]);
        expect(document.getElementById('active-rooms-section').style.display).toBe('block');
        const rows = document.querySelectorAll('#rooms-list tr');
        expect(rows).toHaveLength(2);
    });

    test('hides the section when there are no rooms', () => {
        renderActiveRooms([]);
        expect(document.getElementById('active-rooms-section').style.display).toBe('none');
    });

    test('hides the section when input is null/undefined', () => {
        renderActiveRooms(null);
        expect(document.getElementById('active-rooms-section').style.display).toBe('none');
        renderActiveRooms(undefined);
        expect(document.getElementById('active-rooms-section').style.display).toBe('none');
    });
});

describe('loadActiveRooms', () => {
    test('fetches /api/active-rooms and renders results', async () => {
        global.fetch = jest.fn(() =>
            Promise.resolve({
                json: () =>
                    Promise.resolve([
                        { id: '1234', host: 'Host1', players: 2, current_round: 1, max_rounds: 5, time_limit: 90, mode: 'public' },
                    ]),
            }),
        );
        await loadActiveRooms();
        expect(global.fetch).toHaveBeenCalledWith('/api/active-rooms');
        expect(document.getElementById('rooms-list').innerHTML).toContain('1234');
        expect(document.getElementById('active-rooms-section').style.display).toBe('block');
    });

    test('hides the section when the API returns an empty list', async () => {
        global.fetch = jest.fn(() => Promise.resolve({ json: () => Promise.resolve([]) }));
        await loadActiveRooms();
        expect(document.getElementById('active-rooms-section').style.display).toBe('none');
    });

    test('logs an error and does not throw on fetch failure', async () => {
        const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
        global.fetch = jest.fn(() => Promise.reject(new Error('boom')));
        await expect(loadActiveRooms()).resolves.toBeUndefined();
        expect(spy).toHaveBeenCalledWith('Błąd podczas ładowania pokoi:', expect.any(Error));
        spy.mockRestore();
    });
});

describe('joinRoom global', () => {
    test('sets room_id input and opens the join modal', () => {
        globalThis.joinRoom('5678');
        expect(document.getElementById('room_id').value).toBe('5678');
        expect(document.getElementById('join-modal').style.display).toBe('flex');
    });
});

describe('restoreNickname', () => {
    test('restores nickname from localStorage', () => {
        localStorage.setItem('pm_nickname', 'Filip');
        const restored = restoreNickname();
        expect(restored).toBe('Filip');
        expect(document.getElementById('nickname').value).toBe('Filip');
        localStorage.removeItem('pm_nickname');
    });

    test('returns null when no nickname is stored', () => {
        localStorage.removeItem('pm_nickname');
        const restored = restoreNickname();
        expect(restored).toBeNull();
        expect(document.getElementById('nickname').value).toBe('');
    });
});

describe('applyRoomSettingsFromUrl', () => {
    test('applies rounds and limit from URL search params to selects', () => {
        const originalLocation = globalThis.location;
        delete globalThis.location;
        globalThis.location = new URL('http://localhost/room/1234?rounds=10&limit=60');
        applyRoomSettingsFromUrl();
        expect(document.getElementById('max_rounds').value).toBe('10');
        expect(document.getElementById('time_limit').value).toBe('60');
        globalThis.location = originalLocation;
    });

    test('no-op when params are absent', () => {
        const originalLocation = globalThis.location;
        delete globalThis.location;
        globalThis.location = new URL('http://localhost/');
        const roundsSel = document.getElementById('max_rounds');
        const limitSel = document.getElementById('time_limit');
        roundsSel.value = '5';
        limitSel.value = '90';
        applyRoomSettingsFromUrl();
        expect(roundsSel.value).toBe('5');
        expect(limitSel.value).toBe('90');
        globalThis.location = originalLocation;
    });
});
