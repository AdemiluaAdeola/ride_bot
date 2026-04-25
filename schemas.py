from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from models import RideStatus, RiskLevel

class UserCreate(BaseModel):
    name: str = Field(..., min_length=2)
    email: EmailStr
    phone: Optional[str] = None
    telegram_id: Optional[str] = None

class UserOut(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str]
    telegram_id: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}

class RideRequest(BaseModel):
    user_id: str
    pickup: str = Field(..., min_length=2)
    destination: str = Field(..., min_length=2)

class RideOut(BaseModel):
    id: str
    user_id: str
    driver_id: Optional[str]
    pickup: str
    destination: str
    fare: float
    status: RideStatus
    risk_level: RiskLevel
    risk_score: float
    ride_code: Optional[str]
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    created_at: datetime
    model_config = {"from_attributes": True}

class RideStartRequest(BaseModel):
    ride_code: str

class PaymentVerifyRequest(BaseModel):
    ride_id: str
    reference: str

class PaymentOut(BaseModel):
    id: str
    ride_id: str
    amount: float
    reference: str
    status: str
    verified_at: Optional[datetime]
    created_at: datetime
    model_config = {"from_attributes": True}

class DriverCreate(BaseModel):
    name: str
    vehicle: str
    plate: str

class DriverOut(BaseModel):
    id: str
    name: str
    vehicle: str
    plate: str
    is_available: bool
    created_at: datetime
    model_config = {"from_attributes": True}

class FeedbackCreate(BaseModel):
    ride_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None

class FeedbackOut(BaseModel):
    id: str
    ride_id: str
    rating: int
    comment: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}

class FraudSignal(BaseModel):
    ride_id: str
    risk_score: float
    risk_level: RiskLevel
    flags: list[str] = []
