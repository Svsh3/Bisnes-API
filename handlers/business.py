import asyncio
import logging
from datetime import datetime

from aiogram import Router, Bot
from aiogram.types import Message, BusinessConnection

from config import Config
from database import Database
from services.ai import ask_ai, build_system_prompt

router = Router()
db = Database()
log = logging.getLogger(__name__)

_answered_cache: dict[int, float] = {}
_COOLDOWN = 1


async def is_owner_offline() -> bool:
    last_seen = await db.get_owner_last_seen()
    diff = (datetime.now() - last_seen).total_seconds()
    log.info("⏱ Офлайн проверка: last_seen=%s, diff=%.1f сек, порог=%s",
             last_seen, diff, Config.OFFLINE_THRESHOLD)
    return diff > Config.OFFLINE_THRESHOLD


async def should_respond(chat_id: int) -> bool:
    last = _answered_cache.get(chat_id, 0)
    diff = datetime.now().timestamp() - last
    log.info("⏳ Cooldown проверка chat_id=%s: %.1f сек прошло (cooldown=%s)", chat_id, diff, _COOLDOWN)
    return diff > _COOLDOWN


# ── Общая логика ответа на сообщение ──────────────────────────────────────────

async def _handle_message(message: Message, bot: Bot):
    log.info(
        "📨 Сообщение: from_id=%s | chat_id=%s | business_id=%s | text=%r",
        message.from_user.id if message.from_user else "None",
        message.chat.id,
        message.business_connection_id,
        (message.text or "")[:50],
    )

    # Сообщение от владельца — обновляем last_seen и выходим
    if message.from_user and message.from_user.id == Config.OWNER_ID:
        await db.update_owner_seen()
        log.info("✅ Владелец активен — last_seen обновлён")
        return

    # Не business и не private — игнорируем
    if not message.business_connection_id and message.chat.type != "private":
        log.info("⛔ Не business и не private — пропускаем")
        return

    # Проверяем активность бота
    bot_active = await db.get_setting("bot_active")
    log.info("🔘 bot_active=%s", bot_active)
    if bot_active != "1":
        log.info("⛔ Бот выключен")
        return

    # Проверяем офлайн
    offline = await is_owner_offline()
    if not offline:
        log.info("⛔ Владелец онлайн — не отвечаем")
        return

    # Cooldown
    chat_id = message.chat.id
    if not await should_respond(chat_id):
        log.info("⛔ Cooldown ещё не прошёл")
        return

    text = message.text or message.caption or ""
    if not text:
        log.info("⛔ Пустое сообщение")
        return

    log.info("🤖 Запускаем AI ответ для chat_id=%s", chat_id)

    sender_name = message.from_user.first_name if message.from_user else "Собеседник"
    await db.add_message(chat_id, "user", f"{sender_name}: {text}")

    history = await db.get_history(chat_id, limit=20)
    settings = await db.get_all_settings()
    status_msg, status_active = await db.get_status()
    model = settings.get("model", "meta-llama/llama-3.1-8b-instruct:free")
    system = build_system_prompt(settings)

    log.info("📡 Используем модель: %s", model)

    try:
        action_kwargs = {"chat_id": chat_id, "action": "typing"}
        if message.business_connection_id:
            action_kwargs["business_connection_id"] = message.business_connection_id
        await bot.send_chat_action(**action_kwargs)
        await asyncio.sleep(1.2)

        reply = await ask_ai(
            messages=history,
            system_prompt=system,
            model=model,
            status_message=status_msg,
            status_active=status_active,
            user_message=text,
        )
        log.info("✅ AI ответил: %r", reply[:80])
    except Exception as e:
        log.error("❌ Ошибка AI: %s", e)
        reply = f"Хозяин недоступен, попробуй позже."

    send_kwargs = {"chat_id": chat_id, "text": reply}
    if message.business_connection_id:
        send_kwargs["business_connection_id"] = message.business_connection_id
    await bot.send_message(**send_kwargs)

    await db.add_message(chat_id, "assistant", reply)
    _answered_cache[chat_id] = datetime.now().timestamp()
    log.info("📤 Ответ отправлен в chat_id=%s", chat_id)


# ── Обычные сообщения (в ЛС боту) ─────────────────────────────────────────────

@router.message()
async def on_regular_message(message: Message, bot: Bot):
    await _handle_message(message, bot)


# ── Business-сообщения (когда пишут владельцу в личку) ────────────────────────

@router.business_message()
async def on_business_message(message: Message, bot: Bot):
    await _handle_message(message, bot)


# ── Подключение/отключение Business ────────────────────────────────────────────

@router.business_connection()
async def on_business_connection(connection: BusinessConnection, bot: Bot):
    if connection.user.id == Config.OWNER_ID:
        log.info("🔗 Business-подключение: id=%s, can_reply=%s",
                 connection.id, connection.can_reply)
        if not connection.can_reply:
            log.warning("⚠️ Бот не может отвечать — нет прав can_reply")
