import os
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message, Update
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from fastapi import FastAPI, Request
import uvicorn
from openai import AsyncOpenAI

# --- Настройки ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Имя переменной может быть GROQ_API_KEY или OPENROUTER_API_KEY
AI_API_KEY = os.getenv("AI_API_KEY") 
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL", "https://localhost")

# --- Выбираем провайдера ---
# Для Groq (раскомментируйте эти строки):
client = AsyncOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=AI_API_KEY,
)
MODEL_NAME = "openai/gpt-oss-120b"  # или "llama-3.3-70b-versatile"

# Для OpenRouter (закомментируйте Groq и раскомментируйте это):
# client = AsyncOpenAI(
#     base_url="https://openrouter.ai/api/v1",
#     api_key=AI_API_KEY,
# )
# MODEL_NAME = "cohere/north-mini-code:free"  # или "baidu/ernie-5.5-flash-preview:free"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
app = FastAPI()

user_histories = {}

@dp.message(CommandStart())
async def start(msg: Message):
    await msg.answer("Привет! Я бот с искусственным интеллектом. Задай мне любой вопрос!")

@dp.message()
async def chat_with_ai(msg: Message):
    if not msg.text:
        await msg.answer("Пожалуйста, отправь текстовое сообщение.")
        return

    user_id = msg.from_user.id
    await msg.bot.send_chat_action(chat_id=msg.chat.id, action="typing")

    if user_id not in user_histories:
        user_histories[user_id] = []

    try:
        messages = [{"role": "system", "content": "Ты полезный ассистент."}]
        for role, text in user_histories[user_id]:
            messages.append({"role": role, "content": text})
        messages.append({"role": "user", "content": msg.text})

        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
        )
        
        answer = response.choices[0].message.content
        await msg.answer(answer)

        user_histories[user_id].append(("user", msg.text))
        user_histories[user_id].append(("assistant", answer))
        if len(user_histories[user_id]) > 10:
            user_histories[user_id] = user_histories[user_id][-10:]

    except Exception as e:
        await msg.answer(f"Ошибка: {e}")

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
