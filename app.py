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

# ----------------------------
# Конфигурация
# ----------------------------

BOT_TOKEN = os.getenv("BOT_TOKEN", "8901177637:AAEeFWoKm8X9P9LHeHPDQL_R4zbJISzX-rE")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "8804129581"))

# ----------------------------
# Логирование
# ----------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
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
# База данных
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
EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

# ----------------------------
# КУРСЫ ВАЛЮТ
# ----------------------------

RATES = {
    "USD": 92.50,
    "EUR": 100.20,
    "CNY": 12.80,
    "AED": 25.20
}

# ----------------------------
# FSM
# ----------------------------

class ApplicationForm(StatesGroup):
    waiting_for_phone = State()
    waiting_for_name = State()
    waiting_for_email = State()

# ----------------------------
# ❖ СТИЛЬНОЕ МЕНЮ (инлайн-кнопки, тёмная тема)
# ----------------------------

main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⚡ БЫСТРЫЕ ПЕРЕВОДЫ", callback_data="fast")],
    [InlineKeyboardButton(text="💱 КУРСЫ ВАЛЮТ", callback_data="rates")],
    [InlineKeyboardButton(text="📩 ОСТАВИТЬ ЗАЯВКУ", callback_data="application")],
    [InlineKeyboardButton(text="🏢 О КОМПАНИИ", callback_data="about")]
])

back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="◀ НАЗАД", callback_data="back")]
])

contact_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 ОТПРАВИТЬ НОМЕР", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True
)

# ----------------------------
# ❖ СТАРТ
# ----------------------------

@dp.message(Command("start"))
async def start(message: Message):
    text = (
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n"
        "     <b>GLOBAL PAYMENTS</b>\n"
        "    <b>ИНСТИТУЦИОНАЛЬНЫЙ СЕРВИС</b>\n"
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n\n"
        "▸ МЕЖДУНАРОДНЫЕ ПЛАТЕЖИ\n"
        "▸ КОНСАЛТИНГ И ВЭД\n"
        "▸ СТРУКТУРИРОВАНИЕ РАСЧЁТОВ\n\n"
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n"
        "<i>ВЫБЕРИТЕ НАПРАВЛЕНИЕ</i>"
    )
    await message.answer(text, reply_markup=main_menu)

# ----------------------------
# ❖ НАЗАД
# ----------------------------

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery):
    text = (
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n"
        "     <b>GLOBAL PAYMENTS</b>\n"
        "    <b>ИНСТИТУЦИОНАЛЬНЫЙ СЕРВИС</b>\n"
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n\n"
        "▸ МЕЖДУНАРОДНЫЕ ПЛАТЕЖИ\n"
        "▸ КОНСАЛТИНГ И ВЭД\n"
        "▸ СТРУКТУРИРОВАНИЕ РАСЧЁТОВ\n\n"
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n"
        "<i>ВЫБЕРИТЕ НАПРАВЛЕНИЕ</i>"
    )
    await callback.message.edit_text(text, reply_markup=main_menu)
    await callback.answer()

# ----------------------------
# ❖ БЫСТРЫЕ ПЕРЕВОДЫ
# ----------------------------

@dp.callback_query(F.data == "fast")
async def fast(callback: CallbackQuery):
    text = (
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n"
        "    ⚡ <b>БЫСТРЫЕ ПЕРЕВОДЫ</b>\n"
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n\n"
        "▸ 50+ СТРАН\n"
        "▸ ЗАЧИСЛЕНИЕ 2–3 ДНЯ\n"
        "▸ SWIFT / АГЕНТСКИЕ СХЕМЫ\n"
        "▸ ОТ 50 000 USD — ПЕРСОНАЛЬНЫЕ УСЛОВИЯ\n\n"
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n"
        "<b>ДЛЯ ОФОРМЛЕНИЯ:</b> /order"
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard)
    await callback.answer()

# ----------------------------
# ❖ КУРСЫ ВАЛЮТ
# ----------------------------

@dp.callback_query(F.data == "rates")
async def rates(callback: CallbackQuery):
    text = (
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n"
        "    💱 <b>КУРСЫ ВАЛЮТ</b>\n"
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n\n"
        "▸ 1 USD / ДОЛЛАР США = 92.50 ₽\n"
        "▸ 1 EUR / ЕВРО = 100.20 ₽\n"
        "▸ 1 CNY / КИТАЙСКИЙ ЮАНЬ = 12.80 ₽\n"
        "▸ 1 AED / ДИРХАМ ОАЭ = 25.20 ₽\n\n"
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n"
        "<b>РАСЧЁТ СУММЫ:</b> /calc\n"
        "<i>Пример:</i> <code>/calc 1500 USD</code>"
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard)
    await callback.answer()

# ----------------------------
# ❖ О КОМПАНИИ
# ----------------------------

@dp.callback_query(F.data == "about")
async def about(callback: CallbackQuery):
    text = (
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n"
        "    🏢 <b>О КОМПАНИИ</b>\n"
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n\n"
        "АО «ИННОВАЦИЯ И ЛОГИКА 2.0»\n"
        "ФИНТЕХ-КОМПАНИЯ ПОЛНОГО ЦИКЛА\n\n"
        "▸ ВЭД И ТРАНСГРАНИЧНЫЕ ПЛАТЕЖИ\n"
        "▸ ОПТИМИЗАЦИЯ РАСЧЁТОВ\n"
        "▸ КОНСАЛТИНГ\n\n"
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n"
        "📍 МОСКВА, МАЛАЯ СЕМЁНОВСКАЯ 3АС1\n"
        "⏰ ПН–ПТ / 10:00–19:00\n\n"
        "📞 +7 (495) 129-90-90\n"
        "📧 INFO@IL-2.RU\n"
        "🌐 PORTAL.IL-2.RU"
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard)
    await callback.answer()

# ----------------------------
# ❖ ЗАЯВКА (ШАГ 1)
# ----------------------------

@dp.callback_query(F.data == "application")
async def application(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ApplicationForm.waiting_for_phone)
    await callback.message.answer(
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n"
        "    📩 <b>ОСТАВИТЬ ЗАЯВКУ</b>\n"
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n\n"
        "▸ ШАГ 1 ИЗ 3 ▸ ТЕЛЕФОН\n\n"
        "ВВЕДИТЕ НОМЕР В ФОРМАТЕ:\n"
        "<code>+79991234567</code>\n\n"
        "⬇ ИЛИ НАЖМИТЕ КНОПКУ НИЖЕ ⬇",
        reply_markup=contact_keyboard
    )
    await callback.answer()

# ----------------------------
# ❖ ШАГ 2 (ИМЯ)
# ----------------------------

@dp.message(ApplicationForm.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text.strip().replace(" ", "")

    if not re.match(PHONE_REGEX, phone):
        await message.answer("❌ НЕКОРРЕКТНЫЙ НОМЕР\nПРИМЕР: +79991234567")
        return

    await state.update_data(phone=phone)
    await state.set_state(ApplicationForm.waiting_for_name)
    await message.answer(
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n"
        "▸ ШАГ 2 ИЗ 3 ▸ ИМЯ\n\n"
        "ВВЕДИТЕ ВАШЕ ИМЯ",
        reply_markup=ReplyKeyboardRemove()
    )

# ----------------------------
# ❖ ШАГ 3 (EMAIL)
# ----------------------------

@dp.message(ApplicationForm.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ ВВЕДИТЕ КОРРЕКТНОЕ ИМЯ")
        return
    await state.update_data(name=name)
    await state.set_state(ApplicationForm.waiting_for_email)
    await message.answer(
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n"
        "▸ ШАГ 3 ИЗ 3 ▸ EMAIL\n\n"
        "ВВЕДИТЕ EMAIL\n"
        "ИЛИ НАПИШИТЕ «НЕТ»"
    )

# ----------------------------
# ❖ СОХРАНЕНИЕ ЗАЯВКИ
# ----------------------------

@dp.message(ApplicationForm.waiting_for_email)
async def process_email(message: Message, state: FSMContext):
    email_raw = message.text.strip()
    if email_raw.lower() in ("нет", "-", "skip"):
        email = "Не указан"
    else:
        if not re.match(EMAIL_REGEX, email_raw):
            await message.answer("❌ НЕКОРРЕКТНЫЙ EMAIL\nПРИМЕР: NAME@DOMAIN.RU")
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
        "🆕 <b>НОВАЯ ЗАЯВКА</b>\n\n"
        f"👤 ИМЯ: {name}\n"
        f"📱 ТЕЛЕФОН: {phone}\n"
        f"📧 EMAIL: {email}\n"
        f"🆔 ID: {message.from_user.id}\n"
        f"👤 USERNAME: {username}"
    )
    await bot.send_message(ADMIN_CHAT_ID, admin_text)

    await state.clear()
    await message.answer(
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n"
        "✅ <b>ЗАЯВКА ПРИНЯТА</b>\n\n"
        "МЕНЕДЖЕР СВЯЖЕТСЯ С ВАМИ\n"
        "В БЛИЖАЙШЕЕ ВРЕМЯ\n"
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖",
        reply_markup=ReplyKeyboardRemove()
    )
    await message.answer("ГЛАВНОЕ МЕНЮ 👇", reply_markup=main_menu)

# ----------------------------
# ❖ КАЛЬКУЛЯТОР
# ----------------------------

@dp.message(Command("calc"))
async def calc(message: Message):
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer(
            "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n"
            "    📊 <b>РАСЧЁТ СУММЫ</b>\n"
            "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n\n"
            "<b>ФОРМАТ:</b>\n"
            "<code>/calc 1000 USD</code>\n\n"
            "<b>ДОСТУПНЫЕ ВАЛЮТЫ:</b>\n"
            "USD, EUR, CNY, AED",
            parse_mode="HTML"
        )
        return
    
    try:
        amount = float(parts[1])
        currency = parts[2].upper()
        
        if currency not in RATES:
            await message.answer(f"❌ ВАЛЮТА {currency} НЕ ПОДДЕРЖИВАЕТСЯ")
            return
        
        result = amount * RATES[currency]
        
        amount_str = f"{amount:,.2f}".replace(",", " ")
        result_str = f"{result:,.2f}".replace(",", " ")
        
        await message.answer(
            "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n"
            f"<b>СУММА:</b> {amount_str} {currency}\n"
            f"<b>В РУБЛЯХ:</b> {result_str} ₽\n"
            f"<b>КУРС:</b> 1 {currency} = {RATES[currency]} ₽\n"
            "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖",
            parse_mode="HTML"
        )
        
    except ValueError:
        await message.answer("❌ ОШИБКА: ВВЕДИТЕ ЧИСЛО\nПРИМЕР: /calc 1000 USD")
    except Exception as e:
        logger.error(e)
        await message.answer("❌ ОШИБКА РАСЧЁТА")

# ----------------------------
# ❖ ОФОРМЛЕНИЕ ПЕРЕВОДА
# ----------------------------

@dp.message(Command("order"))
async def order(message: Message):
    await message.answer(
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n"
        "    📝 <b>ОФОРМЛЕНИЕ ПЕРЕВОДА</b>\n"
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n\n"
        "ОТПРАВЬТЕ НАМ:\n\n"
        "▸ СУММУ\n"
        "▸ ВАЛЮТУ\n"
        "▸ СТРАНУ\n\n"
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n"
        "<i>МЕНЕДЖЕР ОТВЕТИТ В ТЕЧЕНИЕ 15 МИНУТ</i>",
        parse_mode="HTML"
    )

# ----------------------------
# ❖ НЕИЗВЕСТНЫЕ СООБЩЕНИЯ
# ----------------------------

@dp.message()
async def unknown(message: Message):
    await message.answer(
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n"
        "    <b>ИСПОЛЬЗУЙТЕ МЕНЮ</b>\n"
        "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖\n\n"
        "👇 КНОПКИ ВНИЗУ ЭКРАНА 👇",
        parse_mode="HTML",
        reply_markup=main_menu
    )

# ----------------------------
# ЗАПУСК
# ----------------------------

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

async def main():
    logger.info("🚀 БОТ ЗАПУЩЕН")
    await bot.send_message(ADMIN_CHAT_ID, "✅ БОТ УСПЕШНО ЗАПУЩЕН")
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    import threading
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(main())
