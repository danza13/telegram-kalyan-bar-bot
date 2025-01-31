import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError
from fastapi.middleware.cors import CORSMiddleware

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

bot = Bot(token=BOT_TOKEN)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://danza13.github.io/"],  # Замініть на ваш фактичний URL WebApp
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Booking(BaseModel):
    establishment: str
    datetime: str
    guests: int
    name: str
    phone: str

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
        await bot.send_message(chat_id=GROUP_CHAT_ID, text=booking_info, parse_mode='Markdown')
        logger.info("Бронювання успішно надіслано до Telegram групи.")
        return {"status": "success", "message": "Бронювання отримано."}
    except TelegramError as e:
        logger.error(f"Помилка при відправці повідомлення до Telegram: {e}")
        raise HTTPException(status_code=500, detail="Не вдалося відправити бронювання до Telegram.")

@app.get("/")
def read_root():
    return {"message": "API для бронювання Telegram працює."}
