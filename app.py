import os
import logging
import asyncio
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# ===== НАСТРОЙКИ =====
BOT_TOKEN = "8901177637:AAEeFWoKm8X9P9LHeHPDQL_R4zbJISzX-rE"
ADMIN_CHAT_ID = "8804129581"
# =====================

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = Flask(__name__)

# Клавиатура с красивыми иконками
menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Быстрые переводы")],
        [KeyboardButton(text="💰 Лучшие курсы")],
        [KeyboardButton(text="🏢 Для бизнеса и частных лиц")],
        [KeyboardButton(text="📞 Оставить заявку")],
        [KeyboardButton(text="ℹ️ О компании")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer(
        "🌍 <b>Международные платежи без границ</b>\n\n"
        "Выберите интересующий вас пункт меню:\n\n"
        "🚀 Быстрые переводы\n"
        "💰 Лучшие курсы\n"
        "🏢 Для бизнеса и частных лиц\n"
        "📞 Оставить заявку\n"
        "ℹ️ О компании",
        parse_mode="HTML",
        reply_markup=menu_keyboard
    )

@dp.message(lambda message: message.text == "🚀 Быстрые переводы")
async def option_1(message: types.Message):
    await message.answer(
        "🚀 <b>Быстрые переводы в любую страну</b>\n\n"
        "✅ Переводы зачисляются в течение 10-30 минут\n"
        "✅ Работаем с 50+ странами\n"
        "✅ Без скрытых комиссий\n\n"
        "💳 Минимальная сумма перевода: 500 USD\n\n"
        "Для оформления перевода нажмите /order",
        parse_mode="HTML"
    )

@dp.message(lambda message: message.text == "💰 Лучшие курсы")
async def option_2(message: types.Message):
    await message.answer(
        "💰 <b>Лучшие курсы обмена</b>\n\n"
        "📊 USD → RUB: 92.50\n"
        "📊 EUR → RUB: 100.20\n"
        "📊 CNY → RUB: 12.80\n"
        "📊 AED → RUB: 25.20\n\n"
        "💡 Индивидуальный курс при сумме от 10 000 USD\n\n"
        "Для расчёта точной суммы нажмите /calculate",
        parse_mode="HTML"
    )

@dp.message(lambda message: message.text == "🏢 Для бизнеса и частных лиц")
async def option_3(message: types.Message):
    await message.answer(
        "🏢 <b>Для бизнеса и частных лиц</b>\n\n"
        "🔹 <b>Бизнес клиентам:</b>\n"
        "   • Оплата поставщиков за рубежом\n"
        "   • Вывод прибыли из зарубежных маркетплейсов\n"
        "   • Зарплатные проекты для удалённых сотрудников\n\n"
        "🔹 <b>Частным клиентам:</b>\n"
        "   • Переводы родственникам за границу\n"
        "   • Оплата обучения и лечения за рубежом\n"
        "   • Конвертация сбережений\n\n"
        "Для консультации оставьте заявку через 📞 Оставить заявку",
        parse_mode="HTML"
    )

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
        "🏢 <b>О компании ИЛ 2.0</b>\n\n"
        "🌟 Наши партнеры доверили нам уже более 10 000 переводов.\n\n"
        "📞 <b>Контакты:</b>\n"
        "   • Телефон: <a href='tel:+79163579415'>8 916 357-94-15</a> (Артур)\n"
        "   • Сайт: <a href='https://portal.il-2.ru/me/orders'>portal.il-2.ru/me/orders</a>\n\n"
        "⏰ <b>Режим работы:</b>\n"
        "   • Пн-Пт: 09:00 - 19:00 МСК\n"
        "   • Сб-Вс: выходной\n\n"
        "💬 Для консультации оставьте заявку через 📞 Оставить заявку",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@dp.message(Command("order"))
async def order_command(message: types.Message):
    await message.answer(
        "📝 <b>Оформление перевода</b>\n\n"
        "Для оформления заявки отправьте:\n"
        "- Сумму перевода\n"
        "- Валюту отправления\n"
        "- Валюту получения\n"
        "- Страну получателя\n\n"
        "Наш менеджер свяжется с вами в течение 15 минут.",
        parse_mode="HTML"
    )

@dp.message(Command("calculate"))
async def calculate_command(message: types.Message):
    await message.answer(
        "🧮 <b>Расчёт платежа</b>\n\n"
        "Чтобы рассчитать точную сумму, отправьте:\n"
        "<code>/calc 1000 USD RUB</code>\n\n"
        "Пример: /calc 1000 USD RUB",
        parse_mode="HTML"
    )

@dp.message(lambda message: message.text and message.text.startswith("/calc"))
async def calculate_rate(message: types.Message):
    parts = message.text.split()
    if len(parts) != 4:
        await message.answer("❌ Неверный формат. Используйте: /calc 1000 USD RUB")
        return
    
    try:
        amount = float(parts[1])
        from_currency = parts[2].upper()
        to_currency = parts[3].upper()
        
        if from_currency not in ["USD", "EUR", "CNY", "AED"]:
            await message.answer("❌ Неподдерживаемая валюта. Доступны: USD, EUR, CNY, AED")
            return
        
        rates_to_rub = {"USD": 92.50, "EUR": 100.20, "CNY": 12.80, "AED": 25.20}
        
        if to_currency == "RUB":
            result = amount * rates_to_rub[from_currency]
            await message.answer(
                f"💰 <b>Результат расчёта:</b>\n\n"
                f"{amount:,.2f} {from_currency} = {result:,.2f} RUB\n\n"
                f"💡 Актуальный курс уточняйте у менеджера.",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Пока поддерживается только расчёт в RUB")
            
    except Exception as e:
        await message.answer("❌ Ошибка в расчёте. Проверьте формат.")

@dp.message(lambda message: message.contact)
async def get_contact(message: types.Message):
    contact = message.contact
    phone = contact.phone_number
    name = contact.first_name
    
    admin_msg = (
        f"🆕 <b>Новая заявка!</b>\n\n"
        f"👤 Имя: {name}\n"
        f"📱 Телефон: {phone}\n"
        f"🆔 ID: {message.from_user.id}\n"
        f"👤 Username: @{message.from_user.username if message.from_user.username else 'Нет'}"
    )
    await bot.send_message(ADMIN_CHAT_ID, admin_msg, parse_mode="HTML")
    
    await message.answer(
        "✅ <b>Заявка принята!</b>\n\n"
        "Менеджер свяжется с вами в ближайшее время.\n\n"
        "А пока можете ознакомиться с услугами в главном меню 👇",
        parse_mode="HTML",
        reply_markup=menu_keyboard
    )

@dp.message()
async def unknown(message: types.Message):
    await message.answer(
        "❌ Неизвестная команда\n\n"
        "Используйте кнопки меню или отправьте /start",
        reply_markup=menu_keyboard
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
