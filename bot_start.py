import logging
import urllib.parse
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
    filters,
    ContextTypes,
    ConversationHandler,
)
from telegram.ext.filters import BaseFilter  # Зверніть увагу: імпортуємо з telegram.ext.filters
from dotenv import load_dotenv
import os
import aiohttp

# Завантаження змінних середовища з файлу .env
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")
WEB_APP_URL = os.getenv("WEB_APP_URL")
API_URL = os.getenv("API_URL")

if TOKEN is None:
    raise ValueError("BOT_TOKEN не встановлений у файлі .env")
if GROUP_CHAT_ID is None:
    raise ValueError("GROUP_CHAT_ID не встановлений у файлі .env")
if WEB_APP_URL is None:
    raise ValueError("WEB_APP_URL не встановлений у файлі .env")
if API_URL is None:
    raise ValueError("API_URL не встановлений у файлі .env")

try:
    GROUP_CHAT_ID = int(GROUP_CHAT_ID)
except ValueError:
    raise ValueError("GROUP_CHAT_ID повинен бути числом.")

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Стани діалогу
CHOOSING, ESTABLISHMENT, GUESTS, NAME, PHONE_CHOICE, PHONE_INPUT, DATETIME_SELECT = range(7)

# Список закладів
ESTABLISHMENTS = ['Вул. Антоновича', 'пр-т. Тичини']

# URL меню
MENU_URL = "https://gustouapp.com/menu"

# Створюємо кастомний фільтр для перевірки наявності даних Web App
class WebAppDataFilter(BaseFilter):
    def filter(self, update: Update) -> bool:
        if update.message and update.message.web_app_data:
            return True
        if update.callback_query and update.callback_query.web_app_data:
            return True
        return False

# Обробник команди /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник start викликано.")
    reply_keyboard = [['Забронювати столик', 'Переглянути меню']]
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
    reply_keyboard = [['Забронювати столик', 'Переглянути меню']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Що ще ви хочете зробити?", reply_markup=markup)
    return CHOOSING

# Обробник повернення до початку
async def return_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник return_to_start викликано.")
    reply_keyboard = [['Забронювати столик', 'Переглянути меню']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Вітаємо вас в Telegram-бот кальян-бар\n\nТут Ви можете:",
        reply_markup=markup
    )
    return CHOOSING

# Обробник початку бронювання
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
    await update.message.reply_text("Будь ласка, введіть кількість гостей:")
    return GUESTS

# Обробник кількості гостей
async def guests_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    guests_text = update.message.text
    logger.info(f"Guests: {guests_text}")
    if not guests_text.isdigit() or int(guests_text) <= 0:
        await update.message.reply_text("Будь ласка, введіть коректну кількість гостей.")
        return GUESTS
    context.user_data['guests'] = guests_text  # Зберігаємо як рядок для передачі в URL
    await update.message.reply_text("Будь ласка, вкажіть Ваше ім'я:")
    return NAME

# Обробник введення імені
async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    logger.info(f"Name: {name}")
    if not name:
        await update.message.reply_text("Будь ласка, введіть Ваше ім'я.")
        return NAME
    context.user_data['name'] = name
    reply_keyboard = [['Ввести номер вручну', 'Поділитись контактом']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Ваш контактний номер телефону для підтвердження бронювання:",
        reply_markup=markup
    )
    return PHONE_CHOICE

# Обробник вибору способу надання номера телефону
async def phone_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_choice = update.message.text
    logger.info(f"Вибір способу подання номера телефону: {user_choice}")
    if user_choice == 'Поділитись контактом':
        contact_button = KeyboardButton("Поділитись контактом", request_contact=True)
        reply_markup = ReplyKeyboardMarkup([[contact_button], ['Відміна']], one_time_keyboard=True, resize_keyboard=True)
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
        reply_keyboard = [['Ввести номер вручну', 'Поділитись контактом']]
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("Будь ласка, оберіть один із варіантів:", reply_markup=markup)
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
            await update.message.reply_text("Будь ласка, введіть коректний номер телефону у форматі +380XXXXXXXXX.")
            return PHONE_INPUT
        phone_number = phone_text

    context.user_data['phone'] = phone_number

    # Формуємо URL для Web App із даними, введеними користувачем
    data = {
        "establishment": context.user_data.get("establishment", ""),
        "guests": context.user_data.get("guests", ""),
        "name": context.user_data.get("name", ""),
        "phone": context.user_data.get("phone", "")
    }
    query = urllib.parse.urlencode(data)
    full_url = f"{WEB_APP_URL}?{query}"
    logger.info(f"Web App URL: {full_url}")

    # Створюємо кнопку для відкриття Web App з параметрами
    keyboard = [
        [InlineKeyboardButton(text="Обрати дату та час", web_app=WebAppInfo(url=full_url))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Натисніть кнопку нижче, щоб обрати дату та час бронювання:",
        reply_markup=reply_markup
    )
    return DATETIME_SELECT

# Обробник отримання даних з Web App (дата та час)
async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник web_app_data_handler викликано.")

    # Отримання даних (дата та час) із Web App
    if update.message and update.message.web_app_data:
        selected_datetime = update.message.web_app_data.data
        logger.info(f"Вибрана дата та час (update.message): {selected_datetime}")
        context.user_data['datetime'] = selected_datetime
        await update.message.reply_text(f"Ви обрали дату та час: {selected_datetime}")
    elif update.callback_query and update.callback_query.web_app_data:
        selected_datetime = update.callback_query.web_app_data.data
        logger.info(f"Вибрана дата та час (callback_query): {selected_datetime}")
        context.user_data['datetime'] = selected_datetime
        await update.callback_query.answer()
        chat_id = update.effective_chat.id
        await context.bot.send_message(chat_id=chat_id, text=f"Ви обрали дату та час: {selected_datetime}")
    else:
        logger.warning("Дані з Web App не отримано. Залишаємось у стані DATETIME_SELECT.")
        return DATETIME_SELECT

    # Формуємо дані бронювання
    booking_info = {
        "establishment": context.user_data['establishment'],
        "datetime": context.user_data['datetime'],
        "guests": context.user_data['guests'],
        "name": context.user_data['name'],
        "phone": context.user_data['phone']
    }
    logger.info(f"Формуємо бронювання: {booking_info}")

    # Відправка даних бронювання до API
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(API_URL, json=booking_info) as resp:
                logger.info(f"Отримано статус від API: {resp.status}")
                if resp.status == 200:
                    response_data = await resp.json()
                    logger.info(f"Відповідь API: {response_data}")
                    if response_data.get('status') == 'success':
                        logger.info("Бронювання успішно відправлено до API.")
                    else:
                        logger.error("API повернув помилку при відправці бронювання.")
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text="Сталася помилка при відправці бронювання. Спробуйте ще раз."
                        )
                        return CHOOSING
                else:
                    logger.error(f"API повернув статус {resp.status}")
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="Сталася помилка при відправці бронювання. Спробуйте ще раз."
                    )
                    return CHOOSING
        except Exception as e:
            logger.error(f"Помилка при зверненні до API: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Сталася помилка при відправці бронювання. Спробуйте ще раз."
            )
            return CHOOSING

    # Відправляємо повідомлення-підтвердження з можливістю повернення до початку
    reply_keyboard = [['Повернутись до початку', 'Переглянути меню']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Дякуємо, що обрали нас! Наш адміністратор незабаром зв'яжеться з вами для підтвердження. "
             "Тим часом ви можете переглянути меню або повернутися на головну сторінку.",
        reply_markup=markup
    )
    logger.info("Повідомлення-підтвердження надіслано, повертаємося до стану CHOOSING.")
    return CHOOSING

# Обробник скасування
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник cancel викликано.")
    await update.message.reply_text(
        'Бронювання скасовано.',
        reply_markup=ReplyKeyboardMarkup([['Повернутись до початку']], resize_keyboard=True)
    )
    return CHOOSING

# Обробник помилок
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    if TOKEN is None or GROUP_CHAT_ID is None or WEB_APP_URL is None or API_URL is None:
        logger.error("BOT_TOKEN, GROUP_CHAT_ID, WEB_APP_URL або API_URL не встановлені.")
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
                MessageHandler(filters.Regex('^' + '$|^'.join(ESTABLISHMENTS) + '$'), establishment_handler)
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
                MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), phone_handler)
            ],
            DATETIME_SELECT: [
                MessageHandler(WebAppDataFilter(), web_app_data_handler)
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
