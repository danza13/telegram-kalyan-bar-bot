import os
import logging
import re
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, 
                           ReplyKeyboardRemove, ContentType)
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor

logging.basicConfig(level=logging.INFO)

# ==============================================================================
# 1. Змінні оточення
# ==============================================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Токен бота
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # ID чату / користувача для повідомлень
WEBHOOK_DOMAIN = os.getenv("WEBHOOK_DOMAIN")  # ваш домен (https://xxxxx.onrender.com), без "/" в кінці

if not BOT_TOKEN:
    raise ValueError("У змінних оточення не знайдено BOT_TOKEN!")
if not ADMIN_CHAT_ID:
    raise ValueError("У змінних оточення не знайдено ADMIN_CHAT_ID!")
if not WEBHOOK_DOMAIN:
    raise ValueError("У змінних оточення не знайдено WEBHOOK_DOMAIN!")

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_DOMAIN}{WEBHOOK_PATH}"

# ==============================================================================
# 2. Ініціалізація бота і Dispatcher
# ==============================================================================
bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ==============================================================================
# 3. Стан машини (FSM)
# ==============================================================================
class BookingStates(StatesGroup):
    CONFIRM_DATA = State()
    WAITING_PHONE = State()

# ==============================================================================
# 4. Проміжне сховище даних
# ==============================================================================
user_booking_data = {}
# user_booking_data[user_id] = {
#   "place": "...",
#   "datetime_str": "...",
#   "guests": "...",
#   "name": "...",
#   "phone": "..."
# }

# ==============================================================================
# 5. Хендлери
# ==============================================================================
@dp.message_handler(commands=['start'], state='*')
async def cmd_start(message: types.Message, state: FSMContext):
    """
    Головне меню з кнопками «Забронювати столик» і «Переглянути меню».
    """
    await state.finish()

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    btn_book = KeyboardButton("🍽Забронювати столик")
    btn_menu = KeyboardButton(
        text="📕Переглянути меню",
        web_app=WebAppInfo(url="https://gustouapp.com/menu")
    )
    kb.add(btn_book)
    kb.add(btn_menu)

    text = (
        "Вітаємо вас в Telegram-боті кальян-бар GUSTOÚ💨\n"
        "Тут Ви можете:\n"
        "🍽 Забронювати столик\n"
        "📕 Переглянути меню\n"
    )
    await message.answer(text, reply_markup=kb)

@dp.message_handler(lambda m: m.text == "🍽Забронювати столик", state='*')
async def cmd_book_table(message: types.Message, state: FSMContext):
    """
    Пропонуємо користувачу відкрити WebApp або повернутися назад.
    """
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    btn_open_form = KeyboardButton(
        text="📲Відкрити форму для бронювання",
        # Ваше посилання на WebApp (GitHub Pages, тощо)
        web_app=WebAppInfo(url="https://danza13.github.io/telegram-kalyan-bar-bot/index.html")
    )
    btn_back = KeyboardButton("⬅️Назад")
    kb.add(btn_open_form)
    kb.add(btn_back)

    await message.answer("Оберіть дію:", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "⬅️Назад", state='*')
async def cmd_back(message: types.Message, state: FSMContext):
    """
    Повернення у головне меню.
    """
    await cmd_start(message, state)

@dp.message_handler(content_types=ContentType.WEB_APP_DATA, state='*')
async def handle_webapp_data(message: types.Message, state: FSMContext):
    """
    Обробка даних, які прийшли з WebApp через tg.sendData(...).
    """
    import json
    try:
        data = json.loads(message.web_app_data.data)
    except:
        await message.answer("Помилка обробки даних з форми. Спробуйте ще раз.")
        return

    # Очікуємо, що у formData приходить:
    # {
    #   "place": "вул. Антоновича, 157",
    #   "datetime": "13.04.2025 18:10",
    #   "name": "Тарас",
    #   "guests": "4"
    # }
    user_id = message.from_user.id
    place = data.get("place")
    datetime_raw = data.get("datetime")
    name = data.get("name")
    guests = data.get("guests")

    if not (place and datetime_raw and name and guests):
        await message.answer("Деякі поля порожні. Спробуйте ще раз.")
        return

    # Спробуємо розпарсити дату "дд.мм.рррр гг:хх"
    try:
        dt = datetime.strptime(datetime_raw, "%d.%m.%Y %H:%M")
        formatted_dt = dt.strftime("%d.%m.%Y %H:%M")  # наприклад, "13.04.2025 18:10"
    except Exception as e:
        # Якщо не вдасться, залишимо сирим
        logging.warning(f"Помилка парсингу дати: {e}")
        formatted_dt = datetime_raw

    user_booking_data[user_id] = {
        "place": place,
        "datetime_str": formatted_dt,
        "guests": guests,
        "name": name
    }

    # Відправляємо повідомлення з перевіркою
    check_text = (
        "Перевірте ваші дані\n"
        f"🏠 Заклад: {place}\n"
        f"🕒 Час та дата: {formatted_dt}\n"
        f"👥 Кількість гостей: {guests}\n"
        f"📝 Контактна особа: {name}"
    )
    await message.answer(check_text)

    # Пропонуємо три кнопки: Далі / Редагувати / Скасувати
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    btn_next = KeyboardButton("Далі")

    # Кнопка "Редагувати" з query params
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
    """
    Якщо користувач передумав – скасовуємо процес бронювання.
    """
    user_id = message.from_user.id
    user_booking_data.pop(user_id, None)

    await state.finish()
    await message.answer("Бронь скасовано.", reply_markup=ReplyKeyboardRemove())
    await cmd_start(message, state)

@dp.message_handler(lambda m: m.text == "Далі", state=BookingStates.CONFIRM_DATA)
async def cmd_confirm_data(message: types.Message, state: FSMContext):
    """
    Якщо все добре, переходимо до введення номера телефону.
    """
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

    # Якщо користувач поділився контактом
    if message.contact:
        raw_phone = message.contact.phone_number
    else:
        raw_phone = message.text

    # Очищуємо нецифрові символи
    digits = re.sub(r"\D+", "", raw_phone)

    # Формат +380XXXXXXXXX
    if len(digits) == 12 and digits.startswith("380"):
        phone = "+" + digits
    else:
        await message.answer("Невірний номер, введіть у форматі +380XXXXXXXXX")
        return

    user_booking_data[user_id]["phone"] = phone

    # Збираємо дані для повідомлення адміну
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
    await bot.send_message(ADMIN_CHAT_ID, admin_text)

    # Повідомлення користувачу
    await message.answer(
        "Дякуємо, бронювання отримано! ✅\n"
        "Наш адміністратор незабаром зв'яжеться з вами. 📲\n"
        "Тим часом ви можете переглянути меню або повернутися на головну сторінку.",
        reply_markup=ReplyKeyboardRemove()
    )

    # Кнопка "Готово"
    kb_done = ReplyKeyboardMarkup(resize_keyboard=True)
    kb_done.add(KeyboardButton("Готово"))
    await message.answer("Натисніть «Готово», щоб повернутися в головне меню.", reply_markup=kb_done)

    await state.finish()

@dp.message_handler(lambda m: m.text == "Готово", state='*')
async def cmd_done(message: types.Message, state: FSMContext):
    """
    Повертаємося в головне меню.
    """
    await cmd_start(message, state)

# ==============================================================================
# 6. Запуск через Webhook
# ==============================================================================
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
