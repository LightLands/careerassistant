"""Репозиторий для вакансий, подписок, статистики."""
import json
import logging
import sqlite3
from typing import Optional

from ..models import SearchParams, Stats, Subscription, Vacancy
from .db import Database

logger = logging.getLogger(__name__)

STATUS_FLOW = ["saved", "applied", "interview", "offer"]


class SQLiteRepository:
    def __init__(self, db: Database):
        self._db = db

    # ---------- temp vacancies ----------
    def save_temp_vacancies(self, vacancies: list[Vacancy]) -> None:
        if not vacancies:
            return
        with self._db.conn() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO temp_vacancies
                   (vacancy_id, title, company, salary, location, url, description,
                    tags, date, salary_min, salary_max)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        v.id,
                        v.title,
                        v.company,
                        v.salary,
                        v.location,
                        v.url,
                        v.description,
                        json.dumps(v.tags, ensure_ascii=False),
                        v.date,
                        v.salary_min,
                        v.salary_max,
                    )
                    for v in vacancies
                ],
            )

    def save_temp_vacancy(self, v: Vacancy) -> None:
        self.save_temp_vacancies([v])

    def get_temp_vacancy(self, vacancy_id: str) -> Optional[Vacancy]:
        with self._db.conn() as conn:
            row = conn.execute(
                """SELECT vacancy_id, title, company, salary, location, url,
                          description, tags, date, salary_min, salary_max
                   FROM temp_vacancies WHERE vacancy_id = ?""",
                (vacancy_id,),
            ).fetchone()
        if not row:
            return None
        try:
            tags = json.loads(row["tags"]) if row["tags"] else []
        except json.JSONDecodeError:
            tags = []
        return Vacancy(
            id=row["vacancy_id"],
            title=row["title"],
            company=row["company"],
            salary=row["salary"],
            location=row["location"],
            url=row["url"],
            description=row["description"],
            tags=tags,
            date=row["date"],
            salary_min=row["salary_min"],
            salary_max=row["salary_max"],
        )

    def cleanup_temp_vacancies(self, days: int) -> int:
        with self._db.conn() as conn:
            cur = conn.execute(
                "DELETE FROM temp_vacancies "
                "WHERE created_at < datetime('now', ?)",
                (f"-{days} days",),
            )
            return cur.rowcount

    # ---------- saved vacancies ----------
    def save_vacancy(self, user_id: int, v: Vacancy) -> bool:
        try:
            with self._db.conn() as conn:
                conn.execute(
                    """INSERT INTO saved_vacancies
                       (user_id, vacancy_id, title, company, salary,
                        location, url, description)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        user_id,
                        v.id,
                        v.title,
                        v.company,
                        v.salary,
                        v.location,
                        v.url,
                        v.description,
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def get_user_vacancies(
        self, user_id: int, limit: int = 10, offset: int = 0
    ) -> list[sqlite3.Row]:
        with self._db.conn() as conn:
            return conn.execute(
                """SELECT id, title, company, salary, location, url,
                          saved_at, status
                   FROM saved_vacancies WHERE user_id = ?
                   ORDER BY saved_at DESC
                   LIMIT ? OFFSET ?""",
                (user_id, limit, offset),
            ).fetchall()

    def count_user_vacancies(self, user_id: int) -> int:
        with self._db.conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM saved_vacancies WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]

    def get_user_vacancy_by_id(
        self, user_id: int, db_id: int
    ) -> Optional[sqlite3.Row]:
        with self._db.conn() as conn:
            return conn.execute(
                """SELECT id, title, company, salary, location, url,
                          saved_at, status
                   FROM saved_vacancies WHERE id = ? AND user_id = ?""",
                (db_id, user_id),
            ).fetchone()

    def delete_vacancy(self, user_id: int, db_id: int) -> bool:
        with self._db.conn() as conn:
            cur = conn.execute(
                "DELETE FROM saved_vacancies WHERE id = ? AND user_id = ?",
                (db_id, user_id),
            )
            return cur.rowcount > 0

    def update_vacancy_status(
        self, user_id: int, db_id: int, new_status: str
    ) -> bool:
        with self._db.conn() as conn:
            row = conn.execute(
                "SELECT status FROM saved_vacancies WHERE id = ? AND user_id = ?",
                (db_id, user_id),
            ).fetchone()
            if not row:
                return False
            current = row["status"]

            # rejected разрешён с любого этапа
            if new_status == "rejected" and current != "rejected":
                conn.execute(
                    "UPDATE saved_vacancies SET status = ? "
                    "WHERE id = ? AND user_id = ?",
                    (new_status, db_id, user_id),
                )
                return True

            # возврат из rejected в saved
            if new_status == "saved" and current == "rejected":
                conn.execute(
                    "UPDATE saved_vacancies SET status = ? "
                    "WHERE id = ? AND user_id = ?",
                    (new_status, db_id, user_id),
                )
                return True

            if new_status not in STATUS_FLOW or current not in STATUS_FLOW:
                return False
            if STATUS_FLOW.index(new_status) <= STATUS_FLOW.index(current):
                return False

            conn.execute(
                "UPDATE saved_vacancies SET status = ? "
                "WHERE id = ? AND user_id = ?",
                (new_status, db_id, user_id),
            )
            return True

    # ---------- stats ----------
    def get_stats(self, user_id: int) -> Stats:
        stats = Stats()
        with self._db.conn() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS c FROM saved_vacancies "
                "WHERE user_id = ? GROUP BY status",
                (user_id,),
            ).fetchall()
        for row in rows:
            if hasattr(stats, row["status"]):
                setattr(stats, row["status"], row["c"])
        return stats

    # ---------- subscriptions ----------
    def add_subscription(
        self,
        user_id: int,
        tech: str,
        salary: Optional[int],
        location: Optional[str],
    ) -> bool:
        try:
            with self._db.conn() as conn:
                conn.execute(
                    """INSERT INTO job_subscriptions
                       (user_id, tech, salary, location)
                       VALUES (?, ?, ?, ?)""",
                    (user_id, tech, salary, location),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def get_active_subscriptions(self) -> list[Subscription]:
        with self._db.conn() as conn:
            rows = conn.execute(
                """SELECT id, user_id, tech, salary, location
                   FROM job_subscriptions WHERE is_active = 1"""
            ).fetchall()
        return [self._sub_from_row(r) for r in rows]

    def get_user_subscriptions(self, user_id: int) -> list[Subscription]:
        with self._db.conn() as conn:
            rows = conn.execute(
                """SELECT id, user_id, tech, salary, location
                   FROM job_subscriptions
                   WHERE user_id = ? AND is_active = 1""",
                (user_id,),
            ).fetchall()
        return [self._sub_from_row(r) for r in rows]

    def delete_subscription(self, sub_id: int, user_id: int) -> bool:
        with self._db.conn() as conn:
            cur = conn.execute(
                "DELETE FROM job_subscriptions WHERE id = ? AND user_id = ?",
                (sub_id, user_id),
            )
            return cur.rowcount > 0

    # ---------- sent ----------
    def mark_vacancy_sent(
        self, user_id: int, vacancy_id: str, sub_id: int
    ) -> None:
        try:
            with self._db.conn() as conn:
                conn.execute(
                    """INSERT INTO sent_vacancies
                       (user_id, vacancy_id, subscription_id)
                       VALUES (?, ?, ?)""",
                    (user_id, vacancy_id, sub_id),
                )
        except sqlite3.IntegrityError:
            pass

    def get_sent_vacancies(self, user_id: int) -> list[str]:
        with self._db.conn() as conn:
            rows = conn.execute(
                "SELECT vacancy_id FROM sent_vacancies WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        return [r["vacancy_id"] for r in rows]

    def cleanup_sent_vacancies(self, days: int) -> int:
        with self._db.conn() as conn:
            cur = conn.execute(
                "DELETE FROM sent_vacancies "
                "WHERE sent_at < datetime('now', ?)",
                (f"-{days} days",),
            )
            return cur.rowcount

    # ---------- search history ----------
    def add_search_history(self, user_id: int, p: SearchParams) -> None:
        with self._db.conn() as conn:
            conn.execute(
                """INSERT INTO search_history
                   (user_id, tech, salary, location)
                   VALUES (?, ?, ?, ?)""",
                (user_id, p.tech, p.salary, p.location),
            )

    def get_recent_searches(
        self, user_id: int, limit: int = 5
    ) -> list[sqlite3.Row]:
        with self._db.conn() as conn:
            return conn.execute(
                """SELECT tech, salary, location, created_at
                   FROM search_history
                   WHERE user_id = ?
                   ORDER BY id DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()

    # ---------- helpers ----------
    @staticmethod
    def _sub_from_row(row: sqlite3.Row) -> Subscription:
        return Subscription(
            id=row["id"],
            user_id=row["user_id"],
            tech=row["tech"],
            salary=row["salary"],
            location=row["location"],
        )