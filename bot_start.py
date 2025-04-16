#!/usr/bin/env python
# ───────────────────────────────────────────────────────────────────
# Telegram‑бот бронювання столиків через webhook (Render Web Service)
# ───────────────────────────────────────────────────────────────────
import os
import json
import re
import logging
from datetime import datetime

from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
    ReplyKeyboardRemove, ContentType
)

# ------------------------------------------------------------------
# 1. Змінні середовища
# ------------------------------------------------------------------
BOT_TOKEN     = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
PUBLIC_URL    = os.getenv("PUBLIC_URL")           # https://<app>.onrender.com
PORT          = int(os.getenv("PORT", 8080))      # Render задає PORT

if not all([BOT_TOKEN, ADMIN_CHAT_ID, PUBLIC_URL]):
    raise RuntimeError(
        "Необхідно задати BOT_TOKEN, ADMIN_CHAT_ID та PUBLIC_URL у налаштуваннях!"
    )

# ------------------------------------------------------------------
# 2. Ініціалізація бота
# ------------------------------------------------------------------
bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ------------------------------------------------------------------
# 3. Машина станів
# ------------------------------------------------------------------
class BookingStates(StatesGroup):
    CONFIRM_DATA  = State()
    WAITING_PHONE = State()

# ------------------------------------------------------------------
# 4. Тимчасове сховище заявок
# ------------------------------------------------------------------
user_booking_data: dict[int, dict] = {}

# ------------------------------------------------------------------
# 5. Хендлери повідомлень
# ------------------------------------------------------------------
@dp.message_handler(commands=["start"], state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("🍽 Забронювати столик"))
    kb.add(KeyboardButton(
        "📕 Переглянути меню",
        web_app=WebAppInfo(url="https://gustouapp.com/menu")
    ))
    await message.answer(
        "Вітаємо в Telegram‑боті кальян‑бару GUSTOÚ💨\n"
        "Тут Ви можете:\n"
        "🍽 Забронювати столик\n"
        "📕 Переглянути меню",
        reply_markup=kb,
    )

@dp.message_handler(lambda m: m.text == "🍽 Забронювати столик", state="*")
async def cmd_book(message: types.Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton(
        "📲 Відкрити форму для бронювання",
        web_app=WebAppInfo(url="https://danza13.github.io/telegram-kalyan-bar-bot")
    ))
    kb.add(KeyboardButton("⬅️ Назад"))
    await message.answer("Оберіть дію:", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "⬅️ Назад", state="*")
async def cmd_back(message: types.Message, state: FSMContext):
    await cmd_start(message, state)

# --- приймаємо дані з WebApp --------------------------------------
@dp.message_handler(content_types=ContentType.WEB_APP_DATA, state="*")
async def handle_webapp(message: types.Message, state: FSMContext):
    try:
        data = json.loads(message.web_app_data.data)
    except Exception as e:
        logging.warning("JSON error: %s", e)
        return await message.answer("Помилка даних форми. Спробуйте ще раз.")

    place, datetime_raw, name, guests = (
        data.get("place"),
        data.get("datetime"),
        data.get("name"),
        data.get("guests"),
    )
    if not all([place, datetime_raw, name, guests]):
        return await message.answer("Деякі поля порожні. Спробуйте ще раз.")

    try:
        dt = datetime.strptime(datetime_raw, "%d.%m.%Y %H:%M")
        dt_str = dt.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        dt_str = datetime_raw

    user_booking_data[message.from_user.id] = {
        "place": place,
        "datetime_str": dt_str,
        "guests": guests,
        "name": name,
    }

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Далі"))
    edit_url = (
        "https://danza13.github.io/telegram-kalyan-bar-bot"
        f"?place={place}&datetime={datetime_raw}"
        f"&name={name}&guests={guests}"
    )
    kb.add(KeyboardButton("Редагувати", web_app=WebAppInfo(url=edit_url)))
    kb.add(KeyboardButton("Скасувати"))

    await message.answer(
        f"Перевірте дані:\n"
        f"🏠 {place}\n🕒 {dt_str}\n👥 {guests}\n📝 {name}\n\n"
        "Якщо все вірно — натисніть «Далі».",
        reply_markup=kb,
    )
    await BookingStates.CONFIRM_DATA.set()

@dp.message_handler(lambda m: m.text == "Скасувати",
                    state=[BookingStates.CONFIRM_DATA, BookingStates.WAITING_PHONE])
async def cmd_cancel(message: types.Message, state: FSMContext):
    user_booking_data.pop(message.from_user.id, None)
    await state.finish()
    await message.answer("Бронювання скасовано.", reply_markup=ReplyKeyboardRemove())
    await cmd_start(message, state)

@dp.message_handler(lambda m: m.text == "Далі", state=BookingStates.CONFIRM_DATA)
async def cmd_confirm(message: types.Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Поділитись контактом", request_contact=True))
    kb.add(KeyboardButton("Скасувати"))
    await BookingStates.WAITING_PHONE.set()
    await message.answer("Надішліть номер телефону або натисніть кнопку:", reply_markup=kb)

@dp.message_handler(content_types=[ContentType.CONTACT, ContentType.TEXT],
                    state=BookingStates.WAITING_PHONE)
async def cmd_phone(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    if uid not in user_booking_data:
        await state.finish()
        return await message.answer("Немає даних бронювання. Почніть з /start.")

    raw = message.contact.phone_number if message.contact else message.text
    digits = re.sub(r"\D+", "", raw)
    if len(digits) != 12 or not digits.startswith("380"):
        return await message.answer("Невірний номер. Формат: +380XXXXXXXXX")
    phone = "+" + digits

    data = user_booking_data[uid]
    data["phone"] = phone

    await bot.send_message(
        ADMIN_CHAT_ID,
        "📅 <b>Бронювання</b>\n"
        f"🏠 {data['place']}\n"
        f"🕒 {data['datetime_str']}\n"
        f"👥 {data['guests']}\n"
        f"📝 {data['name']}\n"
        f"📞 {phone}",
    )

    kb = ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("Готово"))
    await message.answer(
        "Дякуємо! Бронювання отримано ✅\n"
        "Адміністратор зв'яжеться з вами найближчим часом.",
        reply_markup=kb,
    )
    await state.finish()

@dp.message_handler(lambda m: m.text == "Готово", state="*")
async def cmd_done(message: types.Message, state: FSMContext):
    await cmd_start(message, state)

# ------------------------------------------------------------------
# 6. aiohttp‑сервер + webhook
# ------------------------------------------------------------------
WEBHOOK_PATH = f"/telegram/{BOT_TOKEN}"
WEBHOOK_URL  = f"{PUBLIC_URL}{WEBHOOK_PATH}"

app = web.Application()

async def telegram_webhook(request: web.Request):
    """Отримуємо апдейт від Telegram."""
    try:
        data = await request.json()
    except Exception:
        return web.Response(status=400)

    # --- важливо: встановити контекст bot / dispatcher ---
    Bot.set_current(bot)
    Dispatcher.set_current(dp)

    update = types.Update(**data)
    await dp.process_update(update)
    return web.Response(text="OK")

async def healthcheck(request: web.Request):
    return web.Response(text="OK")

app.router.add_post(WEBHOOK_PATH, telegram_webhook)
app.router.add_get("/", healthcheck)

# ------------------------------------------------------------------
# 7. Запуск та життєвий цикл
# ------------------------------------------------------------------
async def on_startup(app_: web.Application):
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    logging.info("Webhook встановлено → %s", WEBHOOK_URL)

async def on_cleanup(app_: web.Application):
    await bot.delete_webhook()
    await storage.close()
    await storage.wait_closed()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Реєструємо колбеки старту / завершення
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    web.run_app(app, host="0.0.0.0", port=PORT)
