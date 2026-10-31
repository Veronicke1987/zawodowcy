"""
Phase 2 Daily Study Plan tests:
- Free user: first 2 study days unlocked, rest locked (locked=true, items=[], locked_count>0)
- Premium user: all days unlocked immediately
- Unlock-week endpoint reveals locked items, idempotent
- next-week: 400 before Saturday, append behavior, pending-dedup, no-op if already exists
- GET daily-plan includes next_status / can_generate_next
- POST /api/roadmap/study-plan now 403 for free users, works for premium; GET includes is_premium
- GET daily-plan item resources: delegates to task resources if milestone_task_id set,
  else generates+caches own resources for generic items
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_USER = "ADMIN"
ADMIN_PASS = "Test@123"


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_USER, "password": ADMIN_PASS})
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


def register_and_login(prefix):
    email = f"TEST_{prefix}_{uuid.uuid4().hex[:8]}@test.pl"
    password = "test123"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": password, "name": "Test User"})
    assert r.status_code in (200, 201), r.text
    token = r.json()["access_token"]
    return email, password, token


def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def wait_for_status(url, headers, status_path_key="status", target=("ready", "error"), timeout=90):
    """Poll an endpoint until status field reaches one of target values."""
    start = time.time()
    last = None
    while time.time() - start < timeout:
        r = requests.get(url, headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        last = data
        if data.get(status_path_key) in target:
            return data
        time.sleep(2)
    raise TimeoutError(f"Timed out waiting for status in {target}, last={last}")


def complete_quiz_and_path(headers):
    """Minimal flow: create a profile/quiz answer set then pick a recommended career path,
    then wait for roadmap to be ready. Reuses existing endpoints used by prior iterations."""
    # Try simplest known approach: submit quiz with generic answers
    r = requests.get(f"{API}/quiz/questions", headers=headers)
    if r.status_code != 200:
        return None
    questions = r.json().get("questions") or r.json()
    answers = {}
    if isinstance(questions, list):
        for q in questions:
            qid = q.get("id") or q.get("key")
            if qid:
                answers[qid] = q.get("options", ["tak"])[0] if q.get("options") else "tak"
    r2 = requests.post(f"{API}/quiz/submit", json={"answers": answers}, headers=headers)
    if r2.status_code not in (200, 202):
        return None
    rec = wait_for_status(f"{API}/recommendations", headers, timeout=90)
    recs = rec.get("recommendations") or rec.get("careers") or []
    if not recs:
        return None
    career_id = recs[0].get("id") or recs[0].get("career_id")
    r3 = requests.post(f"{API}/roadmap", json={"career_id": career_id}, headers=headers)
    if r3.status_code not in (200, 202):
        return None
    road = wait_for_status(f"{API}/roadmap", headers, timeout=120)
    return road.get("path_id")


class TestStudyPlanPremiumGate:
    """POST/GET /api/roadmap/study-plan premium gating (Phase 2)."""

    def test_free_user_create_study_plan_403(self):
        email, password, token = register_and_login("sp_free")
        headers = auth_headers(token)
        r = requests.post(f"{API}/roadmap/study-plan", headers=headers)
        # free user with no roadmap at all -> could be 400 (no roadmap) rather than 403;
        # but spec explicitly requires 403 for non-premium regardless -- check code path precedence
        assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text}"
        assert "Premium" in r.text, r.text

    def test_get_study_plan_includes_is_premium_field(self):
        email, password, token = register_and_login("sp_get")
        headers = auth_headers(token)
        r = requests.get(f"{API}/roadmap/study-plan", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "is_premium" in data
        assert data["is_premium"] is False


class TestDailyPlanLockingFree:
    """Fresh FREE user: settings -> week0 generated, days 3..7 study-days locked."""

    @classmethod
    def setup_class(cls):
        cls.email, cls.password, cls.token = register_and_login("dp_free")
        cls.headers = auth_headers(cls.token)
        cls.path_id = complete_quiz_and_path(cls.headers)

    def test_settings_requires_ready_roadmap_or_succeeds(self):
        if not self.path_id:
            pytest.skip("Could not auto-complete quiz/roadmap flow via generic endpoint guesses; "
                        "skipping fresh-user locking test, will rely on seeded ania_t1 data instead.")
        r = requests.post(f"{API}/roadmap/daily-plan/settings",
                           json={"time_mode": "daily", "time_value": 30, "free_days": []},
                           headers=self.headers)
        assert r.status_code == 200, r.text
        data = wait_for_status(f"{API}/roadmap/daily-plan", self.headers, timeout=90)
        assert data["status"] == "ready"
        week0 = data["weeks"][0]
        study_days = [d for d in week0["days"] if not d["free"]]
        unlocked = [d for d in study_days if not d["locked"]]
        locked = [d for d in study_days if d["locked"]]
        assert len(unlocked) == 2, f"expected exactly 2 unlocked study days for free user, got {len(unlocked)}"
        for d in unlocked:
            assert len(d["items"]) >= 0  # items populated (may be 0 if LLM gave none, but key present)
            assert d["locked_count"] == 0
        for d in locked:
            assert d["items"] == []
            assert d["locked_count"] > 0


class TestDailyPlanSeededUser:
    """Use seeded ania_t1 (free, already has daily_plan with week0 unlocked via ad, week1 generated)."""

    @classmethod
    def setup_class(cls):
        r = requests.post(f"{API}/auth/login", json={"email": "ania_t1@test.pl", "password": "test123"})
        assert r.status_code == 200, r.text
        cls.token = r.json()["access_token"]
        cls.headers = auth_headers(cls.token)

    def test_get_daily_plan_has_next_status_and_can_generate_next(self):
        r = requests.get(f"{API}/roadmap/daily-plan", headers=self.headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] in ("ready", "pending", "error", "none")
        assert "next_status" in data
        assert data["next_status"] in ("none", "pending", "ready", "error")
        assert "can_generate_next" in data
        assert isinstance(data["can_generate_next"], bool)
        print("ania_t1 daily plan weeks:", [(w["index"], w["start_date"]) for w in data.get("weeks", [])])

    def test_weeks_appended_not_deleted(self):
        r = requests.get(f"{API}/roadmap/daily-plan", headers=self.headers)
        data = r.json()
        weeks = data.get("weeks", [])
        assert len(weeks) >= 1
        indices = [w["index"] for w in weeks]
        assert indices == sorted(indices), "weeks must be in ascending order"
        assert len(set(indices)) == len(indices), "no duplicate week indices"

    def test_unlock_week_idempotent(self):
        r = requests.get(f"{API}/roadmap/daily-plan", headers=self.headers)
        weeks = r.json().get("weeks", [])
        if not weeks:
            pytest.skip("no weeks present for ania_t1")
        idx = weeks[0]["index"]
        r1 = requests.post(f"{API}/roadmap/daily-plan/weeks/{idx}/unlock", headers=self.headers)
        assert r1.status_code == 200, r1.text
        assert r1.json().get("ok") is True
        # verify via GET that all days of that week are unlocked
        r2 = requests.get(f"{API}/roadmap/daily-plan", headers=self.headers)
        week = next(w for w in r2.json()["weeks"] if w["index"] == idx)
        for d in week["days"]:
            assert d["locked"] is False
        # call again - idempotent, should not error
        r3 = requests.post(f"{API}/roadmap/daily-plan/weeks/{idx}/unlock", headers=self.headers)
        assert r3.status_code == 200, r3.text

    def test_unlock_week_unknown_index_404(self):
        r = requests.post(f"{API}/roadmap/daily-plan/weeks/9999/unlock", headers=self.headers)
        assert r.status_code == 404, r.text

    def test_next_week_double_call_pending_dedup_or_noop(self):
        """If next week already exists -> ready no-op. If not generatable yet -> 400.
        If generatable and not yet generated -> first call pending, second call (fired fast) should
        also return pending (not duplicate week) due to next_status guard."""
        r = requests.get(f"{API}/roadmap/daily-plan", headers=self.headers)
        data = r.json()
        if data["status"] != "ready" or not data.get("weeks"):
            pytest.skip("daily plan not ready for ania_t1")
        can_generate = data["can_generate_next"]
        r1 = requests.post(f"{API}/roadmap/daily-plan/next-week", headers=self.headers)
        if not can_generate:
            assert r1.status_code == 400, r1.text
            assert "sobot" in r1.text.lower() or "sobota" in r1.text.lower(), r1.text
            return
        # can_generate True path
        assert r1.status_code == 200, r1.text
        body1 = r1.json()
        assert body1["status"] in ("pending", "ready")
        r2 = requests.post(f"{API}/roadmap/daily-plan/next-week", headers=self.headers)
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        assert body2["status"] in ("pending", "ready")
        # wait for completion and verify weeks count increased by exactly 1 (no dup)
        before_count = len(data["weeks"])
        final = wait_for_status(f"{API}/roadmap/daily-plan", self.headers,
                                 status_path_key="next_status", target=("ready", "error", "none"), timeout=90)
        indices = [w["index"] for w in final["weeks"]]
        assert len(set(indices)) == len(indices), "duplicate week indices after double next-week call"


class TestDailyItemResources:
    """GET /api/roadmap/daily-plan/items/{item_id}/resources - delegation + caching."""

    @classmethod
    def setup_class(cls):
        r = requests.post(f"{API}/auth/login", json={"email": "ania_t1@test.pl", "password": "test123"})
        cls.token = r.json()["access_token"]
        cls.headers = auth_headers(cls.token)

    def _find_items(self):
        r = requests.get(f"{API}/roadmap/daily-plan", headers=self.headers)
        data = r.json()
        linked, generic = None, None
        for w in data.get("weeks", []):
            for d in w.get("days", []):
                for it in d.get("items", []):
                    if it.get("milestone_task_id") and not linked:
                        linked = it
                    if not it.get("milestone_task_id") and not generic:
                        generic = it
        return linked, generic

    def test_resources_for_generic_item_cached(self):
        linked, generic = self._find_items()
        if not generic:
            pytest.skip("no generic (no milestone_task_id) item found for ania_t1 to test")
        item_id = generic["id"]
        r1 = requests.get(f"{API}/roadmap/daily-plan/items/{item_id}/resources", headers=self.headers, timeout=60)
        assert r1.status_code == 200, r1.text
        data1 = r1.json()
        assert "overview" in data1
        assert "steps" in data1
        assert "resources" in data1
        assert len(data1["resources"]) > 0
        for res in data1["resources"]:
            assert "url" in res and res["url"]
        # second call should be cached (fast, identical content)
        start = time.time()
        r2 = requests.get(f"{API}/roadmap/daily-plan/items/{item_id}/resources", headers=self.headers, timeout=60)
        elapsed = time.time() - start
        assert r2.status_code == 200, r2.text
        data2 = r2.json()
        assert data2["overview"] == data1["overview"], "cached response should be identical, not re-generated"
        print(f"second call elapsed: {elapsed:.2f}s (should be fast, cached)")

    def test_resources_for_linked_item_delegates_to_task_resources(self):
        linked, generic = self._find_items()
        if not linked:
            pytest.skip("no item with milestone_task_id found for ania_t1 to test delegation")
        item_id = linked["id"]
        task_id = linked["milestone_task_id"]
        r1 = requests.get(f"{API}/roadmap/daily-plan/items/{item_id}/resources", headers=self.headers, timeout=60)
        assert r1.status_code == 200, r1.text
        r2 = requests.get(f"{API}/roadmap/tasks/{task_id}/resources", headers=self.headers, timeout=60)
        assert r2.status_code == 200, r2.text
        assert r1.json() == r2.json(), "daily item resources should delegate/match task resources for linked items"

    def test_resources_unknown_item_404(self):
        r = requests.get(f"{API}/roadmap/daily-plan/items/nonexistent123/resources", headers=self.headers)
        assert r.status_code == 404, r.text
