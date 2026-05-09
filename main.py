import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from manager import ConnectionManager

app = FastAPI(title="Państwa-Miasta Engine")
manager = ConnectionManager()

async def global_round_timeout(room_id: str, round_num: int, wait_time: int):
    # Czekamy na globalny koniec czasu (+2s na lagi sieciowe)
    await asyncio.sleep(wait_time)
    if room_id in manager.rooms:
        room = manager.rooms[room_id]
        if room.is_playing and room.current_round == round_num:
            room.is_playing = False
            room.stop_triggered = False
            round_scores = room.calculate_scores()
            is_game_over = room.current_round >= room.max_rounds
            
            await room.broadcast(json.dumps({
                "type": "round_results",
                "answers": room.answers_received,
                "round_scores": round_scores,
                "total_scores": room.scores,
                "game_over": is_game_over
            }))

async def force_end_round(room_id: str):
    await asyncio.sleep(12)
    if room_id in manager.rooms:
        room = manager.rooms[room_id]
        if room.is_playing and room.stop_triggered:
            room.is_playing = False
            room.stop_triggered = False
            round_scores = room.calculate_scores()
            is_game_over = room.current_round >= room.max_rounds
            
            await room.broadcast(json.dumps({
                "type": "round_results",
                "answers": room.answers_received,
                "round_scores": round_scores,
                "total_scores": room.scores,
                "game_over": is_game_over
            }))

@app.get("/")
async def get():
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

@app.websocket("/ws/{room_id}/{client_name}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, client_name: str, rounds: int = 5, limit: int = 90):
    success = await manager.connect(websocket, room_id, client_name, rounds, limit)
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
    
    # Wznawianie trwającej rundy
    if room.is_playing:
        await websocket.send_text(json.dumps({
            "type": "round_started",
            "letter": room.current_letter,
            "sender": "Serwer (Wznowienie)",
            "current_round": room.current_round,
            "max_rounds": room.max_rounds,
            "time_limit": room.time_limit
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
                    
                elif msg_type == "ready":
                    if not room.is_playing:
                        room.ready_players.add(client_name)
                        await room.broadcast(json.dumps({
                            "type": "system",
                            "message": f"<em>{client_name} jest gotowy! ({len(room.ready_players)}/{len(room.connections)})</em>"
                        }))
                        
                        if len(room.ready_players) >= len(room.connections) and len(room.connections) > 0:
                            letter = room.start_round()
                            await room.broadcast(json.dumps({
                                "type": "round_started",
                                "letter": letter,
                                "sender": "System",
                                "current_round": room.current_round,
                                "max_rounds": room.max_rounds,
                                "time_limit": room.time_limit
                            }))
                            asyncio.create_task(global_round_timeout(room_id, room.current_round, room.time_limit + 2))
                
                elif msg_type == "not_ready":
                    if not room.is_playing:
                        room.ready_players.discard(client_name)
                        await room.broadcast(json.dumps({
                            "type": "system",
                            "message": f"<em>{client_name} nie jest już gotowy. ({len(room.ready_players)}/{len(room.connections)})</em>"
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
                            is_game_over = room.current_round >= room.max_rounds
                            
                            await room.broadcast(json.dumps({
                                "type": "round_results",
                                "answers": room.answers_received,
                                "round_scores": round_scores,
                                "total_scores": room.scores,
                                "game_over": is_game_over
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
