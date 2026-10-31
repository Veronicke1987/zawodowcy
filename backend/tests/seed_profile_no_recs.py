# Seeds a minimal `profiles` doc for a user directly in mongo, WITHOUT triggering
# /recommendations/generate, so GET /api/recommendations returns {"status":"none"}.
# Used only to reach the Home-tab "none" state UI for testing the new "Wpisz stanowisko"
# entry point (this state is hard to reach via normal UI since quiz completion always
# calls /recommendations/generate immediately).
import asyncio
import os
import sys

from motor.motor_asyncio import AsyncIOMotorClient


async def main(email):
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    u = await db.users.find_one({"email": email})
    if not u:
        print("NO_USER")
        return
    uid = str(u["_id"])
    await db.profiles.update_one({"user_id": uid}, {"$set": {"user_id": uid, "answers": {"reset_mode": "search"}}}, upsert=True)
    await db.recommendations.delete_many({"user_id": uid})
    await db.roadmaps.delete_many({"user_id": uid})
    print("SEEDED profile (no recs) for", uid)
    cli.close()


asyncio.run(main(sys.argv[1]))
