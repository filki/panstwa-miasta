from typing import Dict
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # Dictionary structure: { "room_id": { "player_name": WebSocket } }
        self.rooms: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str, client_name: str) -> bool:
        """
        Connects a client to a room. Returns True if successful, False if nickname is taken.
        """
        if room_id not in self.rooms:
            self.rooms[room_id] = {}
        
        if client_name in self.rooms[room_id]:
            return False
            
        await websocket.accept()
        self.rooms[room_id][client_name] = websocket
        return True

    def disconnect(self, room_id: str, client_name: str):
        """
        Removes a client from a room.
        """
        if room_id in self.rooms and client_name in self.rooms[room_id]:
            del self.rooms[room_id][client_name]
            # Clean up empty rooms
            if not self.rooms[room_id]:
                del self.rooms[room_id]

    async def broadcast(self, message: str, room_id: str):
        """
        Broadcasts a message to all clients in a room.
        """
        if room_id in self.rooms:
            for connection in self.rooms[room_id].values():
                await connection.send_text(message)
