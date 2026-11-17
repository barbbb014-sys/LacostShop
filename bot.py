import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, CallbackQuery, LabeledPrice, PreCheckoutQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from dotenv import load_dotenv
from db import init_db, create_order, set_order_paid, get_user_orders
from supplier import deliver_stars

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not TOKEN:
    raise RuntimeError("Укажи BOT_TOKEN в файле .env")

logging.basicConfig(level=logging.INFO)
bot = Bot(TOKEN)
dp = Dispatcher()

# Цены оставлены такими, как согласовали. Это цены в рублях для внешней витрины.
# Внутри Telegram цифровые товары должны оплачиваться в XTR (Telegram Stars).
# Поэтому ниже цены XTR являются временными демонстрационными значениями 1:1.
# Перед запуском замени их на корректные цены в XTR и проверь правила Telegram.
CATALOG = {
    50: 75,
    100: 145,
    250: 350,
    500: 690,
    1000: 1350,
    2500: 3300,
    5000: 6500,
}

def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Купить звёзды", callback_data="catalog")],
        [InlineKeyboardButton(text="📦 Мои заказы", callback_data="orders")],
        [InlineKeyboardButton(text="🆘 Поддержка", url="https://t.me/USERNAME_SUPPORT")]
    ])

def catalog_keyboard():
    rows = []
    for amount, rub_price in CATALOG.items():
        rows.append([InlineKeyboardButton(
            text=f"{amount} ⭐ — {rub_price} ₽",
            callback_data=f"buy:{amount}"
        )])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "🖤 <b>LacostShop</b> ⭐\n\n"
        "Добро пожаловать! Выберите действие:",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "home")
async def home(call: CallbackQuery):
    await call.message.edit_text(
        "🖤 <b>LacostShop</b> ⭐\n\nВыберите действие:",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "catalog")
async def catalog(call: CallbackQuery):
    await call.message.edit_text(
        "⭐ <b>Каталог Telegram Stars</b>\nВыберите пакет:",
        reply_markup=catalog_keyboard(),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("buy:"))
async def buy(call: CallbackQuery):
    amount = int(call.data.split(":")[1])
    if amount not in CATALOG:
        await call.answer("Такого товара нет.", show_alert=True)
        return

    # ВАЖНО: Telegram Stars (XTR) — единица оплаты внутри Telegram.
    # Это демонстрационная конвертация 1 рубль = 1 XTR, НЕ реальный курс.
    # Настрой правильную цену XTR до включения платежей.
    xtr_amount = CATALOG[amount]
    order_id = create_order(
        user_id=call.from_user.id,
        username=call.from_user.username or "",
        stars_amount=amount,
        price_rub=CATALOG[amount],
        price_xtr=xtr_amount
    )

    await bot.send_invoice(
        chat_id=call.from_user.id,
        title=f"{amount} Telegram Stars",
        description=f"Заказ #{order_id} в LacostShop",
        payload=f"lacost:{order_id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"{amount} Stars", amount=xtr_amount)],
        start_parameter=f"lacost-{order_id}"
    )
    await call.answer()

@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    if not payload.startswith("lacost:"):
        return
    order_id = int(payload.split(":")[1])
    set_order_paid(order_id, payment.telegram_payment_charge_id)

    # Автовыдача включится после подключения реального поставщика с API.
    result = await deliver_stars(
        telegram_username=message.from_user.username or "",
        stars_amount=None,
        order_id=order_id
    )

    if result.get("ok"):
        await message.answer(
            f"✅ Оплата получена!\nЗаказ #{order_id} передан на выдачу."
        )
    else:
        await message.answer(
            f"✅ Оплата получена!\n"
            f"Заказ #{order_id} ожидает автоматической выдачи.\n"
            "Если выдача задерживается, напишите в поддержку."
        )
        if ADMIN_ID:
            await bot.send_message(
                ADMIN_ID,
                f"⚠️ Заказ #{order_id} оплачен, но поставщик ещё не подключён."
            )

@dp.callback_query(F.data == "orders")
async def orders(call: CallbackQuery):
    rows = get_user_orders(call.from_user.id)
    if not rows:
        text = "У вас пока нет заказов."
    else:
        text = "📦 <b>Ваши заказы:</b>\n\n" + "\n".join(
            f"#{r['id']} — {r['stars_amount']} ⭐ — {r['status']}"
            for r in rows
        )
    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="home")]
        ]),
        parse_mode="HTML"
    )
    await call.answer()

@dp.message(CommandStart())
async def duplicate_start(message: Message):
    pass

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
