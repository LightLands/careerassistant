import re

from aiogram import Router, types
from aiogram.filters import Command, CommandObject

from ...config import settings
from ..formatting import esc
from ..keyboards import main_keyboard

router = Router(name="profile")

_URL_RE = re.compile(r"^https?://\S+$", re.I)


@router.message(Command("set_company"))
async def cmd_set_company(message: types.Message, command: CommandObject, services: dict) -> None:
    company = (command.args or "").strip()
    if not company:
        await message.answer("⚠️ Укажи название компании:\n/set_company Яндекс")
        return
    services["user_profile"].update_company(message.from_user.id, company[:100])
    await message.answer(f"✅ Компания: {esc(company[:100])}", parse_mode="HTML")


@router.message(Command("add_link"))
async def cmd_add_link(message: types.Message, command: CommandObject, services: dict) -> None:
    url = (command.args or "").strip()
    if not _URL_RE.match(url) or len(url) > 500:
        await message.answer("⚠️ Укажи ссылку целиком:\n/add_link https://example.com")
        return
    services["user_profile"].add_link(message.from_user.id, url)
    await message.answer("✅ Ссылка сохранена. Список: /profile")


@router.message(Command("del_link"))
async def cmd_del_link(message: types.Message, command: CommandObject, services: dict) -> None:
    raw = (command.args or "").strip().lstrip("#")
    if not raw.isdigit():
        await message.answer("⚠️ Укажи номер ссылки из /profile:\n/del_link 3")
        return
    ok = services["user_profile"].delete_link(message.from_user.id, int(raw))
    await message.answer("🗑 Ссылка удалена" if ok else "❌ Нет такой ссылки")


@router.message(Command("set_hour"))
async def cmd_set_hour(message: types.Message, command: CommandObject, services: dict) -> None:
    raw = (command.args or "").strip()
    if not raw.isdigit() or not 0 <= int(raw) <= 23:
        current = services["user_profile"].get_settings(
            message.from_user.id, settings.default_notify_hour
        ).notify_hour
        await message.answer(
            f"⏰ Сейчас уведомления приходят в {current:02d}:00 ({esc(settings.timezone)}).\n"
            "Чтобы поменять: /set_hour 9  (число от 0 до 23)",
            parse_mode="HTML",
        )
        return
    services["user_profile"].set_notify_hour(message.from_user.id, int(raw))
    await message.answer(
        f"✅ Теперь подписки приходят в {int(raw):02d}:00 ({esc(settings.timezone)})",
        parse_mode="HTML",
    )


@router.message(Command("profile"))
async def cmd_profile(message: types.Message, services: dict) -> None:
    repo = services["user_profile"]
    uid = message.from_user.id
    profile = repo.get_profile(uid)
    links = repo.get_links(uid)
    hour = repo.get_settings(uid, settings.default_notify_hour).notify_hour

    name = f"@{profile.username}" if profile and profile.username else (
        profile.first_name if profile and profile.first_name else str(uid)
    )
    lines = [
        "👤 <b>Твой профиль</b>\n",
        f"Имя: {esc(name)}",
        f"Компания: {esc(profile.company) if profile and profile.company else 'не указана'}",
        f"Уведомления: {hour:02d}:00 ({esc(settings.timezone)})\n",
    ]
    if links:
        lines.append(f"📎 <b>Ссылки ({len(links)}):</b>")
        for link in links:
            lines.append(f"#{link.id}: {esc(link.url)}")
        lines.append("\nУдалить: /del_link номер")
    else:
        lines.append("📎 Ссылок пока нет. Добавить: /add_link https://...")
    await message.answer(
        "\n".join(lines), parse_mode="HTML", disable_web_page_preview=True,
        reply_markup=main_keyboard(),
    )
