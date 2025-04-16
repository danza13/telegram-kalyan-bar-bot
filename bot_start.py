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
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Токен бота
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # ID адміністратора
WEBHOOK_DOMAIN = os.getenv("WEBHOOK_DOMAIN")  # https://xxxxx.onrender.com

if not BOT_TOKEN:
    raise ValueError("У змінних оточення не знайдено BOT_TOKEN!")
if not ADMIN_CHAT_ID:
    raise ValueError("У змінних оточення не знайдено ADMIN_CHAT_ID!")
if not WEBHOOK_DOMAIN:
    raise ValueError("У змінних оточення не знайдено WEBHOOK_DOMAIN!")

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_DOMAIN}{WEBHOOK_PATH}"

# ===================================================================
# 2. Ініціалізація бота
# ===================================================================
bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ===================================================================
# 3. Стан машини (FSM)
# ===================================================================
class BookingStates(StatesGroup):
    CONFIRM_DATA = State()
    WAITING_PHONE = State()

# ===================================================================
# 4. Проміжне сховище даних
# ===================================================================
user_booking_data = {}
# user_booking_data[user_id] = {
#   "place": "...",
#   "datetime_str": "...",
#   "guests": "...",
#   "name": "...",
#   "phone": "..."
# }

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

    text = (
        "Вітаємо вас в Telegram-боті кальян-бар GUSTOÚ💨\n"
        "Тут Ви можете:\n"
        "🍽 Забронювати столик\n"
        "📕 Переглянути меню\n"
    )
    await message.answer(text, reply_markup=kb)

@dp.message_handler(lambda m: m.text == "🍽Забронювати столик", state='*')
async def cmd_book_table(message: types.Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    btn_open_form = KeyboardButton(
        text="📲Відкрити форму для бронювання",
        # Ваше посилання на WebApp GitHub Pages:
        web_app=WebAppInfo(url="https://danza13.github.io/telegram-kalyan-bar-bot/index.html")
    )
    btn_back = KeyboardButton("⬅️Назад")
    kb.add(btn_open_form)
    kb.add(btn_back)

    await message.answer("Оберіть дію:", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "⬅️Назад", state='*')
async def cmd_back(message: types.Message, state: FSMContext):
    await cmd_start(message, state)

# Хендлер, який ловить дані з WebApp
@dp.message_handler(content_types=ContentType.WEB_APP_DATA, state='*')
async def handle_webapp_data(message: types.Message, state: FSMContext):
    """
    Обробка даних, які прийшли з WebApp через tg.sendData(...).
    """
    try:
        data = json.loads(message.web_app_data.data)
    except Exception as e:
        logging.warning(f"Помилка парсингу JSON: {e}")
        await message.answer("Помилка обробки даних з форми. Спробуйте ще раз.")
        return

    # Очікуємо поля:
    # place, datetime, name, guests
    user_id = message.from_user.id
    place = data.get("place")
    datetime_raw = data.get("datetime")
    name = data.get("name")
    guests = data.get("guests")

    if not (place and datetime_raw and name and guests):
        await message.answer("Деякі поля порожні. Спробуйте ще раз.")
        return

    # Парсимо дату
    try:
        dt = datetime.strptime(datetime_raw, "%d.%m.%Y %H:%M")
        formatted_dt = dt.strftime("%d.%m.%Y %H:%M")
    except Exception as e:
        logging.warning(f"Не вдалося розпарсити дату: {e}")
        formatted_dt = datetime_raw

    # Зберігаємо у user_booking_data
    user_booking_data[user_id] = {
        "place": place,
        "datetime_str": formatted_dt,
        "guests": guests,
        "name": name
    }

    check_text = (
        "Перевірте ваші дані\n"
        f"🏠 Заклад: {place}\n"
        f"🕒 Час та дата: {formatted_dt}\n"
        f"👥 Кількість гостей: {guests}\n"
        f"📝 Контактна особа: {name}"
    )
    await message.answer(check_text)

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    btn_next = KeyboardButton("Далі")

    # Кнопка "Редагувати" із query-параметрами
    base_url = "https://danza13.github.io/telegram-kalyan-bar-bot/index.html"
    url_edit = f"{base_url}?place={place}&datetime={datetime_raw}&name={name}&guests={guests}"
    btn_edit = KeyboardButton(
        text="Редагувати",
        web_app=WebAppInfo(url=url_edit)
    )
    btn_cancel = KeyboardButton("Скасувати")
    kb.add(btn_next, btn_edit, btn_cancel)

    await message.answer("Якщо все вірно натисніть «Далі»", reply_markup=kb)
    await BookingStates.CONFIRM_DATA.set()

@dp.message_handler(lambda m: m.text == "Скасувати", state=[BookingStates.CONFIRM_DATA, BookingStates.WAITING_PHONE])
async def cmd_cancel_booking(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_booking_data.pop(user_id, None)

    await state.finish()
    await message.answer("Бронь скасовано.", reply_markup=ReplyKeyboardRemove())
    await cmd_start(message, state)

@dp.message_handler(lambda m: m.text == "Далі", state=BookingStates.CONFIRM_DATA)
async def cmd_confirm_data(message: types.Message, state: FSMContext):
    await BookingStates.WAITING_PHONE.set()

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    btn_share = KeyboardButton("Поділитись контактом", request_contact=True)
    btn_cancel = KeyboardButton("Скасувати")
    kb.add(btn_share, btn_cancel)

    await message.answer(
        "Будь ласка, надішліть свій номер телефону або скористайтесь кнопкою:",
        reply_markup=kb
    )

@dp.message_handler(content_types=[ContentType.CONTACT, ContentType.TEXT], state=BookingStates.WAITING_PHONE)
async def cmd_handle_phone(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in user_booking_data:
        await message.answer("Немає даних бронювання. Почніть з /start.")
        await state.finish()
        return

    # Якщо contact – беремо phone_number
    if message.contact:
        raw_phone = message.contact.phone_number
    else:
        raw_phone = message.text

    digits = re.sub(r"\D+", "", raw_phone)
    if len(digits) == 12 and digits.startswith("380"):
        phone = "+" + digits
    else:
        await message.answer("Невірний номер, введіть у форматі +380XXXXXXXXX")
        return

    user_booking_data[user_id]["phone"] = phone

    place = user_booking_data[user_id]["place"]
    dt_str = user_booking_data[user_id]["datetime_str"]
    guests = user_booking_data[user_id]["guests"]
    name = user_booking_data[user_id]["name"]

    admin_text = (
        "📅 <b>Бронювання</b>\n"
        f"🏠 Заклад: {place}\n"
        f"🕒 Час та дата: {dt_str}\n"
        f"👥 Кількість гостей: {guests}\n"
        f"📝 Контактна особа: {name}\n"
        f"📞 Номер телефону: {phone}"
    )
    # Надсилаємо адміну
    await bot.send_message(ADMIN_CHAT_ID, admin_text)

    await message.answer(
        "Дякуємо, бронювання отримано! ✅\n"
        "Адміністратор незабаром зв'яжеться з вами. 📲\n"
        "Тим часом ви можете переглянути меню або повернутися на головну сторінку.",
        reply_markup=ReplyKeyboardRemove()
    )

    kb_done = ReplyKeyboardMarkup(resize_keyboard=True)
    kb_done.add(KeyboardButton("Готово"))
    await message.answer("Натисніть «Готово», щоб повернутися в головне меню.", reply_markup=kb_done)

    await state.finish()

@dp.message_handler(lambda m: m.text == "Готово", state='*')
async def cmd_done(message: types.Message, state: FSMContext):
    await cmd_start(message, state)

# ===================================================================
# 6. Запуск
# ===================================================================
async def on_startup(dp):
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook встановлено: {WEBHOOK_URL}")

async def on_shutdown(dp):
    await bot.delete_webhook()
    logging.info("Webhook видалено")

if __name__ == "__main__":
    from aiogram.utils.executor import start_webhook

    PORT = int(os.getenv("PORT", 5000))
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host="0.0.0.0",
        port=PORT
    )
