import asyncio
import json
import secrets
from collections import deque
from typing import Any, cast

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from .db import (
    delete_room,
    fetch_room_snapshot,
    get_active_rooms,
    remove_player,
    save_player_score,
    save_room,
)
from .limits import check_ws_before_connect, max_rooms_cap, record_ws_connect_ok

# Logger import
from .logger import get_logger

logger = get_logger(__name__)

ALPHABET = "ABCDEFGHIJKLMNOPRSTUWZ"
LETTER_CYCLE_ROUNDS = len(ALPHABET)
GAME_CATEGORIES = ["Państwo", "Miasto", "Rzecz", "Zwierzę", "Roślina", "Imię", "Zawód"]

# Ile ostatnich wylosowanych liter przesuwamy na DNO nowej talii przy
# re-shuffle, żeby kolejny cykl nie zaczął się od litery, która właśnie
# wypadła. Wartość mniejsza od długości alfabetu (22) -- inaczej talia
# byłaby pusta po wykluczeniu.
RECENT_LETTERS_MEMORY = 7


def normalize_text(text: str) -> str:
    return text.strip().lower().replace("-", " ").replace("  ", " ")


def _answer_first_letter_matches_round(ans_raw: str, letter: str) -> bool:
    """Litera rundy z ``ALPHABET`` (ASCII); pierwsza litera odpowiedzi po złożeniu PL → ASCII (np. Ś → S)."""
    from .data import fold_polish_diacritics

    if not ans_raw or not letter:
        return False
    t = letter.strip().lower()
    if len(t) != 1:
        return False
    s = ans_raw.strip().lower()
    if not s:
        return False
    return fold_polish_diacritics(s[0]) == t


def _fauna_flora_norm_valid(ans_norm: str, bucket: set[str]) -> bool:
    """Czy odpowiedź jest w zbiorze albo jest pierwszym słowem wpisu wielowyrazowego (np. „dzięcioł” → „dzięcioł duży”)."""
    if ans_norm in bucket:
        return True
    if len(ans_norm) < 3:
        return False
    prefix = ans_norm + " "
    return any(s.startswith(prefix) for s in bucket)


def normalize_room_visibility(raw: str) -> str:
    v = (raw or "public").strip().lower()
    return v if v in ("public", "private") else "public"


class Room:
    def __init__(
        self,
        room_id: str,
        max_rounds: int = 5,
        time_limit: int = 90,
        *,
        visibility: str = "public",
    ):
        self.room_id = room_id
        self.max_rounds = max_rounds
        self.time_limit = time_limit
        self.visibility = normalize_room_visibility(visibility)
        self.connections: dict[str, WebSocket] = {}
        self.scores: dict[str, int] = {}
        self.host_name = ""

        # Stan gry i rundy
        self.current_round = 0
        self.ready_players = set()
        self.is_playing = False
        self.stop_triggered = False
        self.current_letter = ""
        self.answers_received: dict[str, dict[str, str]] = {}
        self.expected_answers = 0
        self.game_over = False

        # Deck-shuffle: talia liter – każda litera pojawi się raz zanim
        # jakakolwiek się powtórzy. Ostatnie N wylosowanych liter trzymamy
        # w `_recent_letters` i przy re-shuffle wpychamy je na DNO nowej
        # talii, żeby kolejny cykl nie zaczął się od litery, która właśnie
        # wyszła. To zachowuje brak powtórek wewnątrz cyklu, a dodatkowo
        # tłumi kolizje na styku dwóch cykli (czyli też między grami w
        # tym samym pokoju -- patrz `restart_game`).
        self._recent_letters: deque[str] = deque(maxlen=RECENT_LETTERS_MEMORY)
        self.letter_queue: list[str] = []
        self._refill_letter_queue()

        # Task references to prevent premature GC (SonarQube MAJOR)
        self._timeout_task: asyncio.Task | None = None
        self._force_end_task: asyncio.Task | None = None
        self._global_timeout_task: asyncio.Task | None = None

    async def broadcast(self, message: str):
        """Wysyła wiadomość do wszystkich w pokoju.

        Snapshot + obsługa błędów: jedno martwe gniazdo (np. po długiej grze)
        nie blokuje wysyłki do reszty ani rozwiązania pokoju.
        """
        for connection in tuple(self.connections.values()):
            try:
                await connection.send_text(message)
            except Exception as exc:
                logger.warning("broadcast send_text failed: %s", exc)

    def _refill_letter_queue(self):
        """Miesza alfabet i ładuje do kolejki.

        Ostatnie ``RECENT_LETTERS_MEMORY`` wylosowanych liter trafia na DNO
        nowej talii (czyli zostanie wyciągnięte jako OSTATNIE -- ``pop()``
        bierze z końca). Reszta jest tasowana niezależnie i ląduje wyżej.
        """
        rng = secrets.SystemRandom()
        recent = set(self._recent_letters)
        fresh = [c for c in ALPHABET if c not in recent]
        stale = list(recent)
        rng.shuffle(fresh)
        rng.shuffle(stale)
        # ``letter_queue.pop()`` bierze z końca, więc fresh na końcu,
        # stale na początku -> stale pojawi się dopiero, gdy fresh się
        # wyczerpie.
        self.letter_queue = stale + fresh
        logger.info(
            f"Room {self.room_id}: letter queue refilled "
            f"(fresh={len(fresh)}, stale-tail={len(stale)})"
        )

    def start_round(self) -> str:
        self.is_playing = True
        self.stop_triggered = False
        self.ready_players = set()
        self.current_round += 1

        # Jeśli talia pusta – tasujemy ponownie
        if not self.letter_queue:
            self._refill_letter_queue()

        letter = self.letter_queue.pop()
        self._recent_letters.append(letter)
        self.current_letter = letter
        logger.info(
            f"Room {self.room_id}: round {self.current_round} – letter '{letter}' "
            f"(remaining in queue: {len(self.letter_queue)})"
        )

        self.answers_received = {}
        self.expected_answers = len(self.connections)
        return self.current_letter

    async def restart_game(self, rounds: int, limit: int):
        self.max_rounds = rounds
        self.time_limit = limit
        self.current_round = 0
        self.scores = dict.fromkeys(self.connections, 0)
        self.game_over = False
        self.is_playing = False
        self.ready_players = set()
        # NIE wywołujemy _refill_letter_queue() -- kontynuujemy istniejącą
        # talię, żeby dwie sąsiednie gry w tym samym pokoju używały kolejnych
        # unikalnych liter (do 22 zanim cokolwiek się powtórzy).
        for p, s in self.scores.items():
            await save_player_score(self.room_id, p, s)
        await save_room(
            self.room_id,
            self.max_rounds,
            self.time_limit,
            self.current_round,
            self.host_name,
            self.visibility,
        )

    def _calculate_base_category_score(self, category: str, ans_norm: str) -> int:
        """Determines if an answer is valid based on static data. Returns -1 if valid but needs multiplier check."""
        from .data import COUNTRIES, MIASTA, NAMES, ROSLINY, ZWIERZETA, job_answer_accepted

        if category == "Państwo":
            return -1 if ans_norm in COUNTRIES else 0
        if category == "Miasto":
            return -1 if ans_norm in MIASTA else 0
        if category == "Imię":
            return -1 if ans_norm in NAMES else 0
        if category == "Zawód":
            return -1 if job_answer_accepted(ans_norm) else 0
        if category == "Zwierzę":
            return -1 if _fauna_flora_norm_valid(ans_norm, ZWIERZETA) else 0
        if category == "Roślina":
            return -1 if _fauna_flora_norm_valid(ans_norm, ROSLINY) else 0
        return -1  # Rzecz / other

    def _assign_round_points(self, round_scores: dict[str, dict]):
        """Applies 15/10/5 points logic based on uniqueness of answers."""
        for category in GAME_CATEGORIES:
            valid_answers = {}  # ans -> count
            players_with_valid = []

            for player in self.answers_received:
                if round_scores[player]["details"].get(category) == -1:
                    ans = normalize_text(self.answers_received[player].get(category, ""))
                    valid_answers[ans] = valid_answers.get(ans, 0) + 1
                    players_with_valid.append(player)

            num_valid = len(players_with_valid)

            for player in players_with_valid:
                ans = normalize_text(self.answers_received[player].get(category, ""))
                # 15 pkt: Tylko Ty masz poprawną odpowiedź w tej kategorii
                if num_valid == 1:
                    pts = 15
                # 10 pkt: Inni też mają, ale Twoja jest unikalna (nikt inny nie wpisał tego samego)
                elif valid_answers[ans] == 1:
                    pts = 10
                # 5 pkt: Inni mają tę samą poprawną odpowiedź co Ty
                else:
                    pts = 5

                round_scores[player]["details"][category] = pts
                round_scores[player]["total"] += pts

    def _fill_base_scores(self, round_scores: dict[str, dict]) -> None:
        """Wypełnia ``round_scores[*][details][kategoria]`` wstępnymi 0 lub -1 (poprawna odpowiedź)."""
        for category in GAME_CATEGORIES:
            for player, answers in self.answers_received.items():
                ans_raw = answers.get(category, "").strip().lower()
                if not (
                    _answer_first_letter_matches_round(ans_raw, self.current_letter)
                    and ans_raw != ""
                ):
                    round_scores[player]["details"][category] = 0
                    continue

                if category in ("Zwierzę", "Roślina") and len(normalize_text(ans_raw)) < 2:
                    round_scores[player]["details"][category] = 0
                    continue

                res = self._calculate_base_category_score(category, normalize_text(ans_raw))
                round_scores[player]["details"][category] = res

    async def _update_global_scores_and_save(self, round_scores: dict[str, dict]):
        """Updates global scores in memory and persists to database."""
        for player, score_data in round_scores.items():
            self.scores[player] = self.scores.get(player, 0) + score_data["total"]
            await save_player_score(self.room_id, player, self.scores[player])

        await save_room(
            self.room_id,
            self.max_rounds,
            self.time_limit,
            self.current_round,
            self.host_name,
            self.visibility,
        )

    async def calculate_scores(self) -> dict[str, dict]:
        """
        Zwraca: {player: {"total": int, "details": {category: points}}}
        """
        round_scores: dict[str, dict] = {
            player: {"total": 0, "details": {}} for player in self.answers_received
        }

        # 1. Sprawdzanie bazowe (lokalne zbiory; bez zewnętrznego API)
        self._fill_base_scores(round_scores)

        # 2. Przyznawanie punktów
        self._assign_round_points(round_scores)

        # 3. Aktualizacja punktacji globalnej i zapis
        await self._update_global_scores_and_save(round_scores)
        return round_scores


class ConnectionManager:
    def __init__(self):
        self.rooms: dict[str, Room] = {}
        self._room_delete_tasks: dict[str, asyncio.Task[None]] = {}

    def cancel_delayed_room_delete(self, room_id: str) -> None:
        """Anuluje zaplanowane usunięcie pokoju z SQLite (np. przed reconnect)."""
        t = self._room_delete_tasks.pop(room_id, None)
        if t is not None and not t.done():
            t.cancel()

    def schedule_delayed_room_delete(self, room_id: str) -> None:
        """Po opuszczeniu pokoju przez wszystkich — usuwa wiersz z DB po grace (reconnect)."""
        self.cancel_delayed_room_delete(room_id)

        async def _delayed() -> None:
            from . import db as dbmod

            try:
                await asyncio.sleep(dbmod.ROOM_EMPTY_GRACE_SECONDS)
            except asyncio.CancelledError:
                return
            self._room_delete_tasks.pop(room_id, None)
            if room_id not in self.rooms:
                await delete_room(room_id)
                logger.info("Delayed delete_room completed for empty room %s", room_id)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("schedule_delayed_room_delete: no running loop for room %s", room_id)
            return
        self._room_delete_tasks[room_id] = loop.create_task(_delayed())

    async def connect(
        self,
        websocket: WebSocket,
        room_id: str,
        client_name: str,
        max_rounds: int,
        time_limit: int,
        visibility: str = "public",
        client_ip: str = "unknown",
    ) -> bool:
        logger.info(
            f"Attempting connection: room_id={room_id}, client_name={client_name}, "
            f"max_rounds={max_rounds}, time_limit={time_limit}, visibility={visibility}"
        )

        if not client_name or not client_name.strip():
            logger.warning(f"Rejected connection: empty client_name in room {room_id}")
            return False

        is_new_room = room_id not in self.rooms
        if is_new_room and len(self.rooms) >= max_rooms_cap():
            logger.warning(
                "Rejected connection: max rooms (%s) reached, cannot create %s",
                max_rooms_cap(),
                room_id,
            )
            return False
        if not await check_ws_before_connect(client_ip, is_new_room=is_new_room):
            logger.warning(
                "Rejected connection: WS rate limit (ip=%s, new_room=%s, room=%s)",
                client_ip,
                is_new_room,
                room_id,
            )
            return False

        self.cancel_delayed_room_delete(room_id)

        if room_id not in self.rooms:
            snap = await fetch_room_snapshot(room_id)
            if snap is not None:
                snap_any = cast(dict[str, Any], snap)
                vis = normalize_room_visibility(str(snap_any.get("visibility", "public")))
                room = Room(
                    room_id,
                    int(snap_any["max_rounds"]),
                    int(snap_any["time_limit"]),
                    visibility=vis,
                )
                room.current_round = int(snap_any.get("current_round") or 0)
                room.host_name = str(snap_any.get("host_name") or "")
                players = snap_any.get("players")
                if isinstance(players, dict):
                    room.scores = {str(k): int(cast(int | str, v)) for k, v in players.items()}
                self.rooms[room_id] = room
                logger.info(
                    "Restored room %s from DB (scores=%s players)",
                    room_id,
                    len(room.scores),
                )
            else:
                self.rooms[room_id] = Room(
                    room_id,
                    max_rounds,
                    time_limit,
                    visibility=normalize_room_visibility(visibility),
                )
                logger.info(
                    f"Created new room: {room_id} (max_rounds={max_rounds}, time_limit={time_limit}, "
                    f"visibility={self.rooms[room_id].visibility})"
                )

        room = self.rooms[room_id]

        # If a player joins with an existing nickname, close previous connection
        if client_name in room.connections:
            prev_ws = room.connections[client_name]
            try:
                if prev_ws.application_state != WebSocketState.DISCONNECTED:
                    await prev_ws.close()
                    logger.info(
                        f"Closed previous connection for nickname '{client_name}' in room {room_id}"
                    )
            except Exception as e:
                logger.warning(
                    "Reconnect: could not close previous socket for %r in %s: %s",
                    client_name,
                    room_id,
                    e,
                )

        await websocket.accept()
        room.connections[client_name] = websocket
        logger.info(f"WebSocket accepted for client '{client_name}' in room {room_id}")

        if not room.host_name:
            room.host_name = client_name
            logger.info(f"Set host for room {room_id} to '{client_name}'")

        if client_name not in room.scores:
            room.scores[client_name] = 0
            logger.info(f"Initialized score for '{client_name}' in room {room_id}")

        # Save/update room and player in DB
        await save_room(
            room_id,
            room.max_rounds,
            room.time_limit,
            room.current_round,
            room.host_name,
            room.visibility,
        )
        await save_player_score(room_id, client_name, room.scores[client_name])
        logger.debug(f"Persisted room {room_id} and player {client_name} to DB")

        if room.is_playing:
            room.answers_received.pop(client_name, None)
            room.expected_answers = len(room.connections)

        await record_ws_connect_ok(client_ip, is_new_room=is_new_room)

        return True

    async def load_from_db(self):
        """Ładuje aktywne pokoje i wyniki z bazy danych przy starcie"""
        active_rooms = await get_active_rooms()
        for r_data in active_rooms:
            vis = normalize_room_visibility(str(r_data.get("visibility", "public")))
            room = Room(
                r_data["room_id"],
                r_data["max_rounds"],
                r_data["time_limit"],
                visibility=vis,
            )
            room.current_round = r_data["current_round"]
            room.host_name = r_data["host_name"]
            room.scores = r_data["players"]
            self.rooms[r_data["room_id"]] = room
        print(f"✅ Załadowano {len(active_rooms)} pokoi z bazy danych.")

    async def kick_player(
        self, room_id: str, actor_name: str, target_name: str
    ) -> tuple[bool, str]:
        """Host removes another player from the room. Returns (ok, error_code). error_code empty on success."""
        if room_id not in self.rooms:
            return False, "no_room"
        room = self.rooms[room_id]
        if actor_name != room.host_name:
            return False, "not_host"
        if not target_name or target_name == actor_name:
            return False, "bad_target"
        if target_name not in room.connections:
            return False, "not_found"

        ws = room.connections[target_name]
        room.ready_players.discard(target_name)
        room.answers_received.pop(target_name, None)
        room.scores.pop(target_name, None)
        del room.connections[target_name]
        if room.is_playing:
            room.expected_answers = max(0, room.expected_answers - 1)

        await remove_player(room_id, target_name)
        await save_room(
            room.room_id,
            room.max_rounds,
            room.time_limit,
            room.current_round,
            room.host_name,
            room.visibility,
        )

        try:
            await ws.send_text(
                json.dumps(
                    {
                        "type": "kicked",
                        "message": "Host wyrzucił Cię z pokoju.",
                    }
                )
            )
        except Exception as exc:
            logger.warning("kick: send kicked message failed: %s", exc)
        try:
            await ws.close(code=4401)
        except Exception as exc:
            logger.warning("kick: close socket failed: %s", exc)

        await room.broadcast(
            json.dumps(
                {
                    "type": "system",
                    "message": f"<em>Host wyrzucił {target_name} z pokoju.</em>",
                }
            )
        )
        await room.broadcast(
            json.dumps(
                {
                    "type": "score_update",
                    "scores": room.scores,
                    "host_name": room.host_name,
                    "ready_players": sorted(room.ready_players),
                }
            )
        )

        if (
            room.is_playing
            and room.expected_answers > 0
            and len(room.answers_received) >= room.expected_answers
        ):
            from .handlers import _finish_round

            await _finish_round(room, room_id)

        logger.info("Host '%s' kicked '%s' from room %s", actor_name, target_name, room_id)
        return True, ""

    def disconnect(
        self, room_id: str, client_name: str, websocket: WebSocket | None = None
    ) -> bool:
        """Remove *client_name* from *room_id*.

        If *websocket* is set, only removes when it matches the stored socket (reconnect
        race: old socket disconnect must not evict the new one). Returns whether a player
        was actually removed.
        """
        logger.info(
            "Disconnect requested: room_id=%s, client_name=%s, has_socket=%s",
            room_id,
            client_name,
            websocket is not None,
        )
        if room_id not in self.rooms:
            return False
        room = self.rooms[room_id]
        if client_name not in room.connections:
            return False
        current_ws = room.connections.get(client_name)
        if websocket is not None and current_ws is not websocket:
            logger.info(
                "Ignoring stale disconnect for '%s' in room %s (socket mismatch)",
                client_name,
                room_id,
            )
            return False

        del room.connections[client_name]
        logger.info("Removed connection for '%s' from room %s", client_name, room_id)

        # Decrease expected answer count
        if room.is_playing:
            room.answers_received.pop(client_name, None)
            room.expected_answers = max(0, room.expected_answers - 1)
            logger.debug(
                "Adjusted expected_answers for room %s: %s",
                room_id,
                room.expected_answers,
            )

        # If host left, assign new host
        if client_name == room.host_name and room.connections:
            room.host_name = next(iter(room.connections.keys()))
            logger.info("New host for room %s is '%s'", room_id, room.host_name)

        # Remove empty room
        if not room.connections:
            del self.rooms[room_id]
            logger.info("Room %s deleted because it became empty", room_id)
            self.schedule_delayed_room_delete(room_id)
        return True
