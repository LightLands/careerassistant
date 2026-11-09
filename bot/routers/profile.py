# src/career_assistant/bot/routers/profile.py
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, CommandObject
from ..repositories.user_profile import UserProfileRepository

router = Router()

def get_username(message: Message) -> str:
    user = message.from_user
    return f"@{user.username}" if user.username else user.first_name

@router.message(Command("start"))
async def cmd_start(message: Message, data: dict):
    repo: UserProfileRepository = data["services"]["user_profile"]
    username = get_username(message)
    
    profile = repo.get_or_create_user(username.lstrip('@'))
    
    await message.answer(
        f"👋 Привет, {username}!\n\n"
        f"Вы успешно зарегистрированы в системе.\n\n"
        f"📋 Доступные команды:\n"
        f"/set_company <название> — установить компанию\n"
        f"/add_link <url> — сохранить полезную ссылку\n"
        f"/profile — информация о вас и ваши ссылки"
    )

@router.message(Command("set_company"))
async def cmd_set_company(message: Message, command: CommandObject, data: dict):
    repo: UserProfileRepository = data["services"]["user_profile"]
    username = get_username(message).lstrip('@')
    
    if not command.args:
        await message.answer("⚠️ Укажите название компании:\n/set_company <название>")
        return
    
    repo.update_company(username, command.args)
    await message.answer(f"✅ Компания установлена: {command.args}")

@router.message(Command("add_link"))
async def cmd_add_link(message: Message, command: CommandObject, data: dict):
    repo: UserProfileRepository = data["services"]["user_profile"]
    username = get_username(message).lstrip('@')
    
    if not command.args:
        await message.answer("⚠️ Укажите ссылку:\n/add_link <url>")
        return
    
    repo.add_link(username, command.args)
    await message.answer(f"✅ Ссылка сохранена:\n{command.args}")

@router.message(Command("profile"))
async def cmd_profile(message: Message, data: dict):
    repo: UserProfileRepository = data["services"]["user_profile"]
    username = get_username(message).lstrip('@')
    
    profile = repo.get_or_create_user(username)
    links = repo.get_links(username)
    
    response = f"👤 **Информация о вас:**\n\n"
    response += f"Username: {username}\n"
    response += f"Компания: {profile.company or 'не указана'}\n"
    response += f"Последняя операция: {profile.last_operation_time}\n\n"
    
    if links:
        response += f"📎 **Сохранённые ссылки ({len(links)}):**\n"
        for i, link in enumerate(links, 1):
            response += f"{i}. {link.url}\n   🕒 {link.added_time}\n"
    else:
        response += "📎 У вас пока нет сохранённых ссылок.\nИспользуйте /add_link <url>"
    
    await message.answer(response, parse_mode="Markdown")