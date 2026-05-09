import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
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
        await websocket.close(code=1008) 
        return
    
    await manager.broadcast(json.dumps({
        "type": "system", 
        "message": f"{client_name} dołączył do gry"
    }), room_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                msg["sender"] = client_name
                await manager.broadcast(json.dumps(msg), room_id)
            except json.JSONDecodeError:
                pass # ignoruj niepoprawne formaty
    except WebSocketDisconnect:
        manager.disconnect(room_id, client_name)
        await manager.broadcast(json.dumps({
            "type": "system", 
            "message": f"{client_name} opuścił grę"
        }), room_id)
