"""Inline keyboard builders for the Telegram bot."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from telegram_bot.config import LANGUAGES


def language_keyboard() -> InlineKeyboardMarkup:
    """Language selection keyboard — 2 buttons per row."""
    builder = InlineKeyboardBuilder()
    for label, code in LANGUAGES.items():
        builder.button(text=label, callback_data=f"lang:{code}")
    builder.adjust(2)
    return builder.as_markup()


def confirm_keyboard(ticker: str, language: str) -> InlineKeyboardMarkup:
    """Confirm / Cancel keyboard shown before launching analysis."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Запустить анализ", callback_data="confirm:yes"),
            InlineKeyboardButton(text="❌ Отмена",           callback_data="confirm:no"),
        ]
    ])


def cancel_keyboard() -> InlineKeyboardMarkup:
    """Single cancel button shown while analysis runs."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Отменить", callback_data="cancel_analysis")]
    ])
