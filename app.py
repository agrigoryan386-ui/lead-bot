import os
import re
import asyncio
import logging
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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

# ----------------------------
# Конфигурация
# ----------------------------

BOT_TOKEN = os.getenv("BOT_TOKEN", "8901177637:AAEeFWoKm8X9P9LHeHPDQL_R4zbJISzX-rE")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "8804129581"))

# Настройки почты
EMAIL_SENDER = "artur.grigoryan@il-2.ru"
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")  # Пароль от почты (нужно добавить в Render)
EMAIL_RECIPIENT = "artur.grigoryan@il-2.ru"
SMTP_SERVER = "smtp.yandex.ru"  # Если почта на Яндексе, для других провайдеров свой
SMTP_PORT = 465

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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            username TEXT,
            amount REAL,
            currency TEXT,
            country TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_order_application(telegram_id, username, amount, currency, country):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO order_applications (telegram_id, username, amount, currency, country)
        VALUES (?, ?, ?, ?, ?)
    """, (telegram_id, username, amount, currency, country))
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
# FSM для заявки (Оставить заявку)
# ----------------------------

class ApplicationForm(StatesGroup):
    waiting_for_phone = State()
    waiting_for_name  = State()
    waiting_for_email = State()

# ----------------------------
# FSM для заказа /order
# ----------------------------

class OrderForm(StatesGroup):
    waiting_for_amount = State()
    waiting_for_currency = State()
    waiting_for_country = State()

# ----------------------------
# FSM для калькулятора
# ----------------------------

class CalculatorForm(StatesGroup):
    waiting_for_amount = State()
    waiting_for_currency = State()

# ----------------------------
# Функция отправки email
# ----------------------------

def send_email_notification(amount, currency, country, user_id, username):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECIPIENT
        msg["Subject"] = f"🆕 Новая заявка на перевод {amount} {currency}"
        
        body = f"""
        <html>
        <body>
        <h2>🆕 Новая заявка на перевод</h2>
        <p><b>Сумма:</b> {amount} {currency}</p>
        <p><b>Страна:</b> {country}</p>
        <p><b>Пользователь:</b> {username}</p>
        <p><b>Telegram ID:</b> {user_id}</p>
        <p><b>Время заявки:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, "html"))
        
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Email отправлен для заявки {amount} {currency}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки email: {e}")
        return False

# ----------------------------
# Клавиатуры
# ----------------------------

main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⚡ Быстрые переводы", callback_data="fast")],
    [InlineKeyboardButton(text="💰 Курсы валют",      callback_data="rates")],
    [InlineKeyboardButton(text="📩 Оставить заявку",   callback_data="application")],
    [InlineKeyboardButton(text="🏢 О компании",       callback_data="about")],
    [InlineKeyboardButton(text="📰 Новости ВЭД",       callback_data="news")]
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
# Курсы валют
# ----------------------------

RATES = {
    "USD": 92.50,
    "EUR": 100.20,
    "CNY": 12.80,
    "AED": 25.20
}

# ----------------------------
# Функция новостей
# ----------------------------

async def get_ved_news():
    today = datetime.now().strftime("%d.%m.%Y")
    
    news_items = [
        {
            "title": "99% расчётов РФ–Китай в рублях и юанях",
            "summary": "Доля национальных валют во взаимной торговле достигла рекордных 99%.",
            "source": "РБК"
        },
        {
            "title": "ЕС ввёл санкции против платежных агентов",
            "summary": "20-й пакет санкций ЕС впервые затронул небанковских операторов.",
            "source": "РБК"
        },
        {
            "title": "Доля рубля в экспорте РФ достигла рекордных 64,9%",
            "summary": "В марте 2026 года доля рубля в экспортных расчётах обновила максимум.",
            "source": "Интерфакс"
        },
        {
            "title": "Вектор на Восток: роль Ближнего Востока в ВЭД растёт",
            "summary": "Исламский мир становится ключевым направлением для российских расчётов.",
            "source": "РБК"
        },
        {
            "title": "Новые правила валютного контроля с 2026 года",
            "summary": "Банки переходят на риск-ориентированный подход и автоматизацию.",
            "source": "РБК"
        }
    ]
    
    news_text = f"📰 <b>Новости ВЭД и международных платежей</b>\n\n"
    news_text += f"Сводка за {today}\n\n"
    news_text += "─" * 30 + "\n\n"
    
    for i, item in enumerate(news_items, 1):
        news_text += f"<b>{i}. {item['title']}</b>\n"
        news_text += f"{item['summary']}\n"
        news_text += f"<i>Источник: {item['source']}</i>\n\n"
        news_text += "─" * 30 + "\n\n"
    
    return news_text

# ----------------------------
# Обработчики команд
# ----------------------------

@dp.message(Command("start"))
async def start(message: Message):
    text = "👋 Добро пожаловать!\n\nМеждународные платежи для бизнеса.\nБыстро. Надёжно. Без лишней бюрократии."
    await message.answer(text, reply_markup=main_menu)

# ----------------------------
# ЗАЯВКА НА ПЕРЕВОД (/order)
# ----------------------------

@dp.message(Command("order"))
async def order_start(message: Message, state: FSMContext):
    await state.set_state(OrderForm.waiting_for_amount)
    await message.answer(
        "📝 <b>Оформление перевода</b>\n\n"
        "Шаг 1 из 3 — введите сумму перевода:\n\n"
        "Пример: 5000",
        parse_mode="HTML"
    )

@dp.message(OrderForm.waiting_for_amount)
async def order_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(",", "."))
        await state.update_data(amount=amount)
        await state.set_state(OrderForm.waiting_for_currency)
        
        currency_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🇺🇸 USD", callback_data="order_curr_USD")],
            [InlineKeyboardButton(text="🇪🇺 EUR", callback_data="order_curr_EUR")],
            [InlineKeyboardButton(text="🇨🇳 CNY", callback_data="order_curr_CNY")],
            [InlineKeyboardButton(text="🇦🇪 AED", callback_data="order_curr_AED")],
            [InlineKeyboardButton(text="◀ Отмена", callback_data="order_cancel")]
        ])
        
        await message.answer(
            f"Шаг 2 из 3 — выберите валюту для суммы {amount:,.2f}:",
            reply_markup=currency_keyboard
        )
    except ValueError:
        await message.answer("❌ Ошибка: введите число\n\nПример: 5000")

@dp.callback_query(F.data.startswith("order_curr_"))
async def order_currency(callback: CallbackQuery, state: FSMContext):
    currency_code = callback.data.split("_")[2]
    await state.update_data(currency=currency_code)
    await state.set_state(OrderForm.waiting_for_country)
    
    await callback.message.edit_text(
        f"Шаг 3 из 3 — введите страну получателя:\n\n"
        f"Пример: Испания, Германия, США",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀ Отмена", callback_data="order_cancel")]
        ])
    )
    await callback.answer()

@dp.message(OrderForm.waiting_for_country)
async def order_country(message: Message, state: FSMContext):
    country = message.text.strip()
    if len(country) < 2:
        await message.answer("❌ Введите корректное название страны")
        return
    
    await state.update_data(country=country)
    data = await state.get_data()
    
    amount = data["amount"]
    currency = data["currency"]
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else f"ID{user_id}"
    
    # Сохраняем в БД
    save_order_application(user_id, username, amount, currency, country)
    
    # Отправляем админу в Telegram
    admin_msg = (
        f"🆕 <b>НОВАЯ ЗАЯВКА НА ПЕРЕВОД!</b>\n\n"
        f"💰 <b>Сумма:</b> {amount:,.2f} {currency}\n"
        f"🌍 <b>Страна:</b> {country}\n"
        f"👤 <b>Пользователь:</b> {username}\n"
        f"🆔 <b>ID:</b> {user_id}\n"
        f"🕒 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    )
    await bot.send_message(ADMIN_CHAT_ID, admin_msg, parse_mode="HTML")
    
    # Отправляем на почту
    email_sent = send_email_notification(amount, currency, country, user_id, username)
    
    if email_sent:
        email_status = "✅ Копия заявки отправлена на почту"
    else:
        email_status = "⚠️ Не удалось отправить email (проверьте настройки почты)"
    
    await state.clear()
    await message.answer(
        f"✅ <b>Заявка принята!</b>\n\n"
        f"Сумма: {amount:,.2f} {currency}\n"
        f"Страна: {country}\n\n"
        f"Менеджер свяжется с вами в ближайшее время.\n\n"
        f"{email_status}",
        parse_mode="HTML",
        reply_markup=main_menu
    )

@dp.callback_query(F.data == "order_cancel")
async def order_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Оформление перевода отменено.\n\n"
        "Вы можете начать заново командой /order",
        reply_markup=main_menu
    )
    await callback.answer()

# ----------------------------
# Остальные обработчики (fast, rates, about, news, application, calc)
# (здесь продолжается остальной код бота — для краткости опущен, но должен быть)
# В полной версии добавлены все остальные функции
# ----------------------------

# Для краткости в этом сообщении я показываю только NEW код для /order.
# Полный файл я пришлю отдельно, если нужно.

async def start_bot():
    await dp.start_polling(bot, handle_signals=False)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    import threading
    logger.info("Бот запущен")
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(start_bot())
