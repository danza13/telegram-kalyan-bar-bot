import logging
import os
import urllib.parse
import json
from dotenv import load_dotenv

from telegram import (
    Update,
    Bot,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
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
from telegram.ext.filters import BaseFilter

# Завантаження змінних середовища
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

# Перетворимо GROUP_CHAT_ID у число (якщо це можливо)
try:
    GROUP_CHAT_ID = int(GROUP_CHAT_ID)
except ValueError:
    # Якщо не вдається, залишимо як рядок (для випадку з @username каналами)
    pass

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Стани діалогу
CHOOSING, ESTABLISHMENT, GUESTS, NAME, PHONE_CHOICE, PHONE_INPUT, DATETIME_SELECT = range(7)

# Список закладів
ESTABLISHMENTS = ['вул. Антоновича, 157', 'пр-т. Тичини, 8']

# URL меню (можна змінити на свій)
MENU_URL = "https://gustouapp.com/menu"


# --- Кастомний фільтр для обробки даних із Web App (sendData) ---
class WebAppDataFilter(BaseFilter):
    def filter(self, update: Update) -> bool:
        if update.message and update.message.web_app_data:
            return True
        if update.callback_query and update.callback_query.web_app_data:
            return True
        return False


# --- Обробник /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник start викликано.")
    reply_keyboard = [['Забронювати столик']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Вітаємо вас в Telegram-бот кальян-бар GUSTOÚ\n"
        "Тут Ви можете :\n"
        "Забронювати столик",
        reply_markup=markup
    )
    return CHOOSING


# --- Обробник кнопки "Переглянути меню" ---
async def view_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник view_menu викликано.")
    await update.message.reply_text(f"Перегляньте наше меню:\n{MENU_URL}")
    reply_keyboard = [['Забронювати столик', 'Переглянути меню']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Що ще ви хочете зробити?", reply_markup=markup)
    return CHOOSING


# --- Обробник кнопки "Повернутись до початку" ---
async def return_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник return_to_start викликано.")
    reply_keyboard = [['Забронювати столик', 'Переглянути меню']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Вітаємо вас в Telegram-бот кальян-бар GUSTOÚ\n"
        "Тут Ви можете :\n"
        "Забронювати столик",
        reply_markup=markup
    )
    return CHOOSING


# --- Обробник "Забронювати столик" ---
async def reserve_table(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник reserve_table викликано.")
    # Вибір локації
    reply_keyboard = [ESTABLISHMENTS, ['Відміна']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Оберіть локацію:", reply_markup=markup)
    return ESTABLISHMENT


# --- Обробник вибору закладу ---
async def establishment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    establishment = update.message.text
    if establishment == 'Відміна':
        return await cancel(update, context)

    logger.info(f"Вибрано заклад: {establishment}")
    context.user_data['establishment'] = establishment
    await update.message.reply_text("Кількість гостей:", reply_markup=ReplyKeyboardRemove())
    return GUESTS


# --- Обробник введення кількості гостей ---
async def guests_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    guests_text = update.message.text
    if guests_text == 'Відміна':
        return await cancel(update, context)

    if not guests_text.isdigit() or int(guests_text) <= 0:
        await update.message.reply_text("Будь ласка, введіть коректну кількість гостей або натисніть 'Відміна'.")
        return GUESTS

    context.user_data['guests'] = guests_text
    await update.message.reply_text("Будь ласка, вкажіть Ваше ім'я:")
    return NAME


# --- Обробник введення імені ---
async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if name == 'Відміна':
        return await cancel(update, context)

    if not name:
        await update.message.reply_text("Будь ласка, введіть Ваше ім'я або натисніть 'Відміна'.")
        return NAME

    context.user_data['name'] = name
    reply_keyboard = [['Ввести номер вручну', 'Поділитись контактом'], ['Відміна']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Ваш контактний номер телефону для підтвердження бронювання:",
        reply_markup=markup
    )
    return PHONE_CHOICE


# --- Обробник вибору способу надання номера телефону ---
async def phone_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_choice = update.message.text
    if user_choice == 'Відміна':
        return await cancel(update, context)

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
        reply_keyboard = [['Ввести номер вручну', 'Поділитись контактом'], ['Відміна']]
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("Будь ласка, оберіть один із варіантів:", reply_markup=markup)
        return PHONE_CHOICE


# --- Обробник введення номера телефону ---
async def phone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.contact:
        phone_number = update.message.contact.phone_number
    else:
        phone_text = update.message.text.strip()
        if phone_text == 'Відміна':
            return await cancel(update, context)

        if not phone_text.startswith('+380') or not phone_text[1:].isdigit() or len(phone_text) != 13:
            await update.message.reply_text("Будь ласка, введіть коректний номер телефону у форматі +380XXXXXXXXX або натисніть 'Відміна'.")
            return PHONE_INPUT
        phone_number = phone_text

    context.user_data['phone'] = phone_number

    # Сформуємо URL, щоб передати дані в Web App (для відображення)
    data = {
        "establishment": context.user_data.get("establishment", ""),
        "guests": context.user_data.get("guests", ""),
        "name": context.user_data.get("name", ""),
        "phone": context.user_data.get("phone", ""),
        "chat_id": update.effective_chat.id
    }
    query = urllib.parse.urlencode(data)
    full_url = f"{WEB_APP_URL}?{query}"
    logger.info(f"Web App URL: {full_url}")

    # Кнопка для відкриття Web App
    keyboard = [
        [InlineKeyboardButton(text="Обрати дату ⬇️", web_app=WebAppInfo(url=full_url))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Оберіть дату ⬇️",
        reply_markup=reply_markup
    )

    return DATETIME_SELECT


# --- Обробник даних із Web App (через sendData) ---
async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник web_app_data_handler викликано.")

    # Залежно від того, звідки прийшло повідомлення:
    # - update.message.web_app_data
    # - update.callback_query.web_app_data
    if update.message and update.message.web_app_data:
        raw_data = update.message.web_app_data.data
    elif update.callback_query and update.callback_query.web_app_data:
        raw_data = update.callback_query.web_app_data.data
        await update.callback_query.answer()
    else:
        logger.warning("Немає web_app_data у повідомленні.")
        return DATETIME_SELECT

    # Розпарсимо рядок JSON
    try:
        booking_data = json.loads(raw_data)
    except json.JSONDecodeError:
        logger.error("Неможливо розпарсити JSON із web_app_data.")
        return DATETIME_SELECT

    logger.info(f"Отримано дані з Web App: {booking_data}")

    # Тепер у booking_data є: establishment, guests, name, phone, datetime, chat_id
    # Збережемо їх для зручності
    establishment = booking_data.get("establishment", "")
    datetime_str = booking_data.get("datetime", "")
    guests = booking_data.get("guests", "")
    name = booking_data.get("name", "")
    phone = booking_data.get("phone", "")
    user_chat_id = booking_data.get("chat_id", "")

    # 1. Відправимо повідомлення з бронюванням у групу/канал
    booking_info = (
        f"📅 *Нове бронювання*\n"
        f"🏠 *Заклад:* {establishment}\n"
        f"🕒 *Дата та час:* {datetime_str}\n"
        f"👥 *Гостей:* {guests}\n"
        f"🙍‍♂ *Ім'я:* {name}\n"
        f"📞 *Телефон:* {phone}"
    )
    bot: Bot = context.bot
    try:
        await bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=booking_info,
            parse_mode="Markdown"
        )
        logger.info("Повідомлення з бронюванням успішно відправлено в групу.")
    except Exception as e:
        logger.error(f"Помилка при відправленні повідомлення у групу: {e}")

    # 2. Відправимо користувачу фінальне підтвердження
    #    (якщо user_chat_id існує і не пустий)
    if user_chat_id:
        reply_keyboard = [['Повернутись до початку', 'Переглянути меню']]
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        final_text = (
            "Дякуємо, що обрали нас! Наш адміністратор незабаром зв'яжеться з вами для підтвердження бронювання.\n"
            "Тим часом ви можете переглянути наше меню або повернутися на головну сторінку."
        )
        await bot.send_message(
            chat_id=user_chat_id,
            text=final_text,
            reply_markup=markup
        )

    return ConversationHandler.END


# --- Обробник скасування ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник cancel викликано.")
    await update.message.reply_text(
        'Бронювання скасовано.',
        reply_markup=ReplyKeyboardMarkup([['Повернутись до початку']], resize_keyboard=True)
    )
    return ConversationHandler.END


# --- Обробник помилок ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)


def main():
    application = ApplicationBuilder().token(TOKEN).build()

    # Додаємо хендлери
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.Regex('^Повернутись до початку$'), return_to_start))
    application.add_handler(MessageHandler(filters.Regex('^Переглянути меню$'), view_menu))

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^Забронювати столик$'), reserve_table)],
        states={
            CHOOSING: [
                MessageHandler(filters.Regex('^Забронювати столик$'), reserve_table),
                MessageHandler(filters.Regex('^Переглянути меню$'), view_menu),
                MessageHandler(filters.Regex('^Відміна$'), cancel),
            ],
            ESTABLISHMENT: [
                MessageHandler(filters.Regex('^(' + '|'.join(ESTABLISHMENTS + ['Відміна']) + ')$'), establishment_handler)
            ],
            GUESTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, guests_handler)
            ],
            NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, name_handler)
            ],
            PHONE_CHOICE: [
                MessageHandler(filters.Regex('^(Ввести номер вручну|Поділитись контактом|Відміна)$'), phone_choice_handler)
            ],
            PHONE_INPUT: [
                MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), phone_handler)
            ],
            DATETIME_SELECT: [
                MessageHandler(WebAppDataFilter(), web_app_data_handler)
            ],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            MessageHandler(filters.Regex('^Відміна$'), cancel)
        ],
    )

    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)

    logger.info("Бот запущено. Очікування повідомлень...")
    application.run_polling()


if __name__ == '__main__':
    main()
