from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import engine, Base
import models  # noqa: F401 — registers all models with Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="SlickRide API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers import users, rides, payments, drivers, feedback

app.include_router(users.router,    prefix="/users",    tags=["Users"])
app.include_router(rides.router,    prefix="/rides",    tags=["Rides"])
app.include_router(payments.router, prefix="/payments", tags=["Payments"])
app.include_router(drivers.router,  prefix="/drivers",  tags=["Drivers"])
app.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "SlickRide API"}
