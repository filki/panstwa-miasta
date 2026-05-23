import { createStore } from '@mantou/gem';

/** Current player nickname */
export const nickStore = createStore({
  nick: '',
  custom: false,
});

/** Room state from server */
export interface RoomState {
  room_id: string;
  scores: Record<string, number>;
  host_name: string;
  ready_players: string[];
  connected_players: string[];
  disconnected_players: string[] | null;
  is_playing: boolean;
  results_phase_active: boolean;
  game_over: boolean;
}

export const roomStore = createStore<Partial<RoomState>>({
  room_id: '',
  scores: {},
  host_name: '',
  ready_players: [],
  connected_players: [],
  disconnected_players: null,
  is_playing: false,
  results_phase_active: false,
  game_over: false,
});

/** Current round state */
export interface RoundState {
  letter: string;
  time_left: number;
  round_active: boolean;
  stopped: boolean;
  answers_submitted: boolean;
}

export const roundStore = createStore<RoundState>({
  letter: '',
  time_left: 0,
  round_active: false,
  stopped: false,
  answers_submitted: false,
});

/** Round results */
export interface RoundResultData {
  variant: 'card' | 'table' | 'gameOver';
  gameOver: boolean;
  provisional: boolean;
  vetoEndsAt?: number;
  veto_tallies?: Record<string, Record<string, { up: number; down: number }>>;
  round_scores?: Record<string, number>;
  answers?: Record<string, Record<string, string>>;
  letter?: string;
  round_number?: number;
  final?: boolean;
  allow_appeals?: boolean;
  viewer?: string;
  roomId?: string;
}

export const resultsStore = createStore<Partial<RoundResultData>>({
  variant: 'card',
  gameOver: false,
  provisional: false,
});

/** Overlay visibility */
export const overlayStore = createStore({
  lottery: false,
  lotteryLetter: '?',
  roundCountdown: false,
  roundCountdownNum: 0,
  roundResults: false,
  joinModal: false,
  createModal: false,
});

/** Chat messages */
export interface ChatMessage {
  type: 'chat' | 'system' | 'results';
  sender?: string;
  text?: string;
  html?: string;
}

export const chatStore = createStore<{ messages: ChatMessage[] }>({
  messages: [],
});

/** Active rooms list */
export const activeRoomsStore = createStore<{ rooms: any[]; loading: boolean }>({
  rooms: [],
  loading: false,
});

/** Page routing */
export const pageStore = createStore<{ page: 'landing' | 'room' }>({
  page: location.pathname.startsWith('/room/') ? 'room' : 'landing',
});

/** Avatar management */
export const avatarStore = createStore<{ id: number }>({
  id: 0,
});

/** Connection state */
export const connectionStore = createStore<{
  connected: boolean;
  reconnecting: boolean;
  wsGeneration: number;
}>({
  connected: false,
  reconnecting: false,
  wsGeneration: 0,
});

/** Appeal token for postgame appeals */
export const appealStore = createStore<{ token: string }>({
  token: '',
});

/** Game categories (constant) */
export const GAME_CATEGORIES = [
  { id: 'panstwo', label: 'Państwo', icon: '🏴' },
  { id: 'miasto', label: 'Miasto', icon: '🏙️' },
  { id: 'rzecz', label: 'Rzecz', icon: '📦' },
  { id: 'zwierze', label: 'Zwierzę', icon: '🐾' },
  { id: 'roslina', label: 'Roślina', icon: '🌿' },
  { id: 'imie', label: 'Imię', icon: '👤' },
  { id: 'zawod', label: 'Zawód', icon: '💼' },
];

export const ALPHABET = 'AĄBCĆDEĘFGHIJKLŁMNŃOÓPRSŚTUWYZŹŻ';
