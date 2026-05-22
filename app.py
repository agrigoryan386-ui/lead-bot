    except Exception as e:

        logger.error(f"NEWS ERROR: {e}")

        return "❌ Не удалось загрузить новости"


# =========================================================
# START
# =========================================================

@dp.message(Command("start"))
async def start(message: Message):

    await message.answer(
        WELCOME_TEXT,
        reply_markup=persistent_menu
    )

    await message.answer(
        "Главное меню:",
        reply_markup=main_menu
    )


# =========================================================
# MAIN MENU BUTTON
# =========================================================

@dp.message(F.text == "🏠 Главное меню")
async def main_menu_handler(
    message: Message,
    state: FSMContext
):

    await state.clear()

    await message.answer(
        WELCOME_TEXT,
        reply_markup=persistent_menu
    )

    await message.answer(
        "Главное меню:",
        reply_markup=main_menu
    )


# =========================================================
# FAST PAYMENTS
# =========================================================

@dp.callback_query(F.data == "fast")
async def fast(callback: CallbackQuery):

    text = """
<b>⚡ Международный перевод</b>

━━━━━━━━━━━━━━━

🌍 Переводы в 50+ стран

🏦 SWIFT / агентские схемы

⚡ Зачисление 2–3 дня

💱 Любые основные валюты

🔒 Надёжное сопровождение

━━━━━━━━━━━━━━━

Для оформления заявки:
@your_manager
"""

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard
    )

    await callback.answer()


# =========================================================
# RATES
# =========================================================

@dp.callback_query(F.data == "rates")
async def rates(callback: CallbackQuery):

    text = f"""
<b>💱 Курсы валют</b>

━━━━━━━━━━━━━━━

🇺🇸 USD — {RATES['USD']} ₽

🇪🇺 EUR — {RATES['EUR']} ₽

🇨🇳 CNY — {RATES['CNY']} ₽

🇦🇪 AED — {RATES['AED']} ₽

━━━━━━━━━━━━━━━

💡 Индивидуальный курс
от 50 000 USD
"""

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard
    )

    await callback.answer()


# =========================================================
# ABOUT
# =========================================================

@dp.callback_query(F.data == "about")
async def about(callback: CallbackQuery):

    text = """
<b>🏢 INNOVATION & LOGIC</b>

━━━━━━━━━━━━━━━

Финтех-решения
для международного бизнеса.

📍 Москва

🌍 Международные переводы

📄 ВЭД сопровождение

🏦 SWIFT платежи

━━━━━━━━━━━━━━━

📞 +7 (495) 129-90-90

✉ info@il-2.ru
"""

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard
    )

    await callback.answer()


# =========================================================
# NEWS
# =========================================================

@dp.callback_query(F.data == "news")
async def news(callback: CallbackQuery):

    await callback.message.edit_text(
        "📰 Загружаю новости...",
        reply_markup=back_keyboard
    )

    news_text = await get_ved_news()

    await callback.message.edit_text(
        news_text,
        reply_markup=back_keyboard
    )

    await callback.answer()


# =========================================================
# INVOICE CHECK
# =========================================================

@dp.callback_query(F.data == "check_invoice")
async def check_invoice_start(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.set_state(
        InvoiceForm.waiting_for_file
    )

    await callback.message.edit_text(
        """
<b>📄 Проверка инвойса</b>

━━━━━━━━━━━━━━━

Отправьте PDF файл.

Система автоматически
проанализирует документ.
""",
        reply_markup=back_keyboard
    )

    await callback.answer()


@dp.message(
    InvoiceForm.waiting_for_file,
    F.document
)
async def process_invoice(
    message: Message,
    state: FSMContext
):

    await message.answer(
        "🔍 Анализирую документ..."
    )

    try:

        file = await bot.get_file(
            message.document.file_id
        )

        downloaded = await bot.download_file(
            file.file_path
        )

        result = await analyze_invoice(
            downloaded.read(),
            message.document.file_name
        )

        username = (
            f"@{message.from_user.username}"
            if message.from_user.username
            else str(message.from_user.id)
        )

        if result:

            save_invoice_check(
                message.from_user.id,
                username,
                result["amount"],
                result["currency"]
            )

            await bot.send_message(
                ADMIN_CHAT_ID,
                f"""
🆕 Новый инвойс

👤 {username}

💰 {result['amount']} {result['currency']}
"""
            )

            await message.answer(
                """
✅ Инвойс получен.

Менеджер свяжется с вами.
"""
            )

        else:

            await message.answer(
                """
⚠ Не удалось распознать PDF.

Менеджер проверит вручную.
"""
            )

    except Exception as e:

        logger.error(f"INVOICE ERROR: {e}")

        await message.answer(
            "❌ Ошибка обработки файла"
        )

    await state.clear()


# =========================================================
# APPLICATION
# =========================================================

@dp.callback_query(F.data == "application")
async def application(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.set_state(
        ApplicationForm.waiting_for_phone
    )

    await callback.message.answer(
        """
📩 Оставить заявку

Шаг 1 из 3

Введите телефон
или нажмите кнопку ниже 👇
""",
        reply_markup=contact_keyboard
    )

    await callback.answer()


@dp.message(ApplicationForm.waiting_for_phone)
async def process_phone(
    message: Message,
    state: FSMContext
):

    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text.strip()

    await state.update_data(
        phone=phone
    )

    await state.set_state(
        ApplicationForm.waiting_for_name
    )

    await message.answer(
        "Введите ваше имя:"
    )


@dp.message(ApplicationForm.waiting_for_name)
async def process_name(
    message: Message,
    state: FSMContext
):

    await state.update_data(
        name=message.text.strip()
    )

    await state.set_state(
        ApplicationForm.waiting_for_email
    )

    await message.answer(
        "Введите email:"
    )


@dp.message(ApplicationForm.waiting_for_email)
async def process_email(
    message: Message,
    state: FSMContext
):

    data = await state.get_data()

    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else str(message.from_user.id)
    )

    save_application(
        message.from_user.id,
        username,
        data["phone"],
        data["name"],
        message.text.strip()
    )

    await bot.send_message(
        ADMIN_CHAT_ID,
        f"""
🆕 Новая заявка

👤 {data['name']}

📞 {data['phone']}

✉ {message.text.strip()}
"""
    )

    await message.answer(
        """
✅ Заявка отправлена.

Менеджер скоро свяжется.
"""
    )

    await state.clear()


# =========================================================
# BACK
# =========================================================

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery):

    await callback.message.edit_text(
        WELCOME_TEXT,
        reply_markup=main_menu
    )

    await callback.answer()


# =========================================================
# UNKNOWN
# =========================================================

@dp.message()
async def unknown(message: Message):

    await message.answer(
        "Используйте меню ниже 👇"
    )

    await message.answer(
        "Главное меню:",
        reply_markup=main_menu
    )


# =========================================================
# RUN
# =========================================================

async def start_bot():

    await dp.start_polling(
        bot,
        handle_signals=False
    )


def run_flask():

    port = int(
        os.environ.get("PORT", 8080)
    )

    app.run(
        host="0.0.0.0",
        port=port
    )


if __name__ == "__main__":

    import threading

    logger.info("BOT STARTED")

    threading.Thread(
        target=run_flask,
        daemon=True
    ).start()

    asyncio.run(
        start_bot()
    )
