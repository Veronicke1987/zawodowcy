"""
Iteration 53 regression tests:
- POST /api/roadmap/study-plan retry-after-error behavior (should NOT block retry when last block status == 'error')
- POST /api/roadmap/study-plan still blocks when status is 'pending' or 'ready' (400 "Plan tygodniowy już istnieje.")
- GET /api/roadmap/study-plan happy path polling until ready / error
"""
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_token(api_client):
    resp = api_client.post(f"{BASE_URL}/api/auth/login", json={"email": "ania_t1@test.pl", "password": "test123"})
    if resp.status_code != 200:
        pytest.skip(f"Could not login test user: {resp.status_code} {resp.text}")
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in login response: {data}"
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestWeeklyPlanRetryLogic:
    def test_get_study_plan_status(self, api_client, auth_headers):
        resp = api_client.get(f"{BASE_URL}/api/roadmap/study-plan", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        print("Current study-plan status:", data.get("status"), "blocks:", len(data.get("blocks", [])))

    def test_create_study_plan_then_poll(self, api_client, auth_headers):
        """Full happy-path: create (or detect already exists), then poll GET until ready/error."""
        get_resp = api_client.get(f"{BASE_URL}/api/roadmap/study-plan", headers=auth_headers)
        assert get_resp.status_code == 200
        existing_status = get_resp.json().get("status")

        create_resp = api_client.post(f"{BASE_URL}/api/roadmap/study-plan", headers=auth_headers)

        if existing_status in ("pending", "ready"):
            # Must correctly refuse with 400 "already exists"
            assert create_resp.status_code == 400, f"Expected 400 when status={existing_status}, got {create_resp.status_code}: {create_resp.text}"
            assert "już istnieje" in create_resp.text
            print(f"Confirmed 400 'already exists' guard holds when status={existing_status}")
            last_status = existing_status
        else:
            # status none or error -> should be allowed to create (200/202 w/ pending)
            assert create_resp.status_code == 200, f"Expected 200 when status={existing_status}, got {create_resp.status_code}: {create_resp.text}"
            assert create_resp.json().get("status") == "pending"
            last_status = "pending"

        # Poll up to ~90s for generation to complete
        deadline = time.time() + 90
        final = None
        while time.time() < deadline:
            r = api_client.get(f"{BASE_URL}/api/roadmap/study-plan", headers=auth_headers)
            assert r.status_code == 200
            d = r.json()
            final = d
            if d.get("status") in ("ready", "error"):
                break
            time.sleep(5)

        assert final is not None
        print("Final study-plan status after polling:", final.get("status"))

        if final.get("status") == "ready":
            blocks = final.get("blocks", [])
            assert blocks, "Expected at least 1 block"
            plan = blocks[-1].get("plan", {})
            weeks = plan.get("weeks", [])
            assert len(weeks) == 8, f"Expected 8 weeks, got {len(weeks)}"
            for w in weeks:
                assert w.get("items"), "Each week should have items"
            print(f"Plan ready with {len(weeks)} weeks")
        elif final.get("status") == "error":
            print("Plan generation ended in error (acceptable per task note if infrequent)")

    def test_retry_after_error_not_blocked(self, api_client, auth_headers):
        """
        Simulate error state directly checking code logic: if last block status == 'error',
        a new POST should NOT return 400 'już istnieje'. We verify this by inspecting current
        state; if status is error, retry POST should succeed (200) rather than 400.
        """
        r = api_client.get(f"{BASE_URL}/api/roadmap/study-plan", headers=auth_headers)
        status = r.json().get("status")
        if status != "error":
            pytest.skip(f"Current status is '{status}', not 'error' - cannot naturally verify retry-after-error without forcing an AI failure")
        create_resp = api_client.post(f"{BASE_URL}/api/roadmap/study-plan", headers=auth_headers)
        assert create_resp.status_code == 200, f"Retry after error should succeed, got {create_resp.status_code}: {create_resp.text}"
