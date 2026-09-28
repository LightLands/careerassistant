# src/career_assistant/scheduler.py
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .repositories.sqlite import SQLiteRepository
from .services.vacancies import VacancyService


def build_scheduler(bot: Bot, repo: SQLiteRepository, vacancies: VacancyService) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        notify_new_vacancies,
        trigger="cron", hour=10, minute=0,
        kwargs={"bot": bot, "repo": repo, "vacancies": vacancies},
    )
    return scheduler


async def notify_new_vacancies(bot, repo, vacancies): ...