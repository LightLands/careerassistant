import logging

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from ...config import settings
from ...models import Subscription
from ..flow import ask_location, ask_salary, ask_tech, is_skip, parse_salary
from ..formatting import esc, subscription_card
from ..keyboards import main_keyboard, source_keyboard, unsubscribe_keyboard

logger = logging.getLogger(__name__)
router = Router(name="subscriptions")


class SubscriptionStates(StatesGroup):
    source = State()
    tech = State()
    salary = State()
    location = State()


@router.message(Command("subscribe"))
async def cmd_subscribe(message: types.Message, state: FSMContext, services: dict) -> None:
    await state.clear()
    sources = services["vacancies"].available_sources()
    await message.answer("🔔 <b>Подписка на новые вакансии</b>", parse_mode="HTML")
    if len(sources) == 1:
        await state.update_data(source=sources[0])
        await state.set_state(SubscriptionStates.tech)
        await ask_tech(message)
        return
    await state.set_state(SubscriptionStates.source)
    await message.answer(
        "🌐 <b>Где следим за вакансиями?</b>",
        parse_mode="HTML",
        reply_markup=source_keyboard("bsrc", sources),
    )


@router.callback_query(SubscriptionStates.source, F.data.startswith("bsrc_"))
async def pick_source(callback: types.CallbackQuery, state: FSMContext, services: dict) -> None:
    source = callback.data.removeprefix("bsrc_")
    if source not in services["vacancies"].available_sources():
        await callback.answer("Этот источник недоступен", show_alert=True)
        return
    await state.update_data(source=source)
    await state.set_state(SubscriptionStates.tech)
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await ask_tech(callback.message)


@router.message(SubscriptionStates.tech, F.text, ~F.text.startswith("/"))
async def get_tech(message: types.Message, state: FSMContext) -> None:
    tech = message.text.strip().lower()
    if not tech or len(tech) > 100:
        await message.answer("⚠️ Введи запрос покороче: одно-два слова", reply_markup=main_keyboard())
        return
    await state.update_data(tech=tech)
    await state.set_state(SubscriptionStates.salary)
    await ask_salary(message, (await state.get_data())["source"])


@router.message(SubscriptionStates.salary, F.text, ~F.text.startswith("/"))
async def get_salary(message: types.Message, state: FSMContext) -> None:
    ok, salary = parse_salary(message.text)
    if not ok:
        await message.answer("⚠️ Не понял число. Напиши, например, 150000 или «пропустить»",
                             reply_markup=main_keyboard())
        return
    await state.update_data(salary=salary)
    await state.set_state(SubscriptionStates.location)
    await ask_location(message, (await state.get_data())["source"])


@router.message(SubscriptionStates.location, F.text, ~F.text.startswith("/"))
async def get_location(message: types.Message, state: FSMContext, services: dict) -> None:
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

    await state.clear()
    user_id = message.from_user.id
    created = services["repo"].add_subscription(
        user_id, data["tech"], data.get("salary"), location, source
    )
    if not created:
        await message.answer("⚠️ Такая подписка уже есть.", reply_markup=main_keyboard())
        return

    hour = services["user_profile"].get_settings(user_id, settings.default_notify_hour).notify_hour
    sub = Subscription(0, user_id, data["tech"], data.get("salary"), location, source=source)
    await message.answer(
        "✅ <b>Подписка оформлена!</b>\n\n" + subscription_card(sub)
        + f"\n\n📬 Новые вакансии буду присылать каждый день в <b>{hour:02d}:00</b> "
        f"({esc(settings.timezone)}). Время можно поменять: /set_hour",
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


@router.message(Command("my_subscriptions"))
async def cmd_my_subscriptions(message: types.Message, services: dict) -> None:
    subs = services["repo"].get_user_subscriptions(message.from_user.id)
    if not subs:
        await message.answer("📭 У тебя нет активных подписок.\n\nОформить: /subscribe",
                             reply_markup=main_keyboard())
        return
    await message.answer(f"🔔 <b>Твои подписки ({len(subs)}):</b>", parse_mode="HTML",
                         reply_markup=main_keyboard())
    for sub in subs:
        await message.answer(subscription_card(sub), parse_mode="HTML",
                             reply_markup=unsubscribe_keyboard(sub.id))


@router.callback_query(F.data.startswith("unsub_"))
async def unsubscribe(callback: types.CallbackQuery, services: dict) -> None:
    raw = callback.data.removeprefix("unsub_")
    if not raw.isdigit():
        await callback.answer()
        return
    if services["repo"].delete_subscription(int(raw), callback.from_user.id):
        await callback.answer("✅ Подписка удалена", show_alert=True)
        await callback.message.delete()
    else:
        await callback.answer("❌ Не удалось отписаться (уже удалена?)", show_alert=True)
