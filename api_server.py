from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Dict

app = FastAPI(title="Telegram WebApp API Server")

# Проста in-memory база даних (для демонстрації)
bookings: Dict[int, str] = {}

# Схема даних для бронювання
class Booking(BaseModel):
    user_id: int
    selected_datetime: str

@app.post("/webapp_booking")
async def create_booking(booking: Booking):
    """
    Приймає POST-запит із даними бронювання від Web App.
    Зберігає дату і час для користувача (user_id).
    """
    bookings[booking.user_id] = booking.selected_datetime
    return {"message": "Booking saved", "user_id": booking.user_id}

@app.get("/get_booking")
async def get_booking(user_id: int = Query(..., description="Telegram User ID")):
    """
    Повертає збережену дату та час для заданого user_id.
    Дані видаляються після отримання (одноразове використання).
    """
    if user_id in bookings:
        selected_datetime = bookings.pop(user_id)  # видаляємо, щоб уникнути повторного використання
        return {"selected_datetime": selected_datetime}
    else:
        raise HTTPException(status_code=404, detail="Booking not found")
