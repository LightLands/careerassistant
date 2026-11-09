"""Репозиторий профиля пользователя и ссылок."""
import logging
from datetime import datetime
from typing import Optional

from ..models import UserLink, UserProfile, UserSettings
from .db import Database

logger = logging.getLogger(__name__)


class UserProfileRepository:
    def __init__(self, db: Database):
        self._db = db

    # ---------- users ----------
    def touch_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
    ) -> UserProfile:
        """Создаёт юзера если нет, обновляет username/first_name/last_seen_at."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._db.conn() as conn:
            conn.execute(
                """INSERT INTO users
                   (user_id, username, first_name, created_at, last_seen_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                       username = COALESCE(excluded.username, users.username),
                       first_name = COALESCE(excluded.first_name, users.first_name),
                       last_seen_at = excluded.last_seen_at""",
                (user_id, username, first_name, now, now),
            )
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        return self._row_to_profile(row)

    def get_profile(self, user_id: int) -> Optional[UserProfile]:
        with self._db.conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        return self._row_to_profile(row) if row else None

    def update_company(self, user_id: int, company: str) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._db.conn() as conn:
            conn.execute(
                "UPDATE users SET company = ?, last_seen_at = ? "
                "WHERE user_id = ?",
                (company, now, user_id),
            )

    # ---------- links ----------
    def add_link(self, user_id: int, url: str) -> int:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._db.conn() as conn:
            cur = conn.execute(
                "INSERT INTO links (user_id, url, added_at) VALUES (?, ?, ?)",
                (user_id, url, now),
            )
            conn.execute(
                "UPDATE users SET last_seen_at = ? WHERE user_id = ?",
                (now, user_id),
            )
            return cur.lastrowid

    def get_links(self, user_id: int) -> list[UserLink]:
        with self._db.conn() as conn:
            rows = conn.execute(
                """SELECT id, user_id, url, added_at
                   FROM links WHERE user_id = ?
                   ORDER BY added_at DESC""",
                (user_id,),
            ).fetchall()
        return [
            UserLink(
                id=r["id"],
                user_id=r["user_id"],
                url=r["url"],
                added_at=r["added_at"],
            )
            for r in rows
        ]

    def delete_link(self, user_id: int, link_id: int) -> bool:
        with self._db.conn() as conn:
            cur = conn.execute(
                "DELETE FROM links WHERE id = ? AND user_id = ?",
                (link_id, user_id),
            )
            return cur.rowcount > 0

    # ---------- settings ----------
    def get_settings(self, user_id: int, default_hour: int = 10) -> UserSettings:
        with self._db.conn() as conn:
            row = conn.execute(
                "SELECT * FROM user_settings WHERE user_id = ?", (user_id,)
            ).fetchone()
        if not row:
            return UserSettings(user_id=user_id, notify_hour=default_hour)
        return UserSettings(
            user_id=row["user_id"],
            notify_hour=row["notify_hour"],
            language=row["language"],
        )

    def set_notify_hour(self, user_id: int, hour: int) -> None:
        hour = max(0, min(23, hour))
        with self._db.conn() as conn:
            conn.execute(
                """INSERT INTO user_settings (user_id, notify_hour)
                   VALUES (?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET notify_hour = excluded.notify_hour""",
                (user_id, hour),
            )

    # ---------- helpers ----------
    @staticmethod
    def _row_to_profile(row) -> UserProfile:
        return UserProfile(
            user_id=row["user_id"],
            username=row["username"],
            first_name=row["first_name"],
            company=row["company"],
            created_at=row["created_at"],
            last_seen_at=row["last_seen_at"],
        )