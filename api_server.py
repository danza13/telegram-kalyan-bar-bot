import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from telegram import Bot

# Завантаження змінних середовища
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")

if BOT_TOKEN is None:
    raise ValueError("BOT_TOKEN не встановлений у файлі .env")
if GROUP_CHAT_ID is None:
    raise ValueError("GROUP_CHAT_ID не встановлений у файлі .env")

try:
    GROUP_CHAT_ID = int(GROUP_CHAT_ID)
except ValueError:
    raise ValueError("GROUP_CHAT_ID повинен бути числом.")

# Ініціалізація бота
bot = Bot(token=BOT_TOKEN)

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Модель даних для бронювання
class Booking(BaseModel):
    establishment: str
    datetime: str
    guests: int
    name: str
    phone: str

@app.post("/booking/")
async def create_booking(booking: Booking):
    booking_info = (
        "📅 *Бронювання*\n"
        f"🏠 *Заклад:* {booking.establishment}\n"
        f"🕒 *Час та дата:* {booking.datetime}\n"
        f"👥 *Кількість гостей:* {booking.guests}\n"
        f"📝 *Контактна особа:* {booking.name}\n"
        f"📞 *Номер телефону:* {booking.phone}"
    )

    try:
        await bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=booking_info,
            parse_mode='Markdown'
        )
        logger.info("Бронювання успішно надіслано в групу.")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Помилка при відправці бронювання: {e}")
        raise HTTPException(status_code=500, detail="Помилка при відправці бронювання.")

