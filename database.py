import aiosqlite
from datetime import datetime

DB_PATH = "bot.db"

DEFAULT_SETTINGS = {
    "bot_active": "1",
    "model": "meta-llama/llama-3.1-8b-instruct:free",
    "bot_prompt": "",
    "bot_name": "Авто",
}


class Database:
    def __init__(self, path: str = DB_PATH):
        self.path = path

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS chat_history (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id   INTEGER NOT NULL,
                    role      TEXT    NOT NULL,
                    content   TEXT    NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS owner_activity (
                    id        INTEGER PRIMARY KEY CHECK (id = 1),
                    last_seen TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS status (
                    id      INTEGER PRIMARY KEY CHECK (id = 1),
                    message TEXT    NOT NULL DEFAULT '',
                    active  INTEGER NOT NULL DEFAULT 0
                );
            """)

            for key, value in DEFAULT_SETTINGS.items():
                await db.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                    (key, value),
                )

            await db.execute(
                "INSERT OR IGNORE INTO owner_activity (id, last_seen) VALUES (1, ?)",
                (datetime.now().isoformat(),),
            )
            await db.execute(
                "INSERT OR IGNORE INTO status (id, message, active) VALUES (1, '', 0)"
            )
            await db.commit()

    # ── Settings ──────────────────────────────────────────────────────────────

    async def get_setting(self, key: str) -> str:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = await cur.fetchone()
            return row[0] if row else ""

    async def set_setting(self, key: str, value: str):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
            await db.commit()

    async def get_all_settings(self) -> dict[str, str]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT key, value FROM settings")
            rows = await cur.fetchall()
            return dict(rows)

    # ── Owner activity ────────────────────────────────────────────────────────

    async def update_owner_seen(self):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE owner_activity SET last_seen = ? WHERE id = 1",
                (datetime.now().isoformat(),),
            )
            await db.commit()

    async def get_owner_last_seen(self) -> datetime:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT last_seen FROM owner_activity WHERE id = 1")
            row = await cur.fetchone()
            return datetime.fromisoformat(row[0]) if row else datetime.now()

    # ── Chat history ──────────────────────────────────────────────────────────

    async def add_message(self, chat_id: int, role: str, content: str):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO chat_history (chat_id, role, content) VALUES (?, ?, ?)",
                (chat_id, role, content),
            )
            await db.commit()

    async def get_history(self, chat_id: int, limit: int = 20) -> list[dict]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """SELECT role, content FROM chat_history
                   WHERE chat_id = ?
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (chat_id, limit),
            )
            rows = await cur.fetchall()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    async def clear_history(self, chat_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM chat_history WHERE chat_id = ?", (chat_id,))
            await db.commit()

    # ── Status ────────────────────────────────────────────────────────────────

    async def set_status(self, message: str, active: bool):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE status SET message = ?, active = ? WHERE id = 1",
                (message, 1 if active else 0),
            )
            await db.commit()

    async def get_status(self) -> tuple[str, bool]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT message, active FROM status WHERE id = 1")
            row = await cur.fetchone()
            return (row[0], bool(row[1])) if row else ("", False)
