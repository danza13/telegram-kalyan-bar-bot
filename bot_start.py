import logging
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from dotenv import load_dotenv
import os
from datetime import datetime

# Завантаження змінних середовища з файлу .env
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")
WEB_APP_URL = os.getenv("WEB_APP_URL")

if TOKEN is None:
    raise ValueError("BOT_TOKEN не встановлений у файлі .env")
if GROUP_CHAT_ID is None:
    raise ValueError("GROUP_CHAT_ID не встановлений у файлі .env")
if WEB_APP_URL is None:
    raise ValueError("WEB_APP_URL не встановлений у файлі .env")

try:
    GROUP_CHAT_ID = int(GROUP_CHAT_ID)
except ValueError:
    raise ValueError("GROUP_CHAT_ID повинен бути числом.")

# Увімкнення логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Стан бота
CHOOSING, ESTABLISHMENT = range(2)

# Список закладів
ESTABLISHMENTS = ['Вул. Антоновича', 'пр-т. Тичини']

# Обробник /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник start викликано.")
    reply_keyboard = [
        ['Забронювати столик', 'Переглянути меню']
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Вітаємо вас в Telegram-бот кальян-бар\n\nТут Ви можете:",
        reply_markup=markup
    )
    return CHOOSING

# Обробник перегляду меню
async def view_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник view_menu викликано.")
    await update.message.reply_text(f"Перегляньте наше меню:\nhttps://gustouapp.com/menu")

    reply_keyboard = [
        ['Забронювати столик', 'Переглянути меню']
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Що ще ви хочете зробити?", reply_markup=markup)
    return CHOOSING

# Обробник бронювання
async def reserve_table(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник reserve_table викликано.")
    reply_keyboard = [ESTABLISHMENTS]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Будь ласка, оберіть заклад для бронювання:", reply_markup=markup)
    return ESTABLISHMENT

# Обробник вибору закладу
async def establishment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    establishment = update.message.text
    logger.info(f"Вибрано заклад: {establishment}")
    context.user_data['establishment'] = establishment

    WEB_APP_URL = "https://danza13.github.io/telegram-webapp/"

    # Надіслати користувача на Web App для вибору дати та часу
    keyboard = [
        [
            InlineKeyboardButton(
                text="Обрати дату та час",
                web_app=WebAppInfo(url=WEB_APP_URL)  # URL вашого Web App
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Натисніть кнопку нижче, щоб обрати дату та час бронювання:",
        reply_markup=reply_markup
    )
    return ConversationHandler.END  # Завершення розмови, оскільки дані надходять через API

    # Обробник отримання даних з Web App
    async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник web_app_data_handler викликано.")
    
    # Перевіряємо, чи є дані у Web App Data
    if update.message and update.message.web_app_data:
        received_data = update.message.web_app_data.data
        logger.info(f"Отримані дані з WebApp: {received_data}")
        context.user_data['datetime'] = received_data  # Зберігаємо дату та час

        await update.message.reply_text(f"Ви обрали дату та час: {received_data}")
        await update.message.reply_text("Будь ласка, вкажіть кількість гостей:")
        return CHOOSING

    else:
        await update.message.reply_text("Помилка: дані не отримані.")
        return CHOOSING


# Обробник повернення до початку
async def return_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник return_to_start викликано.")
    reply_keyboard = [
        ['Забронювати столик', 'Переглянути меню']
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Вітаємо вас в Telegram-бот кальян-бар\n\nТут Ви можете:",
        reply_markup=markup
    )
    return CHOOSING

# Скасування
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник cancel викликано.")
    await update.message.reply_text(
        'Бронювання скасовано.',
        reply_markup=ReplyKeyboardMarkup([['Повернутись до початку']], resize_keyboard=True)
    )
    return ConversationHandler.END

# Обробник помилок
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    # Перевірка змінних середовища
    if TOKEN is None or GROUP_CHAT_ID is None or WEB_APP_URL is None:
        logger.error("BOT_TOKEN, GROUP_CHAT_ID або WEB_APP_URL не встановлені.")
        return

    # Створюємо екземпляр Application
    application = ApplicationBuilder().token(TOKEN).build()

    # Основні обробники
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.Regex('^Повернутись до початку$'), return_to_start))
    application.add_handler(MessageHandler(filters.Regex('^Переглянути меню$'), view_menu))

    # ConversationHandler
    conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex('^Забронювати столик$'), reserve_table)],
    states={
        CHOOSING: [
            MessageHandler(filters.Regex('^Забронювати столик$'), reserve_table),
            MessageHandler(filters.Regex('^Переглянути меню$'), view_menu),
        ],
        ESTABLISHMENT: [
            MessageHandler(filters.Regex('^' + '$|^'.join(ESTABLISHMENTS) + '$'), establishment_handler)
        ],
        CHOOSING: [
            MessageHandler(filters.ALL, web_app_data_handler)  # Приймаємо дані від Web App
        ],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)

    logger.info("Бот запущено. Очікування повідомлень...")
    application.run_polling()

if __name__ == '__main__':
    main()
