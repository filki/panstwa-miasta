import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from manager import ConnectionManager

app = FastAPI(title="Państwa-Miasta Engine")
manager = ConnectionManager()

async def force_end_round(room_id: str):
    # Dajemy 12 sekund, czyli 2 sekundy "zapasu" na opóźnienia sieciowe (lagi),
    # podczas gdy klient odlicza 10 sekund i potem wysyła odpowiedzi.
    await asyncio.sleep(12)
    if room_id in manager.rooms:
        room = manager.rooms[room_id]
        if room.is_playing and room.stop_triggered:
            room.is_playing = False
            room.stop_triggered = False
            round_scores = room.calculate_scores()
            await room.broadcast(json.dumps({
                "type": "round_results",
                "answers": room.answers_received,
                "round_scores": round_scores,
                "total_scores": room.scores
            }))

@app.get("/")
async def get():
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

@app.websocket("/ws/{room_id}/{client_name}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, client_name: str):
    success = await manager.connect(websocket, room_id, client_name)
    if not success:
        await websocket.close(code=1008) 
        return
        
    room = manager.rooms[room_id]
    
    # Wyślij powitanie i aktualny stan punktów
    await room.broadcast(json.dumps({
        "type": "system", 
        "message": f"{client_name} dołączył do gry"
    }))
    
    # Wyślij aktualną tabelę wyników do wszystkich
    await room.broadcast(json.dumps({
        "type": "score_update",
        "scores": room.scores
    }))
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type")
                
                if msg_type == "chat":
                    await room.broadcast(json.dumps({
                        "type": "chat",
                        "sender": client_name,
                        "text": msg["text"]
                    }))
                    
                elif msg_type == "draw":
                    if not room.is_playing:
                        letter = room.start_round()
                        await room.broadcast(json.dumps({
                            "type": "round_started",
                            "letter": letter,
                            "sender": client_name
                        }))
                        
                elif msg_type == "stop":
                    if room.is_playing and not room.stop_triggered:
                        room.stop_triggered = True
                        await room.broadcast(json.dumps({
                            "type": "stop_round",
                            "sender": client_name,
                            "time_left": 10
                        }))
                        asyncio.create_task(force_end_round(room_id))
                        
                elif msg_type == "answers":
                    if room.is_playing:
                        room.answers_received[client_name] = msg.get("answers", {})
                        
                        # Gdy tylko spłyną odpowiedzi od WSZYSTKICH (np. po 10s odliczania na frontendzie), od razu zakończ.
                        if len(room.answers_received) >= room.expected_answers:
                            room.is_playing = False
                            room.stop_triggered = False
                            round_scores = room.calculate_scores()
                            
                            await room.broadcast(json.dumps({
                                "type": "round_results",
                                "answers": room.answers_received,
                                "round_scores": round_scores,
                                "total_scores": room.scores
                            }))
                            
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(room_id, client_name)
        if room_id in manager.rooms:
            room = manager.rooms[room_id]
            await room.broadcast(json.dumps({
                "type": "system", 
                "message": f"{client_name} opuścił grę"
            }))
            await room.broadcast(json.dumps({
                "type": "score_update",
                "scores": room.scores
            }))
