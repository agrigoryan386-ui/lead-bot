import os
import logging
import asyncio
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# ===== НАСТРОЙКИ =====
BOT_TOKEN = "8901177637:AAEeFWoKm8X9P9LHeHPDQL_R4zbJISzX-rE"
ADMIN_CHAT_ID = "8804129581"  # Твой Telegram ID
# =====================

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = Flask(__name__)

# Клавиатура главного меню
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💱 Курсы валют")],
        [KeyboardButton(text="📞 Оставить заявку")],
        [KeyboardButton(text="ℹ️ О компании")]
    ],
    resize_keyboard=True
)

# Примерные курсы (позже подключим реальный API)
RATES = {
    "USD": 92.50,
    "EUR": 100.20,
    "CNY": 12.80,
    "AED": 25.20
}

@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer(
        "🌍 <b>Международные платежи без границ</b>\n\n"
        "✅ Быстрые переводы в любую страну\n"
        "✅ Лучшие курсы обмена\n"
        "✅ Для бизнеса и частных лиц\n\n"
        "Выберите действие в меню:",
        parse_mode="HTML",
        reply_markup=main_keyboard
    )

@dp.message(lambda message: message.text == "💱 Курсы валют")
async def show_rates(message: types.Message):
    text = "📊 <b>Примерные курсы:</b>\n\n"
    for currency, rate in RATES.items():
        text += f"💵 {currency} → RUB: {rate:.2f}\n"
    text += "\n<i>Точный курс рассчитывается индивидуально</i>"
    await message.answer(text, parse_mode="HTML")

@dp.message(lambda message: message.text == "📞 Оставить заявку")
async def ask_contact(message: types.Message):
    contact_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить номер", request_contact=True)]],
        resize_keyboard=True
    )
    await message.answer(
        "📞 <b>Оставьте ваш номер телефона</b>\n\n"
        "Наш менеджер свяжется с вами в ближайшее время.",
        parse_mode="HTML",
        reply_markup=contact_keyboard
    )

@dp.message(lambda message: message.text == "ℹ️ О компании")
async def about_company(message: types.Message):
    await message.answer(
        "🏢 <b>О компании</b>\n\n"
        "Работаем с 2018 года.\n"
        "Провели более 5000 платежей.\n"
        "Надёжность и скорость — наши приоритеты.\n\n"
        "По вопросам: @your_manager",
        parse_mode="HTML"
    )

@dp.message(lambda message: message.contact)
async def get_contact(message: types.Message):
    contact = message.contact
    phone = contact.phone_number
    name = contact.first_name
    
    # Уведомление админу
    admin_msg = (
        f"🆕 <b>Новая заявка!</b>\n\n"
        f"👤 Имя: {name}\n"
        f"📱 Телефон: {phone}\n"
        f"🆔 ID: {message.from_user.id}\n"
        f"👤 Username: @{message.from_user.username if message.from_user.username else 'Нет'}"
    )
    await bot.send_message(ADMIN_CHAT_ID, admin_msg, parse_mode="HTML")
    
    # Ответ клиенту
    await message.answer(
        "✅ <b>Заявка принята!</b>\n\n"
        "Менеджер свяжется с вами в ближайшее время.",
        parse_mode="HTML",
        reply_markup=main_keyboard
    )

@dp.message()
async def unknown(message: types.Message):
    await message.answer(
        "❌ Неизвестная команда\nИспользуйте кнопки меню.",
        reply_markup=main_keyboard
    )

@app.route('/')
def home():
    return "Бот работает! 🤖", 200

@app.route('/health')
def health():
    return "OK", 200

async def main():
    await bot.send_message(ADMIN_CHAT_ID, "✅ Бот-лидогенератор запущен!")
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    import threading
    port = int(os.environ.get('PORT', 8080))
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port), daemon=True)
    flask_thread.start()
    asyncio.run(main())