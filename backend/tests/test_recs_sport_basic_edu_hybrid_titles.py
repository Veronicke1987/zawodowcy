"""
Backend test for the SECOND iteration of the recommendations-prompt quality fix
(run_recommendations(), /app/backend/server.py ~L1031-1074).

Bug report reproduced here EXACTLY: user profile with education="Podstawowe" (basic
education) and interests=["sport"], all other fields empty/default. Previously the AI
invented ARTIFICIAL HYBRID job titles combining buzzwords (specjalista ds., konsultant
ds., koordynator, analityk) with the "sport" interest even though the person has no
matching education/experience, e.g. "koordynator wydarzeń sportowych", "konsultant ds.
wdrożeń systemów w branży sportowej", and sometimes something unrelated requiring higher
education like "specjalista ds. rozliczeń w biurze rachunkowym".

The new prompt adds an explicit KRYTYCZNE instruction forbidding this pattern, with the
exact buggy examples spelled out, plus good examples (sprzedawca w sklepie sportowym,
pracownik siłowni/klubu fitness, ratownik, obsługa obiektu sportowego) and a
"future" = reachable after ONE small concrete step (course/certificate) requirement.

COST LIMIT: at most ONE real /recommendations/generate call is used in this file (per
agent-to-agent cost guidance of max 2 real generate calls for the whole testing session).
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

# Buzzwords the prompt explicitly forbids combining with a user interest unless it's a
# real, common, matching-education role.
HYBRID_BUZZWORDS = [
    "specjalist", "konsultant", "koordynator", "analityk", "doradc", "menedżer",
    "manager", "kierownik",
]

# Roles clearly requiring higher education / an unrelated specialized field, regardless
# of buzzword use (heuristic from the exact reported bug: "biuro rachunkowe").
HIGHER_EDU_UNRELATED_KEYWORDS = [
    "rozliczeń w biurze rachunkowym", "księgow", "analiz danych", "data analyst",
    "data scientist", "erp", "programist", "inżynier", "prawnik", "architekt",
]

GOOD_SPORT_EXAMPLES = [
    "sprzedaw", "siłowni", "fitness", "ratowni", "obsług", "trener", "instruktor",
]


@pytest.fixture(scope="module")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_client(api_client):
    email = f"TEST_sport_basic_edu_{uuid.uuid4().hex[:8]}@test.pl"
    payload = {"email": email, "password": "Test12345!", "name": "TEST Sport Basic Edu", "country": "PL"}
    resp = api_client.post(f"{API}/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    api_client.headers.update({"Authorization": f"Bearer {token}"})
    return api_client


class TestSportBasicEducationHybridTitles:
    """Reproduces the EXACT reported bug scenario."""

    def test_save_profile_sport_basic_edu(self, auth_client):
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

        get_resp = auth_client.get(f"{API}/profile")
        assert get_resp.status_code == 200
        saved = get_resp.json()
        assert saved["answers"]["education"] == "Podstawowe"
        assert saved["answers"]["interests"] == ["sport"]

    def test_generate_and_check_no_hybrid_titles(self, auth_client):
        gen_resp = auth_client.post(f"{API}/recommendations/generate")
        assert gen_resp.status_code == 200, gen_resp.text
        assert gen_resp.json().get("status") == "pending"

        doc = None
        for _ in range(40):  # up to ~80s
            time.sleep(2)
            r = auth_client.get(f"{API}/recommendations")
            assert r.status_code == 200
            doc = r.json()
            if doc.get("status") in ("ready", "error"):
                break

        assert doc is not None
        assert doc.get("status") == "ready", f"Generation did not complete: {doc}"

        now_items = doc.get("now") or []
        future_items = doc.get("future") or []
        assert len(now_items) == 4, f"expected 4 'now' items, got {len(now_items)}"
        assert len(future_items) == 4, f"expected 4 'future' items, got {len(future_items)}"

        all_items = now_items + future_items
        all_titles = [it.get("title", "") for it in all_items]
        print(f"ALL 8 titles: {all_titles}")

        def has_buzzword(title: str) -> bool:
            t = title.lower()
            return any(b in t for b in HYBRID_BUZZWORDS)

        def mentions_sport(title: str, why: str, summary: str) -> bool:
            blob = f"{title} {why} {summary}".lower()
            return "sport" in blob or any(g in blob for g in GOOD_SPORT_EXAMPLES)

        def is_higher_edu_unrelated(title: str) -> bool:
            t = title.lower()
            return any(k in t for k in HIGHER_EDU_UNRELATED_KEYWORDS)

        hybrid_violations = []
        unrelated_violations = []
        for it in all_items:
            title = it.get("title", "")
            why = it.get("why", "")
            summary = it.get("summary", "")
            buzz = has_buzzword(title)
            sport_related = mentions_sport(title, why, summary)
            if buzz and sport_related:
                # buzzword + sport-flavored title = exactly the reported anti-pattern,
                # UNLESS it's a widely-real role (heuristic can't be perfect, so just flag).
                hybrid_violations.append(title)
            if is_higher_edu_unrelated(title):
                unrelated_violations.append(title)

        print(f"Potential hybrid-title violations (buzzword+sport): {hybrid_violations}")
        print(f"Potential higher-edu/unrelated violations: {unrelated_violations}")

        # Soft report: do not hard-fail the whole suite on heuristic wording alone (LLM
        # phrasing varies), but surface counts clearly for the main agent.
        self.hybrid_violations = hybrid_violations
        self.unrelated_violations = unrelated_violations

        # Hard assertion only for the most unambiguous bug-repro case: a title that is
        # BOTH a corporate buzzword role AND explicitly about "sport" in the title itself
        # (e.g. "koordynator wydarzeń sportowych", "konsultant ds ... sportowej").
        title_level_hybrid = [
            t for t in all_titles
            if any(b in t.lower() for b in HYBRID_BUZZWORDS) and "sport" in t.lower()
        ]
        print(f"Title-level hybrid violations (buzzword AND 'sport' in title itself): {title_level_hybrid}")
        assert not title_level_hybrid, (
            f"Found invented hybrid job title(s) combining buzzword with 'sport': {title_level_hybrid}"
        )

        # shown_titles history still works (regression)
        shown = doc.get("shown_titles") or []
        assert isinstance(shown, list)
        assert set(all_titles).issubset(set(shown))

    # --- regression checks kept in the SAME class/worker (pytest.ini pins loadscope per
    # class, so a separate class would get its own fresh TEST_ user with no generation yet) ---

    def test_recommendations_doc_has_expected_fields(self, auth_client):
        r = auth_client.get(f"{API}/recommendations")
        assert r.status_code == 200
        doc = r.json()
        assert doc.get("status") == "ready"
        assert "summary" in doc
        assert "now" in doc and "future" in doc
        assert "shown_titles" in doc

    def test_account_me_generations_used_incremented(self, auth_client):
        r = auth_client.get(f"{API}/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data.get("recommendations_generations_used"), int)
        assert data["recommendations_generations_used"] >= 1
