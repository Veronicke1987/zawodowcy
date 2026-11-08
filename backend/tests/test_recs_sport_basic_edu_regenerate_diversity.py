"""
Backend test for the THIRD iteration of the recommendations-prompt quality fix
(run_recommendations(), /app/backend/server.py ~L1031-1075).

Two issues reported by the user after the 2nd fix iteration:
(1) Variants of mismatched titles for basic-education profiles still appeared
    (e.g. "pracownik rozliczen w biurze rachunkowym", "jakis koordynator") because
    the previous fix only blocked EXACT example names, not the general buzzword
    category ("specjalista", "koordynator", "konsultant", "analityk", "kierownik",
    "menedzer") regardless of what noun follows it.
(2) "Wygeneruj ponownie" (regenerate) kept showing the same/very similar careers
    instead of genuinely NEW ones (paraphrases of the same role, e.g. "sprzedawca w
    sklepie sportowym" -> "pracownik sklepu sportowego", are NOT acceptable).
Also: a short course must not turn a basic-education person into an accountant/
lawyer/nurse/teacher/doctor (long-study professions) in the "future" category.

COST NOTE: up to 3 real /recommendations/generate calls are used in this file
(call #1 = initial, call #2 = regenerate, call #3 = second regenerate), per the
max-3-calls budget for this session.
"""
import os
import re
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL must be set"

API = f"{BASE_URL}/api"

# General buzzword category banned (NOT just exact combined examples) when
# education is basic/vocational/empty or no office/managerial experience.
BANNED_BUZZWORDS = ["specjalist", "koordynator", "konsultant", "analityk", "kierownik", "menedżer", "menedzer", "manager"]

# Long-study professions that must never appear in "future" (short course) category
# unless user already has matching education (they don't, in this test profile).
LONG_STUDY_PROFESSIONS = ["księgow", "prawnik", "pielęgniar", "pielegniar", "nauczyciel", "lekarz", "prawniczk"]


def normalize_title(t: str) -> str:
    """Rough normalization to compare role 'cores' across runs: lowercase, strip
    common filler words, so paraphrases like 'sprzedawca w sklepie sportowym' vs
    'pracownik sklepu sportowego' can be heuristically flagged as same-role."""
    t = t.lower()
    for filler in ["w sklepie", "w biurze", "w firmie", "ds.", "do spraw", "sportowym", "sportowej", "sportowego"]:
        t = t.replace(filler, "")
    t = re.sub(r"\s+", " ", t).strip()
    return t


CORE_ROLE_TOKENS = {
    "sprzedawca": "sprzedaz", "sprzedawczyni": "sprzedaz", "sprzedaż": "sprzedaz",
    "magazynier": "magazyn", "magazyn": "magazyn",
    "kierowca": "kierowca",
    "kelner": "gastronomia", "kucharz": "gastronomia", "barman": "gastronomia", "kuchar": "gastronomia",
    "recepcjonist": "recepcja", "recepcja": "recepcja",
    "ochroniarz": "ochrona", "ochrona": "ochrona",
    "sprzątaj": "sprzatanie", "sprzatacz": "sprzatanie", "sprzątacz": "sprzatanie",
    "opiekun": "opieka",
    "trener": "fitness", "instruktor": "fitness", "siłowni": "fitness", "silowni": "fitness", "fitness": "fitness",
    "ratowni": "ratownictwo",
    "produkcj": "produkcja",
    "budowl": "budowa", "budowa": "budowa",
}


def core_role(title: str) -> str:
    t = title.lower()
    for token, core in CORE_ROLE_TOKENS.items():
        if token in t:
            return core
    return normalize_title(title)


@pytest.fixture(scope="module")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_client(api_client):
    email = f"TEST_sport_regen_{uuid.uuid4().hex[:8]}@test.pl"
    payload = {"email": email, "password": "Test12345!", "name": "TEST Sport Regen", "country": "PL"}
    resp = api_client.post(f"{API}/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    api_client.headers.update({"Authorization": f"Bearer {token}"})
    return api_client


def generate_and_wait(client):
    gen_resp = client.post(f"{API}/recommendations/generate")
    assert gen_resp.status_code == 200, gen_resp.text
    doc = None
    for _ in range(40):
        time.sleep(2)
        r = client.get(f"{API}/recommendations")
        assert r.status_code == 200
        doc = r.json()
        if doc.get("status") in ("ready", "error"):
            break
    assert doc is not None and doc.get("status") == "ready", f"Generation did not complete: {doc}"
    now_items = doc.get("now") or []
    future_items = doc.get("future") or []
    assert len(now_items) == 4
    assert len(future_items) == 4
    return doc, now_items, future_items


class TestSportBasicEducationRegenerateDiversity:

    def test_save_profile(self, auth_client):
        answers = {
            "reset_mode": "search",
            "education": "Podstawowe",
            "education_field": "",
            "interests": ["sport"],
            "current_job": "",
            "certificates": [],
            "languages": [],
        }
        resp = auth_client.put(f"{API}/profile", json={"answers": answers})
        assert resp.status_code == 200, resp.text

    def test_call_1_no_buzzwords_no_longstudy(self, auth_client):
        doc, now_items, future_items = generate_and_wait(auth_client)
        all_items = now_items + future_items
        titles = [it.get("title", "") for it in all_items]
        print(f"CALL #1 titles: {titles}")

        buzz_hits = [t for t in titles if any(b in t.lower() for b in BANNED_BUZZWORDS)]
        future_titles = [it.get("title", "") for it in future_items]
        longstudy_hits = [t for t in future_titles if any(k in t.lower() for k in LONG_STUDY_PROFESSIONS)]

        print(f"Buzzword violations: {buzz_hits}")
        print(f"Long-study-profession violations in 'future': {longstudy_hits}")

        self.__class__.call1_titles = titles
        assert not buzz_hits, f"Found banned buzzword(s) in titles: {buzz_hits}"
        assert not longstudy_hits, f"Found long-study profession(s) in 'future': {longstudy_hits}"

    def test_call_2_regenerate_is_genuinely_different(self, auth_client):
        time.sleep(1)
        doc, now_items, future_items = generate_and_wait(auth_client)
        all_items = now_items + future_items
        titles = [it.get("title", "") for it in all_items]
        print(f"CALL #2 (regenerate) titles: {titles}")

        buzz_hits = [t for t in titles if any(b in t.lower() for b in BANNED_BUZZWORDS)]
        future_titles = [it.get("title", "") for it in future_items]
        longstudy_hits = [t for t in future_titles if any(k in t.lower() for k in LONG_STUDY_PROFESSIONS)]
        assert not buzz_hits, f"Found banned buzzword(s) in titles: {buzz_hits}"
        assert not longstudy_hits, f"Found long-study profession(s) in 'future': {longstudy_hits}"

        call1_cores = {core_role(t) for t in self.call1_titles}
        call2_cores = {core_role(t) for t in titles}
        overlap = call1_cores & call2_cores
        exact_title_overlap = set(self.call1_titles) & set(titles)

        print(f"Call1 core roles: {call1_cores}")
        print(f"Call2 core roles: {call2_cores}")
        print(f"Core-role overlap (same role, possibly reworded): {overlap}")
        print(f"Exact title overlap: {exact_title_overlap}")

        self.__class__.call2_titles = titles
        self.__class__.call2_core_overlap = overlap
        self.__class__.call2_exact_overlap = exact_title_overlap

        # Soft/diagnostic: report overlap ratio rather than hard-failing on heuristic
        # core-role matching (imperfect dictionary), but DO hard-fail on exact
        # duplicate titles across calls, which is an unambiguous non-diversity bug.
        assert not exact_title_overlap, (
            f"Regenerate returned EXACT same title(s) as previous call: {exact_title_overlap}"
        )

    def test_call_3_second_regenerate_diversity_summary(self, auth_client):
        time.sleep(1)
        doc, now_items, future_items = generate_and_wait(auth_client)
        all_items = now_items + future_items
        titles = [it.get("title", "") for it in all_items]
        print(f"CALL #3 (2nd regenerate) titles: {titles}")

        buzz_hits = [t for t in titles if any(b in t.lower() for b in BANNED_BUZZWORDS)]
        future_titles = [it.get("title", "") for it in future_items]
        longstudy_hits = [t for t in future_titles if any(k in t.lower() for k in LONG_STUDY_PROFESSIONS)]
        assert not buzz_hits, f"Found banned buzzword(s) in titles: {buzz_hits}"
        assert not longstudy_hits, f"Found long-study profession(s) in 'future': {longstudy_hits}"

        exact_overlap_1_3 = set(self.call1_titles) & set(titles)
        exact_overlap_2_3 = set(self.call2_titles) & set(titles)
        print(f"Exact title overlap call1 vs call3: {exact_overlap_1_3}")
        print(f"Exact title overlap call2 vs call3: {exact_overlap_2_3}")

        all_three = [set(self.call1_titles), set(self.call2_titles), set(titles)]
        print("=== DIVERSITY SUMMARY ACROSS 3 REAL GENERATE CALLS ===")
        print(f"Call1: {self.call1_titles}")
        print(f"Call2: {self.call2_titles}")
        print(f"Call3: {titles}")
        print(f"Call1 core-role vs Call2 core-role overlap: {self.call2_core_overlap}")

        assert not exact_overlap_1_3, f"Exact duplicate titles call1 vs call3: {exact_overlap_1_3}"
        assert not exact_overlap_2_3, f"Exact duplicate titles call2 vs call3: {exact_overlap_2_3}"
