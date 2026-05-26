from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import Config
from database import Database
from keyboards.menus import main_menu, model_menu, confirm_clear, back_button
from services.ai import AVAILABLE_MODELS

router = Router()
db = Database()


class SettingsFSM(StatesGroup):
    waiting_status = State()
    waiting_prompt = State()
    waiting_name = State()


def is_owner(user_id: int) -> bool:
    return user_id == Config.OWNER_ID


# ── /start ────────────────────────────────────────────────────────────────────

@router.message(F.chat.type == "private", F.text == "/start")
async def cmd_start(message: Message):
    if message.from_user.id != Config.OWNER_ID:
        return
    settings = await db.get_all_settings()
    bot_active = settings.get("bot_active", "1") == "1"
    _, status_active = await db.get_status()
    await message.answer(
        "👋 <b>Панель управления автоответчиком</b>\n\n"
        f"Бот: {'🟢 активен' if bot_active else '🔴 выключен'}\n"
        f"Статус: {'📍 установлен' if status_active else '—'}",
        reply_markup=main_menu(bot_active, status_active),
        parse_mode="HTML",
    )


# ── Обновление last_seen + FSM при любом сообщении от владельца ──────────────

@router.message(F.from_user.id == Config.OWNER_ID, F.text != "/start")
async def owner_activity(message: Message, state: FSMContext):
    await db.update_owner_seen()

    current_state = await state.get_state()

    if current_state == SettingsFSM.waiting_status:
        await handle_status_input(message, state)
    elif current_state == SettingsFSM.waiting_prompt:
        await handle_prompt_input(message, state)
    elif current_state == SettingsFSM.waiting_name:
        await handle_name_input(message, state)


# ── Callbacks ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "toggle_bot")
async def cb_toggle(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        return
    current = await db.get_setting("bot_active")
    new_val = "0" if current == "1" else "1"
    await db.set_setting("bot_active", new_val)
    _, status_active = await db.get_status()
    await call.message.edit_text(
        f"Бот {'🟢 включён' if new_val == '1' else '🔴 выключен'}.",
        reply_markup=main_menu(new_val == "1", status_active),
    )
    await call.answer()


@router.callback_query(F.data == "set_status")
async def cb_set_status(call: CallbackQuery, state: FSMContext):
    if not is_owner(call.from_user.id):
        return
    msg, active = await db.get_status()
    current_text = f"Текущий: <i>{msg}</i>" if active else "Статус не установлен."
    await call.message.edit_text(
        f"📍 <b>Статус владельца</b>\n{current_text}\n\n"
        "Напиши новый статус (например: <i>ушёл по делам, вернусь вечером</i>).\n"
        "Или напиши <b>0</b> чтобы сбросить статус.",
        reply_markup=back_button(),
        parse_mode="HTML",
    )
    await state.set_state(SettingsFSM.waiting_status)
    await call.answer()


async def handle_status_input(message: Message, state: FSMContext):
    text = message.text.strip()
    if text == "0":
        await db.set_status("", False)
        await message.answer("✅ Статус сброшен.")
    else:
        await db.set_status(text, True)
        await message.answer(f"✅ Статус установлен:\n<i>{text}</i>", parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data == "choose_model")
async def cb_choose_model(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        return
    current = await db.get_setting("model")
    await call.message.edit_text(
        "🤖 <b>Выбери модель</b>:",
        reply_markup=model_menu(current),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("model:"))
async def cb_model_selected(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        return
    model_id = call.data.split("model:")[1]
    label = next((lbl for mid, lbl in AVAILABLE_MODELS if mid == model_id), model_id)
    await db.set_setting("model", model_id)
    current = await db.get_setting("model")
    await call.message.edit_text(
        f"✅ Модель изменена на <b>{label}</b>",
        reply_markup=model_menu(current),
        parse_mode="HTML",
    )
    await call.answer(f"✅ {label}")


@router.callback_query(F.data == "set_prompt")
async def cb_set_prompt(call: CallbackQuery, state: FSMContext):
    if not is_owner(call.from_user.id):
        return
    current = await db.get_setting("bot_prompt")
    text = f"Текущий:\n<i>{current}</i>\n\n" if current else "Промт не задан.\n\n"
    await call.message.edit_text(
        f"✏️ <b>Системный промт</b>\n{text}"
        "Напиши новый промт (дополнит базовый).\nИли <b>0</b> — сбросить.",
        reply_markup=back_button(),
        parse_mode="HTML",
    )
    await state.set_state(SettingsFSM.waiting_prompt)
    await call.answer()


async def handle_prompt_input(message: Message, state: FSMContext):
    text = message.text.strip()
    await db.set_setting("bot_prompt", "" if text == "0" else text)
    await message.answer("✅ Промт обновлён.")
    await state.clear()


@router.callback_query(F.data == "set_name")
async def cb_set_name(call: CallbackQuery, state: FSMContext):
    if not is_owner(call.from_user.id):
        return
    current = await db.get_setting("bot_name")
    await call.message.edit_text(
        f"🏷 <b>Имя бота</b>\nТекущее: <i>{current}</i>\n\nНапиши новое имя:",
        reply_markup=back_button(),
        parse_mode="HTML",
    )
    await state.set_state(SettingsFSM.waiting_name)
    await call.answer()


async def handle_name_input(message: Message, state: FSMContext):
    name = message.text.strip()
    await db.set_setting("bot_name", name)
    await message.answer(f"✅ Имя изменено на <b>{name}</b>", parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data == "clear_history_menu")
async def cb_clear_menu(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        return
    await call.message.edit_text(
        "🗑 Очистить историю ВСЕХ чатов?",
        reply_markup=confirm_clear(0),
    )
    await call.answer()


@router.callback_query(F.data.startswith("clear_confirm:"))
async def cb_clear_confirm(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        return
    await db.clear_history(0)
    _, status_active = await db.get_status()
    active = await db.get_setting("bot_active") == "1"
    await call.message.edit_text(
        "✅ История очищена.",
        reply_markup=main_menu(active, status_active),
    )
    await call.answer()


@router.callback_query(F.data == "show_settings")
async def cb_show_settings(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        return
    s = await db.get_all_settings()
    msg, st_active = await db.get_status()
    text = (
        f"📊 <b>Настройки</b>\n\n"
        f"• Бот: {'🟢 активен' if s.get('bot_active') == '1' else '🔴 выключен'}\n"
        f"• Модель: <code>{s.get('model', '—')}</code>\n"
        f"• Имя: <b>{s.get('bot_name', '—')}</b>\n"
        f"• Статус: {'📍 ' + msg if st_active else '—'}\n"
        f"• Промт: {'задан ✅' if s.get('bot_prompt') else 'не задан'}"
    )
    await call.message.edit_text(text, reply_markup=back_button(), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "back_main")
async def cb_back(call: CallbackQuery, state: FSMContext):
    if not is_owner(call.from_user.id):
        return
    await state.clear()
    settings = await db.get_all_settings()
    bot_active = settings.get("bot_active", "1") == "1"
    _, status_active = await db.get_status()
    await call.message.edit_text(
        "👋 <b>Панель управления</b>",
        reply_markup=main_menu(bot_active, status_active),
        parse_mode="HTML",
    )
    await call.answer()
