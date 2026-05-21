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

# Клавиатура главного меню — стильный минимализм
menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀  Быстрые переводы")],
        [KeyboardButton(text="💰  Лучшие курсы")],
        [KeyboardButton(text="📞  Оставить заявку")],
        [KeyboardButton(text="ℹ️  О компании")]
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите пункт меню 👇"
)

@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer(
        "🌍 <b>Международные платежи без границ</b>\n\n"
        "Выберите интересующий вас пункт меню:\n\n"
        "🚀  Быстрые переводы\n"
        "💰  Лучшие курсы\n"
        "📞  Оставить заявку\n"
        "ℹ️  О компании",
        parse_mode="HTML",
        reply_markup=menu_keyboard
    )

@dp.message(lambda message: message.text == "🚀  Быстрые переводы")
async def option_1(message: types.Message):
    await message.answer(
        "┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        "┃   🚀 <b>БЫСТРЫЕ ПЕРЕВОДЫ</b>   ┃\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        "✅ <b>Переводы зачисляются 2-3 дня</b>\n"
        "   до конечного получателя\n\n"
        "🌍 <b>Работаем с 50+ странами</b>\n\n"
        "🔒 <b>Без скрытых комиссий</b>\n\n"
        "💎 <b>При переводе более 50 000 USD</b>\n"
        "   возможны индивидуальные условия\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📝 <i>Для оформления перевода нажмите</i>\n"
        "➡️ <b>/order</b>",
        parse_mode="HTML"
    )

@dp.message(lambda message: message.text == "💰  Лучшие курсы")
async def option_2(message: types.Message):
    await message.answer(
        "┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        "┃   💰 <b>ЛУЧШИЕ КУРСЫ</b>     ┃\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        "┌─────────────────────────┐\n"
        "│ USD → RUB    │ 92.50 ₽  │\n"
        "│ EUR → RUB    │ 100.20 ₽ │\n"
        "│ CNY → RUB    │ 12.80 ₽  │\n"
        "│ AED → RUB    │ 25.20 ₽  │\n"
        "└─────────────────────────┘\n\n"
        "💡 <b>Индивидуальный курс</b>\n"
        "   при сумме от 150 000 USD\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🧮 <i>Для расчёта точной суммы</i>\n"
        "➡️ <b>/calculate</b>\n\n"
        "📊 <i>Пример:</i> <code>/calc 1000 USD RUB</code>",
        parse_mode="HTML"
    )

@dp.message(lambda message: message.text == "📞  Оставить заявку")
async def ask_phone(message: types.Message, state: FSMContext):
    await state.set_state(ApplicationForm.waiting_for_phone)
    await message.answer(
        "┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        "┃   📞 <b>ОСТАВИТЬ ЗАЯВКУ</b>   ┃\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        "📝 <b>Заполните форму:</b>\n\n"
        "▫️ Поле <b>1/3</b> — Номер телефона\n\n"
        "📱 <i>Пример: +7 916 357 94 15</i>\n"
        "   Или нажмите кнопку ниже 👇\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
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
        "✅ Номер телефона принят!\n\n"
        "▫️ Поле <b>2/3</b> — Введите ваше <b>имя</b>",
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
        "✅ Имя принято!\n\n"
        "▫️ Поле <b>3/3</b> — Введите ваш <b>email</b> (необязательно)\n\n"
        "Если не хотите указывать email, отправьте 'нет' или '-'",
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

@dp.message(lambda message: message.text == "ℹ️  О компании")
async def about_company(message: types.Message):
    await message.answer(
        "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        "┃   🏢 <b>АО «ИННОВАЦИЯ И ЛОГИКА 2.0»</b>   ┃\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        "📌 <b>О КОМПАНИИ</b>\n"
        "Финтех-компания, предоставляющая решения\n"
        "для сопровождения внешнеэкономической\n"
        "деятельности.\n\n"
        "✨ Оптимизация трансграничных платежей\n"
        "✨ Структурирование расчетов\n"
        "✨ Агентские и консультационные услуги\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📍 <b>АДРЕС</b>\n"
        "г. Москва, ул. Малая Семёновская,\n"
        "д. 3а, стр. 1\n\n"
        "⏰ <b>РЕЖИМ РАБОТЫ</b>\n"
        "Пн-Пт, с 10:00 до 19:00\n\n"
        "📞 <b>КОНТАКТЫ</b>\n"
        "Телефон: <a href='tel:+74951299090'>+7 (495) 129-90-90</a>\n"
        "Email: <a href='mailto:info@il-2.ru'>info@il-2.ru</a>\n"
        "Сайт: <a href='https://portal.il-2.ru/me/orders'>portal.il-2.ru/me/orders</a>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🌟 <b>10 000+</b> успешных переводов\n\n"
        "💬 <i>Для консультации оставьте заявку</i>\n"
        "➡️ <b>📞 Оставить заявку</b>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@dp.message(Command("order"))
async def order_command(message: types.Message):
    await message.answer(
        "┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        "┃   📝 <b>ОФОРМЛЕНИЕ ПЕРЕВОДА</b>  ┃\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        "✏️ Для оформления заявки отправьте:\n\n"
        "▫️ Сумму перевода\n"
        "▫️ Валюту отправления\n"
        "▫️ Валюту получения\n"
        "▫️ Страну получателя\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⏳ <i>Наш менеджер свяжется с вами</i>\n"
        "   <i>в течение 15 минут</i>",
        parse_mode="HTML"
    )

@dp.message(Command("calculate"))
async def calculate_command(message: types.Message):
    await message.answer(
        "┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        "┃   🧮 <b>РАСЧЁТ ПЛАТЕЖА</b>    ┃\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        "📐 Чтобы рассчитать точную сумму:\n\n"
        "<code>/calc 1000 USD RUB</code>\n\n"
        "📊 <b>Пример:</b>\n"
        "<code>/calc 15000 EUR RUB</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Доступные валюты:</i>\n"
        "   USD, EUR, CNY, AED",
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
