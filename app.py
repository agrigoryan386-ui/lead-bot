import os
import re
import asyncio
import logging
import sqlite3
import base64
import json
import aiohttp
from datetime import datetime
from io import BytesIO

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

# API для ИИ (OpenRouter бесплатный ключ)
AI_API_KEY = os.getenv("AI_API_KEY", "")  # Вставь свой ключ в Render
AI_API_URL = "https://openrouter.ai/api/v1/chat/completions"

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
# ПОСТОЯННАЯ КНОПКА ГЛАВНОГО МЕНЮ
# ----------------------------

persistent_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🏠 Главное меню")]],
    resize_keyboard=True
)

# ----------------------------
# База данных
# ----------------------------

DB_FILE = "applications.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoice_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            username TEXT,
            amount REAL,
            currency TEXT,
            country TEXT,
            analysis TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_invoice_check(telegram_id, username, amount, currency, country, analysis):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO invoice_checks (telegram_id, username, amount, currency, country, analysis)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (telegram_id, username, amount, currency, country, analysis))
    conn.commit()
    conn.close()

init_db()

# ----------------------------
# FSM для проверки инвойса
# ----------------------------

class InvoiceForm(StatesGroup):
    waiting_for_file = State()

# ----------------------------
# Клавиатуры
# ----------------------------

main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⚡ Быстрые переводы", callback_data="fast")],
    [InlineKeyboardButton(text="💰 Курсы валют", callback_data="rates")],
    [InlineKeyboardButton(text="📄 Проверка инвойса", callback_data="check_invoice")],
    [InlineKeyboardButton(text="📩 Оставить заявку", callback_data="application")],
    [InlineKeyboardButton(text="🏢 О компании", callback_data="about")],
    [InlineKeyboardButton(text="📰 Новости ВЭД", callback_data="news")]
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
# Курсы валют (для справки)
# ----------------------------

RATES = {
    "USD": 92.50,
    "EUR": 100.20,
    "CNY": 12.80,
    "AED": 25.20
}

# ----------------------------
# Функция для анализа инвойса через ИИ
# ----------------------------

async def analyze_invoice(file_bytes, filename):
    """Отправляет файл в нейросеть для распознавания"""
    
    file_base64 = base64.b64encode(file_bytes).decode("utf-8")
    
    if filename.endswith('.pdf'):
        mime_type = "application/pdf"
    elif filename.endswith('.png'):
        mime_type = "image/png"
    elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
        mime_type = "image/jpeg"
    else:
        mime_type = "application/octet-stream"
    
    prompt = """Проанализируй этот инвойс (счёт) и извлеки:
1. Общую сумму к оплате (только цифру)
2. Валюту (USD, EUR, CNY, AED, RUB)
3. Страну получателя (если указана)
4. Краткое описание товара/услуги

Ответь строго в формате JSON:
{"amount": 1234.56, "currency": "USD", "country": "Германия", "description": "Оборудование"}

Если какое-то поле не удаётся определить, поставь null.
"""
    
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "google/gemini-2.0-flash-lite-preview-02-05:free",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{file_base64}"}}
                ]
            }
        ],
        "temperature": 0.1
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(AI_API_URL, headers=headers, json=payload, timeout=60) as response:
                data = await response.json()
                result_text = data["choices"][0]["message"]["content"]
                json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                return None
    except Exception as e:
        logger.error(f"Ошибка при анализе инвойса: {e}")
        return None

# ----------------------------
# Функция для новостей
# ----------------------------

async def get_ved_news():
    today = datetime.now().strftime("%d.%m.%Y")
    news_items = [
        {"title": "99% расчётов РФ–Китай в рублях и юанях", "summary": "Доля национальных валют во взаимной торговле достигла рекордных 99%.", "source": "РБК"},
        {"title": "ЕС ввёл санкции против платежных агентов", "summary": "20-й пакет санкций ЕС впервые затронул небанковских операторов.", "source": "РБК"},
        {"title": "Доля рубля в экспорте РФ достигла рекордных 64,9%", "summary": "В марте 2026 года доля рубля в экспортных расчётах обновила максимум.", "source": "Интерфакс"},
        {"title": "Вектор на Восток: роль Ближнего Востока в ВЭД растёт", "summary": "Исламский мир становится ключевым направлением для российских расчётов.", "source": "РБК"},
        {"title": "Новые правила валютного контроля с 2026 года", "summary": "Банки переходят на риск-ориентированный подход и автоматизацию.", "source": "РБК"}
    ]
    
    news_text = f"📰 <b>Новости ВЭД и международных платежей</b>\n\nСводка за {today}\n\n" + "─" * 30 + "\n\n"
    for i, item in enumerate(news_items, 1):
        news_text += f"<b>{i}. {item['title']}</b>\n{item['summary']}\n<i>Источник: {item['source']}</i>\n\n" + "─" * 30 + "\n\n"
    return news_text

# ----------------------------
# Обработчик постоянной кнопки
# ----------------------------

@dp.message(F.text == "🏠 Главное меню")
async def persistent_menu_handler(message: Message, state: FSMContext):
    await state.clear()
    text = "👋 Добро пожаловать!\n\nМеждународные платежи для бизнеса.\nБыстро. Надёжно. Без лишней бюрократии."
    await message.answer(text, reply_markup=persistent_menu)
    await message.answer("Главное меню:", reply_markup=main_menu)

# ----------------------------
# Старт
# ----------------------------

@dp.message(Command("start"))
async def start(message: Message):
    text = "👋 Добро пожаловать!\n\nМеждународные платежи для бизнеса.\nБыстро. Надёжно. Без лишней бюрократии."
    await message.answer(text, reply_markup=persistent_menu)
    await message.answer("Главное меню:", reply_markup=main_menu)

# ----------------------------
# Проверка инвойса
# ----------------------------

@dp.callback_query(F.data == "check_invoice")
async def check_invoice_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(InvoiceForm.waiting_for_file)
    await callback.message.edit_text(
        "📄 <b>Проверка инвойса</b>\n\n"
        "Отправьте файл с инвойсом (PDF, JPG, PNG)\n\n"
        "После анализа менеджер свяжется с вами.",
        parse_mode="HTML",
        reply_markup=back_keyboard
    )
    await callback.answer()

@dp.message(InvoiceForm.waiting_for_file, F.document | F.photo)
async def process_invoice(message: Message, state: FSMContext):
    await message.answer("🔍 Анализирую инвойс... Это может занять до 30 секунд.", reply_markup=persistent_menu)
    
    try:
        if message.document:
            file_id = message.document.file_id
            file_name = message.document.file_name or "инвойс"
        elif message.photo:
            file_id = message.photo[-1].file_id
            file_name = "инвойс.jpg"
        else:
            await message.answer("❌ Пожалуйста, отправьте файл (PDF, JPG, PNG) или фото", reply_markup=persistent_menu)
            return
        
        file = await bot.get_file(file_id)
        file_bytes = await bot.download_file(file.file_path)
        result = await analyze_invoice(file_bytes.read(), file_name)
        
        username = f"@{message.from_user.username}" if message.from_user.username else f"ID{message.from_user.id}"
        
        if result and result.get("amount"):
            amount = result.get("amount")
            currency = result.get("currency", "Не определена")
            country = result.get("country", "Не указана")
            description = result.get("description", "Не указано")
            
            # Сохраняем в БД
            save_invoice_check(message.from_user.id, username, amount, currency, country, description)
            
            # Отправляем админу подробный отчёт
            admin_msg = (
                f"🆕 <b>НОВЫЙ ИНВОЙС НА ПРОВЕРКУ!</b>\n\n"
                f"👤 <b>Пользователь:</b> {username}\n"
                f"📄 <b>Сумма:</b> {amount:,.2f} {currency}\n"
                f"🌍 <b>Страна:</b> {country}\n"
                f"📝 <b>Описание:</b> {description}\n"
                f"🕒 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
            )
            await bot.send_message(ADMIN_CHAT_ID, admin_msg, parse_mode="HTML")
            
            await message.answer(
                "✅ <b>Инвойс принят!</b>\n\n"
                "Менеджер проверит его и свяжется с вами в ближайшее время.",
                parse_mode="HTML",
                reply_markup=persistent_menu
            )
        else:
            # Даже если не распознали, отправляем админу на ручную проверку
            admin_msg = (
                f"⚠️ <b>НЕ УДАЛОСЬ РАСПОЗНАТЬ ИНВОЙС</b>\n\n"
                f"👤 <b>Пользователь:</b> {username}\n"
                f"📎 <b>Файл:</b> {file_name}\n"
                f"🕒 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
            )
            await bot.send_message(ADMIN_CHAT_ID, admin_msg, parse_mode="HTML")
            
            await message.answer(
                "⚠️ <b>Не удалось автоматически распознать инвойс</b>\n\n"
                "Менеджер проверит его вручную и свяжется с вами.",
                parse_mode="HTML",
                reply_markup=persistent_menu
            )
        
        await message.answer("Главное меню:", reply_markup=main_menu)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке инвойса: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте ещё раз или свяжитесь с менеджером.", reply_markup=persistent_menu)
    finally:
        await state.clear()

# ----------------------------
# Быстрые переводы
# ----------------------------

@dp.callback_query(F.data == "fast")
async def fast(callback: CallbackQuery):
    text = (
        "⚡ Быстрые переводы\n\n"
        "• Переводы в 50+ стран\n"
        "• Зачисление за 2–3 дня\n"
        "• SWIFT / агентские схемы\n"
        "• При сумме от 50 000 USD — индивидуальные условия\n\n"
        "Для оформления: /order"
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard)
    await callback.answer()

# ----------------------------
# Курсы валют
# ----------------------------

@dp.callback_query(F.data == "rates")
async def rates(callback: CallbackQuery):
    text = (
        "💰 Курсы валют\n\n"
        f"1 USD = {RATES['USD']} ₽\n"
        f"1 EUR = {RATES['EUR']} ₽\n"
        f"1 CNY = {RATES['CNY']} ₽\n"
        f"1 AED = {RATES['AED']} ₽\n\n"
        "💡 Индивидуальный курс при сумме от 50 000 USD\n\n"
        "Нажмите /calc для расчёта"
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard)
    await callback.answer()

# ----------------------------
# О компании
# ----------------------------

@dp.callback_query(F.data == "about")
async def about(callback: CallbackQuery):
    text = (
        "🏢 АО «Инновация и логика 2.0»\n\n"
        "Финтех-компания, предоставляющая решения для сопровождения внешнеэкономической деятельности.\n\n"
        "📌 Адрес:\nг. Москва, ул. Малая Семёновская, д. 3а, стр. 1\n\n"
        "⏰ Режим работы:\nПн-Пт, с 10:00 до 19:00\n\n"
        "📞 Контакты:\nТелефон: <a href='tel:+74951299090'>+7 (495) 129-90-90</a>\n"
        "Email: <a href='mailto:info@il-2.ru'>info@il-2.ru</a>\n"
        "Сайт: <a href='https://portal.il-2.ru/me/orders'>portal.il-2.ru/me/orders</a>\n\n"
        "🌟 Наши партнеры доверили нам уже более 10 000 переводов."
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard)
    await callback.answer()

# ----------------------------
# Новости ВЭД
# ----------------------------

@dp.callback_query(F.data == "news")
async def news(callback: CallbackQuery):
    await callback.message.edit_text("📰 Загружаю новости...", reply_markup=back_keyboard)
    try:
        news_text = await get_ved_news()
        await callback.message.edit_text(news_text, reply_markup=back_keyboard)
    except Exception as e:
        logger.error(f"Ошибка при получении новостей: {e}")
        await callback.message.edit_text("❌ Не удалось загрузить новости.", reply_markup=back_keyboard)
    await callback.answer()

# ----------------------------
# Оставить заявку
# ----------------------------

@dp.callback_query(F.data == "application")
async def application(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ApplicationForm.waiting_for_phone)
    await callback.message.answer(
        "📩 Оставить заявку\n\nШаг 1 из 3 — номер телефона\n\n"
        "Введите номер в формате +79991234567\nили нажмите кнопку ниже 👇",
        reply_markup=contact_keyboard
    )
    await callback.answer()

# ----------------------------
# FSM для заявки
# ----------------------------

class ApplicationForm(StatesGroup):
    waiting_for_phone = State()
    waiting_for_name = State()
    waiting_for_email = State()

@dp.message(ApplicationForm.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text.strip().replace(" ", "")
    if not re.match(r"^\+?[1-9]\d{10,14}$", phone):
        await message.answer("❌ Некорректный номер. Пример: +79991234567", reply_markup=persistent_menu)
        return
    await state.update_data(phone=phone)
    await state.set_state(ApplicationForm.waiting_for_name)
    await message.answer("Шаг 2 из 3 — ваше имя\n\nВведите ваше имя:", reply_markup=persistent_menu)

@dp.message(ApplicationForm.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Введите корректное имя", reply_markup=persistent_menu)
        return
    await state.update_data(name=name)
    await state.set_state(ApplicationForm.waiting_for_email)
    await message.answer("Шаг 3 из 3 — email\n\nВведите email или отправьте «нет»", reply_markup=persistent_menu)

@dp.message(ApplicationForm.waiting_for_email)
async def process_email(message: Message, state: FSMContext):
    email_raw = message.text.strip()
    if email_raw.lower() in ("нет", "-", "skip"):
        email = "Не указан"
    else:
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email_raw):
            await message.answer("❌ Некорректный email. Пример: name@domain.ru", reply_markup=persistent_menu)
            return
        email = email_raw
    await state.update_data(email=email)
    data = await state.get_data()
    phone = data["phone"]
    name = data["name"]
    username = f"@{message.from_user.username}" if message.from_user.username else "Нет"
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO applications (telegram_id, username, phone, name, email) VALUES (?, ?, ?, ?, ?)",
                   (message.from_user.id, username, phone, name, email))
    conn.commit()
    conn.close()
    
    admin_text = f"🆕 Новая заявка\n\nИмя: {name}\nТелефон: {phone}\nEmail: {email}\nID: {message.from_user.id}\nUsername: {username}"
    await bot.send_message(ADMIN_CHAT_ID, admin_text)
    await state.clear()
    await message.answer("✅ Заявка отправлена.\n\nМенеджер свяжется с вами.", reply_markup=persistent_menu)
    await message.answer("Главное меню:", reply_markup=main_menu)

# ----------------------------
# Оформление перевода /order
# ----------------------------

class OrderForm(StatesGroup):
    waiting_for_amount = State()
    waiting_for_currency = State()
    waiting_for_country = State()

@dp.message(Command("order"))
async def order_start(message: Message, state: FSMContext):
    await state.set_state(OrderForm.waiting_for_amount)
    await message.answer("📝 Оформление перевода\n\nШаг 1 из 3 — введите сумму перевода:\n\nПример: 5000", reply_markup=persistent_menu)

@dp.message(OrderForm.waiting_for_amount)
async def order_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(",", "."))
        await state.update_data(amount=amount)
        await state.set_state(OrderForm.waiting_for_currency)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🇺🇸 USD", callback_data="order_curr_USD")],
            [InlineKeyboardButton(text="🇪🇺 EUR", callback_data="order_curr_EUR")],
            [InlineKeyboardButton(text="🇨🇳 CNY", callback_data="order_curr_CNY")],
            [InlineKeyboardButton(text="🇦🇪 AED", callback_data="order_curr_AED")],
            [InlineKeyboardButton(text="◀ Отмена", callback_data="order_cancel")]
        ])
        await message.answer(f"Шаг 2 из 3 — выберите валюту для суммы {amount:,.2f}:", reply_markup=keyboard)
    except ValueError:
        await message.answer("❌ Ошибка: введите число", reply_markup=persistent_menu)

@dp.callback_query(F.data.startswith("order_curr_"))
async def order_currency(callback: CallbackQuery, state: FSMContext):
    currency_code = callback.data.split("_")[2]
    await state.update_data(currency=currency_code)
    await state.set_state(OrderForm.waiting_for_country)
    await callback.message.edit_text("Шаг 3 из 3 — введите страну получателя:\n\nПример: Испания, Германия, США",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Отмена", callback_data="order_cancel")]]))
    await callback.answer()

@dp.message(OrderForm.waiting_for_country)
async def order_country(message: Message, state: FSMContext):
    country = message.text.strip()
    if len(country) < 2:
        await message.answer("❌ Введите корректное название страны", reply_markup=persistent_menu)
        return
    await state.update_data(country=country)
    data = await state.get_data()
    amount = data["amount"]
    currency = data["currency"]
    username = f"@{message.from_user.username}" if message.from_user.username else f"ID{message.from_user.id}"
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO order_applications (telegram_id, username, amount, currency, country) VALUES (?, ?, ?, ?, ?)",
                   (message.from_user.id, username, amount, currency, country))
    conn.commit()
    conn.close()
    
    admin_msg = f"🆕 НОВАЯ ЗАЯВКА НА ПЕРЕВОД!\n\n💰 Сумма: {amount:,.2f} {currency}\n🌍 Страна: {country}\n👤 Пользователь: {username}\n🆔 ID: {message.from_user.id}"
    await bot.send_message(ADMIN_CHAT_ID, admin_msg)
    await state.clear()
    await message.answer(f"✅ Заявка принята!\n\nСумма: {amount:,.2f} {currency}\nСтрана: {country}\n\nМенеджер свяжется с вами.", reply_markup=persistent_menu)
    await message.answer("Главное меню:", reply_markup=main_menu)

@dp.callback_query(F.data == "order_cancel")
async def order_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Оформление перевода отменено.", reply_markup=persistent_menu)
    await callback.answer()

# ----------------------------
# Калькулятор
# ----------------------------

class CalculatorForm(StatesGroup):
    waiting_for_amount = State()
    waiting_for_currency = State()

@dp.message(Command("calc"))
async def calc_start(message: Message, state: FSMContext):
    await state.set_state(CalculatorForm.waiting_for_amount)
    await message.answer("💰 Калькулятор валют\n\nВведите сумму в рублях, которую хотите конвертировать:", reply_markup=persistent_menu)

@dp.message(CalculatorForm.waiting_for_amount)
async def calc_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(",", "."))
        await state.update_data(amount=amount)
        await state.set_state(CalculatorForm.waiting_for_currency)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🇺🇸 USD", callback_data="curr_USD")],
            [InlineKeyboardButton(text="🇪🇺 EUR", callback_data="curr_EUR")],
            [InlineKeyboardButton(text="🇨🇳 CNY", callback_data="curr_CNY")],
            [InlineKeyboardButton(text="🇦🇪 AED", callback_data="curr_AED")],
            [InlineKeyboardButton(text="◀ Отмена", callback_data="calc_cancel")]
        ])
        await message.answer(f"Сумма: {amount:,.2f} ₽\n\nВыберите валюту:", reply_markup=keyboard)
    except ValueError:
        await message.answer("❌ Ошибка: введите число", reply_markup=persistent_menu)

@dp.callback_query(F.data.startswith("curr_"))
async def calc_currency(callback: CallbackQuery, state: FSMContext):
    currency_code = callback.data.split("_")[1]
    currency_names = {"USD": "Доллар США", "EUR": "Евро", "CNY": "Китайский юань", "AED": "Дирхам ОАЭ"}
    data = await state.get_data()
    amount = data.get("amount")
    if not amount:
        await state.clear()
        await callback.message.answer("❌ Сессия истекла. Начните заново: /calc")
        await callback.answer()
        return
    rate = RATES.get(currency_code)
    result = amount / rate
    amount_str = f"{amount:,.2f}".replace(",", " ")
    result_str = f"{result:,.2f}".replace(",", " ")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Новый расчёт", callback_data="calc_new"), InlineKeyboardButton(text="🏠 Главное меню", callback_data="calc_back_to_menu")]
    ])
    await callback.message.edit_text(f"💵 Результат конвертации\n\n{amount_str} ₽ = {result_str} {currency_names[currency_code]}\nКурс: 1 {currency_code} = {rate} ₽", reply_markup=keyboard)
    await state.clear()
    await callback.answer()

@dp.callback_query(F.data == "calc_new")
async def calc_new(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CalculatorForm.waiting_for_amount)
    await callback.message.edit_text("💰 Калькулятор валют\n\nВведите сумму в рублях, которую хотите конвертировать:", reply_markup=persistent_menu)
    await callback.answer()

@dp.callback_query(F.data == "calc_cancel")
async def calc_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Расчёт отменён.", reply_markup=persistent_menu)
    await callback.answer()

@dp.callback_query(F.data == "calc_back_to_menu")
async def calc_back_to_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = "👋 Добро пожаловать!\n\nМеждународные платежи для бизнеса.\nБыстро. Надёжно. Без лишней бюрократии."
    await callback.message.edit_text(text, reply_markup=persistent_menu)
    await callback.message.answer("Главное меню:", reply_markup=main_menu)
    await callback.answer()

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery):
    text = "👋 Добро пожаловать!\n\nМеждународные платежи для бизнеса.\nБыстро. Надёжно. Без лишней бюрократии."
    await callback.message.edit_text(text, reply_markup=persistent_menu)
    await callback.message.answer("Главное меню:", reply_markup=main_menu)
    await callback.answer()

@dp.message()
async def unknown(message: Message):
    await message.answer("Используйте меню ниже 👇", reply_markup=persistent_menu)
    await message.answer("Главное меню:", reply_markup=main_menu)

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
