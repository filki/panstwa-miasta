from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import os
from manager import ConnectionManager

app = FastAPI(title="Państwa-Miasta MVP")
manager = ConnectionManager()

@app.get("/")
async def get():
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

@app.websocket("/ws/{room_id}/{client_name}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, client_name: str):
    success = await manager.connect(websocket, room_id, client_name)
    if not success:
        # Policy Violation (Nickname taken)
        await websocket.close(code=1008) 
        return
    
    await manager.broadcast(f"System: {client_name} dołączył do gry w pokoju {room_id}", room_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"{client_name}: {data}", room_id)
    except WebSocketDisconnect:
        manager.disconnect(room_id, client_name)
        await manager.broadcast(f"System: {client_name} opuścił grę", room_id)
