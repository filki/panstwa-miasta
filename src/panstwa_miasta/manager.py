from typing import Dict
from fastapi import WebSocket
import asyncio
from .data import COUNTRIES, NAMES, JOBS
from .db import save_room, save_player_score, delete_room, get_active_rooms

ALPHABET = "ABCDEFGHIJKLMNOPRSTUWZ"

class Room:
    def __init__(self, room_id: str, max_rounds: int = 5, time_limit: int = 90):
        self.room_id = room_id
        self.max_rounds = max_rounds
        self.time_limit = time_limit
        self.connections: Dict[str, WebSocket] = {}
        self.scores: Dict[str, int] = {}
        self.host_name = ""
        
        # Stan gry i rundy
        self.current_round = 0
        self.used_letters = set()
        self.ready_players = set()
        self.is_playing = False
        self.stop_triggered = False
        self.current_letter = ""
        self.answers_received: Dict[str, Dict[str, str]] = {}
        self.expected_answers = 0
        self.game_over = False

    async def broadcast(self, message: str):
        """Wysyła wiadomość do wszystkich w pokoju"""
        for connection in list(self.connections.values()):
            await connection.send_text(message)

    def start_round(self) -> str:
        import random
        self.is_playing = True
        self.stop_triggered = False
        self.ready_players = set() # Reset gotowości
        self.current_round += 1
        
        available = list(set(ALPHABET) - self.used_letters)
        if not available:
            self.used_letters = set()
            available = list(ALPHABET)
            
        self.current_letter = random.choice(available)
        self.used_letters.add(self.current_letter)
        
        self.answers_received = {}
        self.expected_answers = len(self.connections)
        return self.current_letter

    async def calculate_scores(self) -> Dict[str, Dict]:
        """
        Zwraca: {player: {"total": int, "details": {category: points}}}
        """
        from .validator import validator
        
        round_scores = {player: {"total": 0, "details": {}} for player in self.answers_received}
        categories = ["Państwo", "Miasto", "Rzecz", "Zwierzę", "Roślina", "Imię", "Zawód"]
        
        # Przygotowanie listy haseł do walidacji przez Wikipedię
        # (tylko te, których nie mamy w lokalnych słownikach)
        wiki_categories = ["Miasto", "Zwierzę", "Roślina"]
        validation_tasks = []
        task_info = [] # (player, category, ans)
        
        for category in categories:
            for player, answers in self.answers_received.items():
                ans = answers.get(category, "").strip().lower()
                
                # Podstawowa walidacja (litera)
                is_valid_base = ans.startswith(self.current_letter.lower()) and ans != ""
                
                if not is_valid_base:
                    round_scores[player]["details"][category] = 0
                    continue

                # Specjalistyczna walidacja
                if category == "Państwo":
                    if ans not in COUNTRIES:
                        round_scores[player]["details"][category] = 0
                    else:
                        round_scores[player]["details"][category] = -1 # Oznaczenie "do dalszej oceny punktowej"
                elif category == "Imię":
                    if ans not in NAMES:
                        round_scores[player]["details"][category] = 0
                    else:
                        round_scores[player]["details"][category] = -1
                elif category == "Zawód":
                    if ans in JOBS:
                        round_scores[player]["details"][category] = -1
                    else:
                        # Lematyzacja / dopasowanie częściowe: np. "urolog" dopasuje "lekarz urolog"
                        # Szukamy po pełnych słowach (split()), by "log" nie dopasowało "urolog"
                        if any(ans in job.split() for job in JOBS):
                            round_scores[player]["details"][category] = -1
                        else:
                            round_scores[player]["details"][category] = 0
                elif category in wiki_categories:
                    # Kolejkujemy do Wikipedii
                    validation_tasks.append(validator.validate(ans, category))
                    task_info.append((player, category, ans))
                else:
                    # Rzecz - na razie akceptujemy wszystko na dobrą literę
                    round_scores[player]["details"][category] = -1

        # Czekamy na wszystkie wyniki z Wikipedii równolegle
        if validation_tasks:
            wiki_results = await asyncio.gather(*validation_tasks)
            for (player, category, ans), is_valid in zip(task_info, wiki_results):
                if is_valid:
                    round_scores[player]["details"][category] = -1
                else:
                    round_scores[player]["details"][category] = 0

        # Druga faza: Liczenie punktów (5, 10) dla poprawnych haseł
        for category in categories:
            counts = {}
            # Zliczamy tylko poprawne (te z -1)
            for player in self.answers_received:
                if round_scores[player]["details"].get(category) == -1:
                    ans = self.answers_received[player].get(category, "").strip().lower()
                    counts[ans] = counts.get(ans, 0) + 1
            
            # Przypisujemy punkty
            for player in self.answers_received:
                if round_scores[player]["details"].get(category) == -1:
                    ans = self.answers_received[player].get(category, "").strip().lower()
                    pts = 10 if counts[ans] == 1 else 5
                    round_scores[player]["details"][category] = pts
                    round_scores[player]["total"] += pts
                    
        # Dodajemy do wyników całkowitych i zapisujemy w DB
        for player, score_data in round_scores.items():
            self.scores[player] = self.scores.get(player, 0) + score_data["total"]
            await save_player_score(self.room_id, player, self.scores[player])
            
        # Zapisz aktualną rundę i hosta
        await save_room(self.room_id, self.max_rounds, self.time_limit, self.current_round, self.host_name)
            
        return round_scores

class ConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}

    async def connect(self, websocket: WebSocket, room_id: str, client_name: str, max_rounds: int, time_limit: int) -> bool:
        if room_id not in self.rooms:
            self.rooms[room_id] = Room(room_id, max_rounds, time_limit)
            
        room = self.rooms[room_id]
        
        # Jeśli ktoś wchodzi z tym samym nickiem, ubijamy stare połączenie
        if client_name in room.connections:
            try:
                await room.connections[client_name].close()
            except Exception:
                pass
            
        await websocket.accept()
        room.connections[client_name] = websocket
        
        if not room.host_name:
            room.host_name = client_name
        
        if client_name not in room.scores:
            room.scores[client_name] = 0
            
        # Zapisz/Aktualizuj pokój i gracza w DB
        await save_room(room_id, room.max_rounds, room.time_limit, room.current_round, room.host_name)
        await save_player_score(room_id, client_name, room.scores[client_name])
            
        return True

    async def load_from_db(self):
        """Ładuje aktywne pokoje i wyniki z bazy danych przy starcie"""
        active_rooms = await get_active_rooms()
        for r_data in active_rooms:
            room = Room(r_data["room_id"], r_data["max_rounds"], r_data["time_limit"])
            room.current_round = r_data["current_round"]
            room.host_name = r_data["host_name"]
            room.scores = r_data["players"]
            self.rooms[r_data["room_id"]] = room
        print(f"✅ Załadowano {len(active_rooms)} pokoi z bazy danych.")

    def disconnect(self, room_id: str, client_name: str):
        if room_id in self.rooms:
            room = self.rooms[room_id]
            if client_name in room.connections:
                del room.connections[client_name]
                
                # Zmniejsz pulę oczekiwanych odpowiedzi
                if room.is_playing:
                    room.expected_answers = max(0, room.expected_answers - 1)
                
                # Jeśli wyszedł host, mianuj nowego
                if client_name == room.host_name and room.connections:
                    room.host_name = next(iter(room.connections.keys()))
            
            # Usuń pokój, jeśli pusty
            if not room.connections:
                del self.rooms[room_id]
