# src/career_assistant/main.py
import asyncio
import logging
import os
# src/career_assistant/main.py

# ... (существующие импорты)
from .repositories.user_profile import UserProfileRepository  # <-- ДОБАВИТЬ
from .bot.routers import search, applications, subscriptions, cover_letters, profile  # <-- ДОБАВИТЬ profile

# ... (внутри функции main, после создания repo)
user_profile_repo = UserProfileRepository(settings.db_path)  # <-- ДОБАВИТЬ

services = {
    "vacancies": vacancies,
    "analytics": analytics,
    "cover_letters": letters,
    "repo": repo,
    "user_profile": user_profile_repo,  # <-- ДОБАВИТЬ
}

# ... (после dp.include_router)
dp.include_router(profile.router)  # <-- ДОБАВИТЬ

# ... (остальной код без изменений)
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.types import TelegramObject

from .config import settings
from .repositories.sqlite import SQLiteRepository
from .integrations.remoteok import RemoteOKClient
from .services.vacancies import VacancyService
from .services.analytics import AnalyticsService
from .services.cover_letters import CoverLetterService
from .bot.routers import search, applications, subscriptions, cover_letters
from .scheduler import build_scheduler


class ServicesMiddleware(BaseMiddleware):
    """Кладёт словарь сервисов в data для всех хендлеров."""

    def __init__(self, services: dict):
        self._services = services

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["services"] = self._services
        return await handler(event, data)


async def main() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("bot.log", encoding="utf-8"),
        ],
    )

    # --- инфраструктура ---
    db_dir = os.path.dirname(settings.db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    repo = SQLiteRepository(settings.db_path)
    remoteok = RemoteOKClient(user_agent=settings.user_agent)

    # --- сервисы ---
    vacancies = VacancyService(remoteok=remoteok, repo=repo)
    analytics = AnalyticsService(repo=repo)
    letters = CoverLetterService(
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model,
    )

    services = {
        "vacancies": vacancies,
        "analytics": analytics,
        "cover_letters": letters,
        "repo": repo,
    }

    # --- бот ---
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()

    dp.update.middleware(ServicesMiddleware(services))

    dp.include_router(search.router)
    dp.include_router(applications.router)
    dp.include_router(subscriptions.router)
    dp.include_router(cover_letters.router)

    # --- планировщик ---
    scheduler = build_scheduler(bot, repo, vacancies)
    scheduler.start()

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await remoteok.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())