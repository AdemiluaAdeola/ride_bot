import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Ride, Payment, RideStatus
from schemas import PaymentVerifyRequest, PaymentOut

router = APIRouter()


@router.post("/verify", response_model=PaymentOut)
async def verify_payment(payload: PaymentVerifyRequest, db: AsyncSession = Depends(get_db)):
    ride = await db.get(Ride, payload.ride_id)
    if not ride:
        raise HTTPException(404, "Ride not found")
    if ride.status == RideStatus.flagged:
        raise HTTPException(403, "Payment blocked — ride flagged")
    if ride.status != RideStatus.awaiting_payment:
        raise HTTPException(400, f"Ride not awaiting payment (status: {ride.status})")

    # --- Paystack / Flutterwave webhook verification goes here ---
    # For now, any non-empty reference is treated as confirmed.
    if not payload.reference.strip():
        raise HTTPException(400, "Invalid payment reference")

    payment = Payment(
        ride_id=ride.id,
        amount=ride.fare,
        reference=payload.reference,
        status="confirmed",
        verified_at=datetime.now(timezone.utc),
    )
    ride.status = RideStatus.confirmed
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return payment


@router.get("/{ride_id}", response_model=PaymentOut)
async def get_payment(ride_id: str, db: AsyncSession = Depends(get_db)):
    ride = await db.get(Ride, ride_id)
    if not ride or not ride.payment:
        raise HTTPException(404, "Payment not found")
    return ride.payment
