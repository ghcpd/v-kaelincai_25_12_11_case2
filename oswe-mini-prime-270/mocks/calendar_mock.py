from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import random
import time

app = FastAPI(title="Mock Calendar API")

class BookRequest(BaseModel):
    appointment_id: str
    user_id: str
    start_time: str
    end_time: str
    location: str

@app.post("/calendar/book")
def book(req: BookRequest):
    # Simulate delays or failures randomly for testing
    r = random.random()
    if r < 0.1:
        raise HTTPException(status_code=500, detail="Random failure")
    if r < 0.3:
        time.sleep(2)  # simulate delay beyond timeout
    return {"status": "booked", "appointment_id": req.appointment_id}
