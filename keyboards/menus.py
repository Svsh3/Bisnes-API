from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from services.ai import AVAILABLE_MODELS


def main_menu(bot_active: bool, status_active: bool) -> InlineKeyboardMarkup:
    toggle_label = "🔴 Выключить бота" if bot_active else "🟢 Включить бота"
    status_label = "📍 Изменить статус" if status_active else "📍 Установить статус"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_label, callback_data="toggle_bot")],
        [InlineKeyboardButton(text=status_label, callback_data="set_status")],
        [InlineKeyboardButton(text="🤖 Сменить модель", callback_data="choose_model")],
        [InlineKeyboardButton(text="✏️ Промт бота", callback_data="set_prompt")],
        [InlineKeyboardButton(text="🏷 Имя бота", callback_data="set_name")],
        [InlineKeyboardButton(text="🗑 Очистить историю", callback_data="clear_history_menu")],
        [InlineKeyboardButton(text="📊 Текущие настройки", callback_data="show_settings")],
    ])


def model_menu(current_model: str) -> InlineKeyboardMarkup:
    rows = []
    for model_id, label in AVAILABLE_MODELS:
        check = "✅ " if model_id == current_model else ""
        rows.append([
            InlineKeyboardButton(
                text=f"{check}{label}",
                callback_data=f"model:{model_id}"
            )
        ])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_clear(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, очистить", callback_data=f"clear_confirm:{chat_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="back_main"),
        ]
    ])


def back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])
