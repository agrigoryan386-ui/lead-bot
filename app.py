import os
import logging
import asyncio
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ===== НАСТРОЙКИ =====
BOT_TOKEN = "8901177637:AAEeFWoKm8X9P9LHeHPDQL_R4zbJISzX-rE"
ADMIN_CHAT_ID = "8804129581"
# =====================

logging.basicConfig(level=logging.INFO)

storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)
app = Flask(__name__)

# Состояния для формы заявки
class ApplicationForm(StatesGroup):
    waiting_for_phone = State()
    waiting_for_name = State()
    waiting_for_email = State()

# Клавиатура главного меню
menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Быстрые переводы")],
        [KeyboardButton(text="💰 Лучшие курсы")],
        [KeyboardButton(text="📞 Оставить заявку")],
        [KeyboardButton(text="ℹ️ О компании")]
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите пункт меню 👇"
)

@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer(
        "🌍 <b>Международные платежи без границ</b>\n\n"
        "Выберите интересующий вас пункт меню 👇",
        parse_mode="HTML",
        reply_markup=menu_keyboard
    )

@dp.message(lambda message: message.text == "🚀 Быстрые переводы")
async def option_1(message: types.Message):
    await message.answer(
        "✨ * * * Б Ы С Т Р Ы Е   П Е Р Е В О Д Ы * * * ✨\n\n"
        "▫️ Переводы зачисляются <b>2-3 дня</b> до конечного получателя\n"
        "▫️ Работаем с <b>50+ странами</b>\n"
        "▫️ <b>Без скрытых комиссий</b>\n"
        "▫️ При переводе <b>более 50 000 USD</b> — индивидуальные условия\n\n"
        "────────────────────────────────\n"
        "📝 <i>Для оформления перевода нажмите</i> <b>/order</b>",
        parse_mode="HTML"
    )

@dp.message(lambda message: message.text == "💰 Лучшие курсы")
async def option_2(message: types.Message):
    await message.answer(
        "✨ * * * Л У Ч Ш И Е   К У Р С Ы * * * ✨\n\n"
        "<b>USD → RUB</b> — 92.50 ₽\n"
        "<b>EUR → RUB</b> — 100.20 ₽\n"
        "<b>CNY → RUB</b> — 12.80 ₽\n"
        "<b>AED → RUB</b> — 25.20 ₽\n\n"
        "💡 <b>Индивидуальный курс</b> при сумме от <b>150 000 USD</b>\n\n"
        "────────────────────────────────\n"
        "🧮 <i>Для расчёта точной суммы</i> <b>/calculate</b>\n"
        "📊 <i>Пример:</i> <code>/calc 1000 USD RUB</code>",
        parse_mode="HTML"
    )

@dp.message(lambda message: message.text == "📞 Оставить заявку")
async def ask_phone(message: types.Message, state: FSMContext):
    await state.set_state(ApplicationForm.waiting_for_phone)
    await message.answer(
        "✨ * * * О С Т А В И Т Ь   З А Я В К У * * * ✨\n\n"
        "<b>Шаг 1/3</b> — Введите ваш <b>номер телефона</b>\n\n"
        "📱 <i>Пример: +7 916 357 94 15</i>\n"
        "Или нажмите кнопку «Отправить номер» 👇",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📱 Отправить номер", request_contact=True)]],
            resize_keyboard=True
        )
    )

@dp.message(ApplicationForm.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text.strip()
    
    await state.update_data(phone=phone)
    await state.set_state(ApplicationForm.waiting_for_name)
    await message.answer(
        "✅ <b>Номер телефона принят!</b>\n\n"
        "<b>Шаг 2/3</b> — Введите ваше <b>имя</b>",
        parse_mode="HTML",
        reply_markup=menu_keyboard
    )

@dp.message(ApplicationForm.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Имя слишком короткое. Введите полное имя:")
        return
    
    await state.update_data(name=name)
    await state.set_state(ApplicationForm.waiting_for_email)
    await message.answer(
        "✅ <b>Имя принято!</b>\n\n"
        "<b>Шаг 3/3</b> — Введите ваш <b>email</b> <i>(необязательно)</i>\n\n"
        "Если не хотите указывать email, отправьте <b>«нет»</b> или <b>«-»</b>",
        parse_mode="HTML"
    )

@dp.message(ApplicationForm.waiting_for_email)
async def process_email(message: types.Message, state: FSMContext):
    email = message.text.strip()
    if email.lower() in ["нет", "-", "skip", "пропустить"]:
        email = "Не указан"
    
    await state.update_data(email=email)
    data = await state.get_data()
    
    phone = data.get('phone')
    name = data.get('name')
    
    admin_msg = (
        f"🆕 <b>НОВАЯ ЗАЯВКА!</b>\n\n"
        f"👤 <b>Имя:</b> {name}\n"
        f"📱 <b>Телефон:</b> {phone}\n"
        f"📧 <b>Email:</b> {email}\n"
        f"🆔 <b>User ID:</b> {message.from_user.id}\n"
        f"👤 <b>Username:</b> @{message.from_user.username if message.from_user.username else 'Нет'}\n"
        f"🕒 <b>Время:</b> {message.date.strftime('%d.%m.%Y %H:%M:%S')}"
    )
    await bot.send_message(ADMIN_CHAT_ID, admin_msg, parse_mode="HTML")
    
    await state.clear()
    await message.answer(
        "✅ <b>Заявка успешно отправлена!</b>\n\n"
        "Наш менеджер свяжется с вами в ближайшее время.\n\n"
        "А пока можете ознакомиться с услугами в главном меню 👇",
        parse_mode="HTML",
        reply_markup=menu_keyboard
    )

@dp.message(lambda message: message.text == "ℹ️ О компании")
async def about_company(message: types.Message):
    await message.answer(
        "✨ * * * О   К О М П А Н И И * * * ✨\n\n"
        "<b>АО «Инновация и логика 2.0»</b>\n"
        "Финтех-компания, предоставляющая решения\n"
        "для сопровождения внешнеэкономической деятельности.\n\n"
        "▫️ Оптимизация трансграничных платежей\n"
        "▫️ Структурирование расчетов\n"
        "▫️ Агентские и консультационные услуги\n\n"
        "────────────────────────────────\n"
        "<b>📍 АДРЕС</b>\n"
        "г. Москва, ул. Малая Семёновская, д. 3а, стр. 1\n\n"
        "<b>⏰ РЕЖИМ РАБОТЫ</b>\n"
        "Пн-Пт, с 10:00 до 19:00\n\n"
        "<b>📞 КОНТАКТЫ</b>\n"
        "Телефон: <a href='tel:+74951299090'>+7 (495) 129-90-90</a>\n"
        "Email: <a href='mailto:info@il-2.ru'>info@il-2.ru</a>\n"
        "Сайт: <a href='https://portal.il-2.ru/me/orders'>portal.il-2.ru/me/orders</a>\n\n"
        "────────────────────────────────\n"
        "🌟 <b>10 000+</b> успешных переводов\n\n"
        "💬 <i>Для консультации оставьте заявку</i> <b>📞 Оставить заявку</b>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@dp.message(Command("order"))
async def order_command(message: types.Message):
    await message.answer(
        "✨ * * * О Ф О Р М Л Е Н И Е   П Е Р Е В О Д А * * * ✨\n\n"
        "<b>Для оформления заявки отправьте:</b>\n\n"
        "▫️ Сумму перевода\n"
        "▫️ Валюту отправления\n"
        "▫️ Валюту получения\n"
        "▫️ Страну получателя\n\n"
        "────────────────────────────────\n"
        "⏳ <i>Наш менеджер свяжется с вами в течение 15 минут</i>",
        parse_mode="HTML"
    )

@dp.message(Command("calculate"))
async def calculate_command(message: types.Message):
    await message.answer(
        "✨ * * * Р А С Ч Ё Т   П Л А Т Е Ж А * * * ✨\n\n"
        "<b>Чтобы рассчитать точную сумму, отправьте:</b>\n\n"
        "<code>/calc 1000 USD RUB</code>\n\n"
        "<b>📊 Пример:</b>\n"
        "<code>/calc 15000 EUR RUB</code>\n\n"
        "────────────────────────────────\n"
        "💡 <i>Доступные валюты:</i> USD, EUR, CNY, AED",
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
                f"💡 <i>Актуальный курс уточняйте у менеджера.</i>",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Пока поддерживается только расчёт в RUB")
            
    except Exception as e:
        await message.answer("❌ Ошибка в расчёте. Проверьте формат.")

@dp.message()
async def unknown(message: types.Message):
    await message.answer(
        "❌ <b>Неизвестная команда</b>\n\n"
        "Используйте кнопки меню или отправьте /start",
        parse_mode="HTML",
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
