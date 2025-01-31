import os
import logging
import json
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, WebAppInfo
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
import aiohttp
from dotenv import load_dotenv

# Завантаження змінних середовища з файлу .env
load_dotenv()

# Отримання токена бота та ID групи з змінних середовища
TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")
API_URL = os.getenv("API_URL")
WEB_APP_URL = os.getenv("WEB_APP_URL")  # URL для WebApp

# Налаштування логування
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Визначення станів для ConversationHandler
CHOOSING, ADDRESS, GUESTS, NAME, PHONE, DATETIME = range(6)

# Кнопки для вибору адреси
ADDRESS_OPTIONS = ["вул. Антоновича", "пр-т. Тичини"]

# Функція старту
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник start викликано.")
    reply_keyboard = [["Забронювати столик", "Переглянути меню"]]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Вітаємо вас в Telegram-бот кальян-бар\n\nТут Ви можете:", reply_markup=markup
    )
    return CHOOSING

# Обробник вибору "Переглянути меню"
async def view_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник view_menu викликано.")
    await update.message.reply_text("Ось наше меню:", reply_markup=None)
    await update.message.reply_text(
        "https://gustouapp.com/menu",
        reply_markup=ReplyKeyboardMarkup([["Повернутись до початку"]], resize_keyboard=True)
    )
    return ConversationHandler.END

# Обробник вибору "Забронювати столик"
async def reserve_table(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник reserve_table викликано.")
    reply_keyboard = [ADDRESS_OPTIONS]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Виберіть адресу:", reply_markup=markup)
    return ADDRESS

# Обробник вибору адреси
async def choose_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    address = update.message.text
    if address not in ADDRESS_OPTIONS:
        await update.message.reply_text("Будь ласка, оберіть одну з запропонованих адрес.")
        return ADDRESS
    context.user_data["address"] = address
    logger.info(f"Вибрано адресу: {address}")
    # Запит кількості гостей
    await update.message.reply_text("Кількість гостей:", reply_markup=ReplyKeyboardRemove())
    return GUESTS

# Обробник кількості гостей
async def guests_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        guests = int(update.message.text)
        if guests < 1:
            raise ValueError
        context.user_data["guests"] = guests
        logger.info(f"Введено кількість гостей: {guests}")
    except ValueError:
        await update.message.reply_text("Будь ласка, введіть коректну кількість гостей.")
        return GUESTS

    # Запит імені
    await update.message.reply_text("Будь ласка, вкажіть Ваше ім'я:", reply_markup=ReplyKeyboardRemove())
    return NAME

# Обробник імені
async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Ім'я не може бути порожнім. Будь ласка, введіть Ваше ім'я.")
        return NAME
    context.user_data["name"] = name
    logger.info(f"Введено ім'я: {name}")

    # Запит номера телефону з можливістю поділитися контактом
    contact_button = KeyboardButton("Поділитись контактом", request_contact=True)
    reply_keyboard = [[contact_button]]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Ваш контактний номер телефону для підтвердження бронювання:", reply_markup=markup
    )
    return PHONE

# Обробник номера телефону
async def phone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    contact = update.message.contact
    if contact:
        phone = contact.phone_number
    else:
        phone = update.message.text.strip()
        if not phone.startswith("+380") or len(phone) < 12:
            await update.message.reply_text("Будь ласка, введіть валідний номер телефону у форматі +380XXXXXXXXX або поділіться контактом.")
            return PHONE
    context.user_data["phone"] = phone
    logger.info(f"Введено номер телефону: {phone}")

    # Після отримання номера телефону, переходимо до запиту дати та часу
    await update.message.reply_text("Оберіть дату та час для бронювання:", reply_markup=ReplyKeyboardRemove())
    button = KeyboardButton("Оберіть дату та час", web_app=WebAppInfo(url=WEB_APP_URL))
    markup = ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "Будь ласка, натисніть кнопку нижче для вибору дати та часу.",
        reply_markup=markup
    )
    return DATETIME

# Обробник отримання дати та часу з WebApp
async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.web_app_data:
        await update.message.reply_text("Немає даних з WebApp. Спробуйте ще раз.")
        return ConversationHandler.END

    web_app_data = update.message.web_app_data.data
    logger.info(f"Отримані дані з WebApp: {web_app_data}")
    try:
        booking_info = json.loads(web_app_data)
    except json.JSONDecodeError as e:
        logger.error(f"Помилка при декодуванні даних WebApp: {e}")
        await update.message.reply_text("Сталася помилка при обробці даних. Спробуйте ще раз.")
        return ConversationHandler.END

    context.user_data["datetime"] = booking_info.get("datetime")
    logger.info(f"Вибрано дату та час: {context.user_data['datetime']}")

    # Формування повного запиту для бронювання
    booking_data = {
        "establishment": context.user_data.get("address"),
        "datetime": context.user_data.get("datetime"),
        "guests": context.user_data.get("guests"),
        "name": context.user_data.get("name"),
        "phone": context.user_data.get("phone")
    }
    logger.info(f"Формування даних бронювання: {booking_data}")

    # Відправка даних до API
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(API_URL, json=booking_data) as resp:
                response_data = await resp.json()
                logger.info(f"Відповідь API: {response_data}")
                if resp.status == 200 and response_data.get("status") == "success":
                    await update.message.reply_text(
                        "Дякуємо, що обрали нас! Наш адміністратор незабаром зв'яжеться з вами для підтвердження бронювання. Тим часом ви можете переглянути наше меню або повернутися на головну сторінку.",
                        reply_markup=ReplyKeyboardMarkup(
                            [["Повернутись до початку", "Переглянути меню"]],
                            one_time_keyboard=True,
                            resize_keyboard=True
                        )
                    )
                else:
                    logger.error("API повернув помилку при обробці бронювання.")
                    await update.message.reply_text(
                        "Сталася помилка при відправці бронювання. Спробуйте ще раз.",
                        reply_markup=ReplyKeyboardMarkup([["Повернутись до початку"]], resize_keyboard=True)
                    )
        except Exception as e:
            logger.error(f"Помилка при зверненні до API: {e}")
            await update.message.reply_text(
                "Сталася помилка при відправці бронювання. Спробуйте ще раз.",
                reply_markup=ReplyKeyboardMarkup([["Повернутись до початку"]], resize_keyboard=True)
            )

    return ConversationHandler.END

# Обробник повернення до початку
async def return_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник return_to_start викликано.")
    reply_keyboard = [["Забронювати столик", "Переглянути меню"]]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Вітаємо вас в Telegram-бот кальян-бар\n\nТут Ви можете:", reply_markup=markup
    )
    return CHOOSING

# Скасування бронювання
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник cancel викликано.")
    await update.message.reply_text(
        "Бронювання скасовано.",
        reply_markup=ReplyKeyboardMarkup([["Повернутись до початку"]], resize_keyboard=True)
    )
    return ConversationHandler.END

# Обробник помилок
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    if TOKEN is None or GROUP_CHAT_ID is None or WEB_APP_URL is None or API_URL is None:
        logger.error("BOT_TOKEN, GROUP_CHAT_ID, WEB_APP_URL або API_URL не встановлені.")
        return

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex("^Повернутись до початку$"), return_to_start))
    application.add_handler(MessageHandler(filters.Regex("^Переглянути меню$"), view_menu))

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Забронювати столик$"), reserve_table)],
        states={
            CHOOSING: [
                MessageHandler(filters.Regex("^Забронювати столик$"), reserve_table),
                MessageHandler(filters.Regex("^Переглянути меню$"), view_menu),
            ],
            ADDRESS: [
                MessageHandler(filters.Regex("^(" + "|".join(ADDRESS_OPTIONS) + ")$"), choose_address)
            ],
            GUESTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, guests_handler)
            ],
            NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, name_handler)
            ],
            PHONE: [
                MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), phone_handler)
            ],
            DATETIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, web_app_data_handler)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)

    logger.info("Бот запущено. Очікування повідомлень...")
    application.run_polling()

if __name__ == "__main__":
    main()
