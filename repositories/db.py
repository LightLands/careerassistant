"""Единый слой подключения к SQLite + миграции + бэкапы."""
import logging
import os
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


class Database:
    def __init__(self, path: str):
        self.path = path
        db_dir = os.path.dirname(path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        # Гарантируем, что файл существует
        self._connect().close()
        self._migrate()

    # ---------- соединения ----------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def conn(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ---------- миграции ----------
    def _migrate(self) -> None:
        with self.conn() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_version (v INTEGER NOT NULL)"
            )
            row = conn.execute("SELECT v FROM schema_version").fetchone()
            current = row["v"] if row else 0

            if current < 1:
                logger.info("Applying schema v1")
                conn.executescript(_SCHEMA_V1)

            if current != SCHEMA_VERSION:
                conn.execute("DELETE FROM schema_version")
                conn.execute(
                    "INSERT INTO schema_version (v) VALUES (?)", (SCHEMA_VERSION,)
                )
            logger.info("DB schema ready (v%s) at %s", SCHEMA_VERSION, self.path)

    # ---------- бэкапы ----------
    def backup(self, backup_dir: str, keep_days: int = 14) -> str:
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst_path = os.path.join(backup_dir, f"career_bot_{stamp}.db")

        with self._connect() as src, sqlite3.connect(dst_path) as dst:
            src.backup(dst)

        # Чистим старые бэкапы
        cutoff = datetime.now().timestamp() - keep_days * 86400
        for name in os.listdir(backup_dir):
            if not name.startswith("career_bot_") or not name.endswith(".db"):
                continue
            full = os.path.join(backup_dir, name)
            if os.path.getmtime(full) < cutoff:
                try:
                    os.remove(full)
                except OSError:
                    pass
        logger.info("DB backup created: %s", dst_path)
        return dst_path


# ---------- SQL схемы ----------
_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS saved_vacancies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    vacancy_id TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT,
    salary TEXT,
    location TEXT,
    url TEXT NOT NULL,
    description TEXT,
    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'saved',
    UNIQUE(user_id, vacancy_id)
);
CREATE INDEX IF NOT EXISTS idx_saved_user
    ON saved_vacancies(user_id);
CREATE INDEX IF NOT EXISTS idx_saved_status
    ON saved_vacancies(user_id, status);

CREATE TABLE IF NOT EXISTS temp_vacancies (
    vacancy_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT,
    salary TEXT,
    location TEXT,
    url TEXT NOT NULL,
    description TEXT,
    tags TEXT,
    date TEXT,
    salary_min INTEGER,
    salary_max INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_temp_created
    ON temp_vacancies(created_at);

CREATE TABLE IF NOT EXISTS job_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    tech TEXT NOT NULL,
    salary INTEGER,
    location TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, tech, salary, location)
);
CREATE INDEX IF NOT EXISTS idx_subs_active
    ON job_subscriptions(is_active);
CREATE INDEX IF NOT EXISTS idx_subs_user
    ON job_subscriptions(user_id);

CREATE TABLE IF NOT EXISTS sent_vacancies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    vacancy_id TEXT NOT NULL,
    subscription_id INTEGER NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, vacancy_id)
);
CREATE INDEX IF NOT EXISTS idx_sent_user
    ON sent_vacancies(user_id);
CREATE INDEX IF NOT EXISTS idx_sent_time
    ON sent_vacancies(sent_at);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    company TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_links_user
    ON links(user_id);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY,
    notify_hour INTEGER DEFAULT 10,
    language TEXT DEFAULT 'ru'
);

CREATE TABLE IF NOT EXISTS cover_letters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    vacancy_text TEXT,
    letter_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cl_user
    ON cover_letters(user_id);

CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    tech TEXT,
    salary INTEGER,
    location TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sh_user
    ON search_history(user_id);
"""