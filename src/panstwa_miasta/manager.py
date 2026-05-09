from typing import Dict
from fastapi import WebSocket
import asyncio
from .data import COUNTRIES, NAMES, JOBS

ALPHABET = "ABCDEFGHIJKLMNOPRSTUWZ"

class Room:
    def __init__(self, room_id: str, max_rounds: int = 5, time_limit: int = 90):
        self.room_id = room_id
        self.max_rounds = max_rounds
        self.time_limit = time_limit
        self.connections: Dict[str, WebSocket] = {}
        self.scores: Dict[str, int] = {}
        
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
                    if ans not in JOBS:
                        round_scores[player]["details"][category] = 0
                    else:
                        round_scores[player]["details"][category] = -1
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
                    
        # Dodajemy do wyników całkowitych
        for player, score_data in round_scores.items():
            self.scores[player] = self.scores.get(player, 0) + score_data["total"]
            
        return round_scores

class ConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}

    async def connect(self, websocket: WebSocket, room_id: str, client_name: str, max_rounds: int, time_limit: int) -> bool:
        if room_id not in self.rooms:
            self.rooms[room_id] = Room(room_id, max_rounds, time_limit)
            
        room = self.rooms[room_id]
        
        # Jeśli ktoś wchodzi z tym samym nickiem (np. powrót zminimalizowanej przeglądarki na telefonie),
        # ubijamy stare "ducha" połączenie i podmieniamy na nowe.
        if client_name in room.connections:
            try:
                await room.connections[client_name].close()
            except Exception:
                pass
            
        await websocket.accept()
        room.connections[client_name] = websocket
        
        # Jeśli nowy gracz, dodaj mu 0 punktów
        if client_name not in room.scores:
            room.scores[client_name] = 0
            
        return True

    def disconnect(self, room_id: str, client_name: str):
        if room_id in self.rooms:
            room = self.rooms[room_id]
            if client_name in room.connections:
                del room.connections[client_name]
                
                # Zmniejsz pulę oczekiwanych odpowiedzi
                if room.is_playing:
                    room.expected_answers = max(0, room.expected_answers - 1)
            
            # Usuń pokój, jeśli pusty
            if not room.connections:
                del self.rooms[room_id]
