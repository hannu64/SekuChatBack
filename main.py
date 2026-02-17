print("Starting app - DATABASE_URL:", os.getenv("DATABASE_URL"))
import os
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

app = FastAPI(title="SekuChat PoC Backend")

# DB setup
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
