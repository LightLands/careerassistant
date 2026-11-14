import logging

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from ...config import settings
from ...integrations.base import SourceError
from ...models import SearchParams
from ..flow import ask_location, ask_salary, ask_tech, is_skip, parse_salary
from ..formatting import params_summary, vacancy_card
from ..keyboards import main_keyboard, save_keyboard, source_keyboard

logger = logging.getLogger(__name__)
router = Router(name="search")


class SearchStates(StatesGroup):
    source = State()
    tech = State()
    salary = State()
    location = State()


@router.message(Command("search"))
async def cmd_search(message: types.Message, state: FSMContext, services: dict) -> None:
    await state.clear()
    sources = services["vacancies"].available_sources()
    if len(sources) == 1:
        await state.update_data(source=sources[0])
        await state.set_state(SearchStates.tech)
        await ask_tech(message)
        return
    await state.set_state(SearchStates.source)
    await message.answer(
        "🌐 <b>Где ищем?</b>",
        parse_mode="HTML",
        reply_markup=source_keyboard("ssrc", sources),
    )


@router.callback_query(SearchStates.source, F.data.startswith("ssrc_"))
async def pick_source(callback: types.CallbackQuery, state: FSMContext, services: dict) -> None:
    source = callback.data.removeprefix("ssrc_")
    if source not in services["vacancies"].available_sources():
        await callback.answer("Этот источник недоступен", show_alert=True)
        return
    await state.update_data(source=source)
    await state.set_state(SearchStates.tech)
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await ask_tech(callback.message)


@router.message(SearchStates.tech, F.text, ~F.text.startswith("/"))
async def get_tech(message: types.Message, state: FSMContext) -> None:
    tech = message.text.strip().lower()
    if not tech or len(tech) > 100:
        await message.answer("⚠️ Введи запрос покороче: одно-два слова", reply_markup=main_keyboard())
        return
    await state.update_data(tech=tech)
    await state.set_state(SearchStates.salary)
    source = (await state.get_data())["source"]
    await ask_salary(message, source)


@router.message(SearchStates.salary, F.text, ~F.text.startswith("/"))
async def get_salary(message: types.Message, state: FSMContext) -> None:
    ok, salary = parse_salary(message.text)
    if not ok:
        await message.answer("⚠️ Не понял число. Напиши, например, 150000 или «пропустить»",
                             reply_markup=main_keyboard())
        return
    await state.update_data(salary=salary)
    await state.set_state(SearchStates.location)
    source = (await state.get_data())["source"]
    await ask_location(message, source)


@router.message(SearchStates.location, F.text, ~F.text.startswith("/"))
async def get_location_and_search(
    message: types.Message, state: FSMContext, services: dict
) -> None:
    data = await state.get_data()
    source = data["source"]
    text = message.text.strip()

    location = None
    if not is_skip(text) and text.lower() != "worldwide":
        location = await services["vacancies"].validate_location(source, text)
        if location is None:
            await message.answer(
                "🤔 Не нашёл такой город. Проверь написание или напиши «пропустить».",
                reply_markup=main_keyboard(),
            )
            return

    params = SearchParams(
        tech=data["tech"], salary=data.get("salary"), location=location, source=source
    )
    await state.clear()
    await message.answer(
        "🔎 <b>Ищу по параметрам:</b>\n" + params_summary(params) + "\n\n⏳ Ищу вакансии...",
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )

    try:
        vacancies = await services["vacancies"].find_and_cache(params, limit=settings.search_limit)
    except SourceError as e:
        logger.warning("Поиск не удался: %s", e)
        await message.answer("⚠️ Сайт сейчас не отвечает. Попробуй через несколько минут.",
                             reply_markup=main_keyboard())
        return

    services["repo"].add_search_history(message.from_user.id, params)

    if not vacancies:
        await message.answer("😕 Ничего не нашёл. Попробуй убрать фильтры или изменить запрос.",
                             reply_markup=main_keyboard())
        return

    await message.answer(f"✅ Нашёл вакансий: <b>{len(vacancies)}</b>", parse_mode="HTML")
    for i, v in enumerate(vacancies, 1):
        await message.answer(
            vacancy_card(v, i),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=save_keyboard(v.id),
        )
