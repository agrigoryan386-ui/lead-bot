import asyncio
import logging
import os
import threading
from flask import Flask

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = "YOUR_BOT_TOKEN"
ADMIN_CHAT_ID = 123456789

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

app = Flask(__name__)


# =========================================================
# MOCK DATA / PLACEHOLDERS
# =========================================================

RATES = {
    "USD": 92.5,
    "EUR": 100.2,
    "CNY": 12.8,
    "AED": 25.1
}

WELCOME_TEXT = "👋 Добро пожаловать в сервис международных переводов"


# =========================================================
# KEYBOARDS
# =========================================================

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="⚡ Переводы")],
        [KeyboardButton(text="💱 Курсы"), KeyboardButton(text="🏢 О нас")],
        [KeyboardButton(text="📰 Новости"), KeyboardButton(text="📩 Заявка")]
    ],
    resize_keyboard=True
)

persistent_menu = main_menu

back_keyboard = None

contact_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📞 Отправить контакт", request_contact=True)]],
    resize_keyboard=True
)


# =========================================================
# FSM STATES
# =========================================================

class ApplicationForm(StatesGroup):
    waiting_for_phone = State()
    waiting_for_name = State()
    waiting_for_email = State()


class InvoiceForm(StatesGroup):
    waiting_for_file = State()


# =========================================================
# MOCK FUNCTIONS (ЗАГЛУШКИ)
# =========================================================

async def analyze_invoice(file_bytes, filename):
    return {"amount": 1000, "currency": "USD"}


async def get_ved_news():
    return "📰 Новости временно недоступны"


def save_application(user_id, username, phone, name, email):
    logger.info(f"Saved application: {user_id}, {phone}, {name}, {email}")


def save_invoice_check(user_id, username, amount, currency):
    logger.info(f"Saved invoice: {user_id}, {amount} {currency}")


# =========================================================
# START
# =========================================================

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(WELCOME_TEXT)
    await message.answer("Главное меню:", reply_markup=main_menu)


# =========================================================
# MAIN MENU RESET
# =========================================================

@dp.message(F.text == "🏠 Главное меню")
async def main_menu_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(WELCOME_TEXT)
    await message.answer("Главное меню:", reply_markup=main_menu)


# =========================================================
# FAST PAYMENTS
# =========================================================

@dp.message(F.text == "⚡ Переводы")
async def fast(message: Message):
    await message.answer(
        "⚡ Переводы в 50+ стран\nSWIFT / агенты\n2–3 дня"
    )


# =========================================================
# RATES
# =========================================================

@dp.message(F.text == "💱 Курсы")
async def rates(message: Message):
    await message.answer(
        f"USD: {RATES['USD']}\nEUR: {RATES['EUR']}\nCNY: {RATES['CNY']}"
    )


# =========================================================
# ABOUT
# =========================================================

@dp.message(F.text == "🏢 О нас")
async def about(message: Message):
    await message.answer("Финтех компания. Переводы и ВЭД сопровождение.")


# =========================================================
# NEWS
# =========================================================

@dp.message(F.text == "📰 Новости")
async def news(message: Message):
    await message.answer("📰 Загружаю новости...")
    news_text = await get_ved_news()
    await message.answer(news_text)


# =========================================================
# APPLICATION FLOW
# =========================================================

@dp.message(F.text == "📩 Заявка")
async def application_start(message: Message, state: FSMContext):
    await state.set_state(ApplicationForm.waiting_for_phone)
    await message.answer("Введите телефон:")


@dp.message(ApplicationForm.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):

    phone = message.contact.phone_number if message.contact else message.text
    await state.update_data(phone=phone)

    await state.set_state(ApplicationForm.waiting_for_name)
    await message.answer("Введите имя:")


@dp.message(ApplicationForm.waiting_for_name)
async def process_name(message: Message, state: FSMContext):

    await state.update_data(name=message.text)
    await state.set_state(ApplicationForm.waiting_for_email)

    await message.answer("Введите email:")


@dp.message(ApplicationForm.waiting_for_email)
async def process_email(message: Message, state: FSMContext):

    data = await state.get_data()

    save_application(
        message.from_user.id,
        str(message.from_user.username),
        data["phone"],
        data["name"],
        message.text
    )

    await bot.send_message(
        ADMIN_CHAT_ID,
        f"Новая заявка:\n{data['name']}\n{data['phone']}\n{message.text}"
    )

    await message.answer("✅ Заявка отправлена")
    await state.clear()


# =========================================================
# INVOICE CHECK
# =========================================================

@dp.message(F.document)
async def invoice(message: Message, state: FSMContext):

    await message.answer("🔍 Обрабатываю файл...")

    file = await bot.get_file(message.document.file_id)
    downloaded = await bot.download_file(file.file_path)

    result = await analyze_invoice(downloaded.read(), message.document.file_name)

    save_invoice_check(
        message.from_user.id,
        str(message.from_user.username),
        result["amount"],
        result["currency"]
    )

    await message.answer(f"Инвойс: {result['amount']} {result['currency']}")


# =========================================================
# UNKNOWN
# =========================================================

@dp.message()
async def unknown(message: Message):
    await message.answer("Используй меню 👇")


# =========================================================
# FLASK (KEEP ALIVE)
# =========================================================

@app.route("/")
def home():
    return "BOT IS RUNNING"


def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


# =========================================================
# START BOT
# =========================================================

async def start_bot():
    await dp.start_polling(bot)


if __name__ == "__main__":

    logger.info("BOT STARTED")

    threading.Thread(target=run_flask, daemon=True).start()

    asyncio.run(start_bot())
