# Iteration 5 - reset_mode (search / industry / life) in profile + recommendations generation
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", os.environ.get("EXPO_BACKEND_URL", "")).rstrip("/")
API = f"{BASE_URL}/api"

BASE_ANSWERS = {
    "current_status": "Pracuję i chcę zmienić zawód",
    "current_job": "księgowa w biurze rachunkowym, 8 lat",
    "education": "Magister", "education_field": "finanse i rachunkowość",
    "interests": ["Liczby i analizy", "Natura i zwierzęta", "Gotowanie"],
    "dislikes": ["Praca przy biurku cały dzień", "Monotonia"],
    "languages": ["Angielski"], "certificates": ["Excel", "Programy księgowe"],
    "achievements": "Zamknęłam 50 bilansów", "personality": {"social": 4, "thinking": 4},
    "work_mode": "Bez znaczenia", "learn_time": "3–12 miesięcy", "city": "Poznań",
}

FINANCE_WORDS = ["księg", "finans", "rachunk", "podat", "kontrol", "audyt", "bilans", "płac", "kadr", "controll", "skarb", "bank", "kredyt", "ubezpiecz"]


def poll(s, path, timeout=180):
    end = time.time() + timeout
    d = {}
    while time.time() < end:
        d = s.get(f"{API}{path}").json()
        if d.get("status") in ("ready", "error"):
            return d
        time.sleep(5)
    return d


def new_session():
    s = requests.Session()
    email = f"test_mode_{uuid.uuid4().hex[:8]}@test.pl"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "test123", "name": "TEST Mode"})
    assert r.status_code == 201, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


class TestResetModes:
    # Profile persistence of reset_mode + life extra answers
    def test_profile_persists_reset_mode_life(self):
        s = new_session()
        ans = {**BASE_ANSWERS, "reset_mode": "life", "has_idea": "Mam kilka luźnych pomysłów",
               "idea": "praca ze zwierzętami lub mała kawiarnia", "new_directions": ["Zwierzęta i natura", "Kulinaria"],
               "loves": "gotowanie, spacery z psem", "life_values": ["Spokój i mniej stresu"]}
        assert s.put(f"{API}/profile", json={"answers": ans}).status_code == 200
        p = s.get(f"{API}/profile").json()
        assert p["answers"]["reset_mode"] == "life"
        assert p["answers"]["new_directions"] == ["Zwierzęta i natura", "Kulinaria"]
        assert "_id" not in p

    # Life mode: generation -> mode=life and no finance careers
    def test_life_mode_recommendations(self):
        s = new_session()
        ans = {**BASE_ANSWERS, "reset_mode": "life", "has_idea": "Mam kilka luźnych pomysłów",
               "idea": "praca ze zwierzętami lub mała kawiarnia", "new_directions": ["Zwierzęta i natura", "Kulinaria", "Praca na świeżym powietrzu"],
               "loves": "gotowanie, spacery z psem", "life_values": ["Spokój i mniej stresu"]}
        s.put(f"{API}/profile", json={"answers": ans})
        r = s.post(f"{API}/recommendations/generate")
        assert r.status_code == 200 and r.json()["status"] == "pending"
        d = poll(s, "/recommendations")
        assert d.get("status") == "ready", d
        assert d.get("mode") == "life"
        careers = d["now"] + d["future"]
        assert len(careers) >= 8
        titles = [f"{c['title']} | {c.get('industry','')}" for c in careers]
        print("LIFE careers:", titles)
        bad = [t for t in titles if any(w in t.lower() for w in FINANCE_WORDS)]
        assert not bad, f"Finance-related careers in life mode: {bad}"

    # Industry mode: generation -> mode=industry
    def test_industry_mode_recommendations(self):
        s = new_session()
        ans = {**BASE_ANSWERS, "reset_mode": "industry", "target_industries": ["IT i nowe technologie", "Logistyka i magazyn"],
               "leave_reason": "wypalenie"}
        s.put(f"{API}/profile", json={"answers": ans})
        s.post(f"{API}/recommendations/generate")
        d = poll(s, "/recommendations")
        assert d.get("status") == "ready", d
        assert d.get("mode") == "industry"
        titles = [f"{c['title']} | {c.get('industry','')}" for c in d["now"] + d["future"]]
        print("INDUSTRY careers:", titles)

    # Missing reset_mode (legacy profile) defaults to search
    def test_default_mode_search(self):
        s = new_session()
        s.put(f"{API}/profile", json={"answers": {"current_job": "kasjer", "interests": ["Sport"]}})
        s.post(f"{API}/recommendations/generate")
        d = poll(s, "/recommendations")
        assert d.get("status") == "ready", d
        assert d.get("mode") == "search"
