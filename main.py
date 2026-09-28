# src/career_assistant/main.py
import asyncio
import logging
from aiogram import Bot, Dispatcher

from .config import settings
from .repositories.sqlite import SQLiteRepository
from .integrations.remoteok import RemoteOKClient
from .services.vacancies import VacancyService
from .services.analytics import AnalyticsService
from .services.cover_letters import CoverLetterService
from .bot.routers import search, applications, subscriptions, cover_letters
from .scheduler import build_scheduler


async def main() -> None:
    logging.basicConfig(level=settings.log_level)

    # --- инфраструктура ---
    repo = SQLiteRepository(settings.db_path)
    remoteok = RemoteOKClient(user_agent=settings.user_agent)

    # --- сервисы ---
    vacancies = VacancyService(remoteok=remoteok, repo=repo)
    analytics = AnalyticsService(repo=repo)
    letters = CoverLetterService(api_key=settings.openrouter_api_key,
                                 model=settings.openrouter_model)

    # --- бот ---
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()

    # инъекция зависимостей через workflow_data
    dp["services"] = {
        "vacancies": vacancies,
        "analytics": analytics,
        "cover_letters": letters,
    }

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