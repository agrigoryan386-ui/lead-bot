import os
import re
import asyncio
import logging
import sqlite3
import aiohttp
from datetime import datetime, timedelta

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
# FSM для заявки
# ----------------------------

class ApplicationForm(StatesGroup):
    waiting_for_phone = State()
    waiting_for_name  = State()
    waiting_for_email = State()

# ----------------------------
# FSM для калькулятора
# ----------------------------

class CalculatorForm(StatesGroup):
    waiting_for_amount = State()
    waiting_for_currency = State()

# ----------------------------
# Функция для получения новостей ВЭД
# ----------------------------

async def get_ved_news():
    """
    Получает актуальные новости по теме ВЭД и международных платежей
    В данном случае используем локальную базу актуальных новостей из поиска
    """
    today = datetime.now().strftime("%d.%m.%Y")
    
    # Актуальные новости на основе данных из поиска (19-20 мая 2026)
    news_items = [
        {
            "title": "99% расчётов РФ–Китай в рублях и юанях",
            "summary": "Доля национальных валют во взаимной торговле достигла рекордных 99%. Происходит перестройка всей логистики международных платежей, бизнесу теперь нужно управлять не валютой, а маршрутом денег.",
            "source": "РБК"
        },
        {
            "title": "ЕС ввёл санкции против платежных агентов",
            "summary": "20-й пакет санкций ЕС впервые затронул небанковских операторов международных расчётов. Механизмы неттинга и клиринга больше не гарантируют защиту от санкций.",
            "source": "РБК"
        },
        {
            "title": "Доля рубля в экспорте РФ достигла рекордных 64,9%",
            "summary": "В марте 2026 года доля рубля в экспортных расчётах обновила максимум. Одновременно снижается доля валют дружественных стран.",
            "source": "Интерфакс"
        },
        {
            "title": "Вектор на Восток: роль Ближнего Востока в ВЭД растёт",
            "summary": "На KazanForum 2026 эксперты отметили, что исламский мир становится ключевым направлением для российских внешнеторговых расчётов и инвестиций.",
            "source": "РБК"
        },
        {
            "title": "Новые правила валютного контроля с 2026 года",
            "summary": "Банки переходят на риск-ориентированный подход и автоматизированную проверку. ИИ-системы анализируют контракты за минуту.",
            "source": "РБК"
        }
    ]
    
    # Формируем текст новостной сводки
    news_text = f"📰 <b>Новости ВЭД и международных платежей</b>\n\n"
    news_text += f"Сводка за {today}\n\n"
    news_text += "─" * 30 + "\n\n"
    
    for i, item in enumerate(news_items, 1):
        news_text += f"<b>{i}. {item['title']}</b>\n"
        news_text += f"{item['summary']}\n"
        news_text += f"<i>Источник: {item['source']}</i>\n\n"
        news_text += "─" * 30 + "\n\n"
    
    news_text += "💡 <i>Актуальные курсы валют можно узнать в разделе «Курсы валют»</i>"
    
    return news_text

# ----------------------------
# Обработчики команд и колбэков
# ----------------------------

@dp.message(Command("start"))
async def start(message: Message):
    user_name = message.from_user.first_name
    
    text = (
        f"👋 Привет, {user_name}!\n\n"
        "Международные платежи для бизнеса.\n"
        "Быстро. Надёжно. Без лишней бюрократии."
    )
    await message.answer(text, reply_markup=main_menu)

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery):
    user_name = callback.from_user.first_name
    
    text = (
        f"👋 Привет, {user_name}!\n\n"
        "Международные платежи для бизнеса.\n"
        "Быстро. Надёжно. Без лишней бюрократии."
    )
    await callback.message.edit_text(text, reply_markup=main_menu)
    await callback.answer()

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

@dp.callback_query(F.data == "rates")
async def rates(callback: CallbackQuery):
    text = (
        "💰 Курсы валют\n\n"
        f"1 USD = {RATES['USD']} ₽\n"
        f"1 EUR = {RATES['EUR']} ₽\n"
        f"1 CNY = {RATES['CNY']} ₽\n"
        f"1 AED = {RATES['AED']} ₽\n\n"
        "💡 Индивидуальный курс при сумме от 150 000 USD\n\n"
        "Нажмите /calc для расчёта"
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard)
    await callback.answer()

@dp.callback_query(F.data == "about")
async def about(callback: CallbackQuery):
    text = (
        "🏢 АО «Инновация и логика 2.0»\n\n"
        "Финтех-компания, предоставляющая решения для сопровождения внешнеэкономической деятельности, включая организацию и оптимизацию трансграничных платежей, структурирование расчетов с иностранными контрагентами, а также агентские и консультационные услуги в рамках внешнеторговых операций.\n\n"
        "📌 Адрес:\n"
        "г. Москва, ул. Малая Семёновская, д. 3а, стр. 1\n\n"
        "⏰ Режим работы:\n"
        "Пн-Пт, с 10:00 до 19:00\n\n"
        "📞 Контакты:\n"
        "Телефон: <a href='tel:+74951299090'>+7 (495) 129-90-90</a>\n"
        "Email: <a href='mailto:info@il-2.ru'>info@il-2.ru</a>\n"
        "Сайт: <a href='https://portal.il-2.ru/me/orders'>portal.il-2.ru/me/orders</a>\n\n"
        "🌟 Наши партнеры доверили нам уже более 10 000 переводов."
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard)
    await callback.answer()

@dp.callback_query(F.data == "news")
async def news(callback: CallbackQuery):
    # Показываем индикатор загрузки
    await callback.message.edit_text(
        "📰 Загружаю актуальные новости ВЭД...\n\nПожалуйста, подождите.",
        reply_markup=back_keyboard
    )
    
    try:
        news_text = await get_ved_news()
        await callback.message.edit_text(news_text, reply_markup=back_keyboard)
    except Exception as e:
        logger.error(f"Ошибка при получении новостей: {e}")
        await callback.message.edit_text(
            "❌ Не удалось загрузить новости.\n\nПопробуйте позже.",
            reply_markup=back_keyboard
        )
    
    await callback.answer()

@dp.callback_query(F.data == "application")
async def application(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ApplicationForm.waiting_for_phone)
    await callback.message.answer(
        "📩 Оставить заявку\n\n"
        "Шаг 1 из 3 — номер телефона\n\n"
        "Введите номер в формате +79991234567\n"
        "или нажмите кнопку ниже 👇",
        reply_markup=contact_keyboard
    )
    await callback.answer()

# ----------------------------
# Обработчики заявки
# ----------------------------

@dp.message(ApplicationForm.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text.strip().replace(" ", "")

    if not re.match(PHONE_REGEX, phone):
        await message.answer("❌ Некорректный номер. Пример: +79991234567")
        return

    await state.update_data(phone=phone)
    await state.set_state(ApplicationForm.waiting_for_name)
    await message.answer("Шаг 2 из 3 — ваше имя\n\nВведите ваше имя:", reply_markup=ReplyKeyboardRemove())

@dp.message(ApplicationForm.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Введите корректное имя")
        return
    await state.update_data(name=name)
    await state.set_state(ApplicationForm.waiting_for_email)
    await message.answer("Шаг 3 из 3 — email\n\nВведите email или отправьте «нет»")

@dp.message(ApplicationForm.waiting_for_email)
async def process_email(message: Message, state: FSMContext):
    email_raw = message.text.strip()
    if email_raw.lower() in ("нет", "-", "skip"):
        email = "Не указан"
    else:
        if not re.match(EMAIL_REGEX, email_raw):
            await message.answer("❌ Некорректный email. Пример: name@domain.ru")
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
        "✅ Заявка отправлена.\n\nМенеджер свяжется с вами в ближайшее время.",
        reply_markup=ReplyKeyboardRemove()
    )
    await message.answer("Главное меню:", reply_markup=main_menu)

# ----------------------------
# ПОШАГОВЫЙ КАЛЬКУЛЯТОР
# ----------------------------

@dp.message(Command("calc"))
async def calc_start(message: Message, state: FSMContext):
    await state.set_state(CalculatorForm.waiting_for_amount)
    await message.answer(
        "💰 Калькулятор валют\n\n"
        "Введите сумму, которую хотите конвертировать:"
    )

@dp.message(CalculatorForm.waiting_for_amount)
async def calc_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(",", "."))
        await state.update_data(amount=amount)
        await state.set_state(CalculatorForm.waiting_for_currency)
        
        currency_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🇺🇸 USD (Доллар США)", callback_data="curr_USD")],
            [InlineKeyboardButton(text="🇪🇺 EUR (Евро)", callback_data="curr_EUR")],
            [InlineKeyboardButton(text="🇨🇳 CNY (Юань)", callback_data="curr_CNY")],
            [InlineKeyboardButton(text="🇦🇪 AED (Дирхам ОАЭ)", callback_data="curr_AED")],
            [InlineKeyboardButton(text="◀ Отмена", callback_data="calc_cancel")]
        ])
        
        await message.answer(
            f"Сумма: {amount:,.2f}\n\n"
            f"Выберите валюту, в которую хотите конвертировать:",
            reply_markup=currency_keyboard
        )
    except ValueError:
        await message.answer("❌ Ошибка: введите число")

@dp.callback_query(F.data.startswith("curr_"))
async def calc_currency(callback: CallbackQuery, state: FSMContext):
    currency_code = callback.data.split("_")[1]
    currency_names = {
        "USD": "Доллар США",
        "EUR": "Евро",
        "CNY": "Китайский юань",
        "AED": "Дирхам ОАЭ"
    }
    
    data = await state.get_data()
    amount = data.get("amount")
    
    if not amount:
        await state.clear()
        await callback.message.answer("❌ Сессия истекла. Начните заново: /calc")
        await callback.answer()
        return
    
    rate = RATES.get(currency_code)
    if not rate:
        await state.clear()
        await callback.message.answer("❌ Валюта не поддерживается")
        await callback.answer()
        return
    
    result = amount * rate
    
    amount_str = f"{amount:,.2f}".replace(",", " ")
    result_str = f"{result:,.2f}".replace(",", " ")
    
    await callback.message.edit_text(
        f"💵 Результат конвертации\n\n"
        f"{amount_str} {currency_names[currency_code]} = {result_str} ₽\n"
        f"Курс: 1 {currency_code} = {rate} ₽\n\n"
        f"Хотите выполнить новый расчёт? Нажмите /calc"
    )
    await state.clear()
    await callback.answer()

@dp.callback_query(F.data == "calc_cancel")
async def calc_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Расчёт отменён.\n\nДля нового расчёта нажмите /calc")
    await callback.answer()

# ----------------------------
# Оформление перевода
# ----------------------------

@dp.message(Command("order"))
async def order(message: Message):
    await message.answer(
        "📝 Оформление перевода\n\n"
        "Отправьте:\n"
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
    logger.info("Бот запущен")
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(start_bot())
