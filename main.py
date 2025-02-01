import os
import logging
import urllib.parse
import asyncio
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv
from pydantic import BaseModel
from telegram import (
    Update,
    Bot,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo
)
from telegram.error import TelegramError
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import aiohttp

# Завантаження змінних середовища з файлу .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")
WEB_APP_URL = os.getenv("WEB_APP_URL")
API_URL = os.getenv("API_URL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8000))

if BOT_TOKEN is None:
    raise ValueError("BOT_TOKEN не встановлений у .env")
if GROUP_CHAT_ID is None:
    raise ValueError("GROUP_CHAT_ID не встановлений у .env")
if WEB_APP_URL is None:
    raise ValueError("WEB_APP_URL не встановлений у .env")
if API_URL is None:
    raise ValueError("API_URL не встановлений у .env")
if WEBHOOK_URL is None:
    raise ValueError("WEBHOOK_URL не встановлений у .env")

try:
    GROUP_CHAT_ID = int(GROUP_CHAT_ID)
except ValueError:
    raise ValueError("GROUP_CHAT_ID повинен бути числом.")

# Налаштування логування
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Створення FastAPI додатку
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://danza13.github.io"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Модель даних бронювання (для API)
class Booking(BaseModel):
    establishment: str
    datetime: str
    guests: int
    name: str
    phone: str
    chat_id: int = None

# --------------------
# Telegram бот логіка
# --------------------
# Стани діалогу
CHOOSING, ESTABLISHMENT, GUESTS, NAME, PHONE_CHOICE, PHONE_INPUT, DATETIME_SELECT = range(7)

# Список закладів (адреси)
ESTABLISHMENTS = ['вул. Антоновича, 157', 'пр-т. Тичини, 8']
MENU_URL = "https://gustouapp.com/menu"

# Кастомний фільтр для WebApp даних
class WebAppDataFilter(filters.BaseFilter):
    def filter(self, update: Update) -> bool:
        return bool((update.message and update.message.web_app_data) or
                    (update.callback_query and update.callback_query.web_app_data))

# Оголошення обробників
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник /start викликано.")
    reply_keyboard = [['Забронювати столик']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Вітаємо вас в Telegram-бот кальян-бар GUSTOÚ\n"
        "Тут Ви можете:\nЗабронювати столик",
        reply_markup=markup
    )
    return CHOOSING

async def view_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник view_menu викликано.")
    await update.message.reply_text(f"Перегляньте наше меню:\n{MENU_URL}")
    reply_keyboard = [['Забронювати столик', 'Переглянути меню']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Що ще ви хочете зробити?", reply_markup=markup)
    return CHOOSING

async def return_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник return_to_start викликано.")
    reply_keyboard = [['Забронювати столик', 'Переглянути меню']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Вітаємо вас в Telegram-бот кальян-бар GUSTOÚ\n"
        "Тут Ви можете:\nЗабронювати столик",
        reply_markup=markup
    )
    return CHOOSING

async def reserve_table(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник reserve_table викликано.")
    reply_keyboard = [ESTABLISHMENTS, ['Відміна']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Оберіть локацію:", reply_markup=markup)
    return ESTABLISHMENT

async def establishment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    establishment = update.message.text
    if establishment == 'Відміна':
        return await cancel(update, context)
    logger.info(f"Вибрано заклад: {establishment}")
    context.user_data['establishment'] = establishment
    await update.message.reply_text("Кількість гостей:", reply_markup=ReplyKeyboardRemove())
    return GUESTS

async def guests_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    guests_text = update.message.text
    if guests_text == 'Відміна':
        return await cancel(update, context)
    logger.info(f"Guests: {guests_text}")
    if not guests_text.isdigit() or int(guests_text) <= 0:
        await update.message.reply_text("Введіть коректну кількість гостей або 'Відміна' для скасування.")
        return GUESTS
    context.user_data['guests'] = guests_text
    await update.message.reply_text("Вкажіть Ваше ім'я:")
    return NAME

async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if name == 'Відміна':
        return await cancel(update, context)
    logger.info(f"Name: {name}")
    if not name:
        await update.message.reply_text("Введіть Ваше ім'я або 'Відміна' для скасування.")
        return NAME
    context.user_data['name'] = name
    reply_keyboard = [['Ввести номер вручну', 'Поділитись контактом'], ['Відміна']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Ваш контактний номер телефону:", reply_markup=markup)
    return PHONE_CHOICE

async def phone_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_choice = update.message.text
    if user_choice == 'Відміна':
        return await cancel(update, context)
    logger.info(f"Вибір способу подання номера: {user_choice}")
    if user_choice == 'Поділитись контактом':
        contact_button = KeyboardButton("Поділитись контактом", request_contact=True)
        reply_markup = ReplyKeyboardMarkup([[contact_button], ['Відміна']], one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("Натисніть, щоб поділитись своїм контактом:", reply_markup=reply_markup)
        return PHONE_INPUT
    elif user_choice == 'Ввести номер вручну':
        await update.message.reply_text("Введіть номер телефону у форматі +380XXXXXXXXX:", reply_markup=ReplyKeyboardRemove())
        return PHONE_INPUT
    else:
        reply_keyboard = [['Ввести номер вручну', 'Поділитись контактом'], ['Відміна']]
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("Виберіть один із варіантів:", reply_markup=markup)
        return PHONE_CHOICE

async def phone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник phone_handler викликано.")
    if update.message.contact:
        phone_number = update.message.contact.phone_number
        logger.info(f"Номер через контакт: {phone_number}")
    else:
        phone_text = update.message.text.strip()
        if phone_text == 'Відміна':
            return await cancel(update, context)
        logger.info(f"Номер вручну: {phone_text}")
        if not phone_text.startswith('+380') or not phone_text[1:].isdigit() or len(phone_text) != 13:
            await update.message.reply_text("Введіть коректний номер телефону або 'Відміна'.")
            return PHONE_INPUT
        phone_number = phone_text

    context.user_data['phone'] = phone_number
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
    keyboard = [
        [InlineKeyboardButton(text="Обрати дату ⬇️", web_app=WebAppInfo(url=full_url))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Оберіть дату ⬇️", reply_markup=reply_markup)
    return ConversationHandler.END

async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник web_app_data_handler викликано.")
    if update.message and update.message.web_app_data:
        selected_datetime = update.message.web_app_data.data
        logger.info(f"Дата/час з update.message: {selected_datetime}")
        context.user_data['datetime'] = selected_datetime
        await update.message.reply_text(f"Ви обрали: {selected_datetime}")
    elif update.callback_query and update.callback_query.web_app_data:
        selected_datetime = update.callback_query.web_app_data.data
        logger.info(f"Дата/час з callback_query: {selected_datetime}")
        context.user_data['datetime'] = selected_datetime
        await update.callback_query.answer()
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Ви обрали: {selected_datetime}")
    else:
        logger.warning("Дані з Web App не отримано. Залишаємось у стані DATETIME_SELECT.")
        return DATETIME_SELECT

    booking_info = {
        "establishment": context.user_data['establishment'],
        "datetime": context.user_data['datetime'],
        "guests": context.user_data['guests'],
        "name": context.user_data['name'],
        "phone": context.user_data['phone']
    }
    logger.info(f"Формуємо бронювання: {booking_info}")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(API_URL, json=booking_info) as resp:
                logger.info(f"Статус від API: {resp.status}")
                if resp.status == 200:
                    response_data = await resp.json()
                    logger.info(f"Відповідь API: {response_data}")
                    if response_data.get('status') == 'success':
                        logger.info("Бронювання відправлено до API та Telegram групи.")
                    else:
                        logger.error("Помилка API при відправці бронювання.")
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text="Помилка при бронюванні. Спробуйте ще раз."
                        )
                        return ConversationHandler.END
                else:
                    logger.error(f"API повернув статус {resp.status}")
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="Помилка при бронюванні. Спробуйте ще раз."
                    )
                    return ConversationHandler.END
        except Exception as e:
            logger.error(f"Помилка при зверненні до API: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Помилка при бронюванні. Спробуйте ще раз."
            )
            return ConversationHandler.END

    reply_keyboard = [['Повернутись до початку', 'Переглянути меню']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    final_text = ("Дякуємо, що обрали нас! Наш адміністратор незабаром зв'яжеться з вами.\n"
                  "Тим часом ви можете переглянути наше меню або повернутися на головну сторінку.")
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=final_text,
        reply_markup=markup
    )
    logger.info("Фінальне повідомлення надіслано, розмова завершена.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Обробник cancel викликано.")
    await update.message.reply_text(
        'Бронювання скасовано.',
        reply_markup=ReplyKeyboardMarkup([['Повернутись до початку']], resize_keyboard=True)
    )
    return ConversationHandler.END

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)

# Налаштування диспетчера Telegram
def setup_dispatcher(app_obj):
    app_obj.add_handler(CommandHandler('start', start))
    app_obj.add_handler(MessageHandler(filters.Regex('^Повернутись до початку$'), return_to_start))
    app_obj.add_handler(MessageHandler(filters.Regex('^Переглянути меню$'), view_menu))
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
    app_obj.add_handler(conv_handler)
    app_obj.add_error_handler(error_handler)

# Створення Telegram додатку (telegram_app) для вебхука
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
setup_dispatcher(telegram_app)

# Додаємо подію startup, щоб ініціалізувати Telegram додаток
@app.on_event("startup")
async def on_startup():
    await telegram_app.initialize()
    logger.info("Telegram Application ініціалізовано.")

# -------------------------
# FastAPI вебхук-енпоїнт для отримання оновлень від Telegram
# -------------------------
@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
    except Exception as e:
        logger.error(f"Помилка розбору JSON: {e}")
        raise HTTPException(status_code=400, detail="Невірний формат запиту")
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}

@app.get("/")
async def root():
    return {"message": "API для Telegram бота працює."}

if __name__ == '__main__':
    # Створюємо новий event loop та ініціалізуємо Telegram додаток перед запуском uvicorn
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(telegram_app.initialize())
        # За бажанням, можна перевірити get_me:
        # me = loop.run_until_complete(telegram_app.bot.get_me())
        # logger.info(f"Bot info: {me}")
    except Exception as e:
        logger.error(f"Помилка ініціалізації Telegram додатку: {e}")
    # Встановлення вебхука
    async def set_webhook():
        success = await telegram_app.bot.set_webhook(WEBHOOK_URL)
        if success:
            logger.info("Webhook встановлено успішно.")
        else:
            logger.error("Не вдалося встановити webhook.")
    try:
        loop.run_until_complete(set_webhook())
    except Exception as e:
        logger.error(f"Помилка встановлення вебхука: {e}")
    # Запускаємо uvicorn, використовуючи наш event loop
    uvicorn.run(app, host="0.0.0.0", port=PORT)
