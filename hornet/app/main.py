"""Local test interface for an AI reply engine. Does NOT automate Hornet."""
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from .core import get_engine

DB_PATH = Path(os.getenv("DB_PATH", "/app/data/chats.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DB_LOCK = threading.RLock()
app = FastAPI(title="Hornet AI — local demo", version="0.1.0")


@contextmanager
def db():
    with DB_LOCK:
        connection = sqlite3.connect(str(DB_PATH), timeout=20)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()


with db() as con:
    con.executescript("""
        CREATE TABLE IF NOT EXISTS chats (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          label TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          chat_id INTEGER NOT NULL REFERENCES chats(id),
          direction TEXT NOT NULL CHECK(direction IN ('incoming','outgoing')),
          text TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)


class NonBlankPayload(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class NewChat(NonBlankPayload):
    label: str = Field(min_length=1, max_length=80)


class IncomingMessage(NonBlankPayload):
    text: str = Field(min_length=1, max_length=2000)


def chat_exists(chat_id: int) -> bool:
    with db() as con:
        return con.execute("SELECT 1 FROM chats WHERE id = ?", (chat_id,)).fetchone() is not None


def history(chat_id: int) -> list[dict]:
    if not chat_exists(chat_id):
        raise HTTPException(404, "Диалог не найден")
    with db() as con:
        rows = con.execute("SELECT id, direction, text, created_at FROM messages WHERE chat_id=? ORDER BY id ASC", (chat_id,)).fetchall()
    return [dict(row) for row in rows]


@app.get("/")
def home():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/healthz")
def health():
    try:
        with db() as con:
            con.execute("SELECT 1").fetchone()
    except sqlite3.Error:
        raise HTTPException(503, "Storage unavailable") from None
    return {"status": "ok"}


@app.get("/api/info")
def info():
    return {"mode": "demo-only", "connected_to_hornet": False,
            "llm": "OpenAI" if os.getenv("OPENAI_API_KEY", "").strip() else "mock",
            "autopilot": os.getenv("AUTOPILOT", "false").lower() == "true"}


@app.get("/api/chats")
def chats():
    with db() as con:
        rows = con.execute("SELECT id, label, created_at FROM chats ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]


@app.post("/api/chats", status_code=201)
def new_chat(payload: NewChat):
    with db() as con:
        cur = con.execute("INSERT INTO chats(label) VALUES(?)", (payload.label.strip(),))
        return {"id": cur.lastrowid, "label": payload.label.strip()}


@app.get("/api/chats/{chat_id}/messages")
def messages(chat_id: int):
    return history(chat_id)


def generate(chat_id: int):
    messages = history(chat_id)
    if not messages or messages[-1]["direction"] != "incoming":
        raise HTTPException(409, "Для ответа требуется новое входящее сообщение")
    try:
        answer = get_engine().reply(messages)
    except Exception as exc:
        # Do not leak API credentials or raw provider errors in responses/logs.
        raise HTTPException(502, "Не удалось сформировать ответ. Проверь конфигурацию и журналы сервера.") from None
    with db() as con:
        con.execute("INSERT INTO messages(chat_id,direction,text) VALUES(?,?,?)", (chat_id, "outgoing", answer))
    return {"reply": answer, "sent_to_hornet": False}


@app.post("/api/chats/{chat_id}/incoming", status_code=201)
def incoming(chat_id: int, payload: IncomingMessage):
    if not chat_exists(chat_id):
        raise HTTPException(404, "Диалог не найден")
    with db() as con:
        con.execute("INSERT INTO messages(chat_id,direction,text) VALUES(?,?,?)", (chat_id, "incoming", payload.text))
    if os.getenv("AUTOPILOT", "false").lower() == "true":
        return {"stored": True, "generated": generate(chat_id), "sent_to_hornet": False}
    return {"stored": True, "sent_to_hornet": False}


@app.post("/api/chats/{chat_id}/reply")
def reply(chat_id: int):
    return generate(chat_id)


@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: int):
    if not chat_exists(chat_id):
        raise HTTPException(404, "Диалог не найден")
    with db() as con:
        con.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
        con.execute("DELETE FROM chats WHERE id=?", (chat_id,))
    return {"deleted": True}
