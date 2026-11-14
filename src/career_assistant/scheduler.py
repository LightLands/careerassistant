"""Фоновые задачи: уведомления по подпискам, уборка, бэкап базы."""
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError

from .bot.formatting import esc, short_card, SOURCE_LABELS
from .bot.keyboards import save_keyboard
from .config import settings
from .integrations.base import SourceError
from .models import SearchParams

logger = logging.getLogger(__name__)


def build_scheduler(bot: Bot, repo, profiles, vacancies, db):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler  # импорт здесь, чтобы тесты шли без пакета

    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    # Каждый час проверяем, у кого сейчас «его» время уведомлений.
    scheduler.add_job(
        notify_due_subscriptions, trigger="cron", minute=0,
        kwargs={"bot": bot, "repo": repo, "profiles": profiles, "vacancies": vacancies},
        id="notify", max_instances=1, coalesce=True,
    )
    scheduler.add_job(
        maintenance, trigger="cron", hour=3, minute=30,
        kwargs={"repo": repo, "db": db}, id="maintenance",
    )
    return scheduler


async def notify_due_subscriptions(bot, repo, profiles, vacancies, now: datetime | None = None) -> None:
    now = now or datetime.now(ZoneInfo(settings.timezone))
    hour = now.hour

    subs = repo.get_active_subscriptions()
    due = [
        s for s in subs
        if profiles.get_settings(s.user_id, settings.default_notify_hour).notify_hour == hour
    ]
    if not due:
        logger.info("Подписки на %02d:00: нет", hour)
        return
    logger.info("Подписки на %02d:00: %s", hour, len(due))

    cache: dict[tuple, list | None] = {}  # одинаковые запросы разных людей ищем один раз
    blocked: set[int] = set()

    for sub in due:
        if sub.user_id in blocked:
            continue
        key = (sub.source, sub.tech, sub.salary, sub.location)
        if key not in cache:
            try:
                cache[key] = await vacancies.find_and_cache(
                    SearchParams(tech=sub.tech, salary=sub.salary,
                                 location=sub.location, source=sub.source),
                    limit=20,
                )
            except SourceError as e:
                logger.warning("Источник %s недоступен для подписки %s: %s", sub.source, sub.id, e)
                cache[key] = None
            except Exception:
                logger.exception("Поиск по подписке %s упал", sub.id)
                cache[key] = None
        found = cache[key]
        if not found:
            continue

        sent = set(repo.get_sent_vacancies(sub.user_id))
        new = [v for v in found if v.id not in sent]
        if not new:
            continue

        limit = settings.max_vacancies_per_notification
        batch = new[:limit]
        try:
            await bot.send_message(
                sub.user_id,
                f"🔔 <b>Новые вакансии по подписке</b>\n"
                f"🔍 {esc(sub.tech)} · {SOURCE_LABELS.get(sub.source, esc(sub.source))}\n"
                f"Нашёл новых: <b>{len(new)}</b>",
                parse_mode="HTML",
            )
            for v in batch:
                await bot.send_message(
                    sub.user_id, short_card(v), parse_mode="HTML",
                    disable_web_page_preview=True, reply_markup=save_keyboard(v.id),
                )
                repo.mark_vacancy_sent(sub.user_id, v.id, sub.id)
                await asyncio.sleep(0.05)  # лимиты Telegram
            if len(new) > limit:
                await bot.send_message(
                    sub.user_id,
                    f"…и ещё {len(new) - limit}. Остальные придут в следующий раз "
                    "или найдёшь через /search.",
                )
        except TelegramForbiddenError:
            logger.info("Пользователь %s заблокировал бота, удаляю его подписки", sub.user_id)
            repo.delete_user_subscriptions(sub.user_id)
            blocked.add(sub.user_id)
        except Exception:
            logger.exception("Не удалось отправить уведомление пользователю %s", sub.user_id)


async def maintenance(repo, db) -> None:
    """Раз в сутки: чистим кэш вакансий и историю рассылок, делаем бэкап."""
    try:
        t = repo.cleanup_temp_vacancies(settings.temp_vacancy_ttl_days)
        s = repo.cleanup_sent_vacancies(settings.sent_vacancy_ttl_days)
        logger.info("Очистка: временных вакансий %s, записей о рассылке %s", t, s)
        await asyncio.to_thread(db.backup, settings.backup_dir, settings.backup_keep_days)
    except Exception:
        logger.exception("Ошибка обслуживания базы")
