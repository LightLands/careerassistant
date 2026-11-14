"""Трекер откликов: сохранённые вакансии, статусы, статистика."""
import logging
from math import ceil

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command

from ...config import settings
from ..formatting import saved_card, stats_text
from ..keyboards import main_keyboard, pagination_keyboard, status_keyboard

logger = logging.getLogger(__name__)
router = Router(name="applications")

STATUS_ANSWERS = {
    "saved": "↩️ Вернул в работу",
    "applied": "📤 Отклик отмечен",
    "interview": "✅ Интервью — отлично!",
    "offer": "🏆 Поздравляю с оффером!",
    "rejected": "❌ Отмечено как отказ",
}


@router.callback_query(F.data.startswith("save_"))
async def save_vacancy(callback: types.CallbackQuery, services: dict) -> None:
    vacancy_id = callback.data.removeprefix("save_")
    result = services["vacancies"].save_for_user(callback.from_user.id, vacancy_id)
    texts = {
        "saved": "✅ Вакансия сохранена в трекер!",
        "exists": "⚠️ Эта вакансия уже в трекере",
        "expired": "⌛ Карточка устарела — найди вакансию заново через /search",
    }
    await callback.answer(texts[result], show_alert=True)


async def _send_page(message: types.Message, user_id: int, page: int, services: dict) -> None:
    vac = services["vacancies"]
    total = vac.count_for_user(user_id)
    if total == 0:
        await message.answer("📭 В трекере пока пусто.\n\nНайти вакансии: /search",
                             reply_markup=main_keyboard())
        return

    size = settings.vacancies_page_size
    pages = max(1, ceil(total / size))
    page = min(max(page, 0), pages - 1)
    rows = vac.list_for_user(user_id, limit=size, offset=page * size)

    await message.answer(f"📋 <b>Сохранённые вакансии ({total})</b>", parse_mode="HTML",
                         reply_markup=main_keyboard())
    for row in rows:
        await message.answer(
            saved_card(row),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=status_keyboard(row["id"], row["status"]),
        )
    kb = pagination_keyboard(page, total, size)
    if kb:
        await message.answer("Другие страницы:", reply_markup=kb)


@router.message(Command("my_vacancies"))
async def cmd_my_vacancies(message: types.Message, services: dict) -> None:
    await _send_page(message, message.from_user.id, 0, services)


@router.callback_query(F.data.startswith("vpage_"))
async def change_page(callback: types.CallbackQuery, services: dict) -> None:
    raw = callback.data.removeprefix("vpage_")
    if not raw.lstrip("-").isdigit():
        await callback.answer()
        return
    await callback.answer()
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    await _send_page(callback.message, callback.from_user.id, int(raw), services)


@router.message(Command("stats"))
async def cmd_stats(message: types.Message, services: dict) -> None:
    stats = services["analytics"].get_stats(message.from_user.id)
    if stats.total == 0:
        await message.answer("📊 Статистики пока нет. Начни с /search и сохрани пару вакансий!",
                             reply_markup=main_keyboard())
        return
    await message.answer(stats_text(stats), parse_mode="HTML", reply_markup=main_keyboard())


@router.callback_query(F.data.startswith("status_"))
async def change_status(callback: types.CallbackQuery, services: dict) -> None:
    parts = callback.data.split("_", 2)
    if len(parts) != 3 or not parts[1].isdigit():
        await callback.answer()
        return
    db_id, new_status = int(parts[1]), parts[2]
    user_id = callback.from_user.id
    vac = services["vacancies"]

    if not vac.change_status(user_id, db_id, new_status):
        await callback.answer(
            "❌ Статус можно только двигать вперёд: отклик → интервью → оффер (или «отказ»).",
            show_alert=True,
        )
        return

    await callback.answer(STATUS_ANSWERS.get(new_status, "Готово"))
    row = vac.get_by_id(user_id, db_id)
    if row:
        try:
            await callback.message.edit_text(
                saved_card(row),
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=status_keyboard(row["id"], row["status"]),
            )
        except TelegramBadRequest:
            pass  # «message is not modified» и подобное — не критично


@router.callback_query(F.data.startswith("delete_"))
async def delete_vacancy(callback: types.CallbackQuery, services: dict) -> None:
    raw = callback.data.removeprefix("delete_")
    if not raw.isdigit():
        await callback.answer()
        return
    if services["vacancies"].remove(callback.from_user.id, int(raw)):
        await callback.answer("🗑 Вакансия удалена")
        await callback.message.delete()
    else:
        await callback.answer("❌ Не удалось удалить", show_alert=True)
