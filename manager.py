from typing import Dict
from fastapi import WebSocket
from data import COUNTRIES, NAMES

ALPHABET = "ABCDEFGHIJKLMNOPRSTUWZ"

class Room:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.connections: Dict[str, WebSocket] = {}
        self.scores: Dict[str, int] = {}
        
        # Stan rundy
        self.is_playing = False
        self.stop_triggered = False
        self.current_letter = ""
        self.answers_received: Dict[str, Dict[str, str]] = {}
        self.expected_answers = 0

    async def broadcast(self, message: str):
        """Wysyła wiadomość do wszystkich w pokoju"""
        for connection in list(self.connections.values()):
            await connection.send_text(message)

    def start_round(self) -> str:
        import random
        self.is_playing = True
        self.stop_triggered = False
        self.current_letter = random.choice(ALPHABET)
        self.answers_received = {}
        self.expected_answers = len(self.connections)
        return self.current_letter

    def calculate_scores(self) -> Dict[str, int]:
        """
        Zasady (proste MVP):
        - Poprawne i unikalne: 10 pkt
        - Poprawne, ale powtórzone: 5 pkt
        - Błędna litera lub puste: 0 pkt
        """
        round_scores = {player: 0 for player in self.answers_received}
        categories = ["Państwo", "Miasto", "Rzecz", "Zwierzę", "Roślina", "Imię", "Zawód"]
        
        for category in categories:
            # Zbieramy odpowiedzi graczy dla jednej kategorii { nick: hasło }
            category_answers = {}
            for player, answers in self.answers_received.items():
                ans = answers.get(category, "").strip().lower()
                
                is_valid = ans.startswith(self.current_letter.lower())
                
                # Dodatkowa weryfikacja słownikowa
                if is_valid and ans != "":
                    if category == "Państwo" and ans not in COUNTRIES:
                        is_valid = False
                    elif category == "Imię" and ans not in NAMES:
                        is_valid = False
                
                if is_valid and ans != "":
                    category_answers[player] = ans
                else:
                    category_answers[player] = ""
                    
            # Zliczamy, ile razy padło dane słowo
            counts = {}
            for ans in category_answers.values():
                if ans:
                    counts[ans] = counts.get(ans, 0) + 1
                    
            # Przypisujemy punkty
            for player, ans in category_answers.items():
                if ans == "":
                    continue # brak punktów
                
                if counts[ans] == 1:
                    round_scores[player] += 10 # Unikalne
                else:
                    round_scores[player] += 5  # Powtórzone
                    
        # Dodajemy do wyników całkowitych
        for player, score in round_scores.items():
            self.scores[player] = self.scores.get(player, 0) + score
            
        return round_scores

class ConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}

    async def connect(self, websocket: WebSocket, room_id: str, client_name: str) -> bool:
        if room_id not in self.rooms:
            self.rooms[room_id] = Room(room_id)
            
        room = self.rooms[room_id]
        if client_name in room.connections:
            return False # Nick zajęty
            
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
