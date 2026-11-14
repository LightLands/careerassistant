import asyncio
import logging
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import BotCommand

from .bot.middlewares import ContextMiddleware
from .bot.routers import applications, common, cover_letters, profile, search, subscriptions
from .config import settings
from .integrations.hh import HHClient
from .integrations.remoteok import RemoteOKClient
from .repositories import Database, SQLiteRepository, UserProfileRepository
from .scheduler import build_scheduler
from .services.analytics import AnalyticsService
from .services.cover_letters import CoverLetterService
from .services.vacancies import VacancyService

logger = logging.getLogger("career_assistant")

COMMANDS = [
    ("search", "Поиск вакансий"),
    ("my_vacancies", "Сохранённые вакансии"),
    ("stats", "Статистика откликов"),
    ("subscribe", "Подписка на новые вакансии"),
    ("my_subscriptions", "Мои подписки"),
    ("cover_letter", "Сопроводительное письмо"),
    ("set_hour", "Время уведомлений"),
    ("profile", "Мой профиль"),
    ("help", "Помощь"),
]


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            RotatingFileHandler("bot.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"),
        ],
    )


def build_sources() -> dict:
    sources: dict = {}
    for name in settings.sources_list:
        if name == "hh":
            sources["hh"] = HHClient(user_agent=settings.hh_user_agent, token=settings.hh_token or None)
        elif name == "remoteok":
            sources["remoteok"] = RemoteOKClient(user_agent=settings.user_agent)
        else:
            logger.warning("Неизвестный источник в ENABLED_SOURCES: %s", name)
    if not sources:
        raise SystemExit("❌ В ENABLED_SOURCES нет ни одного рабочего источника (hh, remoteok).")
    return sources


async def main() -> None:
    setup_logging()

    db = Database(settings.db_path)
    repo = SQLiteRepository(db)
    profiles = UserProfileRepository(db)

    sources = build_sources()
    vacancies = VacancyService(sources=sources, repo=repo)
    services = {
        "vacancies": vacancies,
        "analytics": AnalyticsService(repo=repo),
        "cover_letters": CoverLetterService(
            api_key=settings.openrouter_api_key or None,
            model=settings.openrouter_model,
            base_url=settings.openrouter_base_url,
        ),
        "repo": repo,
        "user_profile": profiles,
    }

    session = AiohttpSession(proxy=settings.proxy_url) if settings.proxy_url else None
    bot = Bot(token=settings.bot_token, session=session)
    dp = Dispatcher()
    dp.update.outer_middleware(ContextMiddleware(services))

    # Порядок важен: сначала общие (меню, отмена), потом диалоги, в конце запасной.
    for r in (
        common.router, search.router, subscriptions.router,
        applications.router, cover_letters.router, profile.router,
        common.fallback_router,
    ):
        dp.include_router(r)

    scheduler = build_scheduler(bot, repo, profiles, vacancies, db)
    scheduler.start()

    try:
        await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in COMMANDS])
    except Exception:
        logger.warning("Не удалось установить список команд бота", exc_info=True)

    logger.info("Бот запущен. Источники: %s", ", ".join(sources))
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        for src in sources.values():
            await src.close()
        await bot.session.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())
