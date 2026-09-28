# src/career_assistant/bot/routers/search.py
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from ...models import SearchParams
from ...bot.keyboards import main_keyboard, save_keyboard

router = Router(name="search")


class SearchStates(StatesGroup):
    tech = State()
    salary = State()
    location = State()


@router.message(F.text == "/search")
async def start(message: types.Message, state: FSMContext) -> None:
    await message.answer("🔍 Шаг 1/3: технология?")
    await state.set_state(SearchStates.tech)


@router.message(SearchStates.location, F.text)
async def finish(message: types.Message, state: FSMContext, services: dict) -> None:
    data = await state.get_data()
    params = SearchParams(tech=data["tech"], salary=data.get("salary"),
                          location=data.get("location"))
    vacancies = await services["vacancies"].find_and_cache(params, limit=5)
    ...
    await state.clear()