import {
  roomStore, roundStore, resultsStore, overlayStore,
  chatStore, connectionStore, pageStore, nickStore, appealStore,
} from './store';

let ws: WebSocket | null = null;
let wsGeneration = 0;
let myNick = '';
let isLeaving = false;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let currentRoundTimer: ReturnType<typeof setInterval> | null = null;

export function sendJson(data: Record<string, unknown>) {
  if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(data));
}

export function getMyNick(): string { return myNick; }

export function detectRoomId(): string | undefined {
  const parts = location.pathname.split('/');
  const roomIndex = parts.indexOf('room');
  if (roomIndex >= 0 && parts[roomIndex + 1]) return parts[roomIndex + 1];
  return undefined;
}

export function leaveRoom() {
  isLeaving = true;
  if (ws) { ws.close(1000, 'user_left'); ws = null; }
  if (currentRoundTimer) { clearInterval(currentRoundTimer); currentRoundTimer = null; }
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
  roomStore({ room_id: '', scores: {}, host_name: '', ready_players: [], connected_players: [], disconnected_players: null, is_playing: false, results_phase_active: false, game_over: false });
  roundStore({ letter: '', time_left: 0, round_active: false, stopped: false, answers_submitted: false });
  resultsStore({ variant: 'card', gameOver: false, provisional: false });
  overlayStore({ roundResults: false, roundCountdown: false, lottery: false });
  chatStore({ messages: [] });
  connectionStore({ connected: false, reconnecting: false });
  pageStore({ page: 'landing' });
  history.pushState({}, '', '/');
}

function handleCloseCode(code: number) {
  if (isLeaving) { isLeaving = false; return; }
  if (code === 4001 || code === 4002 || code === 4003 || code === 4004) { leaveRoom(); return; }
  connectionStore({ reconnecting: true });
  reconnectTimer = setTimeout(() => connect(), 2000 + Math.random() * 3000);
}

export function connect(roomId?: string, maxRounds?: number, timeLimit?: number, visibility?: string) {
  if (ws) ws.close(1000, 'reconnecting');
  wsGeneration++;
  const gen = wsGeneration;
  connectionStore({ wsGeneration: gen, reconnecting: true });

  const resolvedNick = nickStore.nick.trim() || 'Gracz';
  myNick = resolvedNick;

  const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
  const encNick = encodeURIComponent(resolvedNick);
  let url = `${protocol}://${location.host}/ws/${encNick}`;
  const params: string[] = [];
  const rid = roomId || roomStore.room_id || detectRoomId();
  if (rid) params.push(`room_id=${rid}`);
  if (maxRounds) params.push(`max_rounds=${maxRounds}`);
  if (timeLimit) params.push(`time_limit=${timeLimit}`);
  if (visibility) params.push(`visibility=${visibility}`);
  if (params.length) url += '?' + params.join('&');

  const socket = new WebSocket(url);
  ws = socket;

  socket.onopen = () => {
    if (gen !== wsGeneration) return;
    connectionStore({ connected: true, reconnecting: false });
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
  };

  socket.onmessage = (event) => {
    if (gen !== wsGeneration) return;
    try {
      const msg = JSON.parse(event.data);
      const handler = MESSAGE_HANDLERS[msg.type];
      if (handler) handler(msg);
    } catch (e) { console.error('WS parse error:', e); }
  };

  socket.onclose = (event) => {
    if (gen !== wsGeneration) return;
    connectionStore({ connected: false, reconnecting: true });
    handleCloseCode(event.code);
  };

  socket.onerror = () => {
    if (gen !== wsGeneration) return;
    connectionStore({ connected: false, reconnecting: true });
  };
}

// ── Message handlers ────────────────────────────────────────────────────────

function onLobbyState(msg: any) {
  const { scores, host_name, ready_players, connected_players, disconnected_players } = msg;
  roomStore({ scores: scores || {}, host_name: host_name || '', ready_players: ready_players || [], connected_players: connected_players || [], disconnected_players: disconnected_players || null, is_playing: false, game_over: false, results_phase_active: false });
  roundStore({ round_active: false, letter: '', time_left: 0 });
  resultsStore({ gameOver: false, provisional: false });
  overlayStore({ roundResults: false });
  const rid = msg.room_id || roomStore.room_id;
  if (rid && pageStore.page !== 'room') { pageStore({ page: 'room' }); history.pushState({}, '', '/room/' + rid); }
  roomStore({ room_id: rid });
}

function onRoundStarted(msg: any) {
  const { letter, time_limit: timeLeft, resume } = msg;
  if (currentRoundTimer) { clearInterval(currentRoundTimer); currentRoundTimer = null; }
  roundStore({ letter: letter || '', time_left: timeLeft || 90, round_active: true, stopped: false, answers_submitted: false });
  resultsStore({ gameOver: false, provisional: false });
  overlayStore({ roundResults: false, roundCountdown: false });
  roomStore({ is_playing: true, results_phase_active: false });

  if (!resume) {
    overlayStore({ roundCountdown: true, roundCountdownNum: 3 });
    let step = 3;
    const iv = setInterval(() => {
      step--;
      if (step <= 0) {
        clearInterval(iv);
        overlayStore({ roundCountdown: false });
        runLetterLottery(letter || '?', () => { overlayStore({ lottery: false }); });
      } else { overlayStore({ roundCountdownNum: step }); }
    }, 700);
  }

  let remaining = timeLeft || 90;
  roundStore({ time_left: remaining });
  currentRoundTimer = setInterval(() => {
    remaining--;
    roundStore({ time_left: Math.max(0, remaining) });
    if (remaining <= 0 && currentRoundTimer) { clearInterval(currentRoundTimer); currentRoundTimer = null; }
  }, 1000);
}

function onStopRound(_msg: any) {
  roundStore({ answers_submitted: true, stopped: true });
  if (currentRoundTimer) { clearInterval(currentRoundTimer); currentRoundTimer = null; }
}

function onRoundResults(msg: any) {
  if (currentRoundTimer) { clearInterval(currentRoundTimer); currentRoundTimer = null; }
  roundStore({ round_active: false, stopped: true });
  const { variant = 'card', gameOver = false, provisional = false, vetoEndsAt, veto_tallies, round_scores, answers, letter, round_number, final, allow_appeals, viewer, roomId } = msg;
  resultsStore({ variant, gameOver, provisional, vetoEndsAt, veto_tallies, round_scores, answers, letter, round_number, final, allow_appeals, viewer, roomId });
  roomStore({ results_phase_active: !gameOver && provisional });
  overlayStore({ roundResults: true });
  if (gameOver) roomStore({ is_playing: false, game_over: true, results_phase_active: false });
}

function onScoreUpdate(msg: any) { roomStore({ scores: msg.scores }); }

function onChatMessage(msg: any) {
  const m = chatStore.messages.slice(-99);
  m.push({ type: 'chat', sender: msg.sender, text: msg.text });
  chatStore({ messages: m });
}

function onSystemMessage(msg: any) {
  const m = chatStore.messages.slice(-99);
  m.push({ type: 'system', text: msg.text });
  chatStore({ messages: m });
}

function onKicked() { isLeaving = true; ws?.close(); leaveRoom(); }
function onKickDenied() {}
function onRoomDissolved() { isLeaving = true; ws?.close(); leaveRoom(); }
function onVetoUpdate(msg: any) { resultsStore({ veto_tallies: msg.veto_tallies }); }

function onGameRestarted() {
  resultsStore({ gameOver: false, variant: 'card', provisional: false });
  overlayStore({ roundResults: false });
  roomStore({ is_playing: false, game_over: false, results_phase_active: false });
  roundStore({ round_active: false, letter: '', time_left: 0, stopped: false, answers_submitted: false });
}

function onAppealToken(msg: any) { appealStore({ token: msg.token }); }

const MESSAGE_HANDLERS: Record<string, (msg: any) => void> = {
  lobby_state: onLobbyState, round_started: onRoundStarted, stop_round: onStopRound,
  round_results: onRoundResults, score_update: onScoreUpdate, chat: onChatMessage,
  system: onSystemMessage, kicked: onKicked, kick_denied: onKickDenied,
  room_dissolved: onRoomDissolved, veto_update: onVetoUpdate,
  game_restarted: onGameRestarted, appeal_token: onAppealToken,
};

// ── Letter lottery animation ────────────────────────────────────────────────

function runLetterLottery(target: string, onDone: () => void) {
  const alphabet = 'AĄBCĆDEĘFGHIJKLŁMNŃOÓPRSŚTUWYZŹŻ';
  const duration = 1500, intervalTime = 50;
  let elapsed = 0;
  overlayStore({ lottery: true, lotteryLetter: '?' });
  const iv = setInterval(() => {
    elapsed += intervalTime;
    if (elapsed >= duration) {
      clearInterval(iv);
      overlayStore({ lotteryLetter: target, lottery: true });
      setTimeout(() => { overlayStore({ lottery: false }); onDone(); }, 600);
    } else {
      overlayStore({ lotteryLetter: alphabet[Math.trunc(Math.random() * alphabet.length)] });
    }
  }, intervalTime);
}

// ── Actions ─────────────────────────────────────────────────────────────────

export function sendChat(text: string) { sendJson({ type: 'chat', text }); }
export function toggleReady() { sendJson({ type: 'ready' }); }
export function sendStop() { sendJson({ type: 'stop' }); }
export function sendAnswers(answers: Record<string, string>) { sendJson({ type: 'answers', answers }); }
export function requestRestart(rounds: number, limit: number) { sendJson({ type: 'restart_game', rounds, limit }); }
export function dissolveRoom() { sendJson({ type: 'dissolve_room' }); }
export function kickPlayer(name: string) { sendJson({ type: 'kick', target: name }); }

// ── REST API ────────────────────────────────────────────────────────────────

export async function quickJoin(): Promise<string | null> {
  const resp = await fetch('/api/quick-join', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nick: nickStore.nick }) });
  if (!resp.ok) return null;
  const data = await resp.json();
  return data.room_id;
}

export async function createRoom(rounds: number, limit: number, visibility: string): Promise<string | null> {
  const resp = await fetch('/api/create-room', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ rounds, limit, visibility, nick: nickStore.nick }) });
  if (!resp.ok) return null;
  const data = await resp.json();
  return data.room_id;
}

export async function loadActiveRooms(): Promise<any[]> {
  const resp = await fetch('/api/active-rooms');
  if (!resp.ok) return [];
  return resp.json();
}
