import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import random, string
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import Ride, User, Driver, RideStatus
from schemas import RideRequest, RideOut, RideStartRequest, FraudSignal
from fraud import score_ride

router = APIRouter()

BASE_FARE = 500.0
RATE_PER_KM = 150.0
AVG_KM = 3.2
CODE_TTL_MINUTES = 10


def calc_fare() -> float:
    return round(BASE_FARE + RATE_PER_KM * AVG_KM, 2)


def gen_code(length=4) -> str:
    return "".join(random.choices(string.digits, k=length))


@router.post("/", response_model=RideOut, status_code=201)
async def request_ride(payload: RideRequest, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, payload.user_id)
    if not user:
        raise HTTPException(404, "User not found")

    fraud = score_ride(payload.pickup, payload.destination, payload.user_id)
    fare = calc_fare()

    ride = Ride(
        user_id=payload.user_id,
        pickup=payload.pickup,
        destination=payload.destination,
        fare=fare,
        status=RideStatus.flagged if fraud["risk_level"].value == "high" else RideStatus.requested,
        risk_level=fraud["risk_level"],
        risk_score=fraud["risk_score"],
    )
    db.add(ride)
    await db.commit()
    await db.refresh(ride)
    return ride


@router.get("/{ride_id}", response_model=RideOut)
async def get_ride(ride_id: str, db: AsyncSession = Depends(get_db)):
    ride = await db.get(Ride, ride_id)
    if not ride:
        raise HTTPException(404, "Ride not found")
    return ride


@router.get("/{ride_id}/fraud-signal", response_model=FraudSignal)
async def fraud_signal(ride_id: str, db: AsyncSession = Depends(get_db)):
    ride = await db.get(Ride, ride_id)
    if not ride:
        raise HTTPException(404, "Ride not found")
    return FraudSignal(
        ride_id=ride.id,
        risk_score=ride.risk_score,
        risk_level=ride.risk_level,
        flags=[],
    )


@router.post("/{ride_id}/confirm", response_model=RideOut)
async def confirm_ride(ride_id: str, db: AsyncSession = Depends(get_db)):
    ride = await db.get(Ride, ride_id)
    if not ride:
        raise HTTPException(404, "Ride not found")
    if ride.status == RideStatus.flagged:
        raise HTTPException(403, "Ride flagged — cannot confirm")
    if ride.status != RideStatus.requested:
        raise HTTPException(400, f"Cannot confirm ride in status: {ride.status}")
    ride.status = RideStatus.awaiting_payment
    await db.commit()
    await db.refresh(ride)
    return ride


@router.post("/{ride_id}/assign-driver", response_model=RideOut)
async def assign_driver(ride_id: str, db: AsyncSession = Depends(get_db)):
    ride = await db.get(Ride, ride_id)
    if not ride:
        raise HTTPException(404, "Ride not found")
    if ride.status != RideStatus.confirmed:
        raise HTTPException(400, "Payment must be confirmed before assigning driver")

    result = await db.execute(select(Driver).where(Driver.is_available == 1).limit(1))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(503, "No drivers available right now")

    code = gen_code()
    ride.driver_id = driver.id
    ride.ride_code = code
    ride.code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MINUTES)
    ride.status = RideStatus.driver_arrived
    driver.is_available = 0
    await db.commit()
    await db.refresh(ride)
    return ride


@router.post("/{ride_id}/start", response_model=RideOut)
async def start_ride(ride_id: str, payload: RideStartRequest, db: AsyncSession = Depends(get_db)):
    ride = await db.get(Ride, ride_id)
    if not ride:
        raise HTTPException(404, "Ride not found")
    if ride.status != RideStatus.driver_arrived:
        raise HTTPException(400, "Ride not ready to start")
    if ride.ride_code != payload.ride_code:
        raise HTTPException(400, "Invalid ride code")
    now = datetime.now(timezone.utc)
    expires = ride.code_expires_at
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires and now > expires:
        raise HTTPException(400, "Ride code expired")
    ride.status = RideStatus.in_progress
    ride.started_at = now
    await db.commit()
    await db.refresh(ride)
    return ride


@router.post("/{ride_id}/end", response_model=RideOut)
async def end_ride(ride_id: str, db: AsyncSession = Depends(get_db)):
    ride = await db.get(Ride, ride_id)
    if not ride:
        raise HTTPException(404, "Ride not found")
    if ride.status != RideStatus.in_progress:
        raise HTTPException(400, "Ride is not in progress")
    ride.status = RideStatus.completed
    ride.ended_at = datetime.now(timezone.utc)
    if ride.driver_id:
        driver = await db.get(Driver, ride.driver_id)
        if driver:
            driver.is_available = 1
    await db.commit()
    await db.refresh(ride)
    return ride


@router.delete("/{ride_id}/cancel", response_model=RideOut)
async def cancel_ride(ride_id: str, db: AsyncSession = Depends(get_db)):
    ride = await db.get(Ride, ride_id)
    if not ride:
        raise HTTPException(404, "Ride not found")
    if ride.status in (RideStatus.in_progress, RideStatus.completed):
        raise HTTPException(400, "Cannot cancel an active or completed ride")
    ride.status = RideStatus.cancelled
    await db.commit()
    await db.refresh(ride)
    return ride


@router.get("/user/{user_id}", response_model=list[RideOut])
async def user_rides(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Ride).where(Ride.user_id == user_id).order_by(Ride.created_at.desc())
    )
    return result.scalars().all()
