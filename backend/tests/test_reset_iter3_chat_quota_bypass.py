# Reset iter3: free chat daily quota must NOT reset after DELETE /api/chat (clear history)
import os
import uuid
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", os.environ.get("EXPO_BACKEND_URL", "")).rstrip("/")
API = f"{BASE_URL}/api"


def test_clear_chat_does_not_reset_quota():
    s = requests.Session()
    r = s.post(f"{API}/auth/register", json={"email": f"test_q_{uuid.uuid4().hex[:8]}@test.pl", "password": "test123", "name": "TEST_Q"})
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    for i in range(5):
        r = s.post(f"{API}/chat/stream", json={"text": f"Odpowiedz jednym słowem: {i}"}, stream=True, timeout=120)
        assert r.status_code == 200
        for _ in r.iter_lines():
            pass
    assert s.post(f"{API}/chat/stream", json={"text": "x"}).status_code == 429
    assert s.delete(f"{API}/chat").status_code == 200
    rem = s.get(f"{API}/chat").json()["remaining"]
    assert rem == 0, f"Quota reset after clearing chat: remaining={rem}"
