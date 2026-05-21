@dp.message(Command("calc"))
async def calc(message: Message):
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer(
            "📐 <b>Формат расчёта:</b>\n\n"
            "<code>/calc 1000 USD</code>\n\n"
            "💰 Пример: /calc 1500 EUR\n"
            "💱 Доступные валюты: USD, EUR, CNY, AED",
            parse_mode="HTML"
        )
        return
    
    try:
        amount = float(parts[1])
        currency = parts[2].upper()
        
        if currency not in RATES:
            await message.answer(
                f"❌ Валюта <b>{currency}</b> не поддерживается\n\n"
                f"Доступные валюты: USD, EUR, CNY, AED",
                parse_mode="HTML"
            )
            return
        
        result = amount * RATES[currency]
        
        # Форматируем сумму с пробелами
        amount_str = f"{amount:,.2f}".replace(",", " ")
        result_str = f"{result:,.2f}".replace(",", " ")
        
        await message.answer(
            f"💵 <b>Результат конвертации</b>\n\n"
            f"{amount_str} {currency} = {result_str} ₽\n\n"
            f"💡 Курс: 1 {currency} = {RATES[currency]} ₽",
            parse_mode="HTML"
        )
        
    except ValueError:
        await message.answer(
            "❌ <b>Ошибка в сумме</b>\n\n"
            "Пример: <code>/calc 1000 USD</code>",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(e)
        await message.answer(
            "❌ <b>Ошибка расчёта</b>\n\n"
            "Проверьте формат: <code>/calc 1000 USD</code>",
            parse_mode="HTML"
        )
