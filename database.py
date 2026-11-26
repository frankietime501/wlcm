# database.py
import random
import sqlite3
import threading

from config import DB_PATH

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def init_db():
    global _conn
    _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA synchronous=NORMAL")
    _conn.execute("""
        CREATE TABLE IF NOT EXISTS member_codes (
            guild_id INTEGER NOT NULL,
            member_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            PRIMARY KEY (guild_id, member_id)
        )
    """)
    _conn.commit()


def get_or_create_member_code(guild_id: int, member_id: int, prefix: str) -> str:
    with _lock:
        cur = _conn.execute(
            "SELECT code FROM member_codes WHERE guild_id=? AND member_id=?",
            (guild_id, member_id),
        )
        row = cur.fetchone()
        if row:
            return row[0]

        code = f"{prefix}-{random.randint(10000, 99999)}-{random.randint(10, 99)}"
        _conn.execute(
            "INSERT INTO member_codes (guild_id, member_id, code) VALUES (?,?,?)",
            (guild_id, member_id, code),
        )
        _conn.commit()
        return code