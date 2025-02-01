import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from telegram import Bot, ReplyKeyboardMarkup
from telegram.error import TelegramError
from fastapi.middleware.cors import CORSMiddleware

# Завантаження змінних середовища
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")

if BOT_TOKEN is None:
    raise ValueError("BOT_TOKEN не встановлений у .env")
if GROUP_CHAT_ID is None:
    raise ValueError("GROUP_CHAT_ID не встановлений у .env")

try:
    GROUP_CHAT_ID = int(GROUP_CHAT_ID)
except ValueError:
    raise ValueError("GROUP_CHAT_ID повинен бути числом.")

# Ініціалізація Telegram бота
bot = Bot(token=BOT_TOKEN)

# Ініціалізація FastAPI додатку
app = FastAPI()

# Налаштування CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://danza13.github.io"],  # Змініть на URL вашого Web App
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Модель даних бронювання (з доданим полем chat_id)
class Booking(BaseModel):
    establishment: str
    datetime: str
    guests: int
    name: str
    phone: str
    chat_id: int = None  # необов’язкове поле для передачі chat_id користувача

@app.post("/booking")
async def create_booking(booking: Booking):
    logger.info(f"Отримано бронювання: {booking}")
    
    booking_info = (
        "📅 *Бронювання*\n"
        f"🏠 *Заклад:* {booking.establishment}\n"
        f"🕒 *Час та дата:* {booking.datetime}\n"
        f"👥 *Кількість гостей:* {booking.guests}\n"
        f"📝 *Контактна особа:* {booking.name}\n"
        f"📞 *Номер телефону:* {booking.phone}"
    )
    
    try:
        # Надсилаємо повідомлення до Telegram групи
        await bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=booking_info,
            parse_mode='Markdown'
        )
        logger.info("Бронювання успішно надіслано до Telegram групи.")
        
        # Якщо chat_id передано, надсилаємо підтвердження користувачу із клавіатурою
        if booking.chat_id:
            reply_keyboard = [['Повернутись до початку', 'Переглянути меню']]
            markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
            await bot.send_message(
                chat_id=booking.chat_id,
                text="Дякуємо, бронювання отримано! Наш адміністратор незабаром зв'яжеться з вами.",
                reply_markup=markup
            )
            logger.info("Підтвердження надіслано користувачу.")
            
        return {"status": "success", "message": "Бронювання отримано."}
    except TelegramError as e:
        logger.error(f"Помилка при відправці повідомлення до Telegram: {e}")
        raise HTTPException(status_code=500, detail="Не вдалося відправити бронювання до Telegram.")

# Кореневий маршрут
@app.get("/")
def read_root():
    return {"message": "API для бронювання Telegram працює."}
