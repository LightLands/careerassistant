from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

STATUS_NAMES = {
    "saved": "📥 Сохранена",
    "applied": "📤 Отклик",
    "interview": "✅ Интервью",
    "offer": "🏆 Оффер",
    "rejected": "❌ Отказ",
}

FLOW = ["saved", "applied", "interview", "offer"]


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📋 Меню")]],
        resize_keyboard=True,
    )


def save_keyboard(vacancy_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💾 Сохранить в трекер",
                    callback_data=f"save_{vacancy_id}",
                )
            ]
        ]
    )


def status_keyboard(db_id: int, current: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    if current in FLOW:
        idx = FLOW.index(current)
        row = [
            InlineKeyboardButton(
                text=STATUS_NAMES[st],
                callback_data=f"status_{db_id}_{st}",
            )
            for st in FLOW[idx + 1:]
        ]
        if row:
            rows.append(row)

    if current != "rejected":
        rows.append(
            [
                InlineKeyboardButton(
                    text=STATUS_NAMES["rejected"],
                    callback_data=f"status_{db_id}_rejected",
                )
            ]
        )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    text="↩️ Вернуть в работу",
                    callback_data=f"status_{db_id}_saved",
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="🗑 Удалить", callback_data=f"delete_{db_id}"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pagination_keyboard(
    page: int, total: int, page_size: int
) -> InlineKeyboardMarkup | None:
    pages = max(1, (total + page_size - 1) // page_size)
    if pages <= 1:
        return None
    buttons: list[InlineKeyboardButton] = []
    if page > 0:
        buttons.append(
            InlineKeyboardButton(text="◀ Назад", callback_data=f"vpage_{page - 1}")
        )
    buttons.append(
        InlineKeyboardButton(
            text=f"{page + 1}/{pages}", callback_data="noop"
        )
    )
    if page + 1 < pages:
        buttons.append(
            InlineKeyboardButton(
                text="Вперёд ▶", callback_data=f"vpage_{page + 1}"
            )
        )
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def unsubscribe_keyboard(sub_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 Отписаться", callback_data=f"unsub_{sub_id}"
                )
            ]
        ]
    )


def menu_text() -> str:
    return (
        "📌 <b>Команды:</b>\n\n"
        "/search — поиск вакансий\n"
        "/my_vacancies — сохранённые\n"
        "/stats — статистика\n"
        "/subscribe — подписка\n"
        "/my_subscriptions — мои подписки\n"
        "/cover_letter — сопроводительное письмо\n"
        "/set_company — установить компанию\n"
        "/add_link — добавить ссылку\n"
        "/profile — мой профиль\n"
        "/help — помощь"
    )