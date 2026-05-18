/**
 * @jest-environment jsdom
 * @jest-environment-options { "url": "http://localhost/room/1234" }
 */

// Globals that socket.js calls into (defined in audio.js, game.js, ui.js).
global.initAudio = jest.fn();
global.playGong = jest.fn();
global.playTick = jest.fn();
global.playLotterySpinTick = jest.fn();
global.playRoundStartReveal = jest.fn();
global.playLotterySpinHaptic = jest.fn();
global.playLotteryRevealHaptic = jest.fn();
global.playCountdownHaptic = jest.fn();
global.addLog = jest.fn();
global.updateScoreboard = jest.fn();
global.enableInputs = jest.fn();
global.disableAndSubmit = jest.fn();
global.alert = jest.fn();
global.confirm = jest.fn(() => true);
global.confetti = jest.fn();
global.hideModals = jest.fn();
global.setRoomPhase = jest.fn();
global.syncRoomLobbySettings = jest.fn();

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
jest.spyOn(window.history, "replaceState").mockImplementation(() => {});

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
    <div id="chat-section" style="display: none;">
        <section id="room-lobby" hidden></section>
    </div>
    <div id="join-modal" style="display: none;"></div>
    <div id="create-modal" style="display: none;"></div>
    <div id="lottery-modal" style="display: none;">
        <div id="lottery-letter"></div>
    </div>
    <div id="round-countdown-overlay" hidden><div id="round-countdown-num"></div></div>
    <div id="round-results-overlay" hidden aria-hidden="true">
        <button type="button" class="round-results-overlay-backdrop" aria-label="Zamknij podsumowanie rundy"></button>
        <section class="round-results-modal" role="dialog" aria-modal="true" aria-labelledby="round-results-title">
            <header class="round-results-modal-head">
                <h2 id="round-results-title" class="round-results-modal-title">Podsumowanie rundy</h2>
            </header>
            <div id="round-results-modal-body" class="round-results-modal-body"></div>
            <footer class="round-results-modal-foot">
                <button type="button" id="btn-round-results-dismiss" class="round-results-dismiss-btn">Dalej</button>
            </footer>
        </section>
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
    <select id="room_visibility">
        <option value="public" selected>public</option>
        <option value="private">private</option>
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
                <div id="game-over-results" hidden>
                    <h3 class="game-over-results-title">Wynik końcowy</h3>
                    <div id="game-over-results-body"></div>
                </div>
                <button id="btn-restart-game" style="display: none;"></button>
                <button id="btn-dissolve" style="display: none;"></button>
                <div id="game-over-share" style="display: none;">
                    <a id="share-link-anchor" href="#">link</a>
                    <button type="button" id="btn-copy-share"></button>
                    <button type="button" id="btn-native-share" style="display: none;"></button>
                </div>
            </div>
        </main>
        <aside id="chat-sidebar"></aside>
    </div>

    <section id="room-postgame" hidden></section>

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
const loadSocket = () => require("../static/js/socket.js");

describe("connect()", () => {
  test("opens a WebSocket to /ws/<roomId>/<nick> with rounds & limit from selects", () => {
    const { connect } = loadSocket();
    connect();
    expect(global.WebSocket).toHaveBeenCalledTimes(1);
    const url = lastWs.url;
    expect(url).toMatch(/^ws:\/\/localhost\/ws\/1234\/TestUser\?/);
    expect(url).toContain("rounds=10");
    expect(url).toContain("limit=60");
    expect(url).toContain("visibility=public");
    expect(window.history.replaceState).toHaveBeenCalledWith(
      null,
      "",
      "/room/1234?rounds=10&limit=60&visibility=public",
    );
  });

  test("uses visibility=private from create modal when connecting", () => {
    document.getElementById("create-modal").style.display = "flex";
    document.getElementById("room_visibility").value = "private";
    const { connect } = loadSocket();
    connect();
    expect(lastWs.url).toContain("visibility=private");
  });

  test("assigns a generated nickname when the input is empty", () => {
    global.ensureNicknameInput = jest.fn(() => "Gracz#2137");
    document.getElementById("nickname").value = "";
    const { connect } = loadSocket();
    connect();
    expect(global.ensureNicknameInput).toHaveBeenCalled();
    expect(global.WebSocket).toHaveBeenCalledTimes(1);
    expect(lastWs.url).toContain("Gracz%232137");
  });

  test("ws.onopen reveals chat and navbar room badge", () => {
    const { connect } = loadSocket();
    connect();
    lastWs.onopen();
    expect(document.getElementById("chat-section").style.display).toBe("block");
    expect(document.getElementById("btn-leave").style.display).toBe(
      "inline-flex",
    );
    expect(document.getElementById("current-room").textContent).toBe("1234");
    expect(document.getElementById("nav-room-info").style.display).toBe(
      "inline-flex",
    );
    expect(document.getElementById("nav-home-link").style.display).toBe("none");
    expect(global.updateScoreboard).not.toHaveBeenCalled();
    expect(global.setRoomPhase).toHaveBeenCalledWith("lobby");
    expect(global.syncRoomLobbySettings).toHaveBeenCalledWith("1234");
  });

  test("ws.onopen does not wipe scoreboard; score_update from server fills it", () => {
    const { connect } = loadSocket();
    connect();
    lastWs.onopen();
    expect(global.updateScoreboard).not.toHaveBeenCalled();
    lastWs.onmessage({
      data: JSON.stringify({
        type: "score_update",
        scores: { Anna: 7, Bob: 3 },
        host_name: "Anna",
      }),
    });
    expect(global.updateScoreboard).toHaveBeenCalledWith(
      { Anna: 7, Bob: 3 },
      "Anna",
      "TestUser",
      undefined,
      undefined,
    );
  });
});

describe("sendJson()", () => {
  test("sends serialised payload when the socket is open", () => {
    const { connect, sendJson } = loadSocket();
    connect();
    lastWs.readyState = 1;
    sendJson({ type: "chat", text: "Hi" });
    expect(lastWs.send).toHaveBeenCalledWith(
      JSON.stringify({ type: "chat", text: "Hi" }),
    );
  });

  test("is a no-op when the socket is closed", () => {
    const { connect, sendJson } = loadSocket();
    connect();
    lastWs.readyState = 3;
    sendJson({ type: "chat", text: "Hi" });
    expect(lastWs.send).not.toHaveBeenCalled();
  });
});

describe("ws lifecycle", () => {
  test("onclose 1008 alerts the user about a nickname clash", () => {
    const { connect } = loadSocket();
    connect();
    lastWs.onclose({ code: 1008 });
    expect(global.alert).toHaveBeenCalledWith(expect.stringContaining("Nick"));
  });

  test("onclose 4401 alerts kicked by host and suppresses reconnect", () => {
    jest.useFakeTimers();
    const { connect } = loadSocket();
    connect();
    lastWs.onopen();
    lastWs.onclose({ code: 4401 });
    expect(global.alert).toHaveBeenCalledWith(
      expect.stringContaining("wyrzucił"),
    );
    jest.advanceTimersByTime(2500);
    expect(global.WebSocket).toHaveBeenCalledTimes(1);
    jest.useRealTimers();
  });

  test("onclose triggers reconnect when chat is visible and not leaving", () => {
    jest.useFakeTimers();
    const { connect } = loadSocket();
    connect();
    lastWs.onopen();
    lastWs.onclose({ code: 1000 });
    expect(global.addLog).toHaveBeenCalledWith(
      expect.stringContaining("Utracono połączenie"),
      "system-msg",
    );
    jest.advanceTimersByTime(2000);
    expect(global.WebSocket).toHaveBeenCalledTimes(2);
    jest.useRealTimers();
  });

  test("stale websocket onclose does not schedule another reconnect", () => {
    jest.useFakeTimers();
    const { connect } = loadSocket();
    connect();
    const first = lastWs;
    first.onopen();
    const staleClose = first.onclose;
    connect();
    lastWs.onopen();
    staleClose({ code: 1000 });
    jest.advanceTimersByTime(2500);
    expect(global.WebSocket).toHaveBeenCalledTimes(2);
    jest.useRealTimers();
  });

  test("onclose suppresses reconnect when leaveRoom() was called", () => {
    jest.useFakeTimers();
    const { connect, leaveRoom } = loadSocket();
    connect();
    leaveRoom();
    lastWs.onclose({ code: 1000 });
    jest.advanceTimersByTime(2500);
    expect(global.WebSocket).toHaveBeenCalledTimes(1);
    jest.useRealTimers();
  });

  test("onerror logs to console", () => {
    const spy = jest.spyOn(console, "error").mockImplementation(() => {});
    const { connect } = loadSocket();
    connect();
    lastWs.onerror(new Error("boom"));
    expect(spy).toHaveBeenCalled();
    spy.mockRestore();
  });
});

describe("ws.onmessage dispatch", () => {
  test("system messages call addLog with italic markup", () => {
    const { connect } = loadSocket();
    connect();
    lastWs.onmessage({
      data: JSON.stringify({ type: "system", message: "Hello" }),
    });
    expect(global.addLog).toHaveBeenCalledWith("<em>Hello</em>", "system-msg");
  });

  test("chat messages append a structured element through addLog", () => {
    const { connect } = loadSocket();
    connect();
    lastWs.onmessage({
      data: JSON.stringify({ type: "chat", sender: "Filip", text: "cześć" }),
    });
    expect(global.addLog).toHaveBeenCalled();
    const [node] = global.addLog.mock.calls.at(-1);
    expect(node).toBeInstanceOf(HTMLElement);
    expect(node.textContent).toContain("Filip");
    expect(node.textContent).toContain("cześć");
  });

  test("score_update updates the scoreboard", () => {
    const { connect } = loadSocket();
    connect();
    lastWs.onmessage({
      data: JSON.stringify({
        type: "score_update",
        scores: { Filip: 5 },
        host_name: "Filip",
      }),
    });
    expect(global.updateScoreboard).toHaveBeenCalledWith(
      { Filip: 5 },
      "Filip",
      "TestUser",
      undefined,
      undefined,
    );
  });

  test("round_started switches to playing phase", () => {
    globalThis.runRoundStartCountdown = (cb) => cb();
    globalThis.runLetterLottery = (_letter, cb) => cb();
    const { connect } = loadSocket();
    connect();
    lastWs.onmessage({
      data: JSON.stringify({
        type: "round_started",
        letter: "M",
        current_round: 1,
        max_rounds: 5,
        time_limit: 90,
      }),
    });
    expect(global.setRoomPhase).toHaveBeenCalledWith("playing");
    delete globalThis.runRoundStartCountdown;
    delete globalThis.runLetterLottery;
  });

  test("kick_denied logs a system message", () => {
    const { connect } = loadSocket();
    connect();
    lastWs.onmessage({
      data: JSON.stringify({
        type: "kick_denied",
        message: "Tylko host może wyrzucać graczy.",
      }),
    });
    expect(global.addLog).toHaveBeenCalledWith(
      "<em>Tylko host może wyrzucać graczy.</em>",
      "system-msg",
    );
  });

  test("room_dissolved alerts the user", () => {
    const { connect } = loadSocket();
    connect();
    lastWs.onmessage({
      data: JSON.stringify({ type: "room_dissolved", message: "gone" }),
    });
    expect(global.alert).toHaveBeenCalledWith("gone");
  });

  test("room_dissolved suppresses auto-reconnect on subsequent onclose", () => {
    jest.useFakeTimers();
    const { connect } = loadSocket();
    connect();
    lastWs.onopen();
    lastWs.onmessage({
      data: JSON.stringify({ type: "room_dissolved", message: "gone" }),
    });
    lastWs.onclose({ code: 1000 });
    jest.advanceTimersByTime(2500);
    expect(global.WebSocket).toHaveBeenCalledTimes(1);
    jest.useRealTimers();
  });

  test("room_dissolved does not alert after leaveRoom()", () => {
    const { connect, leaveRoom } = loadSocket();
    connect();
    leaveRoom();
    lastWs.onmessage({
      data: JSON.stringify({ type: "room_dissolved", message: "gone" }),
    });
    expect(global.alert).not.toHaveBeenCalled();
  });
});

describe("leaveRoom()", () => {
  test("toggles UI, closes the socket and clears timers", () => {
    const { connect, leaveRoom } = loadSocket();
    connect();
    lastWs.onopen();
    globalThis.globalRoundTimer = setInterval(() => {}, 1000);
    globalThis.currentCountdown = setInterval(() => {}, 1000);
    leaveRoom();
    expect(document.getElementById("chat-section").style.display).toBe("none");
    expect(document.getElementById("join-section").style.display).toBe("block");
    expect(document.getElementById("btn-leave").style.display).toBe("none");
    expect(document.getElementById("nav-room-info").style.display).toBe("none");
    expect(globalThis.globalRoundTimer).toBeNull();
    expect(globalThis.currentCountdown).toBeNull();
    expect(lastWs.close).toHaveBeenCalled();
  });
});

describe("round event handlers", () => {
  test("onRoundStarted reveals the letter and starts a countdown timer", () => {
    jest.useFakeTimers();
    globalThis.runLetterLottery = (_letter, cb) => cb();
    globalThis.runRoundStartCountdown = (cb) => cb();
    const { onRoundStarted } = loadSocket();
    onRoundStarted({
      letter: "A",
      time_limit: 30,
      current_round: 1,
      max_rounds: 5,
    });
    const timer = document.getElementById("round-timer");
    expect(document.getElementById("current-letter").textContent).toBe("A");
    expect(timer.textContent).toBe("30s");
    jest.advanceTimersByTime(1000);
    expect(timer.textContent).toBe("29s");
    jest.useRealTimers();
    delete globalThis.runLetterLottery;
    delete globalThis.runRoundStartCountdown;
  });

  test("onRoundStarted with resume skips lottery and countdown", () => {
    const spin = jest.fn();
    globalThis.runLetterLottery = spin;
    globalThis.runRoundStartCountdown = jest.fn();
    const { onRoundStarted } = loadSocket();
    onRoundStarted({
      letter: "M",
      time_limit: 90,
      current_round: 2,
      max_rounds: 5,
      resume: true,
    });
    expect(spin).not.toHaveBeenCalled();
    expect(globalThis.runRoundStartCountdown).not.toHaveBeenCalled();
    expect(global.enableInputs).toHaveBeenCalled();
    expect(document.getElementById("round-timer").textContent).toBe("—");
    delete globalThis.runLetterLottery;
    delete globalThis.runRoundStartCountdown;
  });

  test("onRoundStarted with resume restores remaining round timer", () => {
    jest.useFakeTimers();
    const { onRoundStarted } = loadSocket();
    onRoundStarted({
      letter: "T",
      time_limit: 90,
      current_round: 2,
      max_rounds: 5,
      resume: true,
      seconds_left: 42,
    });
    expect(document.getElementById("round-timer").textContent).toBe("42s");
    jest.advanceTimersByTime(1000);
    expect(document.getElementById("round-timer").textContent).toBe("41s");
    jest.useRealTimers();
  });

  test("onRoundStarted with resume during stop phase starts submit countdown", () => {
    jest.useFakeTimers();
    const { onRoundStarted } = loadSocket();
    onRoundStarted({
      letter: "T",
      time_limit: 90,
      current_round: 2,
      max_rounds: 5,
      resume: true,
      stop_triggered: true,
      stop_seconds_left: 6,
    });
    expect(document.getElementById("btn-stop").innerHTML).toContain("6s");
    jest.advanceTimersByTime(6000);
    expect(global.disableAndSubmit).toHaveBeenCalled();
    jest.useRealTimers();
  });

  test("onStopRound starts a 10s countdown and submits when it elapses", () => {
    jest.useFakeTimers();
    const { onStopRound } = loadSocket();
    onStopRound({ sender: "System" });
    const btn = document.getElementById("btn-stop");
    expect(btn.innerHTML).toContain("10s");
    jest.advanceTimersByTime(1000);
    expect(btn.innerHTML).toContain("9s");
    jest.advanceTimersByTime(9000);
    expect(global.disableAndSubmit).toHaveBeenCalled();
    jest.useRealTimers();
  });

  test("onRoundResults opens overlay on every layout", () => {
    const prevMatchMedia = globalThis.matchMedia;
    globalThis.matchMedia = jest.fn(() => ({
      matches: true,
      media: "(min-width: 768px)",
      addListener: jest.fn(),
      removeListener: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    }));
    const { onRoundResults } = loadSocket();
    onRoundResults({
      round_scores: { TestUser: { total: 10, details: {} } },
      answers: { TestUser: {} },
      total_scores: { TestUser: 10 },
      host_name: "TestUser",
      game_over: false,
      room_id: "1234",
      final: true,
    });
    expect(global.addLog).not.toHaveBeenCalled();
    expect(document.getElementById("round-results-overlay").hidden).toBe(false);
    expect(global.setRoomPhase).toHaveBeenCalledWith("round_results");
    expect(global.updateScoreboard).toHaveBeenCalledWith(
      { TestUser: 10 },
      "TestUser",
      "",
    );
    globalThis.matchMedia = prevMatchMedia;
  });

  test("onRoundResults opens mobile overlay on narrow layout", () => {
    const prevMatchMedia = globalThis.matchMedia;
    globalThis.matchMedia = jest.fn(() => ({
      matches: false,
      media: "(min-width: 768px)",
      addListener: jest.fn(),
      removeListener: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    }));
    const { onRoundResults } = loadSocket();
    onRoundResults({
      round_scores: { TestUser: { total: 10, details: { Państwo: 10 } } },
      answers: { TestUser: { Państwo: "Polska" } },
      total_scores: { TestUser: 10 },
      host_name: "TestUser",
      game_over: false,
      room_id: "1234",
    });
    expect(global.addLog).not.toHaveBeenCalled();
    expect(document.getElementById("round-results-overlay").hidden).toBe(false);
    expect(
      document.getElementById("round-results-modal-body").textContent,
    ).toContain("Polska");
    globalThis.matchMedia = prevMatchMedia;
  });

  test("onRoundResults with game_over renders final table without overlay", () => {
    globalThis.myNick = "TestUser";
    const { onRoundResults } = loadSocket();
    onRoundResults({
      round_scores: { TestUser: { total: 10, details: { Państwo: 10 } } },
      answers: { TestUser: { Państwo: "Polska" } },
      total_scores: { TestUser: 10 },
      host_name: "TestUser",
      game_over: true,
      room_id: "1234",
      final: true,
    });
    expect(document.getElementById("round-results-overlay").hidden).toBe(true);
    expect(document.getElementById("game-over-results").hidden).toBe(false);
    expect(
      document.getElementById("game-over-results-body").textContent,
    ).toContain("Polska");
    expect(global.setRoomPhase).toHaveBeenCalledWith("results");
    delete globalThis.myNick;
  });

  test("onRoundResults with game_over shows final scoreboard before round details", () => {
    globalThis.myNick = "TestUser";
    const { onRoundResults } = loadSocket();
    onRoundResults({
      total_scores: { TestUser: 25, Guest: 10 },
      round_history: [
        {
          round: 1,
          letter: "J",
          answers: {
            TestUser: { Państwo: "Jamajka", Miasto: "Japierniczanów" },
          },
          round_scores: {
            TestUser: { total: 15, details: { Państwo: 15, Miasto: 0 } },
          },
          veto_tallies: {},
        },
      ],
      host_name: "TestUser",
      game_over: true,
      room_id: "1234",
      final: true,
    });
    const body = document.getElementById("game-over-results-body");
    expect(body.querySelector(".game-over-scoreboard")).not.toBeNull();
    expect(body.querySelector(".game-over-details")).not.toBeNull();
    expect(body.textContent.indexOf("25 pkt")).toBeLessThan(
      body.textContent.indexOf("Runda 1"),
    );
    expect(body.textContent).toContain("Japierniczanów");
    delete globalThis.myNick;
  });

  test("onRoundResults with game_over closes provisional overlay", () => {
    globalThis.myNick = "TestUser";
    const { showRoundResultsOverlay, onRoundResults } = loadSocket();
    showRoundResultsOverlay("<p>pending</p>", {
      provisional: true,
      vetoEndsAt: Date.now() + 10000,
    });
    expect(document.getElementById("round-results-overlay").hidden).toBe(false);
    onRoundResults({
      round_scores: { TestUser: { total: 10, details: { Państwo: 10 } } },
      answers: { TestUser: { Państwo: "Polska" } },
      total_scores: { TestUser: 10 },
      host_name: "TestUser",
      game_over: true,
      room_id: "1234",
      final: true,
    });
    expect(document.getElementById("round-results-overlay").hidden).toBe(true);
    delete globalThis.myNick;
  });

  test("onGameRestarted resets game layout and inputs", () => {
    const { onGameRestarted } = loadSocket();
    document.getElementById("game-layout").classList.add("game-over");
    document.getElementById("chat-sidebar").classList.add("hidden");
    onGameRestarted({
      scores: { TestUser: 0 },
      host_name: "TestUser",
      sender: "TestUser",
    });
    expect(
      document.getElementById("game-layout").classList.contains("game-over"),
    ).toBe(false);
    expect(
      document.getElementById("chat-sidebar").classList.contains("hidden"),
    ).toBe(false);
    expect(document.getElementById("btn-draw").style.display).toBe(
      "inline-block",
    );
    expect(global.updateScoreboard).toHaveBeenCalledWith(
      { TestUser: 0 },
      "TestUser",
      "",
    );
  });

  test("onGameRestarted hides share panel after game over", () => {
    globalThis.myNick = "HostX";
    Object.assign(globalThis.navigator, {
      clipboard: { writeText: jest.fn().mockResolvedValue(undefined) },
    });
    const { handleGameOver, onGameRestarted } = loadSocket();
    handleGameOver("HostX", "ROOMX");
    expect(document.getElementById("game-over-share").style.display).toBe(
      "block",
    );
    onGameRestarted({
      scores: { HostX: 0 },
      host_name: "HostX",
      sender: "HostX",
    });
    expect(document.getElementById("game-over-share").style.display).toBe(
      "none",
    );
  });
});

describe("pure helpers", () => {
  test("getScoreColor maps scores to design tokens", () => {
    const { getScoreColor } = loadSocket();
    expect(getScoreColor(15)).toBe("var(--pts-15)");
    expect(getScoreColor(10)).toBe("var(--pts-10)");
    expect(getScoreColor(5)).toBe("var(--pts-5)");
    expect(getScoreColor(0)).toBe("var(--danger)");
  });

  test("buildPlayerResultHtml builds player card with category rows", () => {
    const { buildPlayerResultHtml } = loadSocket();
    const html = buildPlayerResultHtml(
      "Anna",
      { total: 10, details: { Państwo: 10, Miasto: 0 } },
      { Państwo: "Polska", Miasto: "" },
      "",
    );
    expect(html).toContain("round-results-table");
    expect(html).not.toContain("<details");
    expect(html).toContain("Polska");
    expect(html).toContain("Państwo");
  });

  test("buildPlayerResultHtml marks the viewer card", () => {
    const { buildPlayerResultHtml } = loadSocket();
    globalThis.myNick = "Filip";
    const html = buildPlayerResultHtml(
      "Filip",
      { total: 15, details: { Państwo: 15 } },
      { Państwo: "Polska" },
      "Filip",
    );
    expect(html).toContain("round-results-player-row--me");
    delete globalThis.myNick;
  });

  test("escapeHtml escapes angle brackets", () => {
    const { escapeHtml } = loadSocket();
    expect(escapeHtml("<img>")).toBe("&lt;img&gt;");
  });

  test("buildRoundResultsHtml includes answers and escapes XSS", () => {
    const { buildRoundResultsHtml } = loadSocket();
    globalThis.myNick = "A";
    const html = buildRoundResultsHtml({
      round_scores: {
        A: { total: 0, details: { Państwo: 0 } },
        B: { total: 0, details: { Państwo: 0 } },
      },
      answers: {
        A: { Państwo: "<b>x</b>" },
        B: { Państwo: "OK" },
      },
    });
    expect(html).toContain("round-results-table");
    expect(html).toContain("&lt;b&gt;");
    expect(html).not.toContain("<b>x</b>");
    delete globalThis.myNick;
  });
});

describe("handleGameOver()", () => {
  test("reshuffles layout, reveals restart settings, share link and confetti", () => {
    globalThis.myNick = "TestUser";
    Object.assign(globalThis.navigator, {
      clipboard: { writeText: jest.fn().mockResolvedValue(undefined) },
    });
    const { handleGameOver } = loadSocket();
    handleGameOver("TestUser", "1234", {
      round_scores: { TestUser: { total: 10, details: { Państwo: 10 } } },
      answers: { TestUser: { Państwo: "Polska" } },
      total_scores: { TestUser: 10 },
    });
    expect(
      document.getElementById("game-layout").classList.contains("game-over"),
    ).toBe(true);
    expect(document.getElementById("game-main-area").style.display).toBe(
      "none",
    );
    expect(document.getElementById("restart-settings").style.display).toBe(
      "block",
    );
    expect(document.getElementById("game-over-results").hidden).toBe(false);
    expect(
      document.getElementById("game-over-results-body").textContent,
    ).toContain("Polska");
    expect(document.getElementById("game-over-share").style.display).toBe(
      "block",
    );
    expect(
      document.getElementById("share-link-anchor").getAttribute("href"),
    ).toContain("1234");
    expect(global.confetti).toHaveBeenCalled();
  });
});

describe("runRoundStartCountdown()", () => {
  test("waits three intervals then completes", () => {
    jest.useFakeTimers();
    const prevMatchMedia = globalThis.matchMedia;
    globalThis.matchMedia = jest.fn(() => ({
      matches: false,
      media: "",
      addListener: jest.fn(),
      removeListener: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    }));
    const done = jest.fn();
    const { runRoundStartCountdown } = loadSocket();
    runRoundStartCountdown(done);
    expect(done).not.toHaveBeenCalled();
    jest.advanceTimersByTime(720 * 3);
    expect(done).toHaveBeenCalledTimes(1);
    jest.useRealTimers();
    globalThis.matchMedia = prevMatchMedia;
  });
});

describe("runLetterLottery()", () => {
  test("cycles through random letters and resolves with the target", () => {
    jest.useFakeTimers();
    globalThis.crypto = {
      getRandomValues: (arr) => {
        arr[0] = 1;
        return arr;
      },
    };
    const onComplete = jest.fn();
    const { runLetterLottery } = loadSocket();
    runLetterLottery("X", onComplete);
    jest.advanceTimersByTime(2500);
    expect(global.playLotterySpinTick).toHaveBeenCalled();
    expect(global.playRoundStartReveal).toHaveBeenCalledTimes(1);
    expect(global.playLotterySpinHaptic).toHaveBeenCalledTimes(24);
    expect(global.playLotteryRevealHaptic).toHaveBeenCalledTimes(1);
    jest.advanceTimersByTime(1500);
    expect(onComplete).toHaveBeenCalled();
    expect(document.getElementById("lottery-letter").innerText).toBe("X");
    jest.useRealTimers();
  });
});
