import os
import logging
import re
import json
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
                           ReplyKeyboardRemove, ContentType)
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor

logging.basicConfig(level=logging.INFO)

# ===================================================================
# 1. Змінні оточення
# ===================================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")        # Токен бота
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # ID адміністратора

if not BOT_TOKEN:
    raise ValueError("У змінних оточення не знайдено BOT_TOKEN!")
if not ADMIN_CHAT_ID:
    raise ValueError("У змінних оточення не знайдено ADMIN_CHAT_ID!")

# ===================================================================
# 2. Ініціалізація бота
# ===================================================================
bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ===================================================================
# 3. Стан‑машина
# ===================================================================
class BookingStates(StatesGroup):
    CONFIRM_DATA = State()
    WAITING_PHONE = State()

# ===================================================================
# 4. Тимчасове сховище
# ===================================================================
user_booking_data: dict[int, dict] = {}

# ===================================================================
# 5. Хендлери
# ===================================================================

@dp.message_handler(commands=['start'], state='*')
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("🍽Забронювати столик"))
    kb.add(KeyboardButton(
        text="📕Переглянути меню",
        web_app=WebAppInfo(url="https://gustouapp.com/menu")
    ))
    await message.answer(
        "Вітаємо вас в Telegram‑боті кальян‑бар GUSTOÚ💨\n"
        "Тут Ви можете:\n"
        "🍽 Забронювати столик\n"
        "📕 Переглянути меню",
        reply_markup=kb
    )

@dp.message_handler(lambda m: m.text == "🍽Забронювати столик", state='*')
async def cmd_book_table(message: types.Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton(
        "📲Відкрити форму для бронювання",
        web_app=WebAppInfo(
            url="https://danza13.github.io/telegram-kalyan-bar-bot/index.html")
    ))
    kb.add(KeyboardButton("⬅️Назад"))
    await message.answer("Оберіть дію:", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "⬅️Назад", state='*')
async def cmd_back(message: types.Message, state: FSMContext):
    await cmd_start(message, state)

@dp.message_handler(content_types=ContentType.WEB_APP_DATA, state='*')
async def handle_webapp_data(message: types.Message, state: FSMContext):
    try:
        data = json.loads(message.web_app_data.data)
    except Exception as e:
        logging.warning(f"JSON error: {e}")
        await message.answer("Помилка в даних форми. Спробуйте ще раз.")
        return

    user_id = message.from_user.id
    place = data.get("place")
    datetime_raw = data.get("datetime")
    name = data.get("name")
    guests = data.get("guests")

    if not all([place, datetime_raw, name, guests]):
        await message.answer("Деякі поля порожні. Спробуйте ще раз.")
        return

    try:
        dt = datetime.strptime(datetime_raw, "%d.%m.%Y %H:%M")
        dt_str = dt.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        dt_str = datetime_raw

    user_booking_data[user_id] = {
        "place": place, "datetime_str": dt_str,
        "guests": guests, "name": name
    }

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Далі"))
    url_edit = (
        f"https://danza13.github.io/telegram-kalyan-bar-bot/index.html"
        f"?place={place}&datetime={datetime_raw}&name={name}&guests={guests}"
    )
    kb.add(KeyboardButton("Редагувати", web_app=WebAppInfo(url=url_edit)))
    kb.add(KeyboardButton("Скасувати"))
    await message.answer(
        "Перевірте ваші дані\n"
        f"🏠 {place}\n🕒 {dt_str}\n👥 {guests}\n📝 {name}\n\n"
        "Якщо все вірно – натисніть «Далі»",
        reply_markup=kb
    )
    await BookingStates.CONFIRM_DATA.set()

@dp.message_handler(lambda m: m.text == "Скасувати",
                    state=[BookingStates.CONFIRM_DATA,
                           BookingStates.WAITING_PHONE])
async def cmd_cancel(message: types.Message, state: FSMContext):
    user_booking_data.pop(message.from_user.id, None)
    await state.finish()
    await message.answer("Бронь скасовано.", reply_markup=ReplyKeyboardRemove())
    await cmd_start(message, state)

@dp.message_handler(lambda m: m.text == "Далі",
                    state=BookingStates.CONFIRM_DATA)
async def cmd_confirm(message: types.Message, state: FSMContext):
    await BookingStates.WAITING_PHONE.set()
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Поділитись контактом", request_contact=True))
    kb.add(KeyboardButton("Скасувати"))
    await message.answer(
        "Надішліть номер телефону або натисніть кнопку:",
        reply_markup=kb)

@dp.message_handler(content_types=[ContentType.CONTACT, ContentType.TEXT],
                    state=BookingStates.WAITING_PHONE)
async def cmd_phone(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    if uid not in user_booking_data:
        await state.finish()
        await message.answer("Немає даних бронювання. Почніть з /start.")
        return

    raw = message.contact.phone_number if message.contact else message.text
    digits = re.sub(r"\D+", "", raw)
    if len(digits) != 12 or not digits.startswith("380"):
        await message.answer("Невірний номер. Формат: +380XXXXXXXXX")
        return
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
        f"📞 {phone}"
    )

    kb = ReplyKeyboardMarkup(resize_keyboard=True).add("Готово")
    await message.answer(
        "Дякуємо! Бронювання отримано ✅\n"
        "Адміністратор зв'яжеться з вами найближчим часом.",
        reply_markup=kb)
    await state.finish()

@dp.message_handler(lambda m: m.text == "Готово", state='*')
async def cmd_done(message: types.Message, state: FSMContext):
    await cmd_start(message, state)

# ===============================================================
# 6.  Port binding для Render + запуск long‑poll
# ===============================================================
import aiohttp.web as web   # додаємо aiohttp

PORT = int(os.getenv("PORT", 8080))  # Render задає PORT автоматично

async def healthcheck(request):
    """Просто повертаємо 200 OK – Render бачить, що порт слухає."""
    return web.Response(text="OK")

async def start_webserver():
    app_web = web.Application()
    app_web.add_routes([web.get("/", healthcheck)])   # GET /  → OK
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"HTTP‑сервер запущено на порті {PORT}")

async def on_startup(dp):
    # 1) прибираємо старий вебхук, якщо колись ставили
    await bot.delete_webhook(drop_pending_updates=True)
    # 2) запускаємо маленький веб‑сервер для Render
    await start_webserver()

if __name__ == "__main__":
    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=on_startup
    )
