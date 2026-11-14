"""Общие шаги диалогов поиска и подписки."""
import re
from typing import Optional

from aiogram import types

from .formatting import SKIP_WORDS
from .keyboards import main_keyboard

_SALARY_RE = re.compile(
    r"^\s*(\d+(?:[ \u00a0]\d{3})*)(?:[.,](\d+))?\s*(к|k|тыс\.?|тысяч)?"
    r"\s*(?:₽|руб\.?|р\.?|\$|usd)?\s*$",
    re.I,
)


def is_skip(text: str) -> bool:
    return text.strip().lower() in SKIP_WORDS


def parse_salary(text: str) -> tuple[bool, Optional[int]]:
    """(понял ли, число). «пропустить» → (True, None). «150к» → 150000."""
    if is_skip(text):
        return True, None
    m = _SALARY_RE.match(text)
    if not m:
        return False, None
    whole = int(re.sub(r"\D", "", m.group(1)))
    frac_digits, suffix = m.group(2), m.group(3)
    if frac_digits and len(frac_digits) == 3 and not suffix:
        # «80,000» или «80.000» — это разделитель тысяч, а не дробь
        value = whole * 1000 + int(frac_digits)
    else:
        value = whole + (float("0." + frac_digits) if frac_digits else 0)
        if suffix:
            value *= 1000
    value = int(value)
    if value <= 0:
        return False, None
    return True, value


async def ask_tech(message: types.Message, title: str = "") -> None:
    await message.answer(
        f"{title}🔍 <b>Что ищем?</b>\n\n"
        "Профессия или технология, например: <b>python</b>, <b>аналитик данных</b>, <b>react</b>",
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


async def ask_salary(message: types.Message, source: str) -> None:
    if source == "hh":
        hint = "Сколько хочешь получать <b>в месяц, в рублях</b>? Например: <b>150000</b> или <b>150к</b>"
    else:
        hint = "Сколько хочешь получать <b>в год, в долларах</b>? Например: <b>80000</b>"
    await message.answer(
        f"💰 <b>Минимальная зарплата</b>\n\n{hint}\n\nЕсли не важно — напиши «<b>пропустить</b>»",
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


async def ask_location(message: types.Message, source: str) -> None:
    if source == "hh":
        hint = "Город (например <b>Москва</b>, <b>Казань</b>) или <b>удалёнка</b>. По умолчанию — вся Россия."
    else:
        hint = "Регион: <b>europe</b>, <b>usa</b> и т.п. По умолчанию — весь мир."
    await message.answer(
        f"🌍 <b>Регион</b>\n\n{hint}\n\nЕсли не важно — напиши «<b>пропустить</b>»",
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )
