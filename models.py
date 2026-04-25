from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime, timezone
import enum, uuid

def new_id():
    return str(uuid.uuid4())

class RideStatus(str, enum.Enum):
    requested = "requested"
    awaiting_payment = "awaiting_payment"
    confirmed = "confirmed"
    driver_arrived = "driver_arrived"
    in_progress = "in_progress"
    completed = "completed"
    flagged = "flagged"
    cancelled = "cancelled"

class RiskLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=new_id)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    phone = Column(String, nullable=True)
    telegram_id = Column(String, unique=True, nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    rides = relationship("Ride", back_populates="user")

class Driver(Base):
    __tablename__ = "drivers"
    id = Column(String, primary_key=True, default=new_id)
    name = Column(String, nullable=False)
    vehicle = Column(String, nullable=False)
    plate = Column(String, nullable=False)
    is_available = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    rides = relationship("Ride", back_populates="driver")

class Ride(Base):
    __tablename__ = "rides"
    id = Column(String, primary_key=True, default=new_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    driver_id = Column(String, ForeignKey("drivers.id"), nullable=True)
    pickup = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    fare = Column(Float, nullable=False)
    status = Column(SAEnum(RideStatus), default=RideStatus.requested)
    risk_level = Column(SAEnum(RiskLevel), default=RiskLevel.low)
    risk_score = Column(Float, default=0.0)
    ride_code = Column(String, nullable=True)
    code_expires_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user = relationship("User", back_populates="rides")
    driver = relationship("Driver", back_populates="rides")
    payment = relationship("Payment", back_populates="ride", uselist=False)
    feedback = relationship("Feedback", back_populates="ride", uselist=False)

class Payment(Base):
    __tablename__ = "payments"
    id = Column(String, primary_key=True, default=new_id)
    ride_id = Column(String, ForeignKey("rides.id"), nullable=False, unique=True)
    amount = Column(Float, nullable=False)
    reference = Column(String, unique=True, nullable=False)
    status = Column(String, default="pending")
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ride = relationship("Ride", back_populates="payment")

class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(String, primary_key=True, default=new_id)
    ride_id = Column(String, ForeignKey("rides.id"), nullable=False, unique=True)
    rating = Column(Integer, nullable=False)
    comment = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ride = relationship("Ride", back_populates="feedback")
