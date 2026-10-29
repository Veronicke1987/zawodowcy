# Reset career app - backend API regression tests (auth, profile, recommendations, careers, roadmap, resources)
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", os.environ.get("EXPO_BACKEND_URL", "")).rstrip("/")
API = f"{BASE_URL}/api"

ANSWERS = {
    "current_job": "Kasjer w sklepie", "education": "średnie", "interests": ["komputery", "liczby"],
    "dislikes": ["praca fizyczna"], "languages": ["angielski B1"], "certificates": [], "achievements": "Pracownik miesiąca",
    "personality": ["dokładny"], "preferences": ["praca zdalna"], "city": "Kraków",
}


def poll(session, path, timeout=150):
    end = time.time() + timeout
    while time.time() < end:
        r = session.get(f"{API}{path}")
        d = r.json()
        if d.get("status") in ("ready", "error"):
            return d
        time.sleep(4)
    return d


@pytest.fixture(scope="module")
def user():
    s = requests.Session()
    email = f"test_{uuid.uuid4().hex[:8]}@test.pl"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "test123", "name": "TEST_User"})
    assert r.status_code == 201, r.text
    d = r.json()
    s.headers["Authorization"] = f"Bearer {d['access_token']}"
    return {"s": s, "email": email, "data": d, "state": {}}


# --- Auth
class TestAuth:
    def test_register_returns_user(self, user):
        u = user["data"]["user"]
        assert u["email"] == user["email"] and u["has_profile"] is False and u["role"] == "user"

    def test_register_duplicate_409(self, user):
        r = requests.post(f"{API}/auth/register", json={"email": user["email"], "password": "test123"})
        assert r.status_code == 409

    def test_login_ok_and_wrong(self, user):
        r = requests.post(f"{API}/auth/login", json={"email": user["email"].upper(), "password": "test123"})
        assert r.status_code == 200 and "access_token" in r.json()
        r2 = requests.post(f"{API}/auth/login", json={"email": user["email"], "password": "wrong123"})
        assert r2.status_code == 401

    def test_admin_login(self):
        r = requests.post(f"{API}/auth/login", json={"email": "admin@reset.app", "password": "ResetAdmin2026!"})
        assert r.status_code == 200 and r.json()["user"]["role"] == "admin"

    def test_me_requires_token(self, user):
        assert requests.get(f"{API}/auth/me").status_code == 401
        assert requests.get(f"{API}/auth/me", headers={"Authorization": "Bearer bad"}).status_code == 401
        r = user["s"].get(f"{API}/auth/me")
        assert r.status_code == 200 and r.json()["email"] == user["email"]


# --- Profile
class TestProfile:
    def test_generate_without_profile_400(self, user):
        assert user["s"].post(f"{API}/recommendations/generate").status_code == 400

    def test_put_get_profile(self, user):
        r = user["s"].put(f"{API}/profile", json={"answers": ANSWERS})
        assert r.status_code == 200
        g = user["s"].get(f"{API}/profile").json()
        assert g["answers"]["current_job"] == "Kasjer w sklepie"
        assert user["s"].get(f"{API}/auth/me").json()["has_profile"] is True


# --- Recommendations + careers + roadmap (LLM, slow)
class TestLLMFlow:
    def test_recommendations(self, user):
        r = user["s"].post(f"{API}/recommendations/generate")
        assert r.status_code == 200 and r.json()["status"] == "pending"
        d = poll(user["s"], "/recommendations")
        assert d["status"] == "ready", d
        assert len(d["now"]) >= 3 and len(d["future"]) >= 3
        assert "_id" not in d
        c = d["now"][0]
        for k in ("id", "title", "category", "match"):
            assert k in c
        user["state"]["career_id"] = c["id"]

    def test_career_detail(self, user):
        cid = user["state"].get("career_id") or pytest.skip("no career")
        t = time.time()
        r = user["s"].get(f"{API}/careers/{cid}", timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("description", "pros", "cons", "requirements", "how_to_start"):
            assert k in d["detail"]
        assert len(d["job_links"]) == 4 and all(l["url"].startswith("https://") for l in d["job_links"])
        print("detail secs", time.time() - t)
        t = time.time()
        r2 = user["s"].get(f"{API}/careers/{cid}")
        assert r2.status_code == 200 and time.time() - t < 5  # cached

    def test_career_404(self, user):
        assert user["s"].get(f"{API}/careers/nonexistent").status_code == 404

    def test_roadmap(self, user):
        cid = user["state"].get("career_id") or pytest.skip("no career")
        r = user["s"].post(f"{API}/roadmap", json={"career_id": cid})
        assert r.status_code == 200
        d = poll(user["s"], "/roadmap")
        assert d["status"] == "ready", d
        assert len(d["milestones"]) >= 3 and all(len(m["tasks"]) >= 1 for m in d["milestones"])
        assert d["career"]["id"] == cid
        user["state"]["task_id"] = d["milestones"][0]["tasks"][0]["id"]

    def test_toggle_task(self, user):
        tid = user["state"].get("task_id") or pytest.skip("no task")
        r = user["s"].patch(f"{API}/roadmap/tasks/{tid}", json={"done": True})
        assert r.status_code == 200 and r.json()["done"] is True
        d = user["s"].get(f"{API}/roadmap").json()
        assert d["milestones"][0]["tasks"][0]["done"] is True
        user["s"].patch(f"{API}/roadmap/tasks/{tid}", json={"done": False})
        assert user["s"].get(f"{API}/roadmap").json()["milestones"][0]["tasks"][0]["done"] is False
        assert user["s"].patch(f"{API}/roadmap/tasks/nope", json={"done": True}).status_code == 404

    def test_task_resources(self, user):
        tid = user["state"].get("task_id") or pytest.skip("no task")
        r = user["s"].get(f"{API}/roadmap/tasks/{tid}/resources", timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "overview" in d and len(d["resources"]) >= 3
        assert all(x["url"].startswith("https://") for x in d["resources"])
        types = {x["type"] for x in d["resources"]}
        print("resource types", types)
        # resources should not leak into GET /roadmap
        rm = user["s"].get(f"{API}/roadmap").json()
        assert "resources" not in rm["milestones"][0]["tasks"][0]

    def test_cleanup(self, user):
        assert user["s"].delete(f"{API}/roadmap").status_code == 200
        assert user["s"].get(f"{API}/roadmap").json()["status"] == "none"
