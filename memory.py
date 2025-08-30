
import sqlite3
from contextlib import closing
from typing import List, Tuple

DB_PATH = "data/bot.db"

def init_db():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        c = conn.cursor()
        c.execute("PRAGMA journal_mode=WAL;")
        c.execute("""CREATE TABLE IF NOT EXISTS warnings (
            chat_id INTEGER,
            user_id INTEGER,
            warnings INTEGER DEFAULT 0,
            mutes INTEGER DEFAULT 0,
            PRIMARY KEY (chat_id, user_id)
        );""")
        c.execute("""CREATE TABLE IF NOT EXISTS memory (
            chat_id INTEGER,
            user_id INTEGER,
            role TEXT,
            content TEXT,
            ts DATETIME DEFAULT CURRENT_TIMESTAMP
        );""")
        c.execute("""CREATE INDEX IF NOT EXISTS idx_memory ON memory(chat_id, user_id, ts);""")
        c.execute("""CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            target_user_id INTEGER,
            moderator_id INTEGER,
            action TEXT,
            reason TEXT,
            ts DATETIME DEFAULT CURRENT_TIMESTAMP
        );""")
        conn.commit()

def inc_warning(chat_id: int, user_id: int) -> Tuple[int, int]:
    """Increase warning by 1; returns (warnings, mutes) after update"""
    with closing(sqlite3.connect(DB_PATH)) as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO warnings(chat_id,user_id,warnings,mutes) VALUES(?,?,0,0)", (chat_id, user_id))
        c.execute("UPDATE warnings SET warnings = warnings + 1 WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        c.execute("SELECT warnings, mutes FROM warnings WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        row = c.fetchone()
        conn.commit()
        return row if row else (0, 0)

def reset_warnings(chat_id: int, user_id: int):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        c = conn.cursor()
        c.execute("UPDATE warnings SET warnings = 0 WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        conn.commit()

def inc_mutes(chat_id: int, user_id: int) -> int:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO warnings(chat_id,user_id,warnings,mutes) VALUES(?,?,0,0)", (chat_id, user_id))
        c.execute("UPDATE warnings SET mutes = mutes + 1 WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        c.execute("SELECT mutes FROM warnings WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        row = c.fetchone()
        conn.commit()
        return row[0] if row else 0

def add_memory(chat_id: int, user_id: int, role: str, content: str):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO memory(chat_id,user_id,role,content) VALUES(?,?,?,?)",
                  (chat_id, user_id, role, content))
        conn.commit()

def get_recent_memory(chat_id: int, user_id: int, limit: int = 10) -> List[Tuple[str, str]]:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        c = conn.cursor()
        c.execute("""SELECT role, content FROM memory
                     WHERE chat_id=? AND user_id=?
                     ORDER BY ts DESC LIMIT ?""",
                  (chat_id, user_id, limit))
        rows = c.fetchall()
        # Return in chronological order
        return list(reversed(rows))

def add_audit(chat_id: int, target_user_id: int, moderator_id: int, action: str, reason: str):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO audit(chat_id,target_user_id,moderator_id,action,reason) VALUES(?,?,?,?,?)",
                  (chat_id, target_user_id, moderator_id, action, reason))
        conn.commit()
