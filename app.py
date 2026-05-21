import os
import re
import asyncio
import logging
import sqlite3
from flask import Flask
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "8901177637:AAEeFWoKm8X9P9LHeHPDQL_R4zbJISzX-rE")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "8804129581"))

# ============================================================
# ЛОГИРОВАНИЕ
# ============================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ============================================================
# БОТ И ДИСПЕТЧЕР
# ============================================================

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ============================================================
# ВЕБ‑СЕРВЕР ДЛЯ RENDER
# ============================================================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running", 200

@app.route("/health")
def health():
    return "OK", 200

# ============================================================
# БАЗА ДАННЫХ
# ============================================================

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
    conn.commit()
    conn.close()

def save_application(telegram_id, username, phone, name, email):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO applications (telegram_id, username, phone, name, email)
        VALUES (?, ?, ?, ?, ?)
    """, (telegram_id, username, phone, name, email))
    conn.commit()
    conn.close()

init_db()

# ============================================================
# РЕГУЛЯРНЫЕ ВЫРАЖЕНИЯ
# ============================================================

PHONE_REGEX = r"^\+?[1-9]\d{10,14}$"
EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

# ============================================================
# КУРСЫ ВАЛЮТ
# ============================================================

RATES = {
    "USD": 92.50,
    "EUR": 100.20,
    "CNY": 12.80,
    "AED": 25.20
}

# ============================================================
# FSM
# ============================================================

class ApplicationForm(StatesGroup):
    waiting_for_phone = State()
    waiting_for_name = State()
    waiting_for_email = State()

# ============================================================
# КЛАВИАТУРЫ (ИНЛАЙН)
# ============================================================

main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⚡ Быстрые переводы", callback_data="fast")],
    [InlineKeyboardButton(text="💰 Курсы валют", callback_data="rates")],
    [InlineKeyboardButton(text="📩 Оставить заявку", callback_data="application")],
    [InlineKeyboardButton(text="🏢 О компании", callback_data="about")]
])

back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="◀ Назад", callback_data="back")]
])

contact_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Отправить номер", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True
)

# ============================================================
# СТАРТ
# ============================================================

@dp.message(Command("start"))
async def start(message: Message):
    text = (
        "Добро пожаловать.\n\n"
        "Международные платежи для бизнеса.\n"
        "Сопровождение ВЭД. Структурирование расчётов.\n\n"
        "Выберите раздел:"
    )
    await message.answer(text, reply_markup=main_menu)

# ============================================================
# НАЗАД
# ============================================================

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery):
    text = (
        "Добро пожаловать.\n\n"
        "Международные платежи для бизнеса.\n"
        "Сопровождение ВЭД. Структурирование расчётов.\n\n"
        "Выберите раздел:"
    )
    await callback.message.edit_text(text, reply_markup=main_menu)
    await callback.answer()

# ============================================================
# БЫСТРЫЕ ПЕРЕВОДЫ
# ============================================================

@dp.callback_query(F.data == "fast")
async def fast(callback: CallbackQuery):
    text = (
        "⚡ Быстрые переводы\n\n"
        "• 50+ стран\n"
        "• Зачисление 2–3 дня\n"
        "• SWIFT / агентские схемы\n"
        "• Индивидуальные условия от 50 000 USD\n\n"
        "Для оформления: /order"
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard)
    await callback.answer()

# ============================================================
# КУРСЫ ВАЛЮТ
# ============================================================

@dp.callback_query(F.data == "rates")
async def rates(callback: CallbackQuery):
    text = (
        "💰 Курсы валют\n\n"
        f"1 USD (Доллар США) = {RATES['USD']} ₽\n"
        f"1 EUR (Евро) = {RATES['EUR']} ₽\n"
        f"1 CNY (Юань) = {RATES['CNY']} ₽\n"
        f"1 AED (Дирхам ОАЭ) = {RATES['AED']} ₽\n\n"
        "Расчёт: /calc\n"
        "Пример: /calc 1500 USD"
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard)
    await callback.answer()

# ============================================================
# О КОМПАНИИ
# ============================================================

@dp.callback_query(F.data == "about")
async def about(callback: CallbackQuery):
    text = (
        "🏢 О компании\n\n"
        "АО «Инновация и логика 2.0»\n\n"
        "Сопровождение международных платежей\n"
        "и внешнеэкономической деятельности.\n\n"
        "📍 Москва, ул. Малая Семёновская, 3а стр.1\n"
        "⏰ Пн–Пт, 10:00 – 19:00\n\n"
        "📞 +7 (495) 129-90-90\n"
        "📧 info@il-2.ru\n"
        "🌐 portal.il-2.ru"
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard)
    await callback.answer()

# ============================================================
# ЗАЯВКА
# ============================================================

@dp.callback_query(F.data == "application")
async def application(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ApplicationForm.waiting_for_phone)
    text = (
        "📩 Оставить заявку\n\n"
        "Шаг 1 из 3 — номер телефона\n\n"
        "Введите номер в формате +79991234567\n"
        "или нажмите кнопку ниже."
    )
    await callback.message.answer(text, reply_markup=contact_keyboard)
    await callback.answer()

@dp.message(ApplicationForm.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text.strip().replace(" ", "")

    if not re.match(PHONE_REGEX, phone):
        await message.answer("Некорректный номер. Пример: +79991234567")
        return

    await state.update_data(phone=phone)
    await state.set_state(ApplicationForm.waiting_for_name)
    await message.answer(
        "Шаг 2 из 3 — ваше имя\n\nВведите имя:",
        reply_markup=ReplyKeyboardRemove()
    )

@dp.message(ApplicationForm.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Введите корректное имя (минимум 2 буквы)")
        return
    await state.update_data(name=name)
    await state.set_state(ApplicationForm.waiting_for_email)
    await message.answer(
        "Шаг 3 из 3 — email\n\n"
        "Введите email или отправьте «нет»"
    )

@dp.message(ApplicationForm.waiting_for_email)
async def process_email(message: Message, state: FSMContext):
    email_raw = message.text.strip()
    if email_raw.lower() in ("нет", "-", "skip"):
        email = "Не указан"
    else:
        if not re.match(EMAIL_REGEX, email_raw):
            await message.answer("Некорректный email. Пример: name@domain.ru")
            return
        email = email_raw

    await state.update_data(email=email)
    data = await state.get_data()

    phone = data["phone"]
    name = data["name"]
    username = f"@{message.from_user.username}" if message.from_user.username else "Нет"

    save_application(
        telegram_id=message.from_user.id,
        username=username,
        phone=phone,
        name=name,
        email=email
    )

    admin_text = (
        "🆕 Новая заявка\n\n"
        f"Имя: {name}\n"
        f"Телефон: {phone}\n"
        f"Email: {email}\n"
        f"ID: {message.from_user.id}\n"
        f"Username: {username}"
    )
    await bot.send_message(ADMIN_CHAT_ID, admin_text)

    await state.clear()
    await message.answer(
        "✅ Заявка принята.\n\n"
        "Менеджер свяжется с вами в ближайшее время.",
        reply_markup=ReplyKeyboardRemove()
    )
    await message.answer("Главное меню:", reply_markup=main_menu)

# ============================================================
# КАЛЬКУЛЯТОР
# ============================================================

@dp.message(Command("calc"))
async def calc(message: Message):
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer(
            "Формат: /calc 1000 USD\n\n"
            "Доступные валюты: USD, EUR, CNY, AED"
        )
        return

    try:
        amount = float(parts[1])
        currency = parts[2].upper()

        if currency not in RATES:
            await message.answer(f"Валюта {currency} не поддерживается.\nДоступны: USD, EUR, CNY, AED")
            return

        result = amount * RATES[currency]

        amount_str = f"{amount:,.2f}".replace(",", " ")
        result_str = f"{result:,.2f}".replace(",", " ")

        await message.answer(
            f"{amount_str} {currency} = {result_str} ₽\n"
            f"Курс: 1 {currency} = {RATES[currency]} ₽"
        )

    except ValueError:
        await message.answer("Ошибка: введите число\nПример: /calc 1000 USD")
    except Exception:
        await message.answer("Ошибка расчёта")

# ============================================================
# ОФОРМЛЕНИЕ ПЕРЕВОДА
# ============================================================

@dp.message(Command("order"))
async def order(message: Message):
    text = (
        "📝 Оформление перевода\n\n"
        "Отправьте:\n"
        "• сумму\n"
        "• валюту\n"
        "• страну\n\n"
        "Менеджер ответит в течение 15 минут."
    )
    await message.answer(text)

# ============================================================
# НЕИЗВЕСТНЫЕ СООБЩЕНИЯ
# ============================================================

@dp.message()
async def unknown(message: Message):
    await message.answer(
        "Используйте меню ниже 👇",
        reply_markup=main_menu
    )

# ============================================================
# ЗАПУСК
# ============================================================

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

async def main():
    logger.info("Бот запущен")
    await bot.send_message(ADMIN_CHAT_ID, "✅ Бот успешно запущен")
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    import threading
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(main())
