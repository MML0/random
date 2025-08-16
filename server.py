
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import json

app = FastAPI()

# Serve index.html from the working directory
# If you place index.html alongside server.py, this will serve it at '/'
@app.get("/")
async def root():
    return FileResponse("index.html")

# Room registry: room_id -> set of live WebSocket connections
rooms: dict[str, set[WebSocket]] = {}

async def join_room(ws: WebSocket, room: str):
    if room not in rooms:
        rooms[room] = set()
    rooms[room].add(ws)

async def leave_room(ws: WebSocket):
    # Remove ws from whichever room it belongs to
    for r, peers in list(rooms.items()):
        if ws in peers:
            peers.remove(ws)
            # Notify remaining peers someone left
            for p in set(peers):
                try:
                    await p.send_text(json.dumps({"type": "bye"}))
                except Exception:
                    pass
            if not peers:
                del rooms[r]
            break

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue

            if msg.get("type") == "join":
                room = msg.get("room", "")
                await join_room(ws, room)
                # Notify peers someone joined
                for p in rooms.get(room, set()):
                    if p is not ws:
                        try:
                            await p.send_text(json.dumps({"type": "peer-joined", "role": msg.get("role")}))
                        except Exception:
                            pass
                continue

            # Relay signaling messages to other peers in the same room
            if msg.get("type") in {"offer", "answer", "ice", "bye"}:
                room = msg.get("room", "")
                for p in rooms.get(room, set()):
                    if p is not ws:
                        try:
                            await p.send_text(json.dumps(msg))
                        except Exception:
                            pass
    except WebSocketDisconnect:
        await leave_room(ws)
    except Exception:
        await leave_room(ws)
