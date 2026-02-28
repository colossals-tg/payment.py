import logging
import aiohttp
from flask import Flask, request, jsonify
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import threading
import asyncio

BOT_TOKEN = "7545528821:AAH8vM7R3VitO6sinXImnU079-gRlRgoDL4"
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI3ZGY0MzZlNS1lNWM4LTQxOGYtYmI0YS1hYWI3YWZmNjA1NjciLCJleHAiOjIwODc3NTY0OTYsImlzcyI6IkF1dGhIdWIiLCJhdWQiOiJSZXNvdXJjZXMifQ.4uiefVsmWLZ2Ciepve93lRrCPTWVYC37J3VP_rtMWxI"
BUSINESS_ID = "7df436e5-e5c8-418f-bb4a-aab7aff60567"
BASE_URL = "https://prod-payments-api.forebit.io"
WEBHOOK_URL = "https://payment-py.onrender.com/webhook"

logging.basicConfig(level=logging.INFO)

app_flask = Flask(__name__)
telegram_app = Application.builder().token(BOT_TOKEN).build()

payment_users = {}
user_state = {}

COINS = [
    "BITCOIN","ETHEREUM","LITECOIN","BITCOIN_CASH","ETH_USD_COIN",
    "ETH_TETHER","MONERO","BNB","ETH_DAI","ETH_UNISWAP","ETH_MATIC",
    "ETH_SHIBA_INU","ETH_APE_COIN","ETH_CRONOS","ETH_BUSD","TRON",
    "TRX_TETHER","TRX_USD_C","SOLANA","SOL_TETHER","SOL_USD_COIN","TON"
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Create Payment", callback_data="create")]]
    await update.message.reply_text("Crypto Payment Bot", reply_markup=InlineKeyboardMarkup(keyboard))

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "create":
        keyboard = [[InlineKeyboardButton(c, callback_data=f"coin_{c}")] for c in COINS]
        await query.message.edit_text("Select Coin:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("coin_"):
        coin = query.data.split("_", 1)[1]
        user_state[query.from_user.id] = {"coin": coin}
        await query.message.edit_text(f"{coin}\nEnter amount:")

async def amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id not in user_state:
        return

    try:
        amount = float(update.message.text)
    except:
        await update.message.reply_text("Invalid amount")
        return

    coin = user_state[user_id]["coin"]
    payment = await create_payment(amount, coin, user_id)

    if payment:
        await update.message.reply_text(f"{payment['url']}")

async def create_payment(amount, coin, user_id):
    url = f"{BASE_URL}/v1/businesses/{BUSINESS_ID}/payments"

    payload = {
        "currency": "USD",
        "amount": amount,
        "notifyUrl": WEBHOOK_URL,
        "metadata": {"userId": str(user_id)},
        "paymentMethods": {"FOREBIT_CRYPTO": [coin]}
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as res:
            if res.status == 200:
                data = await res.json()
                payment_users[data["data"]["id"]] = user_id
                return data["data"]
            return None

@app_flask.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    payment = data.get("data", {})
    payment_id = payment.get("id")
    status = payment.get("status")

    user_id = payment_users.get(payment_id) or payment.get("metadata", {}).get("userId")

    if user_id:
        asyncio.run(telegram_app.bot.send_message(chat_id=int(user_id), text=f"{status}"))

    return jsonify({"ok": True})

def run_flask():
    app_flask.run(host="0.0.0.0", port=5000)

async def main():
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CallbackQueryHandler(button))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, amount_handler))

    threading.Thread(target=run_flask).start()

    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.updater.start_polling()
    await telegram_app.updater.idle()

if __name__ == "__main__":
    asyncio.run(main())
