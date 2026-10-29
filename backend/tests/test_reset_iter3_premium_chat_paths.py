# Reset iter3: premium (demo), advisor chat SSE + daily limit, multi-path roadmaps, weekly study plan
import json
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
    "personality": ["dokładny"], "preferences": ["praca zdalna"], "city": "Kraków", "learn_time": "5-10 godzin tygodniowo",
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


def stream(s, text):
    r = s.post(f"{API}/chat/stream", json={"text": text}, stream=True, timeout=120)
    if r.status_code != 200:
        return r.status_code, None, None, r.text
    chunks, final = [], None
    for line in r.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            ev = json.loads(line[6:])
            if "t" in ev:
                chunks.append(ev["t"])
            if ev.get("done"):
                final = ev
            if ev.get("error"):
                final = ev
    return 200, "".join(chunks), final, None


@pytest.fixture(scope="module")
def u():
    s = requests.Session()
    email = f"test_iter3_{uuid.uuid4().hex[:8]}@test.pl"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "test123", "name": "TEST_Iter3"})
    assert r.status_code == 201, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    assert s.put(f"{API}/profile", json={"answers": ANSWERS}).status_code == 200
    assert s.post(f"{API}/recommendations/generate").status_code == 200
    rec = poll(s, "/recommendations", 200)
    assert rec.get("status") == "ready", rec
    careers = rec["now"] + rec["future"]
    yield {"s": s, "careers": careers, "st": {}}
    s.delete(f"{API}/roadmap"); s.delete(f"{API}/chat")


# --- Premium
class TestPremium:
    def test_info_free(self, u):
        d = u["s"].get(f"{API}/premium").json()
        assert d["is_premium"] is False and d["demo"] is True
        assert d["plans"]["monthly"]["price"] == "19,99 zł" and d["plans"]["yearly"]["price"] == "149,99 zł"
        assert u["s"].get(f"{API}/auth/me").json().get("is_premium") is False

    def test_subscribe_bad_plan(self, u):
        assert u["s"].post(f"{API}/premium/subscribe", json={"plan": "weekly"}).status_code == 400

    def test_study_plan_402_free(self, u):
        r = u["s"].post(f"{API}/roadmap/study-plan")
        assert r.status_code == 402, r.text


# --- Chat (free)
class TestChatFree:
    def test_history_empty(self, u):
        d = u["s"].get(f"{API}/chat").json()
        assert d["messages"] == [] and d["remaining"] == 5 and d["limit"] == 5

    def test_stream_first(self, u):
        code, text, final, err = stream(u["s"], "Jak zacząć szukać pracy w nowym zawodzie?")
        assert code == 200, err
        assert text and len(text) > 20, text
        assert final and final.get("done") and final["remaining"] == 4, final
        msgs = u["s"].get(f"{API}/chat").json()
        assert [m["role"] for m in msgs["messages"]] == ["user", "assistant"] and msgs["remaining"] == 4

    def test_limit_429(self, u):
        for i in range(4):
            code, _, final, err = stream(u["s"], f"Krótko: rada nr {i}")
            assert code == 200, err
            assert final["remaining"] == 3 - i, final
        r = u["s"].post(f"{API}/chat/stream", json={"text": "szóste pytanie"})
        assert r.status_code == 429, r.text
        assert u["s"].get(f"{API}/chat").json()["remaining"] == 0

    def test_empty_text_422(self, u):
        assert u["s"].post(f"{API}/chat/stream", json={"text": ""}).status_code == 422


# --- Paths (free)
class TestPathsFree:
    def test_free_replaces(self, u):
        s, c = u["s"], u["careers"]
        a = s.post(f"{API}/roadmap", json={"career_id": c[0]["id"]}).json()
        b = s.post(f"{API}/roadmap", json={"career_id": c[1]["id"]}).json()
        assert a["status"] == "pending" and b["status"] == "pending"
        p = s.get(f"{API}/paths").json()
        assert len(p["paths"]) == 1 and p["limit"] == 1 and p["paths"][0]["title"] == c[1]["title"]
        u["st"]["pB"] = b["path_id"]


# --- Premium unlocked
class TestPremiumFlows:
    def test_subscribe(self, u):
        r = u["s"].post(f"{API}/premium/subscribe", json={"plan": "yearly"})
        assert r.status_code == 200 and r.json()["premium"]["plan"] == "yearly"
        assert u["s"].get(f"{API}/auth/me").json()["is_premium"] is True
        assert u["s"].get(f"{API}/premium").json()["is_premium"] is True

    def test_chat_unlimited(self, u):
        assert u["s"].get(f"{API}/chat").json()["remaining"] is None
        code, text, final, err = stream(u["s"], "Jedno zdanie motywacji.")
        assert code == 200, err
        assert text and final["done"] and final["remaining"] is None

    def test_multi_paths_limit(self, u):
        s, c = u["s"], u["careers"]
        a = s.post(f"{API}/roadmap", json={"career_id": c[2]["id"]}).json()
        d = s.post(f"{API}/roadmap", json={"career_id": c[3]["id"]}).json()
        p = s.get(f"{API}/paths").json()
        assert len(p["paths"]) == 3 and p["limit"] == 3, p
        actives = [x for x in p["paths"] if x["active"]]
        assert len(actives) == 1 and actives[0]["path_id"] == d["path_id"]
        r = s.post(f"{API}/roadmap", json={"career_id": c[4]["id"]})
        assert r.status_code == 403, r.text
        again = s.post(f"{API}/roadmap", json={"career_id": c[1]["id"]}).json()
        assert again.get("existing") is True and again["path_id"] == u["st"]["pB"]
        assert s.get(f"{API}/roadmap").json()["path_id"] == u["st"]["pB"]
        u["st"].update(pA=a["path_id"], pD=d["path_id"])

    def test_activate_get_by_id(self, u):
        s, st = u["s"], u["st"]
        assert s.post(f"{API}/paths/{st['pA']}/activate").status_code == 200
        assert s.get(f"{API}/roadmap").json()["path_id"] == st["pA"]
        assert s.get(f"{API}/roadmap", params={"path_id": st["pD"]}).json()["path_id"] == st["pD"]
        assert s.post(f"{API}/paths/nope/activate").status_code == 404

    def test_delete_active_path_reassigns(self, u):
        s, st = u["s"], u["st"]
        assert s.delete(f"{API}/paths/{st['pA']}").status_code == 200
        p = s.get(f"{API}/paths").json()["paths"]
        assert len(p) == 2 and sum(x["active"] for x in p) == 1
        assert s.delete(f"{API}/paths/{st['pA']}").status_code == 404

    def test_task_patch_and_study_plan(self, u):
        s, st = u["s"], u["st"]
        rb = poll(s, f"/roadmap?path_id={st['pB']}", 200)
        assert rb.get("status") == "ready", rb.get("status")
        rd = poll(s, f"/roadmap?path_id={st['pD']}", 200)
        assert rd.get("status") == "ready"
        # toggle task on non-active path B
        s.post(f"{API}/paths/{st['pD']}/activate")
        tid = rb["milestones"][0]["tasks"][0]["id"]
        cur = rb["milestones"][0]["tasks"][0]["done"]
        assert s.patch(f"{API}/roadmap/tasks/{tid}", json={"done": not cur}).status_code == 200
        rb2 = s.get(f"{API}/roadmap", params={"path_id": st["pB"]}).json()
        assert rb2["milestones"][0]["tasks"][0]["done"] is (not cur)
        # study plan on active path D
        r = s.post(f"{API}/roadmap/study-plan")
        assert r.status_code == 200 and r.json()["status"] == "pending"
        sp = poll(s, "/roadmap/study-plan", 200)
        assert sp["status"] == "ready", sp
        assert sp["path_id"] == st["pD"] and len(sp["plan"]["weeks"]) >= 6, len(sp["plan"].get("weeks", []))

    def test_cancel_and_clear_chat(self, u):
        s = u["s"]
        assert s.post(f"{API}/premium/cancel").status_code == 200
        assert s.get(f"{API}/auth/me").json()["is_premium"] is False
        assert s.get(f"{API}/paths").json()["limit"] == 1
        assert s.delete(f"{API}/chat").status_code == 200
        assert s.get(f"{API}/chat").json()["messages"] == []
