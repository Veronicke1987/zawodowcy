"""
Iteration 23 regression + new feature tests:
  1. Premium monthly roadmap-generation quota (PREMIUM_MONTHLY_GENERATIONS=25) math.
  2. /api/premium and /api/auth/me expose roadmap_generations_used/limit.
  3. Pricing copy ("19 zł" monthly) in /api/premium PREMIUM_PLANS.
  4. Daily/weekly study-plan generation never bumps the roadmap generation counter.
  5. Free user's counter also increments (data consistency) though always ad-gated (frontend concern, not re-tested here).
  6. Quick regression: quiz -> recommendations -> roadmap -> daily-plan settings reach "ready" with no 500s.
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@reset.app"
ADMIN_PASSWORD = "Test@123"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(session):
    r = session.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


def _register(session, email, password="Test@123", name="Test User"):
    r = session.post(f"{API}/auth/register", json={"email": email, "password": password, "name": name})
    assert r.status_code == 201, r.text
    return r.json()


def _login(session, email, password="Test@123"):
    r = session.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# validate_profession() calls an LLM classifier that rejects made-up "TEST ..." strings as
# not being real professions, so we use a pool of real, distinct Polish job titles instead.
REAL_JOBS = [
    "Grafik komputerowy", "Analityk danych", "Specjalista ds. marketingu", "Księgowy",
    "Elektryk", "Kierowca zawodowy", "Pielęgniarka", "Nauczyciel języka angielskiego",
    "Programista Python", "Tester oprogramowania", "Kucharz", "Fryzjer", "Mechanik samochodowy",
    "Architekt wnętrz", "Prawnik", "Agent nieruchomości", "Fotograf", "Dietetyk",
    "Tłumacz przysięgły", "Weterynarz", "Operator wózka widłowego", "Barista",
    "Specjalista HR", "Logistyk", "Projektant UX", "Murarz", "Spawacz",
    "Piekarz", "Krawiec", "Masażysta",
]


class TestPremiumPricingAndFields:
    def test_premium_plans_pricing_copy(self, session, admin_token):
        r = session.get(f"{API}/premium", headers=_auth_headers(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert data["plans"]["monthly"]["price"] == "19 zł"
        assert data["plans"]["yearly"]["price"] == "149,99 zł"
        assert data["roadmap_generations_limit"] == 25
        assert "roadmap_generations_used" in data

    def test_me_has_quota_fields(self, session, admin_token):
        r = session.get(f"{API}/auth/me", headers=_auth_headers(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert "roadmap_generations_used" in data
        assert data["roadmap_generations_limit"] == 25


class TestPremiumQuotaMath:
    """Grants Premium to a fresh TEST_ user, generates >25 NEW roadmaps (deleting between
    each to bypass the 3-path cap), and verifies the counter increments 1:1 and never
    double-counts daily/weekly plan regeneration."""

    @pytest.fixture(scope="class")
    def premium_user(self, session, admin_token):
        email = f"TEST_premquota_{uuid.uuid4().hex[:8]}@example.com"
        reg = _register(session, email)
        user_id = reg["user"]["id"]
        # grant premium via admin endpoint
        r = session.post(f"{API}/admin/users/{user_id}/premium", json={"active": True}, headers=_auth_headers(admin_token))
        assert r.status_code == 200, r.text
        assert r.json()["is_premium"] is True
        login = _login(session, email)
        token = login["access_token"]
        assert login["user"]["is_premium"] is True
        yield {"email": email, "token": token, "user_id": user_id}
        # cleanup
        session.delete(f"{API}/roadmap", headers=_auth_headers(token))

    def test_generations_increment_past_quota(self, session, premium_user):
        token = premium_user["token"]
        headers = _auth_headers(token)

        # baseline
        r = session.get(f"{API}/premium", headers=headers)
        assert r.status_code == 200
        used_before = r.json()["roadmap_generations_used"]
        assert used_before == 0

        N = 27  # exceeds the 25/month quota by 2
        assert N <= len(REAL_JOBS)
        for i in range(N):
            title = REAL_JOBS[i]
            resp = session.post(f"{API}/roadmap/custom", json={"title": title, "qualifications": ""}, headers=headers)
            assert resp.status_code == 200, f"generation {i} failed: {resp.status_code} {resp.text}"
            body = resp.json()
            assert body["status"] in ("pending", "ready")
            assert body.get("existing") is not True  # must be a genuinely new path each time

            # verify counter bumped by exactly 1 for this new generation
            check = session.get(f"{API}/premium", headers=headers)
            used_now = check.json()["roadmap_generations_used"]
            assert used_now == i + 1, f"expected counter={i + 1} after generation {i}, got {used_now}"

            # free the PREMIUM_PATH_LIMIT=3 slot so the next create isn't blocked by the cap
            d = session.delete(f"{API}/roadmap", headers=headers)
            assert d.status_code == 200

        final = session.get(f"{API}/premium", headers=headers).json()
        assert final["roadmap_generations_used"] == N
        assert final["roadmap_generations_limit"] == 25
        # business rule: quota math is correct - generations 1-25 are within quota,
        # 26 and 27 are past it (ad-gating for those is enforced client-side, see AdsProvider.tsx)
        assert final["roadmap_generations_used"] > final["roadmap_generations_limit"]

    def test_reactivating_existing_path_does_not_bump_counter(self, session, premium_user):
        token = premium_user["token"]
        headers = _auth_headers(token)
        session.delete(f"{API}/roadmap", headers=headers)

        title = "Analityk biznesowy"
        r1 = session.post(f"{API}/roadmap/custom", json={"title": title, "qualifications": ""}, headers=headers)
        assert r1.status_code == 200
        used_after_first = session.get(f"{API}/premium", headers=headers).json()["roadmap_generations_used"]

        # re-submit the SAME title -> should just reactivate, no new generation, no counter bump
        r2 = session.post(f"{API}/roadmap/custom", json={"title": title, "qualifications": ""}, headers=headers)
        assert r2.status_code == 200
        assert r2.json().get("existing") is True
        used_after_second = session.get(f"{API}/premium", headers=headers).json()["roadmap_generations_used"]
        assert used_after_second == used_after_first, "reactivating an existing path must NOT bump the generation counter"

    def test_daily_plan_regeneration_never_bumps_counter(self, session, premium_user):
        token = premium_user["token"]
        headers = _auth_headers(token)
        session.delete(f"{API}/roadmap", headers=headers)

        title = "Programista Java"
        r1 = session.post(f"{API}/roadmap/custom", json={"title": title, "qualifications": ""}, headers=headers)
        assert r1.status_code == 200
        path_id = r1.json()["path_id"]

        # wait for the roadmap to become ready (needed before daily-plan settings can run)
        ready = False
        for _ in range(40):
            time.sleep(3)
            doc = session.get(f"{API}/roadmap", params={"path_id": path_id}, headers=headers).json()
            if doc.get("status") == "ready":
                ready = True
                break
            if doc.get("status") == "error":
                pytest.skip("roadmap generation errored (LLM issue) - cannot continue daily-plan sub-test")
        if not ready:
            pytest.skip("roadmap did not become ready in time - skipping daily-plan sub-test")

        used_before = session.get(f"{API}/premium", headers=headers).json()["roadmap_generations_used"]

        # regenerate the daily plan settings 3x in a row
        for _ in range(3):
            s = session.post(f"{API}/roadmap/daily-plan/settings", params={"path_id": path_id},
                              json={"time_mode": "daily", "time_value": 30, "free_days": [5, 6]}, headers=headers)
            assert s.status_code == 200, s.text
            time.sleep(1)

        used_after = session.get(f"{API}/premium", headers=headers).json()["roadmap_generations_used"]
        assert used_after == used_before, "daily-plan settings regeneration must NEVER bump roadmap_generations_used"


class TestFreeUserCounterConsistency:
    def test_free_user_counter_increments_too(self, session, admin_token):
        email = f"TEST_freequota_{uuid.uuid4().hex[:8]}@example.com"
        reg = _register(session, email)
        token = reg["access_token"]
        assert reg["user"]["is_premium"] is False
        headers = _auth_headers(token)

        used_before = session.get(f"{API}/premium", headers=headers).json()["roadmap_generations_used"]
        assert used_before == 0

        title = "Projektant graficzny"
        r = session.post(f"{API}/roadmap/custom", json={"title": title, "qualifications": ""}, headers=headers)
        assert r.status_code == 200

        used_after = session.get(f"{API}/premium", headers=headers).json()["roadmap_generations_used"]
        assert used_after == used_before + 1
        # cleanup
        session.delete(f"{API}/roadmap", headers=headers)


class TestRegressionQuickFlow:
    def test_custom_path_full_regression_no_500(self, session, admin_token):
        email = f"TEST_regress_{uuid.uuid4().hex[:8]}@example.com"
        reg = _register(session, email)
        token = reg["access_token"]
        headers = _auth_headers(token)

        title = "Specjalista ds. sprzedaży"
        r = session.post(f"{API}/roadmap/custom", json={"title": title, "qualifications": "Brak doswiadczenia"}, headers=headers)
        assert r.status_code == 200
        path_id = r.json()["path_id"]

        ready = False
        for _ in range(40):
            time.sleep(3)
            doc = session.get(f"{API}/roadmap", params={"path_id": path_id}, headers=headers).json()
            if doc.get("status") == "ready":
                ready = True
                break
            assert doc.get("status") != "error", f"roadmap generation errored: {doc}"
        assert ready, "roadmap did not become ready within timeout"

        s = session.post(f"{API}/roadmap/daily-plan/settings", params={"path_id": path_id},
                          json={"time_mode": "daily", "time_value": 20, "free_days": [6]}, headers=headers)
        assert s.status_code == 200
        session.delete(f"{API}/roadmap", headers=headers)
