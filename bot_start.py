# bot_start.py

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
import aiohttp

# Завантаження змінних середовища з файлу .env
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")
WEB_APP_URL = os.getenv("WEB_APP_URL")
API_URL = os.getenv("API_URL")  # Додано

if TOKEN is None:
    raise ValueError("BOT_TOKEN не встановлений у файлі .env")
if GROUP_CHAT_ID is None:
    raise ValueError("GROUP_CHAT_ID не встановлений у файлі .env")
if WEB_APP_URL is None:
    raise ValueError("WEB_APP_URL не встановлений у файлі .env")
if API_URL is None:
    raise ValueError("API_URL не встановлений у файлі .env")  # Перевірка нового змінного середовища

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
CHOOSING, ESTABLISHMENT, DATETIME_SELECT, GUESTS, NAME, PHONE_CHOICE, PHONE_INPUT = range(7)

# Список закладів
ESTABLISHMENTS = ['Вул. Антоновича', 'пр-т. Тичини']

# Посилання на меню
MENU_URL = "https://gustouapp.com/menu"

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
    await update.message.reply_text(f"Перегляньте наше меню:\n{MENU_URL}")

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

    # Кнопка з WebAppInfo
    keyboard = [
        [
            InlineKeyboardButton(
                text="Обрати дату та час",
                web_app=WebAppInfo(url=WEB_APP_URL)  # Передаємо URL вашого Web App
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Натисніть кнопку нижче, щоб обрати дату та час бронювання:",
        reply_markup=reply_markup
    )
    return DATETIME_SELECT

# Обробник отримання даних з Web App
async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник web_app_data_handler викликано.")
    # Перевіряємо, чи є web_app_data у звичайному повідомленні
    if update.message and update.message.web_app_data:
        selected_datetime = update.message.web_app_data.data
        logger.info(f"Вибрана дата та час: {selected_datetime}")
        context.user_data['datetime'] = selected_datetime
        await update.message.reply_text(f"Ви обрали дату та час: {selected_datetime}")
        await update.message.reply_text("Кількість гостей:")
        return GUESTS

    # Перевіряємо, чи є web_app_data у callback_query
    elif update.callback_query and update.callback_query.web_app_data:
        query = update.callback_query
        selected_datetime = query.web_app_data.data
        logger.info(f"Вибрана дата та час: {selected_datetime}")
        context.user_data['datetime'] = selected_datetime
        await query.answer()
        await query.message.edit_text(f"Ви обрали дату та час: {selected_datetime}")
        await query.message.reply_text("Кількість гостей:")
        return GUESTS

    else:
        await update.message.reply_text("Не вдалося отримати дату та час.")
        return DATETIME_SELECT

# Обробник кількості гостей
async def guests_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    guests_text = update.message.text
    logger.info(f"Guests: {guests_text}")
    if not guests_text.isdigit() or int(guests_text) <= 0:
        await update.message.reply_text("Будь ласка, введіть коректну кількість гостей.")
        return GUESTS
    context.user_data['guests'] = int(guests_text)
    await update.message.reply_text("Будь ласка, вкажіть Ваше ім'я:")
    return NAME

# Обробник імені
async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    logger.info(f"Name: {name}")
    if not name:
        await update.message.reply_text("Будь ласка, введіть Ваше ім'я.")
        return NAME
    context.user_data['name'] = name

    reply_keyboard = [
        ['Ввести номер вручну', 'Поділитись контактом']
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Ваш контактний номер телефону для підтвердження бронювання:",
        reply_markup=markup
    )
    return PHONE_CHOICE

# Обробник вибору способу надання номера
async def phone_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_choice = update.message.text
    logger.info(f"Вибір способу подання номера телефону: {user_choice}")

    if user_choice == 'Поділитись контактом':
        contact_button = KeyboardButton(
            "Поділитись контактом",
            request_contact=True
        )
        reply_markup = ReplyKeyboardMarkup(
            [[contact_button], ['Відміна']],
            one_time_keyboard=True,
            resize_keyboard=True
        )
        await update.message.reply_text(
            "Натисніть кнопку нижче, щоб поділитись своїм контактом:",
            reply_markup=reply_markup
        )
        return PHONE_INPUT

    elif user_choice == 'Ввести номер вручну':
        await update.message.reply_text(
            "Будь ласка, введіть свій номер телефону у форматі +380XXXXXXXXX:",
            reply_markup=ReplyKeyboardRemove()
        )
        return PHONE_INPUT

    else:
        reply_keyboard = [
            ['Ввести номер вручну', 'Поділитись контактом']
        ]
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "Будь ласка, оберіть один із варіантів:",
            reply_markup=markup
        )
        return PHONE_CHOICE

# Обробник введення номера телефону
async def phone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник phone_handler викликано.")
    if update.message.contact:
        phone_number = update.message.contact.phone_number
        logger.info(f"Отримано номер через контакт: {phone_number}")
    else:
        phone_text = update.message.text.strip()
        logger.info(f"Отримано номер вручну: {phone_text}")
        if not phone_text.startswith('+380') or not phone_text[1:].isdigit() or len(phone_text) != 13:
            await update.message.reply_text(
                "Будь ласка, введіть коректний номер телефону у форматі +380XXXXXXXXX."
            )
            return PHONE_INPUT
        phone_number = phone_text

    context.user_data['phone'] = phone_number

    # Формуємо дані бронювання
    booking_info = {
        "establishment": context.user_data['establishment'],
        "datetime": context.user_data['datetime'],
        "guests": context.user_data['guests'],
        "name": context.user_data['name'],
        "phone": phone_number
    }

    # Відправляємо дані бронювання до API
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(API_URL, json=booking_info) as resp:
                if resp.status == 200:
                    response_data = await resp.json()
                    if response_data.get('status') == 'success':
                        logger.info("Бронювання успішно відправлено до API.")
                    else:
                        logger.error("API повернув помилку при відправці бронювання.")
                        await update.message.reply_text("Сталася помилка при відправці бронювання. Спробуйте ще раз.")
                        return ConversationHandler.END
                else:
                    logger.error(f"API повернув статус {resp.status}")
                    await update.message.reply_text("Сталася помилка при відправці бронювання. Спробуйте ще раз.")
                    return ConversationHandler.END
        except Exception as e:
            logger.error(f"Помилка при зверненні до API: {e}")
            await update.message.reply_text("Сталася помилка при відправці бронювання. Спробуйте ще раз.")
            return ConversationHandler.END

    reply_keyboard = [['Повернутись до початку', 'Переглянути меню']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Дякуємо, що обрали нас! Наш адміністратор незабаром зв'яжеться з вами для підтвердження. "
        "Тим часом ви можете переглянути меню або повернутися на головну сторінку.",
        reply_markup=markup
    )
    return ConversationHandler.END

# Повернутись до початку
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
    if TOKEN is None or GROUP_CHAT_ID is None or WEB_APP_URL is None or API_URL is None:
        logger.error("BOT_TOKEN, GROUP_CHAT_ID, WEB_APP_URL або API_URL не встановлені.")
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
            DATETIME_SELECT: [
                # Замість WebAppData - filters.ALL, і перевірка web_app_data всередині
                MessageHandler(filters.ALL, web_app_data_handler)
            ],
            GUESTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, guests_handler)
            ],
            NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, name_handler)
            ],
            PHONE_CHOICE: [
                MessageHandler(filters.Regex('^(Ввести номер вручну|Поділитись контактом)$'), phone_choice_handler)
            ],
            PHONE_INPUT: [
                MessageHandler(filters.CONTACT | filters.TEXT & ~filters.COMMAND, phone_handler)
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
