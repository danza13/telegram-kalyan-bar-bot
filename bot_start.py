import os
import json
import re
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, ReplyKeyboardRemove, ContentType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# 1. Environment variables
# ------------------------------------------------------------------
BOT_TOKEN     = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # admin chat ID as integer or string

if not BOT_TOKEN or not ADMIN_CHAT_ID:
    logger.error("Missing required environment variables BOT_TOKEN or ADMIN_CHAT_ID")
    raise RuntimeError("Please set BOT_TOKEN and ADMIN_CHAT_ID environment variables.")

# Convert ADMIN_CHAT_ID to int if needed
try:
    ADMIN_CHAT_ID = int(ADMIN_CHAT_ID)
except ValueError:
    logger.warning("ADMIN_CHAT_ID is not an integer, using as string")

# ------------------------------------------------------------------
# 2. Bot and Dispatcher initialization
# ------------------------------------------------------------------
bot     = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp      = Dispatcher(bot, storage=storage)

# ------------------------------------------------------------------
# 3. FSM States
# ------------------------------------------------------------------
class BookingStates(StatesGroup):
    CONFIRM_DATA  = State()
    WAITING_PHONE = State()

# ------------------------------------------------------------------
# 4. In-memory storage for user bookings
# ------------------------------------------------------------------
user_booking_data: dict[int, dict] = {}

# ------------------------------------------------------------------
# 5. Global error handler
# ------------------------------------------------------------------
@dp.errors_handler()
async def global_error_handler(update, exception):
    logger.exception("Error handling update %s: %s", update, exception)
    return True

# ------------------------------------------------------------------
# 6. Handlers
# ------------------------------------------------------------------
@dp.message_handler(commands="start", state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    logger.info("/start received from user %s", message.from_user.id)
    await state.finish()
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("🍽 Забронювати столик"))
    kb.add(
        KeyboardButton(
            "📕 Переглянути меню",
            web_app=WebAppInfo(url="https://gustouapp.com/menu")
        )
    )
    await message.answer(
        "Вітаємо в Telegram‑боті кальян‑бару GUSTOÚ💨\n"
        "Тут Ви можете:\n🍽 забронювати столик\n📕 переглянути меню",
        reply_markup=kb
    )

@dp.message_handler(lambda m: m.text == "🍽 Забронювати столик", state="*")
async def cmd_book(message: types.Message, state: FSMContext):
    logger.info("Book flow started by user %s", message.from_user.id)
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        KeyboardButton(
            "📲 Відкрити форму для бронювання",
            web_app=WebAppInfo(
                url="https://danza13.github.io/telegram-kalyan-bar-bot"
            )
        )
    )
    kb.add(KeyboardButton("⬅️ Назад"))
    await message.answer("Оберіть дію:", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "⬅️ Назад", state="*")
async def cmd_back(message: types.Message, state: FSMContext):
    logger.info("User %s navigated back to main menu", message.from_user.id)
    await cmd_start(message, state)

@dp.message_handler(content_types=ContentType.WEB_APP_DATA, state="*")
async def handle_webapp(message: types.Message, state: FSMContext):
    logger.info("Received WebApp data from user %s: %s", message.from_user.id, message.web_app_data.data)
    try:
        data = json.loads(message.web_app_data.data)
    except Exception as e:
        logger.warning("JSON parse error: %s", e)
        return await message.answer("Помилка даних форми. Спробуйте ще раз.")

    place        = data.get("place")
    datetime_raw = data.get("datetime")
    name         = data.get("name")
    guests       = data.get("guests")

    if not all([place, datetime_raw, name, guests]):
        logger.warning("Incomplete form data: %s", data)
        return await message.answer("Деякі поля порожні. Спробуйте ще раз.")

    try:
        dt     = datetime.strptime(datetime_raw, "%d.%m.%Y %H:%M")
        dt_str = dt.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        dt_str = datetime_raw

    user_booking_data[message.from_user.id] = {
        "place": place,
        "datetime_str": dt_str,
        "guests": guests,
        "name": name,
    }
    logger.info("Stored booking data for user %s: %s", message.from_user.id,
                user_booking_data[message.from_user.id])

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Далі"))
    kb.add(KeyboardButton("Скасувати"))
    await message.answer(
        f"Перевірте дані:\n"
        f"🏠 <b>Заклад:</b> {place}\n"
        f"🕒 <b>Час та дата:</b> {dt_str}\n"
        f"👥 <b>Кількість гостей:</b> {guests}\n"
        f"📝 <b>Контактна особа:</b> {name}\n\n"
        "Якщо все вірно — натисніть «Далі».",
        reply_markup=kb
    )
    await BookingStates.CONFIRM_DATA.set()

@dp.message_handler(lambda m: m.text == "Скасувати",
                    state=[BookingStates.CONFIRM_DATA, BookingStates.WAITING_PHONE])
async def cmd_cancel(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    user_booking_data.pop(uid, None)
    logger.info("Booking cancelled for user %s", uid)
    await state.finish()
    await message.answer("Бронювання скасовано.", reply_markup=ReplyKeyboardRemove())
    await cmd_start(message, state)

@dp.message_handler(lambda m: m.text == "Далі", state=BookingStates.CONFIRM_DATA)
async def cmd_confirm(message: types.Message, state: FSMContext):
    logger.info("User %s confirmed booking data", message.from_user.id)
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Поділитись контактом", request_contact=True))
    kb.add(KeyboardButton("Скасувати"))
    await BookingStates.WAITING_PHONE.set()
    await message.answer("Надішліть номер телефону або натисніть кнопку:",
                         reply_markup=kb)

@dp.message_handler(content_types=[ContentType.CONTACT, ContentType.TEXT],
                    state=BookingStates.WAITING_PHONE)
async def cmd_phone(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    if uid not in user_booking_data:
        logger.warning("No booking data for user %s when sending phone", uid)
        await state.finish()
        return await message.answer("Немає даних бронювання. Почніть з /start.")

    raw = message.contact.phone_number if message.contact else message.text
    digits = re.sub(r"\D+", "", raw)
    if len(digits) != 12 or not digits.startswith("380"):
        logger.warning("Invalid phone format from user %s: %s", uid, raw)
        return await message.answer("Невірний номер. Формат: +380XXXXXXXXX")
    phone = "+" + digits

    data = user_booking_data[uid]
    data["phone"] = phone
    logger.info("Final booking for user %s: %s", uid, data)

    # Send booking to admin
    await bot.send_message(
        ADMIN_CHAT_ID,
        "📅 <b>Бронювання</b>\n"
        f"🏠 <b>Заклад:</b> {data['place']}\n"
        f"🕒 <b>Час та дата:</b> {data['datetime_str']}\n"
        f"👥 <b>Кількість гостей:</b> {data['guests']}\n"
        f"📝 <b>Контактна особа:</b> {data['name']}\n"
        f"📞 <b>Номер телефону:</b> {phone}",
    )

    kb = ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("Готово"))
    await message.answer("Дякуємо! Бронювання отримано ✅",
                         reply_markup=kb)
    await state.finish()

@dp.message_handler(lambda m: m.text == "Готово", state="*")
async def cmd_done(message: types.Message, state: FSMContext):
    logger.info("User %s finished booking flow", message.from_user.id)
    await cmd_start(message, state)

# ------------------------------------------------------------------
# 7. Bot startup
# ------------------------------------------------------------------
async def on_startup(dp):
    logger.info("Bot started. Long polling initiated.")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
