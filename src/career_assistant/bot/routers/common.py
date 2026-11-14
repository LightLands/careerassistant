from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from ..formatting import esc
from ..keyboards import main_keyboard, menu_text

router = Router(name="common")
fallback_router = Router(name="fallback")  # подключается последним


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    name = esc(message.from_user.first_name or "друг")
    await message.answer(
        f"👋 Привет, {name}! Я твой карьерный ассистент.\n\n"
        "Ищу вакансии на hh.ru и других сайтах, веду трекер твоих откликов, "
        "присылаю новые вакансии по подписке и помогаю с сопроводительными письмами.\n\n"
        + menu_text()
        + "\n\n💡 Кнопка «📋 Меню» внизу всегда покажет этот список.",
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


@router.message(Command("help"))
@router.message(F.text == "📋 Меню")
async def show_menu(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(menu_text(), parse_mode="HTML", reply_markup=main_keyboard())


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Окей, отменил. Что дальше? /help", reply_markup=main_keyboard())


@router.callback_query(F.data == "noop")
async def noop(callback: types.CallbackQuery) -> None:
    await callback.answer()


@fallback_router.callback_query(F.data.startswith(("ssrc_", "bsrc_")))
async def stale_choice(callback: types.CallbackQuery) -> None:
    await callback.answer("Этот диалог уже закрыт. Начни заново: /search или /subscribe",
                          show_alert=True)
