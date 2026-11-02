"""One-off idempotent script to seed/update the admin account with a professional
premium package valid until 2026-12-31. Safe to re-run (upsert by email)."""
import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

import bcrypt
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

EMAIL = "konto.administratora@wp.pl"
PASSWORD = "admin2026!"
NAME = "Administrator"
UNTIL = "2026-12-31T23:59:59+00:00"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_pw(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


async def main():
    mongo_url = os.environ["MONGO_URL"]
    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ["DB_NAME"]]

    existing = await db.users.find_one({"email": EMAIL})
    premium = {
        "active": True,
        "plan": "professional",
        "since": now_iso(),
        "until": UNTIL,
        "granted_by": "admin_seed",
    }

    if existing:
        await db.users.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "password_hash": hash_pw(PASSWORD),
                "role": "admin",
                "premium": premium,
                "name": existing.get("name") or NAME,
            }},
        )
        print(f"Zaktualizowano istniejące konto: {EMAIL}")
    else:
        doc = {
            "email": EMAIL,
            "name": NAME,
            "password_hash": hash_pw(PASSWORD),
            "role": "admin",
            "created_at": now_iso(),
            "premium": premium,
            "streak": None,
            "country": "PL",
            "ui_language": "pl",
        }
        await db.users.insert_one(doc)
        print(f"Utworzono nowe konto administratora: {EMAIL}")

    saved = await db.users.find_one({"email": EMAIL})
    print("role:", saved.get("role"))
    print("premium:", saved.get("premium"))

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
