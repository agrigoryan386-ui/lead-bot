import os
import re
import asyncio
import logging
import sqlite3

from dotenv import load_dotenv

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


# =========================================================
# ENV
# =========================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден")

if not ADMIN_CHAT_ID:
    raise ValueError("❌ ADMIN_CHAT_ID не найден")

ADMIN_CHAT_ID = int(ADMIN_CHAT_ID)


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# =========================================================
# BOT
# =========================================================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher(storage=MemoryStorage())


# =========================================================
# DATABASE
# =========================================================

conn = sqlite3.connect("applications.db")
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

conn.commit()


def save_application(
    telegram_id,
    username,
    phone,
    name,
    email
):

    conn = sqlite3.connect("applications.db")
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


# =========================================================
# REGEX
# =========================================================

PHONE_REGEX = r"^\+?[1-9]\d{7,14}$"
EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


# =========================================================
# FSM
# =========================================================

class ApplicationForm(StatesGroup):

    waiting_for_phone = State()
    waiting_for_name = State()
    waiting_for_email = State()


# =========================================================
# MENU
# =========================================================

main_menu = InlineKeyboardMarkup(
    inline_keyboard=[

        [
            InlineKeyboardButton(
                text="⚡ Быстрые переводы",
                callback_data="fast"
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
# RATES
# =========================================================

RATES = {
    "USD": 92.50,
    "EUR": 100.20,
    "CNY": 12.80,
    "AED": 25.20
}


# =========================================================
# START
# =========================================================

@dp.message(Command("start"))
async def start(message: Message):

    text = (
        "👋 <b>Добро пожаловать</b>\n\n"

        "Международные платежи для бизнеса.\n"
        "Быстро. Надёжно. Без лишней бюрократии."
    )

    await message.answer(
        text,
        reply_markup=main_menu
    )


# =========================================================
# BACK
# =========================================================

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery):

    text = (
        "👋 <b>Добро пожаловать</b>\n\n"

        "Международные платежи для бизнеса.\n"
        "Быстро. Надёжно. Без лишней бюрократии."
    )

    await callback.message.edit_text(
        text,
        reply_markup=main_menu
    )

    await callback.answer()


# =========================================================
# FAST
# =========================================================

@dp.callback_query(F.data == "fast")
async def fast(callback: CallbackQuery):

    text = (
        "⚡ <b>Быстрые переводы</b>\n\n"

        "• Переводы в 50+ стран\n"
        "• Зачисление за 2–3 дня\n"
        "• SWIFT / агентские схемы\n"
        "• Индивидуальные условия\n\n"

        "Для оформления:\n"
        "/order"
    )

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

    text = (
        "💱 <b>Курсы валют</b>\n\n"
    )

    for currency, rate in RATES.items():

        text += f"{currency} → RUB — {rate}\n"

    text += (
        "\nДля расчёта:\n"
        "<code>/calc 1000 USD RUB</code>"
    )

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

    text = (
        "🏢 <b>О компании</b>\n\n"

        "АО «Инновация и логика 2.0»\n\n"

        "Сопровождение международных платежей\n"
        "и внешнеэкономической деятельности.\n\n"

        "📍 Москва\n"
        "⏰ Пн-Пт 10:00–19:00\n\n"

        "📞 +7 (495) 129-90-90\n"
        "📧 info@il-2.ru"
    )

    await callback.message.edit_text(
        text,
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

    text = (
        "📩 <b>Оставить заявку</b>\n\n"

        "Шаг 1 из 3\n\n"

        "Введите номер телефона\n"
        "или нажмите кнопку ниже 👇"
    )

    await callback.message.answer(
        text,
        reply_markup=contact_keyboard
    )

    await callback.answer()


# =========================================================
# PHONE
# =========================================================

@dp.message(ApplicationForm.waiting_for_phone)
async def process_phone(
    message: Message,
    state: FSMContext
):

    if message.contact:

        phone = message.contact.phone_number

    else:

        phone = message.text.strip()

    phone = phone.replace(" ", "")

    if not re.match(PHONE_REGEX, phone):

        await message.answer(
            "❌ Некорректный номер телефона\n\n"
            "Пример:\n"
            "+79991234567"
        )

        return

    await state.update_data(phone=phone)

    await state.set_state(
        ApplicationForm.waiting_for_name
    )

    await message.answer(
        "👤 Шаг 2 из 3\n\n"
        "Введите ваше имя"
    )


# =========================================================
# NAME
# =========================================================

@dp.message(ApplicationForm.waiting_for_name)
async def process_name(
    message: Message,
    state: FSMContext
):

    name = message.text.strip()

    if len(name) < 2:

        await message.answer(
            "❌ Введите корректное имя"
        )

        return

    await state.update_data(name=name)

    await state.set_state(
        ApplicationForm.waiting_for_email
    )

    await message.answer(
        "📧 Шаг 3 из 3\n\n"
        "Введите email\n"
        "или отправьте «нет»"
    )


# =========================================================
# EMAIL
# =========================================================

@dp.message(ApplicationForm.waiting_for_email)
async def process_email(
    message: Message,
    state: FSMContext
):

    email = message.text.strip()

    if email.lower() in [
        "нет",
        "-",
        "skip"
    ]:

        email = "Не указан"

    else:

        if not re.match(EMAIL_REGEX, email):

            await message.answer(
                "❌ Некорректный email"
            )

            return

    await state.update_data(email=email)

    data = await state.get_data()

    phone = data["phone"]
    name = data["name"]

    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "Нет"
    )

    save_application(
        telegram_id=message.from_user.id,
        username=username,
        phone=phone,
        name=name,
        email=email
    )

    admin_text = (
        "🆕 <b>Новая заявка</b>\n\n"

        f"👤 Имя: {name}\n"
        f"📱 Телефон: {phone}\n"
        f"📧 Email: {email}\n"
        f"🆔 ID: {message.from_user.id}\n"
        f"👤 Username: {username}"
    )

    await bot.send_message(
        ADMIN_CHAT_ID,
        admin_text
    )

    await state.clear()

    await message.answer(
        "✅ Заявка отправлена.\n\n"
        "Менеджер свяжется с вами в ближайшее время.",
        reply_markup=ReplyKeyboardRemove()
    )

    await message.answer(
        "Главное меню 👇",
        reply_markup=main_menu
    )


# =========================================================
# CALC
# =========================================================

@dp.message(Command("calc"))
async def calc(message: Message):

    parts = message.text.split()

    if len(parts) != 4:

        await message.answer(
            "Формат:\n"
            "<code>/calc 1000 USD RUB</code>"
        )

        return

    try:

        amount = float(parts[1])

        from_currency = parts[2].upper()
        to_currency = parts[3].upper()

        if from_currency not in RATES:

            await message.answer(
                "❌ Валюта не поддерживается"
            )

            return

        if to_currency != "RUB":

            await message.answer(
                "❌ Пока доступен только RUB"
            )

            return

        result = amount * RATES[from_currency]

        await message.answer(
            f"💵 <b>Результат</b>\n\n"
            f"{amount:,.2f} {from_currency}\n"
            f"≈ {result:,.2f} RUB"
        )

    except Exception as e:

        logger.error(e)

        await message.answer(
            "❌ Ошибка расчёта"
        )


# =========================================================
# ORDER
# =========================================================

@dp.message(Command("order"))
async def order(message: Message):

    text = (
        "📝 <b>Оформление перевода</b>\n\n"

        "Отправьте:\n\n"

        "• сумму\n"
        "• валюту\n"
        "• страну\n\n"

        "Менеджер ответит в течение 15 минут."
    )

    await message.answer(text)


# =========================================================
# UNKNOWN
# =========================================================

@dp.message()
async def unknown(message: Message):

    await message.answer(
        "Используйте меню ниже 👇",
        reply_markup=main_menu
    )


# =========================================================
# MAIN
# =========================================================

async def main():

    logger.info("🚀 Бот запущен")

    await bot.send_message(
        ADMIN_CHAT_ID,
        "✅ Бот успешно запущен"
    )

    await dp.start_polling(bot)


# =========================================================
# START APP
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        print("❌ Бот остановлен")
