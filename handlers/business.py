import asyncio
from datetime import datetime, timezone

from aiogram import Router, F, Bot
from aiogram.types import Message

from config import Config
from database import Database
from services.ai import ask_ai, build_system_prompt

router = Router()
db = Database()

# Кэш "уже ответили в этот раз офлайна" чтобы не спамить
_answered_cache: dict[int, float] = {}
_COOLDOWN = 60  # секунд между авто-ответами одному юзеру


def _is_offline() -> bool:
    """Проверяем через asyncio — вызывается из sync-контекста"""
    return True  # Заглушка, реальная логика — async ниже


async def is_owner_offline() -> bool:
    last_seen = await db.get_owner_last_seen()
    now = datetime.now()
    diff = (now - last_seen).total_seconds()
    return diff > Config.OFFLINE_THRESHOLD


async def should_respond(chat_id: int) -> bool:
    last = _answered_cache.get(chat_id, 0)
    now = datetime.now().timestamp()
    return (now - last) > _COOLDOWN


# ── Business incoming message ─────────────────────────────────────────────────

@router.message(F.business_connection_id.is_not(None))
async def handle_business_message(message: Message, bot: Bot):
    # Игнорируем собственные сообщения владельца
    if message.from_user and message.from_user.id == Config.OWNER_ID:
        await db.update_owner_seen()
        return

    # Проверяем активность бота
    bot_active = await db.get_setting("bot_active")
    if bot_active != "1":
        return

    # Проверяем офлайн
    offline = await is_owner_offline()
    if not offline:
        return

    # Cooldown
    chat_id = message.chat.id
    if not await should_respond(chat_id):
        return

    text = message.text or message.caption or ""
    if not text:
        return

    # Сохраняем входящее в историю
    sender_name = message.from_user.first_name if message.from_user else "Собеседник"
    await db.add_message(chat_id, "user", f"{sender_name}: {text}")

    # Подгружаем историю и настройки
    history = await db.get_history(chat_id, limit=20)
    settings = await db.get_all_settings()
    status_msg, status_active = await db.get_status()
    model = settings.get("model", "openai/gpt-4o-mini")
    system = build_system_prompt(settings)

    try:
        await bot.send_chat_action(
            chat_id=chat_id,
            action="typing",
            business_connection_id=message.business_connection_id,
        )
        await asyncio.sleep(1.2)

        reply = await ask_ai(
            messages=history,
            system_prompt=system,
            model=model,
            status_message=status_msg,
            status_active=status_active,
            user_message=text,
        )
    except Exception as e:
        reply = f"Хозяин недоступен, попробуй позже. (ошибка: {e})"

    # Отправляем через Business API
    await bot.send_message(
        chat_id=chat_id,
        text=reply,
        business_connection_id=message.business_connection_id,
    )

    # Сохраняем ответ в историю
    await db.add_message(chat_id, "assistant", reply)
    _answered_cache[chat_id] = datetime.now().timestamp()
