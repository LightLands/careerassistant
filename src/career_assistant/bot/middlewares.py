import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

logger = logging.getLogger(__name__)


class ContextMiddleware(BaseMiddleware):
    """Кладёт сервисы в data хендлеров и отмечает пользователя в базе
    (создаёт запись и обновляет last_seen_at)."""

    def __init__(self, services: dict):
        self._services = services

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["services"] = self._services
        user = data.get("event_from_user")
        if user is not None and not user.is_bot:
            try:
                self._services["user_profile"].touch_user(
                    user.id, user.username, user.first_name
                )
            except Exception:
                logger.exception("Не удалось обновить пользователя %s", user.id)
        return await handler(event, data)
