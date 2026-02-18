import os
import json
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from collections import defaultdict
from datetime import datetime, timedelta

app = FastAPI(title="SekuChat PoC Backend")

# DB setup (your existing connection)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set!")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Simple in-memory message queue (chat_id -> list of pending messages)
message_queues = defaultdict(list)

# Active WebSocket connections (chat_id -> list of websockets)
active_connections = defaultdict(list)

@app.get("/")
async def root():
    return {"message": "SekuChat Backend is LIVE! 🚀"}

@app.get("/test-db")
async def test_db(db: Session = Depends(get_db)):
    try:
        result = db.execute(text("SELECT 1"))
        return {"status": "DB connected", "result": result.scalar()}
    except Exception as e:
        return {"status": "DB error", "detail": str(e)}

# WebSocket endpoint
@app.websocket("/ws/{chat_id}")
async def websocket_endpoint(websocket: WebSocket, chat_id: str):
    await websocket.accept()
    active_connections[chat_id].append(websocket)
    print(f"Client connected to chat {chat_id}. Total: {len(active_connections[chat_id])}")

    # Send any queued messages to new client
    for msg in message_queues[chat_id]:
        await websocket.send_json(msg)

    try:
        while True:
            data = await websocket.receive_json()
            print(f"Received in {chat_id}: {data}")

            # Broadcast to all in this chat (for now 1:1, so only one other)
            message = {
                "nick": data.get("nick", "Guest"),
                "content": data.get("content", ""),
                "timestamp": datetime.utcnow().isoformat()
            }

            # Queue for offline users
            message_queues[chat_id].append(message)

            # Send to all connected clients
            for connection in active_connections[chat_id]:
                if connection != websocket:  # Don't echo to sender
                    await connection.send_json(message)

            # Auto-delete old queued messages (48h TTL for PoC)
            message_queues[chat_id] = [
                m for m in message_queues[chat_id]
                if datetime.fromisoformat(m["timestamp"]) > datetime.utcnow() - timedelta(hours=48)
            ]

    except WebSocketDisconnect:
        active_connections[chat_id].remove(websocket)
        print(f"Client disconnected from {chat_id}. Remaining: {len(active_connections[chat_id])}")
        if not active_connections[chat_id]:
            del active_connections[chat_id]
