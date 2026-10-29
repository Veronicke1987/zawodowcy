"""
Iteration 14: chat daily quota changes.
- FREE_CHAT_PER_DAY = 5, PREMIUM_CHAT_PER_DAY = 10 (premium no longer unlimited)
- GET /api/chat must return numeric remaining/limit for both free & premium
- POST /api/chat/stream: Nth+1 message -> 429 with Polish message, remaining stays 0
- Premium /api/premium/subscribe grants premium (demo), then 10/day cap applies
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", os.environ.get("EXPO_BACKEND_URL")).rstrip("/")
API = f"{BASE_URL}/api"


def register_and_login(session: requests.Session, email: str, password: str = "test123"):
    r = session.post(f"{API}/auth/register", json={"email": email, "password": password})
    if r.status_code not in (200, 201):
        # maybe already exists -> login instead
        r = session.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code in (200, 201), f"register/login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"no token in response: {data}"
    session.headers.update({"Authorization": f"Bearer {token}"})
    return data


def stream_one_message(session: requests.Session, text="Jak zmienić zawód?"):
    """POST /api/chat/stream and consume the SSE stream, return (status_code, last_done_payload_or_None, raw_text)."""
    r = session.post(f"{API}/chat/stream", json={"text": text}, stream=True, timeout=60)
    if r.status_code != 200:
        return r.status_code, None, r.text
    done_payload = None
    body = ""
    for line in r.iter_lines(decode_unicode=True):
        if not line:
            continue
        body += line + "\n"
        if line.startswith("data:"):
            import json as _json
            try:
                payload = _json.loads(line[len("data:"):].strip())
            except Exception:
                continue
            if payload.get("done"):
                done_payload = payload
    return 200, done_payload, body


@pytest.fixture
def free_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"TEST_chatfree_{uuid.uuid4().hex[:8]}@test.pl"
    register_and_login(s, email)
    yield s


@pytest.fixture
def premium_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"TEST_chatprem_{uuid.uuid4().hex[:8]}@test.pl"
    register_and_login(s, email)
    r = s.post(f"{API}/premium/subscribe", json={"plan": "monthly"})
    assert r.status_code == 200, f"premium subscribe failed: {r.status_code} {r.text}"
    body = r.json()
    assert body.get("ok") is True and body.get("premium", {}).get("active") is True, body
    yield s


class TestChatHistoryLimits:
    def test_free_user_chat_history_has_numeric_limit_5(self, free_session):
        r = free_session.get(f"{API}/chat")
        assert r.status_code == 200
        data = r.json()
        assert data["limit"] == 5
        assert data["remaining"] == 5
        assert data["is_premium"] is False

    def test_premium_user_chat_history_has_numeric_limit_10(self, premium_session):
        r = premium_session.get(f"{API}/chat")
        assert r.status_code == 200
        data = r.json()
        assert data["limit"] == 10
        assert data["remaining"] == 10
        assert data["is_premium"] is True


class TestFreeQuotaEnforcement:
    def test_free_user_5_messages_then_429_on_6th(self, free_session):
        for i in range(5):
            status, done, body = stream_one_message(free_session, text=f"Pytanie testowe numer {i}")
            assert status == 200, f"message {i} failed: {body}"
            # even if LLM call itself errors, the 'done' event with remaining must be present
            assert done is not None, f"no done payload for message {i}: {body}"

        r_hist = free_session.get(f"{API}/chat")
        assert r_hist.status_code == 200
        hist = r_hist.json()
        assert hist["remaining"] == 0, f"expected 0 remaining after 5 msgs, got {hist}"

        r6 = free_session.post(f"{API}/chat/stream", json={"text": "szóste pytanie"})
        assert r6.status_code == 429
        msg = r6.json().get("detail", "")
        assert "limit" in msg.lower() or "pytań" in msg.lower() or "wykorzystano" in msg.lower(), msg
        # polish wording check
        assert "Wykorzystano" in msg and "darmowych" in msg, f"unexpected message: {msg}"

        # remaining still 0, not negative
        r_hist2 = free_session.get(f"{API}/chat")
        assert r_hist2.json()["remaining"] == 0


class TestPremiumQuotaEnforcement:
    def test_premium_user_10_messages_then_429_on_11th(self, premium_session):
        for i in range(10):
            status, done, body = stream_one_message(premium_session, text=f"Premium pytanie {i}")
            assert status == 200, f"message {i} failed: {body}"
            assert done is not None, f"no done payload for message {i}: {body}"

        r_hist = premium_session.get(f"{API}/chat")
        assert r_hist.json()["remaining"] == 0

        r11 = premium_session.post(f"{API}/chat/stream", json={"text": "jedenaste pytanie"})
        assert r11.status_code == 429
        msg = r11.json().get("detail", "")
        assert "Premium" in msg and "Wykorzystano" in msg, f"unexpected premium 429 message: {msg}"
