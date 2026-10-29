# Reset - iteration 7: verify all AI endpoints work with user's own ANTHROPIC_API_KEY (Sonnet analysis / Haiku fast)
import os
import json
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", os.environ.get("EXPO_BACKEND_URL", "")).rstrip("/")
API = f"{BASE_URL}/api"

ANSWERS = {
    "current_job": "Kasjer w sklepie", "education": "średnie", "interests": ["komputery", "liczby"],
    "dislikes": ["praca fizyczna"], "languages": ["angielski B1"], "certificates": [], "achievements": "Pracownik miesiąca",
    "personality": ["dokładny"], "preferences": ["praca zdalna"], "city": "Kraków", "learn_time": "5 godzin tygodniowo",
}


def poll(s, path, timeout=200):
    end = time.time() + timeout
    d = {}
    while time.time() < end:
        d = s.get(f"{API}{path}").json()
        if d.get("status") in ("ready", "error"):
            return d
        time.sleep(4)
    return d


@pytest.fixture(scope="module")
def ctx():
    s = requests.Session()
    email = f"test_ai7_{uuid.uuid4().hex[:8]}@test.pl"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "test123", "name": "TEST_AI7"})
    assert r.status_code == 201, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    assert s.put(f"{API}/profile", json={"answers": ANSWERS}).status_code == 200
    yield {"s": s, "state": {}}
    try:
        s.post(f"{API}/premium/cancel")
    except Exception:
        pass


# --- Recommendations (Sonnet / ANALYSIS_MODEL)
def test_recommendations(ctx):
    s = ctx["s"]
    r = s.post(f"{API}/recommendations/generate")
    assert r.status_code == 200 and r.json()["status"] == "pending"
    d = poll(s, "/recommendations")
    assert d.get("status") == "ready", d
    assert len(d["now"]) >= 3 and len(d["future"]) >= 3
    assert d["summary"]
    ctx["state"]["career"] = d["now"][0]


# --- Career detail (Haiku / FAST_MODEL)
def test_career_detail(ctx):
    c = ctx["state"].get("career") or pytest.skip("no recs")
    r = ctx["s"].get(f"{API}/careers/{c['id']}", timeout=120)
    assert r.status_code == 200, r.text
    det = r.json()["detail"]
    assert det.get("description") and isinstance(det.get("pros"), list) and det["pros"]


# --- Roadmap (Sonnet)
def test_roadmap(ctx):
    c = ctx["state"].get("career") or pytest.skip("no recs")
    s = ctx["s"]
    r = s.post(f"{API}/roadmap", json={"career_id": c["id"]})
    assert r.status_code == 200, r.text
    d = poll(s, "/roadmap")
    assert d.get("status") == "ready", d
    assert len(d["milestones"]) >= 3 and d["milestones"][0]["tasks"]
    ctx["state"]["task_id"] = d["milestones"][0]["tasks"][0]["id"]


# --- Task resources (Haiku)
def test_task_resources(ctx):
    tid = ctx["state"].get("task_id") or pytest.skip("no roadmap")
    r = ctx["s"].get(f"{API}/roadmap/tasks/{tid}/resources", timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("overview") and d.get("resources") and all(x.get("url") for x in d["resources"])


# --- Chat SSE (Haiku)
def test_chat_stream(ctx):
    r = ctx["s"].post(f"{API}/chat/stream", json={"text": "Jaki jeden kurs polecasz na start? Odpowiedz krótko."}, stream=True, timeout=120)
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")
    text, done, err = "", None, None
    for line in r.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            ev = json.loads(line[6:])
            text += ev.get("t", "")
            err = ev.get("error") or err
            if ev.get("done"):
                done = ev
                break
    assert err is None, err
    assert len(text) > 20 and done is not None
    h = ctx["s"].get(f"{API}/chat").json()
    assert [m["role"] for m in h["messages"]][-2:] == ["user", "assistant"]


# --- Study plan (Sonnet, premium)
def test_study_plan_premium(ctx):
    s = ctx["s"]
    if not ctx["state"].get("task_id"):
        pytest.skip("no roadmap")
    assert s.post(f"{API}/roadmap/study-plan").status_code == 402
    assert s.post(f"{API}/premium/subscribe", json={"plan": "monthly"}).status_code == 200
    r = s.post(f"{API}/roadmap/study-plan")
    assert r.status_code == 200 and r.json()["status"] == "pending"
    d = poll(s, "/roadmap/study-plan")
    assert d.get("status") == "ready", d
    assert len(d["plan"]["weeks"]) >= 4 and d["plan"]["weeks"][0]["items"]
    assert s.post(f"{API}/premium/cancel").status_code == 200
