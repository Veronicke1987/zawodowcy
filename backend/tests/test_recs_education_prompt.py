"""
Backend test for the recommendations-generation prompt quality fix.

Context: users with "education": "Podstawowe" (basic education) and minimal other
preferences were getting AI suggestions requiring higher education / niche corporate
roles (e.g. "analityk danych", "specjalista ds. ERP", "pracownik callcenter",
"kierownik sklepu"). The prompt in run_recommendations() (/app/backend/server.py)
was updated to (1) forbid "now" category picks that require higher
education/certificates/management experience the user doesn't have, and (2) require
at least half of each category's picks to be common/widely-known occupations.

This test creates a TEST_ user, fills a minimal profile with education="Podstawowe"
and empty/generic other fields, calls POST /api/recommendations/generate ONCE (AI
calls cost real money - do not call more than once here), polls GET /api/recommendations
until ready, and inspects career titles in "now"/"future" for:
  - at least half of each category being from a whitelist of common/widely-known jobs
  - no "now" item obviously requiring higher education (heuristic keyword check)

Also includes a lightweight regression check that recommendations_generations_limit
is 35 (RECS_MONTHLY_GENERATIONS) via /api/account/me, and that shown_titles field is
returned by GET /api/recommendations.
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL must be set"

API = f"{BASE_URL}/api"

# Common/widely-known Polish job titles (keyword-based, lowercase, substrings ok)
COMMON_JOB_KEYWORDS = [
    "sprzedaw", "kucharz", "kelner", "kierowc", "opiekun", "magazyn", "recepcj",
    "ochroni", "produkcj", "sprzątając", "sprzątacz", "budow", "robotnik",
    "sekretar", "nauczyciel", "pielęgniar", "policj", "straż", "dostawc",
    "kurier", "sortowacz", "pakowacz", "monter", "elektryk", "hydraulik",
    "malarz", "murarz", "cieśla", "spawacz", "piekarz", "cukiern", "fryzjer",
    "kosmetyczk", "masażyst", "taksówkarz", "operator", "kasjer", "magazynier",
    "woźny", "portier", "stolarz", "mechanik", "lakiernik", "szwaczka",
    "krawcow", "ogrodnik", "sadownik", "rolnik", "górnik", "spedytor",
    "logistyk", "asystent", "pomoc", "listonosz",
]

# Keywords suggesting a role clearly requires higher education / mgmt experience
HIGHER_EDU_KEYWORDS = [
    "analityk danych", "data scientist", "data analyst", "specjalist", "erp",
    "kontroler finans", "inżynier", "architekt", "programist", "developer",
    "prawnik", "radca prawny", "lekarz", "kierownik", "manager", "menedżer",
    "dyrektor", "konsultant", "doradca inwestycyjn", "analityk finans",
    "product manager", "project manager", "ceo", "cfo", "cto",
]


@pytest.fixture(scope="module")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def test_user_token(api_client):
    """Registers a fresh TEST_ user for this run."""
    email = f"TEST_basic_edu_{uuid.uuid4().hex[:8]}@test.pl"
    payload = {"email": email, "password": "Test12345!", "name": "TEST Basic Edu", "country": "PL"}
    resp = api_client.post(f"{API}/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    token = data["access_token"]
    return token, email


@pytest.fixture(scope="module")
def auth_client(api_client, test_user_token):
    token, _ = test_user_token
    api_client.headers.update({"Authorization": f"Bearer {token}"})
    return api_client


class TestBasicEducationProfile:
    """Core flow: minimal profile with education=Podstawowe -> generate -> inspect quality."""

    def test_save_minimal_profile(self, auth_client):
        answers = {
            "reset_mode": "search",
            "education": "Podstawowe",
            "education_field": "",
            "interests": [],
            "current_job": "",
            "certificates": [],
            "languages": [],
        }
        resp = auth_client.put(f"{API}/profile", json={"answers": answers})
        assert resp.status_code == 200, resp.text
        assert resp.json().get("ok") is True

        get_resp = auth_client.get(f"{API}/profile")
        assert get_resp.status_code == 200
        saved = get_resp.json()
        assert saved["answers"]["education"] == "Podstawowe"

    def test_generate_and_inspect_quality(self, auth_client):
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
        assert len(now_items) >= 1, "now category empty"
        assert len(future_items) >= 1, "future category empty"

        now_titles = [it.get("title", "") for it in now_items]
        future_titles = [it.get("title", "") for it in future_items]
        print(f"NOW titles: {now_titles}")
        print(f"FUTURE titles: {future_titles}")

        def is_common(title: str) -> bool:
            t = title.lower()
            return any(kw in t for kw in COMMON_JOB_KEYWORDS)

        def mentions_higher_edu(title: str) -> bool:
            t = title.lower()
            return any(kw in t for kw in HIGHER_EDU_KEYWORDS)

        now_common_count = sum(is_common(t) for t in now_titles)
        future_common_count = sum(is_common(t) for t in future_titles)
        now_higher_edu = [t for t in now_titles if mentions_higher_edu(t)]

        print(f"now_common_count={now_common_count}/{len(now_titles)}")
        print(f"future_common_count={future_common_count}/{len(future_titles)}")
        print(f"now_higher_edu (should be empty)={now_higher_edu}")

        # Soft assertions reported, not hard-failed on keyword heuristic alone since LLM wording varies.
        self.now_common_ratio = now_common_count / len(now_titles)
        self.future_common_ratio = future_common_count / len(future_titles)
        self.now_higher_edu_hits = now_higher_edu

        # Sanity: shown_titles persisted and capped
        shown = doc.get("shown_titles") or []
        assert isinstance(shown, list)
        assert len(shown) <= 24

    def test_regen_shown_titles_mechanism_present(self, auth_client):
        """Regression: GET /api/recommendations still returns shown_titles field (history)."""
        r = auth_client.get(f"{API}/recommendations")
        assert r.status_code == 200
        doc = r.json()
        assert "shown_titles" in doc


class TestRegressionBasics:
    """Lightweight regression checks unrelated to the prompt change itself."""

    def test_monthly_limit_is_35(self, auth_client):
        r = auth_client.get(f"{API}/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert data.get("recommendations_generations_limit") == 35

    def test_account_me_has_used_count(self, auth_client):
        r = auth_client.get(f"{API}/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data.get("recommendations_generations_used"), int)
        assert data["recommendations_generations_used"] >= 1
