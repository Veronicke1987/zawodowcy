# Helper for iteration 13 UI retest: inspect / seed / cleanup fake roadmap docs for ania_t1 (avoids LLM calls)
import asyncio
import os
import sys

from motor.motor_asyncio import AsyncIOMotorClient

EMAIL = "ania_t1@test.pl"


async def main(cmd):
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    u = await db.users.find_one({"email": EMAIL})
    uid = str(u["_id"])
    print("uid", uid, "premium", u.get("is_premium"))
    if cmd == "seed":
        n = await db.roadmaps.count_documents({"user_id": uid})
        docs = [{"user_id": uid, "path_id": f"testfake{i:04d}", "active": False,
                 "career": {"id": f"testfake{i:04d}", "title": f"TEST_fake_{i}"}, "status": "ready",
                 "milestones": [], "created_at": "2026-01-01T00:00:00+00:00"} for i in range(max(0, 3 - n))]
        if docs:
            await db.roadmaps.insert_many(docs)
        print("seeded", len(docs))
    if cmd == "cleanup":
        r = await db.roadmaps.delete_many({"user_id": uid, "path_id": {"$regex": "^testfake"}})
        print("deleted", r.deleted_count)
    paths = [d async for d in db.roadmaps.find({"user_id": uid}, {"_id": 0, "path_id": 1, "active": 1, "career.title": 1, "career.id": 1})]
    print("paths", paths)
    rec = await db.recommendations.find_one({"user_id": uid}, {"_id": 0}) or {}
    titles = {p["career"]["title"] for p in paths}
    for c in (rec.get("now") or []) + (rec.get("future") or []):
        cached = bool(await db.career_details.find_one({"user_id": uid, "career_id": c["id"]}, {"_id": 1}))
        print("career", c["id"], c["title"], "existing" if c["title"] in titles else "new", "cached" if cached else "NOT_CACHED")
    cli.close()


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "show"))
