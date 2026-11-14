import logging
import time

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from ..formatting import esc
from ..keyboards import main_keyboard

logger = logging.getLogger(__name__)
router = Router(name="cover_letters")

COOLDOWN_SECONDS = 20  # защита платного API от спама
_last_call: dict[int, float] = {}


class CoverLetterStates(StatesGroup):
    vacancy = State()
    profile = State()


@router.message(Command("cover_letter"))
async def start(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(CoverLetterStates.vacancy)
    await message.answer(
        "📝 Скинь <b>описание вакансии</b> (скопируй текст с сайта).\n"
        "Язык письма выберу сам: по языку вакансии.",
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


@router.message(CoverLetterStates.vacancy, F.text, ~F.text.startswith("/"))
async def get_vacancy(message: types.Message, state: FSMContext) -> None:
    await state.update_data(vacancy_text=message.text)
    await state.set_state(CoverLetterStates.profile)
    await message.answer(
        "Принял! Теперь коротко напиши <b>о своём опыте</b>: технологии, годы работы, "
        "самые сильные проекты.",
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


@router.message(CoverLetterStates.profile, F.text, ~F.text.startswith("/"))
async def generate(message: types.Message, state: FSMContext, services: dict) -> None:
    user_id = message.from_user.id
    wait = COOLDOWN_SECONDS - (time.monotonic() - _last_call.get(user_id, -1e9))
    if wait > 0:
        await message.answer(f"⏳ Подожди ещё {int(wait) + 1} сек. и отправь опыт снова.")
        return
    _last_call[user_id] = time.monotonic()

    data = await state.get_data()
    vacancy_text = data.get("vacancy_text", "")
    await state.clear()

    letters = services["cover_letters"]
    await message.answer("⏳ Пишу письмо...", reply_markup=main_keyboard())
    letter = await letters.generate(vacancy_text, message.text)

    try:
        services["repo"].save_cover_letter(user_id, vacancy_text, letter)
    except Exception:
        logger.exception("Не удалось сохранить письмо")

    note = "" if letters.ai_enabled else (
        "\n\nℹ️ ИИ не подключён (нет ключа в .env), поэтому это простой шаблон."
    )
    await message.answer(
        "🎉 <b>Готово! Вот письмо:</b>\n\n" + esc(letter)[:3800] + note,
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )
