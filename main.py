import os
import json
from datetime import datetime, timedelta
from collections import defaultdict
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

app = FastAPI(title="SekuChat PoC Backend")

# DB setup (keep your existing)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set!")

# Force psycopg driver by changing scheme to postgresql+psycopg
engine = create_engine(DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1))

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Simple in-memory message queue per chat (chat_id → list of messages)
message_queues = defaultdict(list)

# Active WebSocket connections per chat (chat_id → list of websockets)
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

# WebSocket endpoint for chat
@app.websocket("/ws/{chat_id}")
async def websocket_endpoint(websocket: WebSocket, chat_id: str):
    await websocket.accept()
    active_connections[chat_id].append(websocket)
    print(f"Client connected to chat {chat_id}. Total: {len(active_connections[chat_id])}")

    # Send queued (offline) messages to new client
    for msg in message_queues[chat_id]:
        await websocket.send_json(msg)

    try:
        while True:
            data = await websocket.receive_json()
            print(f"Received in {chat_id}: {data}")

            message = {
                "nick": data.get("nick", "Guest"),
                "content": data.get("content", ""),
                "timestamp": datetime.utcnow().isoformat()
            }

            # Queue for offline delivery
            message_queues[chat_id].append(message)

            # Broadcast to all connected in this chat
            for connection in active_connections[chat_id][:]:  # copy to avoid modification during iteration
                try:
                    await connection.send_json(message)
                except:
                    active_connections[chat_id].remove(connection)

            # Clean old queued messages (48h TTL)
            cutoff = datetime.utcnow() - timedelta(hours=48)
            message_queues[chat_id] = [
                m for m in message_queues[chat_id]
                if datetime.fromisoformat(m["timestamp"]) > cutoff
            ]

    except WebSocketDisconnect:
        if websocket in active_connections[chat_id]:
            active_connections[chat_id].remove(websocket)
        print(f"Client disconnected from {chat_id}. Remaining: {len(active_connections[chat_id])}")
        if not active_connections[chat_id]:
            del active_connections[chat_id]
