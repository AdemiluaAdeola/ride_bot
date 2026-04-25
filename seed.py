"""
Seed the database with test drivers.
Run once: python seed.py
"""
import asyncio
import httpx

API_BASE = "http://localhost:8000"

DRIVERS = [
    {"name": "Tunde Okafor",  "vehicle": "Toyota Camry",   "plate": "AGL-231-KJ"},
    {"name": "Bisi Adeyemi",  "vehicle": "Honda Accord",   "plate": "KJA-045-LG"},
    {"name": "Emeka Nwosu",   "vehicle": "Hyundai Elantra","plate": "EKY-882-AB"},
    {"name": "Funke Salami",  "vehicle": "Toyota Corolla", "plate": "OYO-119-IB"},
    {"name": "Chidi Okonkwo", "vehicle": "Kia Rio",        "plate": "LAG-774-EK"},
]


async def seed():
    async with httpx.AsyncClient(base_url=API_BASE, timeout=10) as client:
        for d in DRIVERS:
            r = await client.post("/drivers/", json=d)
            if r.status_code == 201:
                print(f"✅  Added driver: {d['name']}")
            else:
                print(f"⚠️  Skipped {d['name']}: {r.json()}")


if __name__ == "__main__":
    asyncio.run(seed())
