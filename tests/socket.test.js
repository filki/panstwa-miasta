/**
 * @jest-environment jsdom
 * @jest-environment-options { "url": "http://localhost/room/1234" }
 */

// Globals that socket.js calls into (defined in audio.js, game.js, ui.js).
global.initAudio = jest.fn();
global.playGong = jest.fn();
global.playTick = jest.fn();
global.addLog = jest.fn();
global.updateScoreboard = jest.fn();
global.enableInputs = jest.fn();
global.disableAndSubmit = jest.fn();
global.alert = jest.fn();
global.confetti = jest.fn();
global.hideModals = jest.fn();

// WebSocket constructor mock — exposes last instance for assertions.
let lastWs;
global.WebSocket = jest.fn().mockImplementation((url) => {
    lastWs = {
        url,
        send: jest.fn(),
        close: jest.fn(),
        readyState: 1,
        onopen: null,
        onclose: null,
        onmessage: null,
        onerror: null,
    };
    return lastWs;
});
global.WebSocket.OPEN = 1;

// Suppress jsdom navigation noise: we never want real page navigation in
// tests, only to observe what socket.js *would* have done.
jest.spyOn(window.history, 'replaceState').mockImplementation(() => {});

const FULL_DOM = `
    <header>
        <nav>
            <a id="nav-home-link" href="/">Strona główna</a>
            <span id="nav-room-info" style="display: none;">
                Pokój <strong id="nav-room-code"></strong>
            </span>
        </nav>
    </header>

    <div id="join-section" style="display: block;"></div>
    <div id="chat-section" style="display: none;"></div>
    <div id="join-modal" style="display: none;"></div>
    <div id="create-modal" style="display: none;"></div>
    <div id="lottery-modal" style="display: none;">
        <div id="lottery-letter"></div>
    </div>

    <input id="nickname" value="TestUser" />
    <input id="room_id" value="1234" />

    <select id="max_rounds">
        <option value="5">5</option>
        <option value="10" selected>10</option>
    </select>
    <select id="time_limit">
        <option value="60" selected>60</option>
        <option value="90">90</option>
    </select>

    <span id="current-room"></span>
    <button id="btn-leave" style="display: none;"></button>
    <div id="room-inline-join" style="display: none;"></div>

    <div id="game-layout">
        <aside id="scoreboard-sidebar"></aside>
        <main id="game-main-area">
            <div id="categories">
                <input data-category="Państwo" />
                <input data-category="Miasto" />
            </div>
            <div id="round-timer"></div>
            <div id="current-letter">?</div>
            <button id="btn-stop">🛑 STOP!</button>
            <button id="btn-draw"></button>
            <div id="sticky-timer" style="display: none;">
                <span id="sticky-time">10</span>
            </div>
            <div id="restart-settings" style="display: none;">
                <button id="btn-restart-game" style="display: none;"></button>
                <button id="btn-dissolve" style="display: none;"></button>
            </div>
        </main>
        <aside id="chat-sidebar"></aside>
    </div>

    <div id="logs"></div>
`;

beforeEach(() => {
    document.body.innerHTML = FULL_DOM;
    jest.clearAllMocks();
    // Reset module-level state in socket.js (myNick, isLeaving, ws) by
    // re-evaluating the module — each test gets fresh closure state.
    jest.resetModules();
});

// helper: require fresh socket.js per test (after jest.resetModules)
const loadSocket = () => require('../static/js/socket.js');

describe('connect()', () => {
    test('opens a WebSocket to /ws/<roomId>/<nick> with rounds & limit from selects', () => {
        const { connect } = loadSocket();
        connect();
        expect(global.WebSocket).toHaveBeenCalledTimes(1);
        const url = lastWs.url;
        expect(url).toMatch(/^ws:\/\/localhost\/ws\/1234\/TestUser\?/);
        expect(url).toContain('rounds=10');
        expect(url).toContain('limit=60');
    });

    test('alerts when nickname is empty', () => {
        document.getElementById('nickname').value = '';
        const { connect } = loadSocket();
        connect();
        expect(global.alert).toHaveBeenCalledWith(expect.stringContaining('nickname'));
        expect(global.WebSocket).not.toHaveBeenCalled();
    });

    test('ws.onopen reveals chat and navbar room badge', () => {
        const { connect } = loadSocket();
        connect();
        lastWs.onopen();
        expect(document.getElementById('chat-section').style.display).toBe('block');
        expect(document.getElementById('btn-leave').style.display).toBe('inline-flex');
        expect(document.getElementById('current-room').textContent).toBe('1234');
        expect(document.getElementById('nav-room-info').style.display).toBe('inline-flex');
        expect(document.getElementById('nav-home-link').style.display).toBe('none');
        expect(global.updateScoreboard).toHaveBeenCalledWith({}, '');
    });
});

describe('sendJson()', () => {
    test('sends serialised payload when the socket is open', () => {
        const { connect, sendJson } = loadSocket();
        connect();
        lastWs.readyState = 1;
        sendJson({ type: 'chat', text: 'Hi' });
        expect(lastWs.send).toHaveBeenCalledWith(JSON.stringify({ type: 'chat', text: 'Hi' }));
    });

    test('is a no-op when the socket is closed', () => {
        const { connect, sendJson } = loadSocket();
        connect();
        lastWs.readyState = 3;
        sendJson({ type: 'chat', text: 'Hi' });
        expect(lastWs.send).not.toHaveBeenCalled();
    });
});

describe('ws lifecycle', () => {
    test('onclose 1008 alerts the user about a nickname clash', () => {
        const { connect } = loadSocket();
        connect();
        lastWs.onclose({ code: 1008 });
        expect(global.alert).toHaveBeenCalledWith(expect.stringContaining('Nick'));
    });

    test('onclose triggers reconnect when chat is visible and not leaving', () => {
        jest.useFakeTimers();
        const { connect } = loadSocket();
        connect();
        lastWs.onopen();
        lastWs.onclose({ code: 1000 });
        expect(global.addLog).toHaveBeenCalledWith(
            expect.stringContaining('Utracono połączenie'),
            'system-msg',
        );
        jest.advanceTimersByTime(2000);
        expect(global.WebSocket).toHaveBeenCalledTimes(2);
        jest.useRealTimers();
    });

    test('onclose suppresses reconnect when leaveRoom() was called', () => {
        jest.useFakeTimers();
        const { connect, leaveRoom } = loadSocket();
        connect();
        leaveRoom();
        lastWs.onclose({ code: 1000 });
        jest.advanceTimersByTime(2500);
        expect(global.WebSocket).toHaveBeenCalledTimes(1);
        jest.useRealTimers();
    });

    test('onerror logs to console', () => {
        const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
        const { connect } = loadSocket();
        connect();
        lastWs.onerror(new Error('boom'));
        expect(spy).toHaveBeenCalled();
        spy.mockRestore();
    });
});

describe('ws.onmessage dispatch', () => {
    test('system messages call addLog with italic markup', () => {
        const { connect } = loadSocket();
        connect();
        lastWs.onmessage({ data: JSON.stringify({ type: 'system', message: 'Hello' }) });
        expect(global.addLog).toHaveBeenCalledWith('<em>Hello</em>', 'system-msg');
    });

    test('chat messages append a structured element through addLog', () => {
        const { connect } = loadSocket();
        connect();
        lastWs.onmessage({
            data: JSON.stringify({ type: 'chat', sender: 'Filip', text: 'cześć' }),
        });
        expect(global.addLog).toHaveBeenCalled();
        const [node] = global.addLog.mock.calls.at(-1);
        expect(node).toBeInstanceOf(HTMLElement);
        expect(node.textContent).toContain('Filip');
        expect(node.textContent).toContain('cześć');
    });

    test('score_update updates the scoreboard', () => {
        const { connect } = loadSocket();
        connect();
        lastWs.onmessage({
            data: JSON.stringify({ type: 'score_update', scores: { Filip: 5 }, host_name: 'Filip' }),
        });
        expect(global.updateScoreboard).toHaveBeenCalledWith({ Filip: 5 }, 'Filip');
    });

    test('room_dissolved alerts the user', () => {
        const { connect } = loadSocket();
        connect();
        lastWs.onmessage({ data: JSON.stringify({ type: 'room_dissolved', message: 'gone' }) });
        expect(global.alert).toHaveBeenCalledWith('gone');
    });
});

describe('leaveRoom()', () => {
    test('toggles UI, closes the socket and clears timers', () => {
        const { connect, leaveRoom } = loadSocket();
        connect();
        lastWs.onopen();
        globalThis.globalRoundTimer = setInterval(() => {}, 1000);
        globalThis.currentCountdown = setInterval(() => {}, 1000);
        leaveRoom();
        expect(document.getElementById('chat-section').style.display).toBe('none');
        expect(document.getElementById('join-section').style.display).toBe('block');
        expect(document.getElementById('btn-leave').style.display).toBe('none');
        expect(document.getElementById('nav-room-info').style.display).toBe('none');
        expect(globalThis.globalRoundTimer).toBeNull();
        expect(globalThis.currentCountdown).toBeNull();
        expect(lastWs.close).toHaveBeenCalled();
    });
});

describe('round event handlers', () => {
    test('onRoundStarted reveals the letter and starts a countdown timer', () => {
        jest.useFakeTimers();
        globalThis.runLetterLottery = (_letter, cb) => cb();
        const { onRoundStarted } = loadSocket();
        onRoundStarted({ letter: 'A', time_limit: 30, current_round: 1, max_rounds: 5 });
        const timer = document.getElementById('round-timer');
        expect(document.getElementById('current-letter').textContent).toBe('A');
        expect(timer.textContent).toBe('30s');
        jest.advanceTimersByTime(1000);
        expect(timer.textContent).toBe('29s');
        jest.useRealTimers();
        delete globalThis.runLetterLottery;
    });

    test('onStopRound starts a 10s countdown and submits when it elapses', () => {
        jest.useFakeTimers();
        const { onStopRound } = loadSocket();
        onStopRound({ sender: 'System' });
        const btn = document.getElementById('btn-stop');
        expect(btn.innerHTML).toContain('10s');
        jest.advanceTimersByTime(1000);
        expect(btn.innerHTML).toContain('9s');
        jest.advanceTimersByTime(9000);
        expect(global.disableAndSubmit).toHaveBeenCalled();
        jest.useRealTimers();
    });

    test('onRoundResults pushes summary to addLog and updates scoreboard', () => {
        const { onRoundResults } = loadSocket();
        onRoundResults({
            round_scores: { TestUser: { total: 10, details: {} } },
            answers: { TestUser: {} },
            total_scores: { TestUser: 10 },
            host_name: 'TestUser',
            game_over: false,
        });
        expect(global.addLog).toHaveBeenCalled();
        expect(global.updateScoreboard).toHaveBeenCalledWith({ TestUser: 10 }, 'TestUser');
    });

    test('onGameRestarted resets game layout and inputs', () => {
        const { onGameRestarted } = loadSocket();
        document.getElementById('game-layout').classList.add('game-over');
        document.getElementById('chat-sidebar').classList.add('hidden');
        onGameRestarted({ scores: { TestUser: 0 }, host_name: 'TestUser', sender: 'TestUser' });
        expect(document.getElementById('game-layout').classList.contains('game-over')).toBe(false);
        expect(document.getElementById('chat-sidebar').classList.contains('hidden')).toBe(false);
        expect(document.getElementById('btn-draw').style.display).toBe('inline-block');
        expect(global.updateScoreboard).toHaveBeenCalledWith({ TestUser: 0 }, 'TestUser');
    });
});

describe('pure helpers', () => {
    test('getScoreColor maps scores to design tokens', () => {
        const { getScoreColor } = loadSocket();
        expect(getScoreColor(15)).toBe('var(--pts-15)');
        expect(getScoreColor(10)).toBe('var(--pts-10)');
        expect(getScoreColor(5)).toBe('var(--pts-5)');
        expect(getScoreColor(0)).toBe('var(--danger)');
    });

    test('buildPlayerResultHtml renders a single-line summary', () => {
        const { buildPlayerResultHtml } = loadSocket();
        const html = buildPlayerResultHtml('Filip', { total: 15, details: {} }, {});
        expect(html).toContain('Filip');
        expect(html).toContain('+15 pkt');
    });
});

describe('handleGameOver()', () => {
    test('reshuffles layout, reveals restart settings and fires confetti', () => {
        const { handleGameOver } = loadSocket();
        handleGameOver('TestUser');
        expect(document.getElementById('game-layout').classList.contains('game-over')).toBe(true);
        expect(document.getElementById('game-main-area').style.display).toBe('none');
        expect(document.getElementById('restart-settings').style.display).toBe('block');
        expect(global.confetti).toHaveBeenCalled();
    });
});

describe('runLetterLottery()', () => {
    test('cycles through random letters and resolves with the target', () => {
        jest.useFakeTimers();
        globalThis.crypto = { getRandomValues: (arr) => { arr[0] = 1; return arr; } };
        const onComplete = jest.fn();
        const { runLetterLottery } = loadSocket();
        runLetterLottery('X', onComplete);
        jest.advanceTimersByTime(2500);
        jest.advanceTimersByTime(1500);
        expect(onComplete).toHaveBeenCalled();
        expect(document.getElementById('lottery-letter').innerText).toBe('X');
        jest.useRealTimers();
    });
});
