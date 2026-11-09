# src/career_assistant/scheduler.py
import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import settings
from .models import SearchParams
from .repositories.sqlite import SQLiteRepository
from .services.vacancies import VacancyService
from .bot.keyboards import save_keyboard

logger = logging.getLogger(__name__)


def build_scheduler(bot: Bot, repo: SQLiteRepository,
                    vacancies: VacancyService) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    scheduler.add_job(
        notify_new_vacancies,
        trigger="cron", hour=10, minute=0,
        kwargs={"bot": bot, "repo": repo, "vacancies": vacancies},
    )
    return scheduler


async def notify_new_vacancies(bot: Bot, repo: SQLiteRepository,
                               vacancies: VacancyService) -> None:
    logger.info("Checking new vacancies for subscriptions...")
    subs = repo.get_active_subscriptions()
    if not subs:
        logger.info("No active subscriptions")
        return

    for sub in subs:
        try:
            found = await vacancies.find_and_cache(
                SearchParams(tech=sub.tech, salary=sub.salary, location=sub.location),
                limit=10,
            )
        except Exception as e:
            logger.exception("Search failed for sub %s: %s", sub.id, e)
            continue

        if not found:
            continue

        sent = set(repo.get_sent_vacancies(sub.user_id))
        new = [v for v in found if v.id not in sent]
        if not new:
            continue

        try:
            await bot.send_message(
                sub.user_id,
                f"🔔 <b>Новые вакансии по подписке!</b>\n\n"
                f"🔍 Технология: <b>{sub.tech}</b>\n"
                f"Найдено <b>{len(new)}</b> новых вакансий:",
                parse_mode="HTML",
            )
            for v in new[:3]:
                await bot.send_message(
                    sub.user_id,
                    f"<b>{v.title}</b>\n🏢 {v.company}\n💰 {v.salary}\n"
                    f"🔗 <a href='{v.url}'>Открыть</a>",
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=save_keyboard(v.id),
                )
                repo.mark_vacancy_sent(sub.user_id, v.id, sub.id)
        except Exception as e:
            logger.exception("Failed to notify user %s: %s", sub.user_id, e)

    logger.info("Subscription check completed")