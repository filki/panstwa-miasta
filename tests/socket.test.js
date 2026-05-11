/**
 * @jest-environment jsdom
 */

// Mock DOM
document.body.innerHTML = `
    <div id="join-section"></div>
    <div id="chat-section" style="display: none;"></div>
    <div id="btn-leave" style="display: none;"></div>
    <div id="current-room"></div>
    <input id="nickname" value="TestUser" />
    <input id="room_id" value="1234" />
    <div id="categories">
        <input data-category="Państwo" />
        <input data-category="Miasto" />
    </div>
    <div id="round-timer"></div>
    <div id="current-letter"></div>
    <button id="btn-stop"></button>
    <button id="btn-draw"></button>
    <div id="sticky-timer"></div>
    <div id="sticky-time"></div>
    <div id="restart-settings" style="display: none;"></div>
    <button id="btn-restart-game"></button>
    <button id="btn-dissolve"></button>
    <div id="lottery-modal"></div>
    <div id="lottery-letter"></div>
`;

// Mock dependencies
global.initAudio = jest.fn();
global.playGong = jest.fn();
global.playTick = jest.fn();
global.addLog = jest.fn();
global.updateScoreboard = jest.fn();
global.initAudio = jest.fn();
global.playGong = jest.fn();
global.playTick = jest.fn();
global.enableInputs = jest.fn();
global.disableAndSubmit = jest.fn();
global.runLetterLottery = jest.fn((letter, cb) => cb());
global.alert = jest.fn();
global.confetti = jest.fn();

let lastWs;
global.WebSocket = jest.fn().mockImplementation(() => {
    lastWs = {
        send: jest.fn(),
        close: jest.fn(),
        readyState: 1, // OPEN
        onopen: null,
        onclose: null,
        onmessage: null,
        onerror: null
    };
    return lastWs;
});
global.WebSocket.OPEN = 1;

// Better Location Mock for JSDOM
const originalLocation = window.location;
delete window.location;
window.location = new URL('http://localhost/');
global.history.replaceState = jest.fn();
global.runLetterLottery = jest.fn((letter, cb) => cb());

beforeEach(() => {
    jest.clearAllMocks();
    document.getElementById('chat-section').style.display = 'none';
    document.getElementById('join-section').style.display = 'block';
});

const {
    connect,
    leaveRoom,
    sendJson,
    onRoundStarted,
    onStopRound,
    onRoundResults,
    onGameRestarted,
    getScoreColor,
    buildPlayerResultHtml,
    handleGameOver
} = require('../static/js/socket.js');

describe('Socket and Game Events', () => {
    test('connect includes room rounds and limit in URL', () => {
        globalThis.roomRounds = 10;
        globalThis.roomLimit = 60;
        connect();
        expect(global.WebSocket).toHaveBeenCalledWith(expect.stringContaining('?rounds=10&limit=60'));
        delete globalThis.roomRounds;
        delete globalThis.roomLimit;
    });

    test('sendJson sends message if ws is open', () => {
        connect();
        lastWs.readyState = 1; // OPEN
        sendJson({ type: 'test' });
        expect(lastWs.send).toHaveBeenCalledWith(JSON.stringify({ type: 'test' }));
    });

    test('sendJson does nothing if ws is not open', () => {
        connect();
        lastWs.readyState = 3; // CLOSED
        sendJson({ type: 'test' });
        expect(lastWs.send).not.toHaveBeenCalled();
    });

    test('ws.onclose handles code 1008', () => {
        connect();
        lastWs.onclose({ code: 1008 });
        expect(global.alert).toHaveBeenCalledWith(expect.stringContaining('Nick jest już zajęty'));
    });

    test('ws.onclose suppresses reconnect if isLeaving is true', () => {
        jest.useFakeTimers();
        connect();
        leaveRoom(); // Sets isLeaving = true
        lastWs.onclose({ code: 1000 });
        
        jest.advanceTimersByTime(2000);
        // Should only be called once (from the first connect)
        expect(global.WebSocket).toHaveBeenCalledTimes(1);
        jest.useRealTimers();
    });

    test('ws.onmessage handles system and chat messages', () => {
        connect();
        lastWs.onmessage({ data: JSON.stringify({ type: 'system', message: 'Hello' }) });
        expect(global.addLog).toHaveBeenCalledWith('<em>Hello</em>', 'system-msg');

        lastWs.onmessage({ data: JSON.stringify({ type: 'chat', sender: 'User', text: 'Hi' }) });
        expect(global.addLog).toHaveBeenCalled();
    });

    test('ws.onmessage handles score_update and room_dissolved', () => {
        connect();
        lastWs.onmessage({ data: JSON.stringify({ type: 'score_update', scores: { 'User': 10 }, host_name: 'User' }) });
        expect(global.updateScoreboard).toHaveBeenCalled();

        // room_dissolved uses alert and location.href
        lastWs.onmessage({ data: JSON.stringify({ type: 'room_dissolved', message: 'Room closed' }) });
        expect(global.alert).toHaveBeenCalledWith('Room closed');
    });

    test('ws.onerror logs error', () => {
        console.error = jest.fn();
        connect();
        lastWs.onerror('error');
        expect(console.error).toHaveBeenCalled();
    });

    test('runLetterLottery completes after duration', () => {
        jest.useFakeTimers();
        const onComplete = jest.fn();
        // Mock crypto.getRandomValues
        global.crypto = { getRandomValues: jest.fn().mockImplementation((arr) => arr[0] = 1) };
        
        const { runLetterLottery } = require('../static/js/socket.js');
        runLetterLottery('X', onComplete);
        
        jest.advanceTimersByTime(2500); // Animation duration
        jest.advanceTimersByTime(1500); // Timeout after animation
        
        expect(onComplete).toHaveBeenCalled();
        expect(document.getElementById('lottery-letter').innerText).toBe('X');
        jest.useRealTimers();
    });

    test('ws.onclose triggers reconnect if not leaving', () => {
        jest.useFakeTimers();
        connect();
        lastWs.onopen(); // Must be open to have chat-section visible
        lastWs.onclose({ code: 1000 });
        expect(global.addLog).toHaveBeenCalledWith(expect.stringContaining('Utracono połączenie'), "system-msg");
        
        jest.advanceTimersByTime(2000);
        expect(global.WebSocket).toHaveBeenCalledTimes(2);
        jest.useRealTimers();
    });

    test('leaveRoom closes socket and resets UI and clears timers', () => {
        globalThis.globalRoundTimer = setInterval(() => {}, 1000);
        globalThis.currentCountdown = setInterval(() => {}, 1000);
        leaveRoom();
        expect(document.getElementById('chat-section').style.display).toBe('none');
        expect(document.getElementById('join-section').style.display).toBe('block');
        expect(globalThis.globalRoundTimer).toBe(null);
        expect(globalThis.currentCountdown).toBe(null);
    });

    test('onRoundStarted updates UI and sets timer', () => {
        jest.useFakeTimers();
        onRoundStarted({ letter: 'A', time_limit: 30, current_round: 1, max_rounds: 5 });
        expect(document.getElementById('current-letter').textContent).toBe('A');
        expect(document.getElementById('round-timer').textContent).toBe('30s');
        
        jest.advanceTimersByTime(1000);
        expect(document.getElementById('round-timer').textContent).toBe('29s');
        jest.useRealTimers();
    });

    test('getScoreColor returns correct colors', () => {
        expect(getScoreColor(10)).toBe("var(--accent)");
        expect(getScoreColor(5)).toBe("var(--warning)");
        expect(getScoreColor(0)).toBe("var(--danger)");
    });

    test('buildPlayerResultHtml generates valid string', () => {
        const html = buildPlayerResultHtml('User', { total: 15, details: { 'Państwo': 10, 'Miasto': 5 } }, { 'Państwo': 'Polska', 'Miasto': 'Mława' });
        expect(html).toContain('User: +15 pkt');
        expect(html).toContain('Państwo:</span> Polska');
        expect(html).toContain('Miasto:</span> Mława');
    });

    test('handleGameOver triggers confetti and shows restart', () => {
        handleGameOver('TestUser');
        expect(global.addLog).toHaveBeenCalledWith(expect.stringContaining('Koniec Gry'), "system-msg");
        expect(document.getElementById('restart-settings').style.display).toBe('block');
        expect(global.confetti).toHaveBeenCalled();
    });

    test('onStopRound starts 10s countdown and submits', () => {
        jest.useFakeTimers();
        onStopRound({ sender: 'System' });
        expect(document.getElementById('btn-stop').innerHTML).toContain('10s');
        
        jest.advanceTimersByTime(1000);
        expect(document.getElementById('btn-stop').innerHTML).toContain('9s');
        
        jest.advanceTimersByTime(9000);
        expect(global.disableAndSubmit).toHaveBeenCalled();
        jest.useRealTimers();
    });

    test('onRoundResults updates scoreboard and UI', () => {
        onRoundResults({
            round_scores: { 'TestUser': { total: 10, details: {} } },
            answers: { 'TestUser': {} },
            total_scores: { 'TestUser': 10 },
            host_name: 'TestUser',
            game_over: false
        });
        expect(global.updateScoreboard).toHaveBeenCalled();
        expect(document.getElementById('current-letter').innerHTML).not.toBe('');
    });

    test('onGameRestarted resets UI', () => {
        onGameRestarted({
            scores: { 'TestUser': 0 },
            host_name: 'TestUser',
            sender: 'TestUser'
        });
        expect(document.getElementById('restart-settings').style.display).toBe('none');
        expect(document.getElementById('btn-draw').style.display).toBe('inline-block');
    });
});
