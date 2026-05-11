/**
 * @jest-environment jsdom
 */

// Mock dependencies before requiring the script
global.sendJson = jest.fn();
global.connect = jest.fn();
global.scrollTo = jest.fn();
global.alert = jest.fn();

// Require the script
const {
    addLog,
    updateScoreboard,
    showJoinInputs,
    createRoom,
    doCreateRoom,
    sendChat,
    loadActiveRooms
} = require('../static/js/ui.js');

describe('UI Logic', () => {
    beforeEach(() => {
        document.body.innerHTML = `
            <div id="logs"></div>
            <div id="scoreboard"></div>
            <div id="join-inputs" style="display: none;"></div>
            <div id="buttons-grid"></div>
            <div id="create-settings" style="display: none;"></div>
            <input id="nickname" value="TestUser" />
            <input id="room_id" />
            <input id="rounds-input" value="5" />
            <input id="limit-input" value="90" />
            <input id="message-input" value="Hello world" />
            <div id="active-rooms-section"></div>
            <div id="rooms-list"></div>
        `;
        jest.clearAllMocks();
    });
    test('addLog adds an entry to the logs div (html)', () => {
        addLog('<b>Bold</b>', 'html-msg', true);
        const logs = document.getElementById('logs');
        expect(logs.innerHTML).toContain('<b>Bold</b>');
    });

    test('addLog adds an entry to the logs div (text)', () => {
        addLog('Test text', 'text-msg', false);
        const logs = document.getElementById('logs');
        expect(logs.innerHTML).toContain('Test text');
    });

    test('addLog handles HTMLElement content', () => {
        const span = document.createElement('span');
        span.textContent = 'Span Content';
        addLog(span, 'html-msg');
        const logs = document.getElementById('logs');
        expect(logs.innerHTML).toContain('Span Content');
    });

    test('updateScoreboard renders scores correctly', () => {
        const scores = { 'Player1': 10, 'Player2': 20 };
        updateScoreboard(scores, 'Player2');
        const sb = document.getElementById('scoreboard');
        expect(sb.innerHTML).toContain('Player1');
        expect(sb.innerHTML).toContain('10 pkt');
        expect(sb.innerHTML).toContain('Player2');
        expect(sb.innerHTML).toContain('20 pkt');
        expect(sb.innerHTML).toContain('👑'); // Player2 is host
    });

    test('showJoinInputs changes display style', () => {
        showJoinInputs();
        expect(document.getElementById('join-inputs').style.display).toBe('block');
    });

    test('createRoom hides buttons and shows settings', () => {
        document.getElementById('nickname').value = 'Test';
        createRoom();
        expect(document.getElementById('buttons-grid').style.display).toBe('none');
        expect(document.getElementById('create-settings').style.display).toBe('block');
    });

    test('doCreateRoom sets room_id and calls connect', () => {
        global.crypto = { getRandomValues: (arr) => { arr[0] = 1234567; return arr; } };
        doCreateRoom();
        expect(document.getElementById('room_id').value).not.toBe('');
        expect(global.connect).toHaveBeenCalled();
    });

    test('sendChat sends json and clears input', () => {
        const input = document.getElementById('message-input');
        input.value = 'Hello';
        sendChat();
        expect(global.sendJson).toHaveBeenCalledWith({ type: 'chat', text: 'Hello' });
        expect(input.value).toBe('');
    });

    test('loadActiveRooms renders room cards', async () => {
        const mockRooms = [{ id: '1234', host: 'Host1', round: 1, players: 2 }];
        global.fetch = jest.fn(() => Promise.resolve({ json: () => Promise.resolve(mockRooms) }));
        await loadActiveRooms();
        const list = document.getElementById('rooms-list');
        expect(list.innerHTML).toContain('Pokój #1234');
        const card = list.querySelector('.room-card');
        card.onclick();
        expect(document.getElementById('room_id').value).toBe('1234');
    });

    test('addLog handles text content (isRawHtml=false)', () => {
        addLog('<b>Text</b>', 'text-msg', false);
        const logs = document.getElementById('logs');
        expect(logs.textContent).toContain('<b>Text</b>');
        expect(logs.innerHTML).not.toContain('<b>Text</b>');
    });

    test('addLog returns early if logsDiv is missing', () => {
        document.body.innerHTML = '';
        addLog('test', 'test'); // Should not throw
    });

    test('updateScoreboard sorts players by score', () => {
        const scores = { 'C': 10, 'A': 30, 'B': 20 };
        updateScoreboard(scores, 'A');
        const items = document.querySelectorAll('.score-item');
        expect(items[0].textContent).toContain('A');
        expect(items[1].textContent).toContain('B');
        expect(items[2].textContent).toContain('C');
    });

    test('loadActiveRooms handles fetch error', async () => {
        console.error = jest.fn();
        global.fetch = jest.fn(() => Promise.reject('API Error'));
        await loadActiveRooms();
        expect(console.error).toHaveBeenCalledWith("Błąd podczas ładowania pokoi:", "API Error");
    });

    test('updateScoreboard returns early if sb is missing', () => {
        document.body.innerHTML = '';
        updateScoreboard({}, 'host'); // Should not throw
    });

    test('createRoom alerts if nickname is empty', () => {
        document.getElementById('nickname').value = '';
        createRoom();
        expect(global.alert).toHaveBeenCalledWith(expect.stringContaining('podać swój nick'));
    });

    test('doCreateRoom uses default values if inputs are empty', () => {
        document.getElementById('rounds-input').value = '';
        document.getElementById('limit-input').value = '';
        global.crypto = { getRandomValues: (arr) => { arr[0] = 1234567; return arr; } };
        doCreateRoom();
        expect(globalThis.roomRounds).toBe(5);
        expect(globalThis.roomLimit).toBe(90);
    });

    test('loadActiveRooms card click scrolls to top', async () => {
        const mockRooms = [{ id: '1234', host: 'Host', round: 1, players: 2 }];
        global.fetch = jest.fn(() => Promise.resolve({ json: () => Promise.resolve(mockRooms) }));
        await loadActiveRooms();
        const card = document.querySelector('.room-card');
        card.click();
        expect(global.scrollTo).toHaveBeenCalled();
    });

    test('loadActiveRooms handles null or empty rooms', async () => {
        // Reset DOM for this test
        document.body.innerHTML = '<div id="active-rooms-section"></div><div id="rooms-list"></div>';
        global.fetch = jest.fn(() => Promise.resolve({ json: () => Promise.resolve(null) }));
        await loadActiveRooms();
        expect(document.getElementById('active-rooms-section').style.display).toBe('none');
        
        global.fetch = jest.fn(() => Promise.resolve({ json: () => Promise.resolve([]) }));
        await loadActiveRooms();
        expect(document.getElementById('active-rooms-section').style.display).toBe('none');
    });
});
