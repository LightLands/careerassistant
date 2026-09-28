import logging
import sqlite3
from typing import Optional

from ..models import Subscription, Stats, Vacancy

logger = logging.getLogger(__name__)

STATUS_FLOW = ["saved", "applied", "interview", "offer"]


class SQLiteRepository:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._init_tables()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_tables(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
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

                CREATE TABLE IF NOT EXISTS temp_vacancies (
                    vacancy_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    company TEXT,
                    salary TEXT,
                    location TEXT,
                    url TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

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

                CREATE TABLE IF NOT EXISTS sent_vacancies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    vacancy_id TEXT NOT NULL,
                    subscription_id INTEGER NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, vacancy_id, subscription_id)
                );
            """)
        logger.info("DB initialized at %s", self._db_path)

    # --- temp ---
    def save_temp_vacancy(self, v: Vacancy) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO temp_vacancies
                   (vacancy_id, title, company, salary, location, url, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (v.id, v.title, v.company, v.salary, v.location, v.url, v.description),
            )

    def get_temp_vacancy(self, vacancy_id: str) -> Optional[Vacancy]:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT vacancy_id, title, company, salary, location, url, description
                   FROM temp_vacancies WHERE vacancy_id = ?""",
                (vacancy_id,),
            ).fetchone()
        if not row:
            return None
        return Vacancy(id=row[0], title=row[1], company=row[2], salary=row[3],
                       location=row[4], url=row[5], description=row[6])

    # --- saved ---
    def save_vacancy(self, user_id: int, v: Vacancy) -> bool:
        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO saved_vacancies
                       (user_id, vacancy_id, title, company, salary, location, url, description)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, v.id, v.title, v.company, v.salary,
                     v.location, v.url, v.description),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def get_user_vacancies(self, user_id: int) -> list[tuple]:
        with self._connect() as conn:
            return conn.execute(
                """SELECT id, title, company, salary, location, url, saved_at, status
                   FROM saved_vacancies WHERE user_id = ?
                   ORDER BY saved_at DESC""",
                (user_id,),
            ).fetchall()

    def delete_vacancy(self, user_id: int, db_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM saved_vacancies WHERE id = ? AND user_id = ?",
                (db_id, user_id),
            )
        return cur.rowcount > 0

    def update_vacancy_status(self, user_id: int, db_id: int, new_status: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM saved_vacancies WHERE id = ? AND user_id = ?",
                (db_id, user_id),
            ).fetchone()
            if not row:
                return False
            current = row[0]

            # rejected разрешено с любого этапа
            if new_status == "rejected" and current != "rejected":
                conn.execute(
                    "UPDATE saved_vacancies SET status = ? WHERE id = ? AND user_id = ?",
                    (new_status, db_id, user_id),
                )
                return True

            if new_status not in STATUS_FLOW or current not in STATUS_FLOW:
                return False
            if STATUS_FLOW.index(new_status) <= STATUS_FLOW.index(current):
                return False

            conn.execute(
                "UPDATE saved_vacancies SET status = ? WHERE id = ? AND user_id = ?",
                (new_status, db_id, user_id),
            )
            return True

    # --- stats ---
    def get_stats(self, user_id: int) -> Stats:
        stats = Stats()
        with self._connect() as conn:
            for st in ["saved", "applied", "interview", "offer", "rejected"]:
                count = conn.execute(
                    "SELECT COUNT(*) FROM saved_vacancies WHERE user_id = ? AND status = ?",
                    (user_id, st),
                ).fetchone()[0]
                setattr(stats, st, count)
        return stats

    # --- subscriptions ---
    def add_subscription(self, user_id: int, tech: str,
                         salary: Optional[int], location: Optional[str]) -> bool:
        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO job_subscriptions (user_id, tech, salary, location)
                       VALUES (?, ?, ?, ?)""",
                    (user_id, tech, salary, location),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def get_active_subscriptions(self) -> list[Subscription]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT id, user_id, tech, salary, location
                   FROM job_subscriptions WHERE is_active = 1"""
            ).fetchall()
        return [Subscription(id=r[0], user_id=r[1], tech=r[2],
                             salary=r[3], location=r[4]) for r in rows]

    def get_user_subscriptions(self, user_id: int) -> list[Subscription]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT id, user_id, tech, salary, location
                   FROM job_subscriptions WHERE user_id = ? AND is_active = 1""",
                (user_id,),
            ).fetchall()
        return [Subscription(id=r[0], user_id=r[1], tech=r[2],
                             salary=r[3], location=r[4]) for r in rows]

    def delete_subscription(self, sub_id: int, user_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM job_subscriptions WHERE id = ? AND user_id = ?",
                (sub_id, user_id),
            )
        return cur.rowcount > 0

    def mark_vacancy_sent(self, user_id: int, vacancy_id: str, sub_id: int) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO sent_vacancies (user_id, vacancy_id, subscription_id)
                       VALUES (?, ?, ?)""",
                    (user_id, vacancy_id, sub_id),
                )
        except sqlite3.IntegrityError:
            pass

    def get_sent_vacancies(self, user_id: int) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT vacancy_id FROM sent_vacancies WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        return [r[0] for r in rows]