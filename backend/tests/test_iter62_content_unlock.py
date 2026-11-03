"""Iter62: per-user ad-paywall for lazily-AI-generated content.
Covers GET /api/content/unlock-status and POST /api/content/unlock for free vs premium users.
"""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")


@pytest.fixture
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def login(api_client, email, password):
    r = api_client.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    token = r.json().get("access_token")
    assert token
    return token


class TestContentUnlockFree:
    def test_free_user_unlock_flow(self, api_client):
        token = login(api_client, "test_ui_fresh@test.pl", "test123")
        headers = {"Authorization": f"Bearer {token}"}
        cid_a = f"TEST_career:{uuid.uuid4()}"
        cid_b = f"TEST_career:{uuid.uuid4()}"

        r = api_client.get(f"{BASE_URL}/api/content/unlock-status", params={"id": cid_a}, headers=headers)
        assert r.status_code == 200
        assert r.json()["unlocked"] is False

        r = api_client.post(f"{BASE_URL}/api/content/unlock", json={"id": cid_a}, headers=headers)
        assert r.status_code == 200
        assert r.json()["ok"] is True

        r = api_client.get(f"{BASE_URL}/api/content/unlock-status", params={"id": cid_a}, headers=headers)
        assert r.json()["unlocked"] is True

        r = api_client.get(f"{BASE_URL}/api/content/unlock-status", params={"id": cid_b}, headers=headers)
        assert r.json()["unlocked"] is False


class TestContentUnlockPremium:
    def test_premium_user_always_unlocked(self, api_client):
        token = login(api_client, "ania_t1@test.pl", "test123")
        headers = {"Authorization": f"Bearer {token}"}
        cid = f"TEST_career:{uuid.uuid4()}"
        r = api_client.get(f"{BASE_URL}/api/content/unlock-status", params={"id": cid}, headers=headers)
        assert r.status_code == 200
        assert r.json()["unlocked"] is True
