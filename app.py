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
    ReplyKeyboardMarkup
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
    "ТВОЙ_BOT_TOKEN"
)

ADMIN_CHAT_ID = int(
    os.getenv(
        "ADMIN_CHAT_ID",
        "ТВОЙ_ADMIN_ID"
    )
)

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY",
    "ТВОЙ_GEMINI_API_KEY"
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

━━━━━━━━━━━━━━━

🌍 SWIFT переводы

📄 Проверка инвойсов

💱 Международные расчёты

🏦 Агентские схемы

⚡ Быстро

🔒 Надёжно

━━━━━━━━━━━━━━━

Выберите действие ниже 👇
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


# =========================================================
# DATABASE
# =========================================================

DB_FILE = "applications.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            username TEXT,
            phone TEXT,
            name TEXT,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoice_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            username TEXT,
            amount REAL,
            currency TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


init_db()


# =========================================================
# FSM
# =========================================================

class InvoiceForm(StatesGroup):
    waiting_for_file = State()


class ApplicationForm(StatesGroup):
    waiting_for_phone = State()
    waiting_for_name = State()
    waiting_for_email = State()


# =========================================================
# RATES
# =========================================================

RATES = {
    "USD": 92.50,
    "EUR": 100.20,
    "CNY": 12.80,
    "AED": 25.20
}


# =========================================================
# SAVE FUNCTIONS
# =========================================================

def save_application(
    telegram_id,
    username,
    phone,
    name,
    email
):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO applications (
            telegram_id,
            username,
            phone,
            name,
            email
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        telegram_id,
        username,
        phone,
        name,
        email
    ))

    conn.commit()
    conn.close()


def save_invoice_check(
    telegram_id,
    username,
    amount,
    currency
):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO invoice_checks (
            telegram_id,
            username,
            amount,
            currency
        )
        VALUES (?, ?, ?, ?)
    """, (
        telegram_id,
        username,
        amount,
        currency
    ))

    conn.commit()
    conn.close()


# =========================================================
# PDF ANALYSIS
# =========================================================

async def analyze_invoice(file_bytes, filename):

    try:

        if not filename.lower().endswith(".pdf"):
            return None

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:

            full_text = ""

            for page in pdf.pages:

                text = page.extract_text()

                if text:
                    full_text += text + "\n"

        amount_match = re.search(
            r'([\d,]+\.?\d*)\s*(USD|EUR|CNY|AED|RUB)',
            full_text
        )

        if amount_match:

            amount = float(
                amount_match.group(1).replace(",", "")
            )

            currency = amount_match.group(2)

            return {
                "amount": amount,
                "currency": currency
            }

        return None

    except Exception as e:

        logger.error(f"PDF ERROR: {e}")

        return None


# =========================================================
# NEWS
# =========================================================

async def get_ved_news():

    if not GEMINI_API_KEY:
        return "❌ Gemini API key отсутствует"

    try:

        model = genai.GenerativeModel(
            "gemini-1.5-flash"
        )

        response = model.generate_content(
            """
            Дай 5 коротких актуальных новостей
            по теме:
            - ВЭД
            - SWIFT
            - международные платежи
            - санкции
            - трансграничные расчёты

            Формат:
            • Заголовок
            Краткое описание
            """
        )

        return f"""
📰 <b>Новости ВЭД</b>

━━━━━━━━━━━━━━━

{response.text}
"""

    except Exception as e:

        logger.error(f"NEWS ERROR: {e}")

        return "❌ Ошибка загрузки новостей"


# =========================================================
# START
# =========================================================

@dp.message(Command("start"))
async def start(message: Message):

    loading = await message.answer(
        "⚡ Инициализация платформы..."
    )

    await asyncio.sleep(0.7)

    await loading.edit_text(
        "🔐 Проверка защищённого соединения..."
    )

    await asyncio.sleep(0.7)

    await loading.edit_text(
        "🌍 Подключение международных шлюзов..."
    )

    await asyncio.sleep(1)

    await loading.edit_text(
        WELCOME_TEXT,
        reply_markup=main_menu
    )

    await message.answer(
        "Система готова к работе.",
        reply_markup=persistent_menu
    )


# =========================================================
# MAIN MENU BUTTON
# =========================================================

@dp.message(F.text == "🏠 Главное меню")
async def main_menu_handler(
    message: Message,
    state: FSMContext
):

    await state.clear()

    await message.answer(
        WELCOME_TEXT,
        reply_markup=main_menu
    )


# =========================================================
# FAST PAYMENTS
# =========================================================

@dp.callback_query(F.data == "fast")
async def fast(callback: CallbackQuery):

    text = """
⚡ <b>Международные переводы</b>

━━━━━━━━━━━━━━━

🌍 50+ стран

🏦 SWIFT / агентские схемы

⚡ Срок: 1–3 дня

💰 От 5 000 USD

🔒 Полное сопровождение

━━━━━━━━━━━━━━━

Для оформления заявки:
@your_manager
"""

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard
    )

    await callback.answer()


# =========================================================
# RATES
# =========================================================

@dp.callback_query(F.data == "rates")
async def rates(callback: CallbackQuery):

    text = f"""
💱 <b>Курсы валют</b>

━━━━━━━━━━━━━━━

🇺🇸 USD — {RATES['USD']} ₽

🇪🇺 EUR — {RATES['EUR']} ₽

🇨🇳 CNY — {RATES['CNY']} ₽

🇦🇪 AED — {RATES['AED']} ₽

━━━━━━━━━━━━━━━

💡 Индивидуальный курс
для крупных объёмов
"""

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard
    )

    await callback.answer()


# =========================================================
# ABOUT
# =========================================================

@dp.callback_query(F.data == "about")
async def about(callback: CallbackQuery):

    text = """
🏢 <b>INNOVATION & LOGIC</b>

━━━━━━━━━━━━━━━

Финтех-решения
для международного бизнеса.

• ВЭД сопровождение

• Международные переводы

• Проверка контрагентов

• Оплата поставщиков

━━━━━━━━━━━━━━━

📍 Москва

🕒 Пн-Пт 10:00–19:00

📧 info@company.ru
"""

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard
    )

    await callback.answer()


# =========================================================
# NEWS
# =========================================================

@dp.callback_query(F.data == "news")
async def news(callback: CallbackQuery):

    await callback.message.edit_text(
        "📰 Загружаем новости...",
        reply_markup=back_keyboard
    )

    news_text = await get_ved_news()

    await callback.message.edit_text(
        news_text,
        reply_markup=back_keyboard
    )

    await callback.answer()


# =========================================================
# APPLICATION
# =========================================================

@dp.callback_query(F.data == "application")
async def application(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.set_state(
        ApplicationForm.waiting_for_phone
    )

    await callback.message.answer(
        """
📩 <b>Заявка</b>

Шаг 1 из 3

Введите номер телефона
или отправьте контакт 👇
""",
        reply_markup=contact_keyboard
    )

    await callback.answer()


@dp.message(ApplicationForm.waiting_for_phone)
async def process_phone(
    message: Message,
    state: FSMContext
):

    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text.strip()

    await state.update_data(phone=phone)

    await state.set_state(
        ApplicationForm.waiting_for_name
    )

    await message.answer(
        "Введите ваше имя:"
    )


@dp.message(ApplicationForm.waiting_for_name)
async def process_name(
    message: Message,
    state: FSMContext
):

    await state.update_data(
        name=message.text.strip()
    )

    await state.set_state(
        ApplicationForm.waiting_for_email
    )

    await message.answer(
        "Введите email:"
    )


@dp.message(ApplicationForm.waiting_for_email)
async def process_email(
    message: Message,
    state: FSMContext
):

    data = await state.get_data()

    phone = data["phone"]
    name = data["name"]

    email = message.text.strip()

    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "Нет"
    )

    save_application(
        message.from_user.id,
        username,
        phone,
        name,
        email
    )

    admin_text = f"""
🆕 НОВАЯ ЗАЯВКА

👤 Имя: {name}

📱 Телефон: {phone}

📧 Email: {email}

🆔 User ID: {message.from_user.id}

🌐 Username: {username}
"""

    await bot.send_message(
        ADMIN_CHAT_ID,
        admin_text
    )

    await state.clear()

    await message.answer(
        """
✅ <b>Заявка отправлена</b>

Менеджер свяжется
с вами в ближайшее время.
""",
        reply_markup=persistent_menu
    )

    await message.answer(
        WELCOME_TEXT,
        reply_markup=main_menu
    )


# =========================================================
# INVOICE CHECK
# =========================================================

@dp.callback_query(F.data == "check_invoice")
async def check_invoice(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.set_state(
        InvoiceForm.waiting_for_file
    )

    await callback.message.edit_text(
        """
📄 <b>Проверка инвойса</b>

Отправьте PDF-файл.

Система автоматически
проанализирует документ.
""",
        reply_markup=back_keyboard
    )

    await callback.answer()


@dp.message(
    InvoiceForm.waiting_for_file,
    F.document
)
async def process_invoice(
    message: Message,
    state: FSMContext
):

    loading = await message.answer(
        "🔍 Анализ документа..."
    )

    file = await bot.get_file(
        message.document.file_id
    )

    file_bytes = await bot.download_file(
        file.file_path
    )

    result = await analyze_invoice(
        file_bytes.read(),
        message.document.file_name
    )

    if result:

        username = (
            f"@{message.from_user.username}"
            if message.from_user.username
            else "Нет"
        )

        save_invoice_check(
            message.from_user.id,
            username,
            result["amount"],
            result["currency"]
        )

        await loading.edit_text(
            f"""
✅ <b>Инвойс обработан</b>

💰 Сумма:
{result['amount']:,.2f} {result['currency']}

Менеджер получил данные.
"""
        )

    else:

        await loading.edit_text(
            """
⚠️ Не удалось
распознать документ.

Менеджер проверит его вручную.
"""
        )

    await state.clear()


# =========================================================
# BACK
# =========================================================

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery):

    await callback.message.edit_text(
        WELCOME_TEXT,
        reply_markup=main_menu
    )

    await callback.answer()


# =========================================================
# UNKNOWN
# =========================================================

@dp.message()
async def unknown(message: Message):

    await message.answer(
        "Используйте меню ниже 👇",
        reply_markup=persistent_menu
    )

    await message.answer(
        WELCOME_TEXT,
        reply_markup=main_menu
    )


# =========================================================
# RUN
# =========================================================

async def start_bot():

    logger.info("BOT STARTED")

    await dp.start_polling(
        bot,
        handle_signals=False
    )


def run_flask():

    port = int(
        os.environ.get("PORT", 8080)
    )

    app.run(
        host="0.0.0.0",
        port=port
    )


if __name__ == "__main__":

    import threading

    threading.Thread(
        target=run_flask,
        daemon=True
    ).start()

    asyncio.run(start_bot())
