from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton, ReplyKeyboardMarkup)

STATUS_NAMES = {
    "applied": "📤 Отклик",
    "interview": "✅ Интервью",
    "offer": "🏆 Оффер",
    "rejected": "❌ Отказ",
}


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📋 Меню")]],
        resize_keyboard=True,
    )


def save_keyboard(vacancy_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💾 Сохранить в трекер",
                             callback_data=f"save_{vacancy_id}")
    ]])


def status_keyboard(db_id: int, current: str) -> InlineKeyboardMarkup:
    flow = ["saved", "applied", "interview", "offer", "rejected"]
    rows = []
    if current in flow:
        idx = flow.index(current)
        row = []
        for st in flow[idx + 1:]:
            row.append(InlineKeyboardButton(
                text=STATUS_NAMES[st],
                callback_data=f"status_{db_id}_{st}",
            ))
        if row:
            rows.append(row)
    rows.append([InlineKeyboardButton(
        text="🗑 Удалить", callback_data=f"delete_{db_id}"
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def unsubscribe_keyboard(sub_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🗑 Отписаться",
                             callback_data=f"unsub_{sub_id}")
    ]])


def menu_text() -> str:
    return (
        "📌 <b>Команды:</b>\n\n"
        "/search — поиск вакансий\n"
        "/my_vacancies — сохранённые\n"
        "/stats — статистика\n"
        "/subscribe — подписка\n"
        "/my_subscriptions — мои подписки\n"
        "/cover_letter — сопроводительное письмо\n"
        "/help — помощь"
    )