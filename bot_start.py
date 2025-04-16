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
# 1. ЗМІННІ ОТОЧЕННЯ
# ==============================================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Токен бота (встановити на Render)
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # ID чату для сповіщень
WEBHOOK_DOMAIN = os.getenv("WEBHOOK_DOMAIN")  # Ваш домен від Render (без "/" в кінці)
if not BOT_TOKEN:
    raise ValueError("У змінних оточення не знайдено BOT_TOKEN!")
if not ADMIN_CHAT_ID:
    raise ValueError("У змінних оточення не знайдено ADMIN_CHAT_ID!")
if not WEBHOOK_DOMAIN:
    raise ValueError("У змінних оточення не знайдено WEBHOOK_DOMAIN!")

# Формуємо URL webhook
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_DOMAIN}{WEBHOOK_PATH}"

# ==============================================================================
# 2. ІНІЦІАЛІЗАЦІЯ БОТА ТА DISPATCHER
# ==============================================================================
bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


# ==============================================================================
# 3. КЛАСИ СТАНІВ (FSM)
# ==============================================================================
class BookingStates(StatesGroup):
    WAITING_WEBAPP_DATA = State()  # Користувач відкрив форму й надішле дані
    CONFIRM_DATA = State()         # Підтвердження / редагування / скасування
    WAITING_PHONE = State()        # Очікуємо номер телефону


# ==============================================================================
# 4. ТИМЧАСОВЕ ЗБЕРІГАННЯ ДАНИХ (in-memory)
# ==============================================================================
# user_booking_data[user_id] = {
#     "place": ...,
#     "datetime_str": ...,
#     "guests": ...,
#     "name": ...,
#     "phone": ...
# }
user_booking_data = {}


# ==============================================================================
# 5. ХЕНДЛЕРИ
# ==============================================================================
@dp.message_handler(commands=['start'], state='*')
async def cmd_start(message: types.Message, state: FSMContext):
    """
    Головне меню після /start або повернення до початкового екрану.
    """
    await state.finish()  # Скидаємо стани, якщо були

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    btn_menu = KeyboardButton(
        text="📕Переглянути меню",
        web_app=WebAppInfo(url="https://gustouapp.com/menu")
    )
    btn_book = KeyboardButton(text="🍽Забронювати столик")
    keyboard.add(btn_book)
    keyboard.add(btn_menu)

    text = (
        "Вітаємо вас в Telegram-бот кальян-бар GUSTOÚ💨\n"
        "Тут Ви можете:\n"
        "🍽 Забронювати столик\n"
        "📕 Переглянути меню\n"
    )
    await message.answer(text, reply_markup=keyboard)


@dp.message_handler(lambda m: m.text == "🍽Забронювати столик", state='*')
async def process_booking_menu(message: types.Message, state: FSMContext):
    """
    Показує кнопки: Назад, Відкрити форму.
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    btn_back = KeyboardButton(text="⬅️Назад")
    # Кнопка з WebApp (форма бронювання)
    btn_open_form = KeyboardButton(
        text="📲Відкрити форму для бронювання",
        web_app=WebAppInfo(url="https://danza13.github.io/telegram-kalyan-bar-bot/index.html")
    )
    keyboard.add(btn_open_form)
    keyboard.add(btn_back)

    await message.answer("Оберіть дію:", reply_markup=keyboard)


@dp.message_handler(lambda m: m.text == "⬅️Назад", state='*')
async def process_back_to_main(message: types.Message, state: FSMContext):
    """
    Повертає у головне меню.
    """
    await cmd_start(message, state)


@dp.message_handler(content_types=ContentType.WEB_APP_DATA, state='*')
async def webapp_data_handler(message: types.Message, state: FSMContext):
    """
    Користувач надіслав дані з WebApp через tg.sendData().
    """
    import json
    try:
        data = json.loads(message.web_app_data.data)
    except:
        await message.answer("Помилка обробки даних з форми. Спробуйте ще раз.")
        return

    # Очікуємо, що приходить об'єкт:
    # {
    #   "place": "...",
    #   "datetime": "...",
    #   "guests": "...",
    #   "name": "..."
    # }
    user_id = message.from_user.id
    place = data.get("place")
    datetime_raw = data.get("datetime")
    guests = data.get("guests")
    name = data.get("name")

    # Зберігаємо попередньо
    user_booking_data[user_id] = {
        "place": place,
        "datetime_str": datetime_raw,
        "guests": guests,
        "name": name
    }

    # Форматуємо дату (наприклад "2025-04-13T18:10" -> "13.04.2025 18:10")
    formatted_dt = datetime_raw
    try:
        dt = datetime.strptime(datetime_raw, "%Y-%m-%dT%H:%M")
        formatted_dt = dt.strftime("%d.%m.%Y %H:%M")
        user_booking_data[user_id]["datetime_str"] = formatted_dt
    except:
        pass

    # Показуємо перевірку
    check_text = (
        "Перевірте ваші дані\n"
        f"🏠 Заклад: {place}\n"
        f"🕒 Час та дата: {formatted_dt}\n"
        f"👥 Кількість гостей: {guests}\n"
        f"📝 Контактна особа: {name}"
    )
    await message.answer(check_text)

    # Пропонуємо "Далі", "Редагувати", "Скасувати"
    text_next = "Якщо все вірно — натисніть «Далі»"
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    btn_next = KeyboardButton("Далі")

    # URL для "Редагувати" (підставимо параметри)
    base_url = "https://danza13.github.io/telegram-kalyan-bar-bot/index.html"
    url_with_data = (
        f"{base_url}?place={place}&datetime={datetime_raw}&guests={guests}&name={name}"
    )
    btn_edit = KeyboardButton(
        text="Редагувати",
        web_app=WebAppInfo(url=url_with_data)
    )
    btn_cancel = KeyboardButton("Скасувати")
    keyboard.add(btn_next, btn_edit, btn_cancel)

    await message.answer(text_next, reply_markup=keyboard)
    await BookingStates.CONFIRM_DATA.set()


@dp.message_handler(lambda m: m.text == "Скасувати", state=[BookingStates.CONFIRM_DATA, BookingStates.WAITING_PHONE])
async def process_cancel_booking(message: types.Message, state: FSMContext):
    """
    Скасування бронювання на будь-якому з двох станів.
    """
    user_id = message.from_user.id
    user_booking_data.pop(user_id, None)  # Видаляємо дані, якщо існують

    await state.finish()
    await message.answer("Бронь скасовано.", reply_markup=ReplyKeyboardRemove())
    await cmd_start(message, state)


@dp.message_handler(lambda m: m.text == "Далі", state=BookingStates.CONFIRM_DATA)
async def process_confirm_data(message: types.Message, state: FSMContext):
    """
    Переходимо до введення / отримання номера телефону.
    """
    await BookingStates.WAITING_PHONE.set()

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    btn_share = KeyboardButton(
        text="Поділитись контактом",
        request_contact=True
    )
    btn_cancel = KeyboardButton("Скасувати")
    keyboard.add(btn_share, btn_cancel)

    await message.answer(
        "Будь ласка, відправте свій номер телефону:",
        reply_markup=keyboard
    )


@dp.message_handler(content_types=[ContentType.CONTACT, ContentType.TEXT], state=BookingStates.WAITING_PHONE)
async def process_phone(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in user_booking_data:
        await message.answer("Дані бронювання відсутні. Спробуйте /start.")
        await state.finish()
        return

    # Якщо користувач поділився контактом
    if message.contact:
        raw_phone = message.contact.phone_number
    else:
        raw_phone = message.text

    # Залишаємо лише цифри
    digits = re.sub(r"\D+", "", raw_phone)

    # Перевірка формату +380...
    if len(digits) == 12 and digits.startswith("380"):
        phone = "+" + digits
    else:
        await message.answer("Невірний номер, введіть номер у форматі +380XXXXXXXXX")
        return

    user_booking_data[user_id]["phone"] = phone

    # Збираємо всі дані
    place = user_booking_data[user_id]["place"]
    dt_str = user_booking_data[user_id]["datetime_str"]
    guests = user_booking_data[user_id]["guests"]
    name = user_booking_data[user_id]["name"]

    # Відправляємо адміністратору (ADMIN_CHAT_ID)
    admin_text = (
        "📅 <b>Бронювання</b>\n"
        f"🏠 Заклад: {place}\n"
        f"🕒 Час та дата: {dt_str}\n"
        f"👥 Кількість гостей: {guests}\n"
        f"📝 Контактна особа: {name}\n"
        f"📞 Номер телефону: {phone}"
    )
    await bot.send_message(ADMIN_CHAT_ID, admin_text)

    # Повідомляємо користувача
    await message.answer(
        "Дякуємо, бронювання отримано! ✅\n"
        "Наш адміністратор незабаром зв'яжеться з вами. 📲\n"
        "Тим часом ви можете переглянути наше меню або повернутися на головну сторінку.",
        reply_markup=ReplyKeyboardRemove()
    )

    # Даємо кнопку "Готово"
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    btn_done = KeyboardButton("Готово")
    keyboard.add(btn_done)
    await message.answer("Натисніть «Готово», щоб повернутися в головне меню.", reply_markup=keyboard)

    await state.finish()


@dp.message_handler(lambda m: m.text == "Готово", state='*')
async def process_done(message: types.Message, state: FSMContext):
    """
    Повертаємо у головне меню.
    """
    await cmd_start(message, state)


# ==============================================================================
# 6. МЕТОДИ STARTUP/SHUTDOWN ДЛЯ WEBHOOK
# ==============================================================================
async def on_startup(dp):
    # Встановлюємо webhook
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook встановлено: {WEBHOOK_URL}")

async def on_shutdown(dp):
    # Видаляємо webhook
    await bot.delete_webhook()
    logging.info("Webhook видалено")

# ==============================================================================
# 7. ЗАПУСК (WEBHOOK)
# ==============================================================================
if __name__ == "__main__":
    from aiogram.utils.executor import start_webhook

    # PORT з середовища (для Render зазвичай)
    PORT = int(os.environ.get('PORT', 5000))

    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host="0.0.0.0",
        port=PORT
    )
