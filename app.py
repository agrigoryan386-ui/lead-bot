import os
import re
import json
import asyncio
import logging
import sqlite3
import io
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
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "8901177637:AAEeFWoKm8X9P9LHeHPDQL_R4zbJISzX-rE")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "8804129581"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyCnf6FUrGPZ0ZQ1sZE0OVebGec8b9ZXiNQ")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("Gemini API настроен")

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

# =========================================================
# BOT & WEB
# =========================================================

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
app = Flask(__name__)

@app.route("/")
def home():
    return "Бот работает! 🤖", 200

@app.route("/health")
def health():
    return "OK", 200

# =========================================================
# CONSTANTS
# =========================================================

WELCOME_TEXT = """
👋 Добро пожаловать!

Международные платежи для бизнеса.
Быстро. Надёжно. Без лишней бюрократии.
"""

RATES = {
    "USD": 92.50,
    "EUR": 100.20,
    "CNY": 12.80,
    "AED": 25.20
}

# =========================================================
# PERSISTENT MENU
# =========================================================

persistent_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🏠 Главное меню")]],
    resize_keyboard=True
)

# =========================================================
# INLINE KEYBOARDS
# =========================================================

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

# =========================================================
# DATABASE
# =========================================================

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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
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

def save_invoice_check(telegram_id, username, amount, currency):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO invoice_checks (telegram_id, username, amount, currency)
        VALUES (?, ?, ?, ?)
    """, (telegram_id, username, amount, currency))
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
# INVOICE PARSING
# =========================================================

async def analyze_invoice(file_bytes, filename):
    try:
        if not filename.lower().endswith('.pdf'):
            return None
        
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
        
        if not full_text:
            return None
        
        total_match = re.search(r'Total\s+([A-Za-z]+)\s+([\d,]+\.?\d*)', full_text, re.IGNORECASE)
        if not total_match:
            total_match = re.search(r'TOTAL\s+([A-Za-z]+)\s+([\d,]+\.?\d*)', full_text)
        
        if total_match:
            currency = total_match.group(1).upper()
            amount_str = total_match.group(2).replace(',', '')
            amount = float(amount_str)
            return {"amount": amount, "currency": currency}
        
        amount_match = re.search(r'([\d,]+\.?\d*)\s*(USD|EUR|CNY|AED|RUB)', full_text)
        if amount_match:
            amount_str = amount_match.group(1).replace(',', '')
            amount = float(amount_str)
            currency = amount_match.group(2).upper()
            return {"amount": amount, "currency": currency}
        
        return None
    except Exception as e:
        logger.error(f"INVOICE ERROR: {e}")
        return None

# =========================================================
# NEWS (AI + FALLBACK)
# =========================================================

async def get_fallback_news():
    today = datetime.now().strftime("%d.%m.%Y")
    news_items = [
        {"title": "Новые риски для бизнеса при использовании платежных агентов", "summary": "ЕС ввёл санкции против небанковских операторов международных расчётов.", "source": "РБК"},
        {"title": "ЦБ: участникам ВЭД разрешат любые операции с криптовалютами", "summary": "Законопроект о регулировании криптовалют в РФ вступит в силу с 1 июля 2026 года.", "source": "Финмаркет"},
        {"title": "ЕС запретил транзакции с пятью российскими банками", "summary": "В 19-й пакет санкций включены Альфа-банк, МТС банк.", "source": "Эксперт"},
        {"title": "Банк России актуализировал меры по борьбе с финансовым мошенничеством", "summary": "С 1 июля 2026 года банки должны полностью возвращать клиентам средства.", "source": "Банк России"},
        {"title": "Тенденции ВЭД 2026", "summary": "Эксперты обсудили эффективность и контроль в международной логистике.", "source": "РБК Компании"}
    ]
    news_text = f"📰 <b>Новости ВЭД и международных платежей</b>\n\nСводка за {today}\n\n" + "─" * 30 + "\n\n"
    for i, item in enumerate(news_items, 1):
        news_text += f"<b>{i}. {item['title']}</b>\n{item['summary']}\n<i>Источник: {item['source']}</i>\n\n" + "─" * 30 + "\n\n"
    news_text += "⚠️ <i>Новости из резервного источника (ИИ временно недоступен)</i>"
    return news_text

async def get_ved_news():
    if not GEMINI_API_KEY:
        return await get_fallback_news()
    
    today = datetime.now().strftime("%d.%m.%Y")
    
    prompt = f"""Ты — профессиональный финансовый аналитик. Найди 5 самых актуальных новостей по темам:
- ВЭД (внешнеэкономическая деятельность)
- международные платежи и переводы
- трансграничные расчеты
- валютное регулирование
- санкции и их влияние на платежи

Важные условия:
1. Новости должны быть за ПОСЛЕДНИЙ ДЕНЬ (за {today})
2. Упор на Россию, но можно добавить 1-2 мировые новости

Ответь строго в формате JSON:
{{
  "news": [
    {{"title": "Заголовок", "summary": "Краткое содержание (1-2 предложения)", "source": "Источник"}},
    ...
  ]
}}"""
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = await asyncio.wait_for(
            model.generate_content_async(prompt),
            timeout=10.0
        )
        
        result_text = response.text
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        
        if json_match:
            data = json.loads(json_match.group())
            news_items = data.get("news", [])
            
            if news_items:
                news_text = f"📰 <b>Новости ВЭД и международных платежей</b>\n\n"
                news_text += f"Актуальные новости за {today}\n\n"
                news_text += "─" * 30 + "\n\n"
                
                for i, item in enumerate(news_items, 1):
                    news_text += f"<b>{i}. {item['title']}</b>\n"
                    news_text += f"{item['summary']}\n"
                    news_text += f"<i>Источник: {item.get('source', 'Эксперт')}</i>\n\n"
                    news_text += "─" * 30 + "\n\n"
                
                news_text += "💡 <i>Новости обновляются каждый день через ИИ</i>"
                return news_text
        
        return await get_fallback_news()
        
    except asyncio.TimeoutError:
        logger.warning("Таймаут при получении новостей от Gemini")
        return await get_fallback_news()
    except Exception as e:
        logger.error(f"NEWS ERROR: {e}")
        return await get_fallback_news()

# =========================================================
# HANDLERS
# =========================================================

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(WELCOME_TEXT, reply_markup=persistent_menu)
    await message.answer("Главное меню:", reply_markup=main_menu)

@dp.message(F.text == "🏠 Главное меню")
async def main_menu_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(WELCOME_TEXT, reply_markup=persistent_menu)
    await message.answer("Главное меню:", reply_markup=main_menu)

@dp.callback_query(F.data == "fast")
async def fast(callback: CallbackQuery):
    text = """
⚡ Быстрые переводы

━━━━━━━━━━━━━━━

🌍 Переводы в 50+ стран
🏦 SWIFT / агентские схемы
⚡ Зачисление 2–3 дня
💱 Любые основные валюты
🔒 Надёжное сопровождение

━━━━━━━━━━━━━━━

Для оформления заявки нажмите /order
"""
    await callback.message.edit_text(text, reply_markup=back_keyboard)
    await callback.answer()

@dp.callback_query(F.data == "rates")
async def rates(callback: CallbackQuery):
    text = f"""
💰 Курсы валют

━━━━━━━━━━━━━━━

🇺🇸 USD — {RATES['USD']} ₽
🇪🇺 EUR — {RATES['EUR']} ₽
🇨🇳 CNY — {RATES['CNY']} ₽
🇦🇪 AED — {RATES['AED']} ₽

━━━━━━━━━━━━━━━

💡 Индивидуальный курс от 50 000 USD
📊 Для расчёта нажмите /calc
"""
    await callback.message.edit_text(text, reply_markup=back_keyboard)
    await callback.answer()

@dp.callback_query(F.data == "about")
async def about(callback: CallbackQuery):
    text = """
🏢 АО «Инновация и логика 2.0»

━━━━━━━━━━━━━━━

Финтех-решения для международного бизнеса.

📍 Москва, ул. Малая Семёновская, д. 3а, стр. 1
⏰ Пн-Пт 10:00–19:00

━━━━━━━━━━━━━━━

📞 +7 (495) 129-90-90
✉ info@il-2.ru
🌐 portal.il-2.ru

━━━━━━━━━━━━━━━

🌟 10 000+ успешных переводов
"""
    await callback.message.edit_text(text, reply_markup=back_keyboard)
    await callback.answer()

@dp.callback_query(F.data == "news")
async def news(callback: CallbackQuery):
    await callback.message.edit_text("📰 Загружаю новости...", reply_markup=back_keyboard)
    news_text = await get_ved_news()
    await callback.message.edit_text(news_text, reply_markup=back_keyboard)
    await callback.answer()

@dp.callback_query(F.data == "check_invoice")
async def check_invoice_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(InvoiceForm.waiting_for_file)
    await callback.message.edit_text(
        "📄 <b>Проверка инвойса</b>\n\nОтправьте PDF-файл.\n\nСистема автоматически проанализирует документ.",
        reply_markup=back_keyboard
    )
    await callback.answer()

@dp.message(InvoiceForm.waiting_for_file, F.document)
async def process_invoice(message: Message, state: FSMContext):
    await message.answer("🔍 Анализирую документ...")
    try:
        file = await bot.get_file(message.document.file_id)
        downloaded = await bot.download_file(file.file_path)
        result = await analyze_invoice(downloaded.read(), message.document.file_name)
        username = f"@{message.from_user.username}" if message.from_user.username else str(message.from_user.id)
        
        if result:
            save_invoice_check(message.from_user.id, username, result["amount"], result["currency"])
            await bot.send_message(ADMIN_CHAT_ID, f"🆕 Новый инвойс\n\n👤 {username}\n💰 {result['amount']} {result['currency']}")
            await message.answer("✅ Инвойс получен.\n\nМенеджер свяжется с вами.")
        else:
            await bot.send_message(ADMIN_CHAT_ID, f"⚠️ Не удалось распознать PDF\n\n👤 {username}\n📎 {message.document.file_name}")
            await message.answer("⚠️ Не удалось распознать PDF.\n\nМенеджер проверит вручную.")
    except Exception as e:
        logger.error(f"INVOICE ERROR: {e}")
        await message.answer("❌ Ошибка обработки файла")
    await state.clear()

@dp.callback_query(F.data == "application")
async def application(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ApplicationForm.waiting_for_phone)
    await callback.message.answer(
        "📩 Оставить заявку\n\nШаг 1 из 3\n\nВведите телефон\nили нажмите кнопку ниже 👇",
        reply_markup=contact_keyboard
    )
    await callback.answer()

@dp.message(ApplicationForm.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else message.text.strip()
    await state.update_data(phone=phone)
    await state.set_state(ApplicationForm.waiting_for_name)
    await message.answer("Введите ваше имя:", reply_markup=ReplyKeyboardRemove())

@dp.message(ApplicationForm.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(ApplicationForm.waiting_for_email)
    await message.answer("Введите email:")

@dp.message(ApplicationForm.waiting_for_email)
async def process_email(message: Message, state: FSMContext):
    data = await state.get_data()
    username = f"@{message.from_user.username}" if message.from_user.username else str(message.from_user.id)
    save_application(message.from_user.id, username, data["phone"], data["name"], message.text.strip())
    await bot.send_message(ADMIN_CHAT_ID, f"🆕 Новая заявка\n\n👤 {data['name']}\n📞 {data['phone']}\n✉ {message.text.strip()}")
    await message.answer("✅ Заявка отправлена.\n\nМенеджер скоро свяжется.", reply_markup=persistent_menu)
    await message.answer("Главное меню:", reply_markup=main_menu)
    await state.clear()

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery):
    await callback.message.edit_text(WELCOME_TEXT, reply_markup=main_menu)
    await callback.answer()

@dp.message(Command("calc"))
async def calc(message: Message):
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Формат: /calc 1000 USD\n\nДоступные валюты: USD, EUR, CNY, AED")
        return
    try:
        amount = float(parts[1])
        currency = parts[2].upper()
        if currency not in RATES:
            await message.answer(f"❌ Валюта {currency} не поддерживается")
            return
        result = amount / RATES[currency]
        await message.answer(f"💵 {amount:,.2f} ₽ = {result:,.2f} {currency}\nКурс: 1 {currency} = {RATES[currency]} ₽")
    except ValueError:
        await message.answer("❌ Ошибка: введите число")

@dp.message(Command("order"))
async def order(message: Message):
    await message.answer(
        "📝 Оформление перевода\n\n"
        "Для заявки отправьте:\n"
        "• сумму\n"
        "• валюту\n"
        "• страну\n\n"
        "Менеджер ответит в течение 15 минут.\n\n"
        "Или оставьте заявку через кнопку 📩 Оставить заявку"
    )

@dp.message()
async def unknown(message: Message):
    await message.answer("Используйте меню ниже 👇", reply_markup=persistent_menu)
    await message.answer("Главное меню:", reply_markup=main_menu)

# =========================================================
# RUN
# =========================================================

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
