import os
import re
import logging
import asyncio
import aiosqlite

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton
)

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage


# =========================================
# ЗАГРУЗКА ENV
# =========================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден")

if not ADMIN_CHAT_ID:
    raise ValueError("❌ ADMIN_CHAT_ID не найден")


# =========================================
# ЛОГИ
# =========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# =========================================
# BOT
# =========================================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# =========================================
# DATABASE
# =========================================

DB_NAME = "applications.db"


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
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
        await db.commit()

    logger.info("✅ База данных подключена")


async def save_application(
    telegram_id,
    username,
    phone,
    name,
    email
):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
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

        await db.commit()


# =========================================
# REGEX
# =========================================

PHONE_REGEX = r"^\+?[1-9]\d{7,14}$"
EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


# =========================================
# FSM
# =========================================

class ApplicationForm(StatesGroup):
    waiting_for_phone = State()
    waiting_for_name = State()
    waiting_for_email = State()


# =========================================
# KEYBOARDS
# =========================================

menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Быстрые переводы")],
        [KeyboardButton(text="💰 Лучшие курсы")],
        [KeyboardButton(text="📞 Оставить заявку")],
        [KeyboardButton(text="ℹ️ О компании")]
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите пункт меню 👇"
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
    resize_keyboard=True
)


# =========================================
# START
# =========================================

@dp.message(Command("start"))
async def start_command(message: Message):

    await message.answer(
        "🌍 <b>Международные платежи без границ</b>\n\n"
        "Выберите интересующий вас пункт меню 👇",
        reply_markup=menu_keyboard
    )


# =========================================
# БЫСТРЫЕ ПЕРЕВОДЫ
# =========================================

@dp.message(F.text == "🚀 Быстрые переводы")
async def fast_transfers(message: Message):

    await message.answer(
        "🚀 <b>БЫСТРЫЕ ПЕРЕВОДЫ</b>\n\n"
        "▫️ Зачисление 2-3 дня\n"
        "▫️ 50+ стран\n"
        "▫️ Без скрытых комиссий\n"
        "▫️ Индивидуальные условия от 50 000 USD\n\n"
        "📝 Для оформления отправьте /order"
    )


# =========================================
# КУРСЫ
# =========================================

RATES = {
    "USD": 92.50,
    "EUR": 100.20,
    "CNY": 12.80,
    "AED": 25.20
}


@dp.message(F.text == "💰 Лучшие курсы")
async def rates(message: Message):

    text = (
        "💰 <b>АКТУАЛЬНЫЕ КУРСЫ</b>\n\n"
    )

    for currency, rate in RATES.items():
        text += f"▫️ {currency} → RUB = {rate}\n"

    text += (
        "\n📊 Для расчёта:\n"
        "<code>/calc 1000 USD RUB</code>"
    )

    await message.answer(text)


# =========================================
# CALC
# =========================================

@dp.message(Command("calc"))
async def calc(message: Message):

    parts = message.text.split()

    if len(parts) != 4:
        await message.answer(
            "❌ Формат:\n"
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
            f"💵 <b>Результат:</b>\n\n"
            f"{amount:,.2f} {from_currency}\n"
            f"≈ {result:,.2f} RUB"
        )

    except Exception as e:

        logger.error(e)

        await message.answer(
            "❌ Ошибка расчёта"
        )


# =========================================
# ЗАЯВКА
# =========================================

@dp.message(F.text == "📞 Оставить заявку")
async def leave_application(
    message: Message,
    state: FSMContext
):

    await state.set_state(
        ApplicationForm.waiting_for_phone
    )

    await message.answer(
        "📱 <b>Шаг 1/3</b>\n\n"
        "Введите номер телефона\n"
        "или нажмите кнопку ниже 👇",
        reply_markup=contact_keyboard
    )


# =========================================
# PHONE
# =========================================

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
            "❌ Неверный формат телефона\n\n"
            "Пример:\n"
            "+79991234567"
        )
        return

    await state.update_data(phone=phone)

    await state.set_state(
        ApplicationForm.waiting_for_name
    )

    await message.answer(
        "✅ Телефон сохранён\n\n"
        "👤 <b>Шаг 2/3</b>\n"
        "Введите ваше имя",
        reply_markup=menu_keyboard
    )


# =========================================
# NAME
# =========================================

@dp.message(ApplicationForm.waiting_for_name)
async def process_name(
    message: Message,
    state: FSMContext
):

    name = message.text.strip()

    if len(name) < 2:

        await message.answer(
            "❌ Слишком короткое имя"
        )
        return

    await state.update_data(name=name)

    await state.set_state(
        ApplicationForm.waiting_for_email
    )

    await message.answer(
        "📧 <b>Шаг 3/3</b>\n\n"
        "Введите email\n"
        "или отправьте <b>нет</b>"
    )


# =========================================
# EMAIL
# =========================================

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

    await save_application(
        telegram_id=message.from_user.id,
        username=username,
        phone=phone,
        name=name,
        email=email
    )

    admin_text = (
        "🆕 <b>НОВАЯ ЗАЯВКА</b>\n\n"
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
        "✅ <b>Заявка отправлена!</b>\n\n"
        "Менеджер свяжется с вами в ближайшее время 👌",
        reply_markup=menu_keyboard
    )


# =========================================
# О КОМПАНИИ
# =========================================

@dp.message(F.text == "ℹ️ О компании")
async def about(message: Message):

    await message.answer(
        "🏢 <b>О КОМПАНИИ</b>\n\n"
        "АО «Инновация и логика 2.0»\n\n"
        "▫️ Международные платежи\n"
        "▫️ ВЭД сопровождение\n"
        "▫️ Консультационные услуги\n\n"
        "📍 Москва\n"
        "⏰ Пн-Пт 10:00-19:00\n\n"
        "📞 +7 (495) 129-90-90\n"
        "📧 info@il-2.ru"
    )


# =========================================
# ORDER
# =========================================

@dp.message(Command("order"))
async def order(message: Message):

    await message.answer(
        "📝 <b>ОФОРМЛЕНИЕ ПЕРЕВОДА</b>\n\n"
        "Отправьте:\n"
        "▫️ сумму\n"
        "▫️ валюту\n"
        "▫️ страну\n\n"
        "Менеджер ответит в течение 15 минут"
    )


# =========================================
# UNKNOWN
# =========================================

@dp.message()
async def unknown(message: Message):

    await message.answer(
        "❌ Неизвестная команда\n\n"
        "Используйте меню 👇",
        reply_markup=menu_keyboard
    )


# =========================================
# MAIN
# =========================================

async def main():

    logger.info("🚀 Бот запускается")

    await init_db()

    await bot.send_message(
        ADMIN_CHAT_ID,
        "✅ Бот успешно запущен"
    )

    await dp.start_polling(bot)


if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print("❌ Бот остановлен")
