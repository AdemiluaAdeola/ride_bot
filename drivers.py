import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import Driver
from schemas import DriverCreate, DriverOut

router = APIRouter()

@router.post("/", response_model=DriverOut, status_code=201)
async def add_driver(payload: DriverCreate, db: AsyncSession = Depends(get_db)):
    driver = Driver(**payload.model_dump())
    db.add(driver)
    await db.commit()
    await db.refresh(driver)
    return driver

@router.get("/", response_model=list[DriverOut])
async def list_drivers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Driver).order_by(Driver.created_at.desc()))
    return result.scalars().all()

@router.get("/available", response_model=list[DriverOut])
async def available_drivers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Driver).where(Driver.is_available == 1))
    return result.scalars().all()

@router.get("/{driver_id}", response_model=DriverOut)
async def get_driver(driver_id: str, db: AsyncSession = Depends(get_db)):
    driver = await db.get(Driver, driver_id)
    if not driver:
        raise HTTPException(404, "Driver not found")
    return driver
