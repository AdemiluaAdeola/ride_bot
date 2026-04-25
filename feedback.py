import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Ride, Feedback, RideStatus
from schemas import FeedbackCreate, FeedbackOut

router = APIRouter()

@router.post("/", response_model=FeedbackOut, status_code=201)
async def submit_feedback(payload: FeedbackCreate, db: AsyncSession = Depends(get_db)):
    ride = await db.get(Ride, payload.ride_id)
    if not ride:
        raise HTTPException(404, "Ride not found")
    if ride.status != RideStatus.completed:
        raise HTTPException(400, "Feedback only allowed after ride is completed")
    if ride.feedback:
        raise HTTPException(400, "Feedback already submitted for this ride")
    fb = Feedback(**payload.model_dump())
    db.add(fb)
    await db.commit()
    await db.refresh(fb)
    return fb

@router.get("/{ride_id}", response_model=FeedbackOut)
async def get_feedback(ride_id: str, db: AsyncSession = Depends(get_db)):
    ride = await db.get(Ride, ride_id)
    if not ride or not ride.feedback:
        raise HTTPException(404, "Feedback not found")
    return ride.feedback
