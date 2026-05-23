import { createStore } from '@mantou/gem';

export const nickStore = createStore({ nick: '', custom: false });

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
  room_id: '', scores: {}, host_name: '', ready_players: [], connected_players: [],
  disconnected_players: null, is_playing: false, results_phase_active: false, game_over: false,
});

export const roundStore = createStore({
  letter: '', time_left: 0, round_active: false, stopped: false, answers_submitted: false,
});

export const resultsStore = createStore<Record<string, any>>({
  variant: 'card', gameOver: false, provisional: false,
});

export const overlayStore = createStore({
  lottery: false, lotteryLetter: '?', roundCountdown: false, roundCountdownNum: 0,
  roundResults: false, joinModal: false, createModal: false,
});

export const chatStore = createStore<{ messages: { type: string; sender?: string; text?: string }[] }>({ messages: [] });
export const activeRoomsStore = createStore<{ rooms: any[]; loading: boolean }>({ rooms: [], loading: false });
export const connectionStore = createStore({ connected: false, reconnecting: false, wsGeneration: 0 });
export const appealStore = createStore({ token: '' });

const rp = (n: string) => location.pathname.includes(n);
export const pageStore = createStore({ page: rp('/room/') ? 'room' as const : 'landing' as const });

export const GAME_CATEGORIES = [
  { id: 'panstwo', label: 'Państwo', icon: '🏴' },
  { id: 'miasto', label: 'Miasto', icon: '🏙️' },
  { id: 'rzecz', label: 'Rzecz', icon: '📦' },
  { id: 'zwierze', label: 'Zwierzę', icon: '🐾' },
  { id: 'roslina', label: 'Roślina', icon: '🌿' },
  { id: 'imie', label: 'Imię', icon: '👤' },
  { id: 'zawod', label: 'Zawód', icon: '💼' },
];
