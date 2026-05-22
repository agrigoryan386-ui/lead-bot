import os
import re
import io
import json
import asyncio
import logging
import sqlite3

from datetime import datetime

from flask import Flask

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties

from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove
)

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

import pdfplumber
import google.generativeai as genai


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    "ТВОЙ_ТОКЕН"
)

ADMIN_CHAT_ID = int(
    os.getenv(
        "ADMIN_CHAT_ID",
        "ТВОЙ_ID"
    )
)

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY",
    "ТВОЙ_GEMINI"
)


# =========================================================
# GEMINI
# =========================================================

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("Gemini подключен")
else:
    logger.warning("Gemini API key отсутствует")


# =========================================================
# BOT
# =========================================================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher(
    storage=MemoryStorage()
)


# =========================================================
# FLASK
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Fintech bot is running 🚀", 200


@app.route("/health")
def health():
    return "OK", 200


# =========================================================
# UI
# =========================================================

WELCOME_TEXT = """
<b>INNOVATION & LOGIC</b>

Современные международные платежи для бизнеса.

• SWIFT
• Агентские схемы
• Оплата поставщиков
• ВЭД сопровождение
• Проверка инвойсов

⚡ Быстро
🔒 Надёжно
🌍 Глобально
"""


persistent_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="🏠 Главное меню"
            )
        ]
    ],
    resize_keyboard=True
)


main_menu = InlineKeyboardMarkup(
    inline_keyboard=[

        [
            InlineKeyboardButton(
                text="⚡ Международный перевод",
                callback_data="fast"
            )
        ],

        [
            InlineKeyboardButton(
                text="📄 Проверка инвойса",
                callback_data="check_invoice"
            )
        ],

        [
            InlineKeyboardButton(
                text="💱 Курсы валют",
                callback_data="rates"
            )
        ],

        [
            InlineKeyboardButton(
                text="📰 Новости ВЭД",
                callback_data="news"
            )
        ],

        [
            InlineKeyboardButton(
                text="📩 Оставить заявку",
                callback_data="application"
            )
        ],

        [
            InlineKeyboardButton(
                text="🏢 О компании",
                callback_data="about"
            )
        ]
    ]
)


back_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="back"
            )
        ]
    ]
)


contact_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="📱 Отправить номер",
                request_contact=True
            )
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)
