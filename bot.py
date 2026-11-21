import os
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message, Update
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from fastapi import FastAPI, Request
import uvicorn
from google import genai

# --- Настройки ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL", "https://localhost")

# Клиент Gemini
client = genai.Client(api_key=GEMINI_API_KEY)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
app = FastAPI()

# Хранилище истории диалогов
user_histories = {}

@dp.message(CommandStart())
async def start(msg: Message):
    await msg.answer("Привет! Я бот с искусственным интеллектом. Задай мне любой вопрос!")

@dp.message()
async def chat_with_gemini(msg: Message):
    if not msg.text:
        await msg.answer("Пожалуйста, отправь текстовое сообщение.")
        return

    user_id = msg.from_user.id
    await msg.bot.send_chat_action(chat_id=msg.chat.id, action="typing")

    if user_id not in user_histories:
        user_histories[user_id] = []

    try:
        # Вызов Gemini
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=f"История диалога:\n{user_histories[user_id]}\n\nПользователь: {msg.text}"
        )
        
        answer = response.text
        await msg.answer(answer)

        # Обновляем историю
        user_histories[user_id].append(f"Пользователь: {msg.text}")
        user_histories[user_id].append(f"Бот: {answer}")
        if len(user_histories[user_id]) > 10:
            user_histories[user_id] = user_histories[user_id][-10:]

    except Exception as e:
        await msg.answer(f"Ошибка: {e}")

# --- Webhook ---
@app.post("/webhook")
async def webhook(request: Request):
    update_data = await request.json()
    update = Update.model_validate(update_data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print("Вебхук установлен!")

@app.on_event("shutdown")
async def on_shutdown():
    await bot.delete_webhook()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
