# Iteration 12: premium no longer gates paths/study plan; free users get up to 3 paths (ads are client-side only)
import os
import uuid
import asyncio
import pytest
import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", os.environ.get("EXPO_BACKEND_URL", "")).rstrip("/")
API = f"{BASE_URL}/api"
EXISTING_CAREER_ID = "0259052ff57d"  # ania's existing path career (same title -> no LLM call)


def login(email, pw="test123"):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed for {email}: {r.status_code}")
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    s.user = r.json()["user"]
    return s


def mongo(coro_fn):
    async def run():
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            return await coro_fn(cli[os.environ["DB_NAME"]])
        finally:
            cli.close()
    return asyncio.run(run())


@pytest.fixture(scope="module")
def ania():
    return login("ania_t1@test.pl")


# Paths listing: free user limit is 3
class TestPathsFree:
    def test_paths_limit_3_for_free(self, ania):
        r = ania.get(f"{API}/paths")
        assert r.status_code == 200
        d = r.json()
        assert d["limit"] == 3
        assert d["is_premium"] is False
        assert isinstance(d["paths"], list) and len(d["paths"]) >= 1

    def test_choose_existing_career_returns_existing(self, ania):
        uid = ania.user["id"]

        async def find(db):
            rec = await db.recommendations.find_one({"user_id": uid}, {"_id": 0}) or {}
            titles = {d["career"]["title"] async for d in db.roadmaps.find({"user_id": uid}, {"career.title": 1})}
            return next((c["id"] for c in (rec.get("now") or []) + (rec.get("future") or []) if c["title"] in titles), None)

        cid = mongo(find)
        if not cid:
            pytest.skip("no recommended career matches an existing path (would trigger LLM)")
        r = ania.post(f"{API}/roadmap", json={"career_id": cid})
        assert r.status_code == 200, r.text
        assert r.json().get("existing") is True

    def test_fourth_path_forbidden_for_free_and_no_replace(self, ania):
        uid = ania.user["id"]
        fake_ids = [f"test{uuid.uuid4().hex[:8]}" for _ in range(2)]

        async def seed(db):
            n = await db.roadmaps.count_documents({"user_id": uid})
            docs = [{"user_id": uid, "path_id": p, "active": False, "career": {"id": p, "title": f"TEST_fake_{p}"},
                     "status": "ready", "milestones": [], "created_at": "2026-01-01T00:00:00+00:00"} for p in fake_ids[: max(0, 3 - n)]]
            if docs:
                await db.roadmaps.insert_many(docs)
            rec = await db.recommendations.find_one({"user_id": uid}, {"_id": 0})
            titles = {d["career"]["title"] async for d in db.roadmaps.find({"user_id": uid}, {"career.title": 1})}
            other = next((c["id"] for c in (rec.get("now") or []) + (rec.get("future") or []) if c["title"] not in titles), None)
            return other

        other = mongo(seed)
        try:
            if not other:
                pytest.skip("no other career available")
            r = ania.post(f"{API}/roadmap", json={"career_id": other})
            assert r.status_code == 403, r.text
            assert "3" in r.json()["detail"]
            paths = ania.get(f"{API}/paths").json()["paths"]
            assert len(paths) == 3  # nothing replaced / added
        finally:
            mongo(lambda db: db.roadmaps.delete_many({"user_id": uid, "path_id": {"$in": fake_ids}}))
            ania.post(f"{API}/paths/fba2ceb59234/activate")


# Study plan: no premium gate (402) for free users
class TestStudyPlanFree:
    def test_get_study_plan_free(self, ania):
        r = ania.get(f"{API}/roadmap/study-plan")
        assert r.status_code == 200
        assert r.json()["status"] in ("ready", "pending", "none", "error")

    def test_post_study_plan_without_path_is_400_not_402(self):
        s = login("test_ui_fresh@test.pl")
        if s.get(f"{API}/paths").json()["paths"]:
            pytest.skip("fresh user has paths")
        r = s.post(f"{API}/roadmap/study-plan")
        assert r.status_code == 400, r.text

    def test_premium_config_path_limit(self, ania):
        r = ania.get(f"{API}/premium")
        if r.status_code == 404:
            pytest.skip("no /premium endpoint")
        assert r.json().get("path_limit") == 3
