# Reset - iteration 2 regression: job_id guard (recs/roadmap), stale pending expiry, resources by task id, career_details upsert
import os
import time
import uuid
import threading
from datetime import datetime, timezone, timedelta
import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", os.environ.get("EXPO_BACKEND_URL", "")).rstrip("/")
API = f"{BASE_URL}/api"
mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

ANSWERS = {
    "current_job": "Magazynier", "education": "średnie", "interests": ["komputery"],
    "dislikes": ["praca fizyczna"], "languages": ["angielski B1"], "certificates": [], "achievements": "",
    "personality": ["dokładny"], "preferences": ["praca zdalna"], "city": "Poznań",
}


def poll(s, path, timeout=180):
    end = time.time() + timeout
    d = {}
    while time.time() < end:
        d = s.get(f"{API}{path}").json()
        if d.get("status") in ("ready", "error"):
            return d
        time.sleep(4)
    return d


@pytest.fixture(scope="module")
def user():
    s = requests.Session()
    email = f"test_it2_{uuid.uuid4().hex[:8]}@test.pl"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "test123", "name": "TEST_It2"})
    assert r.status_code == 201, r.text
    d = r.json()
    s.headers["Authorization"] = f"Bearer {d['access_token']}"
    assert s.put(f"{API}/profile", json={"answers": ANSWERS}).status_code == 200
    u = {"s": s, "id": d["user"]["id"] if "user" in d else None, "state": {}}
    if not u["id"]:
        u["id"] = s.get(f"{API}/auth/me").json()["id"]
    yield u
    mdb.users.delete_one({"email": email})
    for c in ("profiles", "recommendations", "roadmaps", "career_details"):
        mdb[c].delete_many({"user_id": u["id"]})


class TestJobGuard:
    def test_recommendations_double_post_latest_wins(self, user):
        s = user["s"]
        assert s.post(f"{API}/recommendations/generate").status_code == 200
        job1 = mdb.recommendations.find_one({"user_id": user["id"]})["job_id"]
        time.sleep(1)
        assert s.post(f"{API}/recommendations/generate").status_code == 200
        job2 = mdb.recommendations.find_one({"user_id": user["id"]})["job_id"]
        assert job1 != job2
        d = poll(s, "/recommendations")
        assert d["status"] == "ready", d
        assert d["job_id"] == job2
        ids = [c["id"] for c in d["now"] + d["future"]]
        # wait so the first (stale) job has surely finished, result must be unchanged
        time.sleep(25)
        d2 = s.get(f"{API}/recommendations").json()
        assert d2["job_id"] == job2 and d2["status"] == "ready"
        assert [c["id"] for c in d2["now"] + d2["future"]] == ids, "stale job overwrote newer result"
        user["state"]["careers"] = d2["now"] + d2["future"]

    def test_roadmap_double_post_latest_wins(self, user):
        cs = user["state"].get("careers") or pytest.skip("no careers")
        s = user["s"]
        assert s.post(f"{API}/roadmap", json={"career_id": cs[0]["id"]}).status_code == 200
        time.sleep(1)
        assert s.post(f"{API}/roadmap", json={"career_id": cs[1]["id"]}).status_code == 200
        job2 = mdb.roadmaps.find_one({"user_id": user["id"]})["job_id"]
        d = poll(s, "/roadmap")
        assert d["status"] == "ready", d
        assert d["career"]["id"] == cs[1]["id"] and d["job_id"] == job2
        mids = [m["id"] for m in d["milestones"]]
        time.sleep(25)
        d2 = s.get(f"{API}/roadmap").json()
        assert d2["career"]["id"] == cs[1]["id"] and [m["id"] for m in d2["milestones"]] == mids
        user["state"]["roadmap"] = d2


class TestResourcesAndDetails:
    def test_resources_saved_by_task_id(self, user):
        rm = user["state"].get("roadmap") or pytest.skip("no roadmap")
        task = rm["milestones"][1]["tasks"][-1]
        r = user["s"].get(f"{API}/roadmap/tasks/{task['id']}/resources", timeout=120)
        assert r.status_code == 200, r.text
        doc = mdb.roadmaps.find_one({"user_id": user["id"]})
        saved = {t["id"]: t.get("resources") for m in doc["milestones"] for t in m["tasks"]}
        assert saved[task["id"]] and saved[task["id"]]["overview"] == r.json()["overview"]
        assert sum(1 for v in saved.values() if v) == 1, "resources written to wrong/multiple tasks"
        t = time.time()
        r2 = user["s"].get(f"{API}/roadmap/tasks/{task['id']}/resources")
        assert r2.status_code == 200 and time.time() - t < 5 and r2.json()["overview"] == r.json()["overview"]

    def test_career_details_upsert_concurrent(self, user):
        cs = user["state"].get("careers") or pytest.skip("no careers")
        cid = cs[2]["id"]
        codes = []

        def hit():
            codes.append(user["s"].get(f"{API}/careers/{cid}", timeout=120).status_code)
        th = [threading.Thread(target=hit) for _ in range(2)]
        [t.start() for t in th]
        [t.join() for t in th]
        assert codes == [200, 200], codes
        assert mdb.career_details.count_documents({"user_id": user["id"], "career_id": cid}) == 1


class TestStale:
    def test_stale_pending_recommendations_becomes_error(self, user):
        old = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        mdb.recommendations.update_one({"user_id": user["id"]}, {"$set": {"status": "pending", "started_at": old}})
        d = user["s"].get(f"{API}/recommendations").json()
        assert d["status"] == "error"
        assert mdb.recommendations.find_one({"user_id": user["id"]})["status"] == "error"

    def test_fresh_pending_stays_pending(self, user):
        mdb.roadmaps.update_one({"user_id": user["id"]}, {"$set": {"status": "pending", "started_at": datetime.now(timezone.utc).isoformat()}})
        assert user["s"].get(f"{API}/roadmap").json()["status"] == "pending"

    def test_stale_pending_roadmap_becomes_error(self, user):
        old = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        mdb.roadmaps.update_one({"user_id": user["id"]}, {"$set": {"status": "pending", "started_at": old}})
        assert user["s"].get(f"{API}/roadmap").json()["status"] == "error"
        assert mdb.roadmaps.find_one({"user_id": user["id"]})["status"] == "error"
