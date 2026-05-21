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

# ----------------------------
# Конфигурация
# ----------------------------

BOT_TOKEN = os.getenv("BOT_TOKEN", "8901177637:AAEeFWoKm8X9P9LHeHPDQL_R4zbJISzX-rE")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "8804129581"))

# ----------------------------
# Логирование
# ----------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

# ----------------------------
# Бот и диспетчер
# ----------------------------

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ----------------------------
# Веб‑сервер для Render
# ----------------------------

app = Flask(__name__)

@app.route("/")
def home():
    return "Бот работает! 🤖", 200

@app.route("/health")
def health():
    return "OK", 200

# ----------------------------
# База данных (SQLite)
# ----------------------------

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

# ----------------------------
# Регулярные выражения
# ----------------------------

PHONE_REGEX = r"^\+?[1-9]\d{10,14}$"
EMAIL_REGEX   = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

# ----------------------------
# Клавиатуры
# ----------------------------

main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⚡ Быстрые переводы", callback_data="fast")],
    [InlineKeyboardButton(text="💰 Курсы валют",      callback_data="rates")],
    [InlineKeyboardButton(text="📩 Оставить заявку",   callback_data="application")],
    [InlineKeyboardButton(text="🏢 О компании",       callback_data="about")]
])

back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
])

contact_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Отправить номер", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True
)

# ----------------------------
# Курсы валют (можно потом заменить на реальный API)
# ----------------------------

RATES = {
    "USD": 92.50,
    "EUR": 100.20,
    "CNY": 12.80,
    "AED": 25.20
}

# ----------------------------
# FSM (машина состояний для заявки)
# ----------------------------

class ApplicationForm(StatesGroup):
    waiting_for_phone = State()
    waiting_for_name  = State()
    waiting_for_email = State()

# ----------------------------
# Обработчики команд и колбэков
# ----------------------------

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "👋 <b>Добро пожаловать!</b>\n\n"
        "Международные платежи для бизнеса.\n"
        "Быстро. Надёжно. Без лишней бюрократии.",
        reply_markup=main_menu
    )

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery):
    await callback.message.edit_text(
        "👋 <b>Добро пожаловать!</b>\n\n"
        "Международные платежи для бизнеса.\n"
        "Быстро. Надёжно. Без лишней бюрократии.",
        reply_markup=main_menu
    )
    await callback.answer()

@dp.callback_query(F.data == "fast")
async def fast(callback: CallbackQuery):
    text = (
        "⚡ <b>Быстрые переводы</b>\n\n"
        "• Переводы в 50+ стран\n"
        "• Зачисление за 2–3 дня\n"
        "• SWIFT / агентские схемы\n"
        "• Индивидуальные условия\n\n"
        "Для оформления: /order"
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard)
    await callback.answer()

@dp.callback_query(F.data == "rates")
async def rates(callback: CallbackQuery):
    text = "💱 <b>Курсы валют</b>\n\n"
    for curr, rate in RATES.items():
        text += f"• {curr} → RUB — {rate} ₽\n"
    text += "\nДля расчёта:\n<code>/calc 1000 USD RUB</code>"
    await callback.message.edit_text(text, reply_markup=back_keyboard)
    await callback.answer()

@dp.callback_query(F.data == "about")
async def about(callback: CallbackQuery):
    text = (
        "🏢 <b>О компании</b>\n\n"
        "АО «Инновация и логика 2.0»\n\n"
        "Сопровождение международных платежей\n"
        "и внешнеэкономической деятельности.\n\n"
        "📍 Москва, ул. Малая Семёновская, д. 3а, стр. 1\n"
        "⏰ Пн-Пт 10:00–19:00\n\n"
        "📞 +7 (495) 129-90-90\n"
        "📧 info@il-2.ru\n"
        "🌐 portal.il-2.ru"
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard)
    await callback.answer()

@dp.callback_query(F.data == "application")
async def application(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ApplicationForm.waiting_for_phone)
    await callback.message.answer(
        "📩 <b>Оставить заявку</b>\n\n"
        "Шаг 1 из 3\n\n"
        "Введите номер телефона\n"
        "или нажмите кнопку ниже 👇",
        reply_markup=contact_keyboard
    )
    await callback.answer()

@dp.message(ApplicationForm.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text.strip().replace(" ", "")

    if not re.match(PHONE_REGEX, phone):
        await message.answer("❌ Некорректный номер телефона\nПример: +79991234567")
        return

    await state.update_data(phone=phone)
    await state.set_state(ApplicationForm.waiting_for_name)
    await message.answer("👤 Шаг 2 из 3\n\nВведите ваше имя", reply_markup=ReplyKeyboardRemove())

@dp.message(ApplicationForm.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Введите корректное имя")
        return
    await state.update_data(name=name)
    await state.set_state(ApplicationForm.waiting_for_email)
    await message.answer("📧 Шаг 3 из 3\n\nВведите email\nили отправьте «нет»")

@dp.message(ApplicationForm.waiting_for_email)
async def process_email(message: Message, state: FSMContext):
    email_raw = message.text.strip()
    if email_raw.lower() in ("нет", "-", "skip"):
        email = "Не указан"
    else:
        if not re.match(EMAIL_REGEX, email_raw):
            await message.answer("❌ Некорректный email")
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
        "🆕 <b>Новая заявка</b>\n\n"
        f"👤 Имя: {name}\n"
        f"📱 Телефон: {phone}\n"
        f"📧 Email: {email}\n"
        f"🆔 ID: {message.from_user.id}\n"
        f"👤 Username: {username}"
    )
    await bot.send_message(ADMIN_CHAT_ID, admin_text)

    await state.clear()
    await message.answer(
        "✅ Заявка отправлена.\n\nМенеджер свяжется с вами в ближайшее время.",
        reply_markup=ReplyKeyboardRemove()
    )
    await message.answer("Главное меню 👇", reply_markup=main_menu)

# ----------------------------
# Калькулятор
# ----------------------------

@dp.message(Command("calc"))
async def calc(message: Message):
    parts = message.text.split()
    if len(parts) != 4:
        await message.answer("Формат:\n<code>/calc 1000 USD RUB</code>")
        return
    try:
        amount = float(parts[1])
        from_curr = parts[2].upper()
        if from_curr not in RATES:
            await message.answer("❌ Валюта не поддерживается")
            return
        if parts[3].upper() != "RUB":
            await message.answer("❌ Пока доступен только RUB")
            return
        result = amount * RATES[from_curr]
        await message.answer(f"💵 <b>Результат</b>\n\n{amount:,.2f} {from_curr} ≈ {result:,.2f} RUB")
    except Exception:
        await message.answer("❌ Ошибка расчёта")

# ----------------------------
# Оформление перевода
# ----------------------------

@dp.message(Command("order"))
async def order(message: Message):
    await message.answer(
        "📝 <b>Оформление перевода</b>\n\n"
        "Отправьте:\n\n"
        "• сумму\n"
        "• валюту\n"
        "• страну\n\n"
        "Менеджер ответит в течение 15 минут."
    )

# ----------------------------
# Обработка неизвестных сообщений
# ----------------------------

@dp.message()
async def unknown(message: Message):
    await message.answer("Используйте меню ниже 👇", reply_markup=main_menu)

# ----------------------------
# Запуск бота + Flask‑сервер
# ----------------------------

async def start_bot():
    await dp.start_polling(bot, handle_signals=False)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    import threading
    logger.info("🚀 Бот запущен")
    # Запускаем Flask в отдельном потоке
    threading.Thread(target=run_flask, daemon=True).start()
    # Запускаем бота в основном потоке
    asyncio.run(start_bot())
