import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from .manager import ConnectionManager
import os
import pathlib

app = FastAPI(title="Państwa-Miasta Engine")
manager = ConnectionManager()

# Montowanie plików statycznych
static_path = pathlib.Path(__file__).parent.parent.parent / "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")


async def global_round_timeout(room_id: str, round_num: int, wait_time: int):
    # Czekamy na globalny koniec czasu (+2s na lagi sieciowe)
    await asyncio.sleep(wait_time)
    if room_id in manager.rooms:
        room = manager.rooms[room_id]
        if room.is_playing and room.current_round == round_num and not room.stop_triggered:
            # Zamiast ucinać punkty i zakańczać grę z pustymi wynikami, 
            # serwer symuluje wciśnięcie przycisku STOP po upływie czasu globalnego.
            room.stop_triggered = True
            await room.broadcast(json.dumps({
                "type": "stop_round",
                "sender": "System (Koniec czasu)",
                "time_left": 10
            }))
            asyncio.create_task(force_end_round(room_id))

async def force_end_round(room_id: str):
    await asyncio.sleep(12)
    if room_id in manager.rooms:
        room = manager.rooms[room_id]
        if room.is_playing and room.stop_triggered:
            room.is_playing = False
            room.stop_triggered = False
            round_scores = await room.calculate_scores()
            is_game_over = room.current_round >= room.max_rounds
            if is_game_over:
                room.game_over = True
            
            await room.broadcast(json.dumps({
                "type": "round_results",
                "answers": room.answers_received,
                "round_scores": round_scores,
                "total_scores": room.scores,
                "game_over": is_game_over,
                "host_name": room.host_name
            }))

@app.get("/")
async def get():
    # Ścieżka do index.html w folderze static/
    base_path = pathlib.Path(__file__).parent.parent.parent
    index_path = base_path / "static" / "index.html"
    with open(index_path, "r", encoding="utf-8") as f:
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
        "scores": room.scores,
        "host_name": room.host_name
    }))
    
    # Wznawianie trwającej rundy lub wyświetlanie wyników końcowych
    if room.is_playing:
        await websocket.send_text(json.dumps({
            "type": "round_started",
            "letter": room.current_letter,
            "sender": "Serwer (Wznowienie)",
            "current_round": room.current_round,
            "max_rounds": room.max_rounds,
            "time_limit": room.time_limit
        }))
    elif room.game_over:
        await websocket.send_text(json.dumps({
            "type": "round_results",
            "answers": {},
            "round_scores": {},
            "total_scores": room.scores,
            "game_over": True,
            "host_name": room.host_name
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
                    if not room.is_playing and not room.game_over:
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
                        
                elif msg_type == "restart_game":
                    if room.game_over and client_name == room.host_name:
                        room.game_over = False
                        room.current_round = 0
                        room.scores = {p: 0 for p in room.scores.keys()}
                        room.answers_received = {}
                        room.ready_players.clear()
                        room.used_letters.clear()
                        room.is_playing = False
                        room.stop_triggered = False
                        
                        room.max_rounds = msg.get("rounds", 5)
                        room.time_limit = msg.get("limit", 90)
                        
                        await room.broadcast(json.dumps({
                            "type": "game_restarted",
                            "sender": client_name,
                            "scores": room.scores,
                            "host_name": room.host_name
                        }))
                
                elif msg_type == "dissolve_room":
                    if client_name == room.host_name:
                        await room.broadcast(json.dumps({
                            "type": "room_dissolved",
                            "message": "Pokój został rozwiązany przez hosta."
                        }))
                        # Rozłączamy wszystkich
                        for conn in list(room.connections.values()):
                            await conn.close()
                        
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
                            round_scores = await room.calculate_scores()
                            is_game_over = room.current_round >= room.max_rounds
                            if is_game_over:
                                room.game_over = True
                            
                            await room.broadcast(json.dumps({
                                "type": "round_results",
                                "answers": room.answers_received,
                                "round_scores": round_scores,
                                "total_scores": room.scores,
                                "game_over": is_game_over,
                                "host_name": room.host_name
                            }))
                            
            except json.JSONDecodeError:
                pass
            except Exception as e:
                print(f"❌ Błąd w obsłudze wiadomości od {client_name}: {e}")
                import traceback
                traceback.print_exc()
                # Nie zamykamy połączenia, próbujemy dalej
                continue
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
                "scores": room.scores,
                "host_name": room.host_name
            }))
