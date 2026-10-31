# Seeds a ready roadmap doc directly in mongo for a given user_id/path_id (skips LLM/quiz flow)
# so we can test the daily-plan settings locking behavior cleanly without consuming LLM credits
# on roadmap generation itself.
import asyncio
import os
import sys
import uuid

from motor.motor_asyncio import AsyncIOMotorClient


async def main(email):
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    u = await db.users.find_one({"email": email})
    if not u:
        print("NO_USER")
        return
    uid = str(u["_id"])
    path_id = f"TEST_fresh_{uuid.uuid4().hex[:8]}"
    task1 = {"id": uuid.uuid4().hex[:10], "title": "Naucz się Excela", "description": "Podstawy arkuszy kalkulacyjnych", "type": "skill", "done": False}
    task2 = {"id": uuid.uuid4().hex[:10], "title": "Zrob kurs online", "description": "Kurs wprowadzający", "type": "course", "done": False}
    doc = {
        "user_id": uid, "path_id": path_id, "active": True, "status": "ready",
        "career": {"id": "testfresh", "title": "TEST Analityk danych"},
        "milestones": [{"id": uuid.uuid4().hex[:10], "title": "Start", "tasks": [task1, task2]}],
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    await db.roadmaps.update_many({"user_id": uid}, {"$set": {"active": False}})
    await db.roadmaps.insert_one(doc)
    print("SEEDED", uid, path_id)
    cli.close()


asyncio.run(main(sys.argv[1]))
