import re

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from ...models import SearchParams
from ...bot.keyboards import main_keyboard, menu_text, save_keyboard

router = Router(name="search")


class SearchStates(StatesGroup):
    tech = State()
    salary = State()
    location = State()


@router.message(Command("search"))
async def start(message: types.Message, state: FSMContext) -> None:
    await message.answer(
        "🔍 <b>Шаг 1/3: технология</b>\n\n"
        "Какую технологию ищешь? (например: <b>python</b>, <b>react</b>)",
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )
    await state.set_state(SearchStates.tech)


@router.message(SearchStates.tech, F.text == "📋 Меню")
@router.message(SearchStates.salary, F.text == "📋 Меню")
@router.message(SearchStates.location, F.text == "📋 Меню")
async def menu_in_fsm(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        menu_text(), parse_mode="HTML", reply_markup=main_keyboard()
    )


@router.message(SearchStates.tech, F.text)
async def get_tech(message: types.Message, state: FSMContext) -> None:
    tech = message.text.strip().lower()
    if not tech:
        await message.answer(
            "⚠️ Введи хотя бы одно слово", reply_markup=main_keyboard()
        )
        return
    await state.update_data(tech=tech)
    await message.answer(
        "💰 <b>Шаг 2/3: минимальная зарплата</b>\n\n"
        "Сколько хочешь в год (USD)? Например: <b>80000</b>\n"
        "Если не важно — напиши '<b>пропустить</b>'",
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )
    await state.set_state(SearchStates.salary)


@router.message(SearchStates.salary, F.text)
async def get_salary(message: types.Message, state: FSMContext) -> None:
    txt = message.text.strip().lower()
    if txt in ("пропустить", "skip", "не важно", "-"):
        salary = None
    else:
        digits = re.sub(r"\D", "", txt)
        if not digits:
            await message.answer(
                "⚠️ Не понял число. Введи число или 'пропустить'",
                reply_m