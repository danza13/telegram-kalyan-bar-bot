import logging
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from dotenv import load_dotenv
import os

# Завантаження змінних середовища з файлу .env
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")
WEB_APP_URL = os.getenv("WEB_APP_URL")

if not TOKEN or not GROUP_CHAT_ID or not WEB_APP_URL:
    raise ValueError("BOT_TOKEN, GROUP_CHAT_ID або WEB_APP_URL не встановлені у файлі .env")

try:
    GROUP_CHAT_ID = int(GROUP_CHAT_ID)
except ValueError:
    raise ValueError("GROUP_CHAT_ID повинен бути числом.")

# Увімкнення логування
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Стан бота
CHOOSING, ESTABLISHMENT, DATETIME_SELECT, GUESTS = range(4)

# Список закладів
ESTABLISHMENTS = ['Вул. Антоновича', 'пр-т. Тичини']

# Обробник /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник start викликано.")
    reply_keyboard = [['Забронювати столик', 'Переглянути меню']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Вітаємо вас у Telegram-боті кальян-бару!\n\nОберіть дію:", reply_markup=markup)
    return CHOOSING

# Обробник перегляду меню
async def view_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник view_menu викликано.")
    await update.message.reply_text("Перегляньте наше меню: https://gustouapp.com/menu")
    return CHOOSING

# Обробник бронювання
async def reserve_table(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник reserve_table викликано.")
    reply_keyboard = [[loc] for loc in ESTABLISHMENTS]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Оберіть заклад для бронювання:", reply_markup=markup)
    return ESTABLISHMENT

# Обробник вибору закладу
async def establishment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    establishment = update.message.text
    logger.info(f"Вибрано заклад: {establishment}")
    context.user_data['establishment'] = establishment

    keyboard = [[InlineKeyboardButton("Обрати дату та час", web_app=WebAppInfo(url=WEB_APP_URL))]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Натисніть кнопку, щоб обрати дату та час:", reply_markup=reply_markup)
    return DATETIME_SELECT

# Обробник отримання даних з Web App
async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник web_app_data_handler викликано.")

    if update.message and update.message.web_app_data:
        received_data = update.message.web_app_data.data
        logger.info(f"Отримані дані з WebApp: {received_data}")
        context.user_data['datetime'] = received_data  # Зберігаємо дату та час у контекст

        await update.message.reply_text(f"Ви обрали дату та час: {received_data}")
        await update.message.reply_text("Будь ласка, введіть кількість гостей:")
        return GUESTS

    await update.message.reply_text("Помилка: дані не отримані.")
    return DATETIME_SELECT

# Обробник введення кількості гостей
async def guests_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    guests_text = update.message.text
    if not guests_text.isdigit() or int(guests_text) <= 0:
        await update.message.reply_text("Будь ласка, введіть коректну кількість гостей (число).")
        return GUESTS

    context.user_data['guests'] = int(guests_text)
    await update.message.reply_text("Ваше бронювання записане! Наш адміністратор зв'яжеться з вами.")
    return ConversationHandler.END

# Повернення до головного меню
async def return_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник return_to_start викликано.")
    reply_keyboard = [['Забронювати столик', 'Переглянути меню']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Оберіть дію:", reply_markup=markup)
    return CHOOSING

# Скасування бронювання
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник cancel викликано.")
    await update.message.reply_text("Бронювання скасовано.", reply_markup=ReplyKeyboardMarkup([['Повернутись до початку']], resize_keyboard=True))
    return ConversationHandler.END

# Обробник помилок
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    if not TOKEN or not GROUP_CHAT_ID or not WEB_APP_URL:
        logger.error("BOT_TOKEN, GROUP_CHAT_ID або WEB_APP_URL не встановлені.")
        return

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.Regex('^Повернутись до початку$'), return_to_start))
    application.add_handler(MessageHandler(filters.Regex('^Переглянути меню$'), view_menu))

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^Забронювати столик$'), reserve_table)],
        states={
            CHOOSING: [
                MessageHandler(filters.Regex('^Забронювати столик$'), reserve_table),
                MessageHandler(filters.Regex('^Переглянути меню$'), view_menu),
            ],
            ESTABLISHMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, establishment_handler)
            ],
            DATETIME_SELECT: [
                MessageHandler(filters.ALL, web_app_data_handler)
            ],
            GUESTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, guests_handler)
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
