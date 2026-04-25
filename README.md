# SlickRide — FastAPI + Telegram Bot

Campus ride-booking system with fraud awareness, full ride lifecycle management, and user data collection.

## Stack
- **FastAPI** (async) — REST backend
- **SQLAlchemy 2 + aiosqlite** — async ORM, SQLite (swap for Postgres in prod)
- **python-telegram-bot v20+** — async Telegram bot
- **httpx** — async HTTP client (bot → API)

## Project layout
```
slickride/
├── main.py              # FastAPI app + router registration
├── database.py          # Async engine + session factory
├── models.py            # SQLAlchemy ORM models
├── schemas.py           # Pydantic v2 schemas
├── fraud.py             # Fraud scoring engine
├── telegram_bot.py      # Telegram ConversationHandler
├── seed.py              # Seed drivers
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── routers/
    ├── users.py         # POST /users, GET /users/{id}
    ├── rides.py         # Full ride lifecycle
    ├── payments.py      # Payment verification
    ├── drivers.py       # Driver management
    └── feedback.py      # Post-ride rating
```

## Quickstart (local)
```bash
pip install -r requirements.txt

# Start API
uvicorn main:app --reload --port 8000

# Seed drivers (new terminal)
python seed.py

# Start bot (new terminal)
TELEGRAM_BOT_TOKEN=xxx python telegram_bot.py
```

## Quickstart (Docker)
```bash
cp .env.example .env
# edit .env — set TELEGRAM_BOT_TOKEN

docker-compose up --build
```

## API docs
Visit http://localhost:8000/docs for the full interactive Swagger UI.

## Ride flow
```
POST /users/                    register user (name + email collected here)
POST /rides/                    book ride → returns risk_level
POST /rides/{id}/confirm        user confirms fare
POST /payments/verify           verify payment reference
POST /rides/{id}/assign-driver  auto-assigns available driver, generates ride_code
POST /rides/{id}/start          validate ride_code → start trip
POST /rides/{id}/end            complete trip
POST /feedback/                 submit 1–5 star rating
```

## Fraud levels
| risk_level | Bot behaviour |
|------------|---------------|
| `low`      | Normal flow |
| `medium`   | Extra confirmation step |
| `high`     | Ride blocked, user told to contact support |

## Swapping SQLite → Postgres
In `database.py`, change:
```python
DATABASE_URL = "postgresql+asyncpg://user:pass@host/dbname"
```
Add `asyncpg` to `requirements.txt`. No other changes needed.

## Payment integration (Paystack)
In `routers/payments.py`, replace the stub with:
```python
import httpx
r = await httpx.AsyncClient().get(
    f"https://api.paystack.co/transaction/verify/{reference}",
    headers={"Authorization": f"Bearer {os.getenv('PAYSTACK_SECRET_KEY')}"}
)
data = r.json()
if not data["status"] or data["data"]["status"] != "success":
    raise HTTPException(400, "Payment not successful")
```
