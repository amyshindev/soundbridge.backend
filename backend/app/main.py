import os
import asyncpg
from fastapi import FastAPI

app = FastAPI(title="SoundBridge API")

DATABASE_URL = os.getenv("DATABASE_URL")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/health/db")
async def health_db():
    # SQLAlchemy 없이 asyncpg로 직접 연결
    conn = await asyncpg.connect(
        dsn=DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"),
        ssl="require"
    )
    await conn.execute("SELECT 1")
    await conn.close()
    return {"status": "db connected"}