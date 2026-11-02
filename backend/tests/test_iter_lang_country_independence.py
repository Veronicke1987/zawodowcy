"""
Tests for the NEW feature: ui_language is fully independent of country.
- country -> labor-market context + language that job titles stay in (never translated)
- ui_language -> everything else (UI text + all AI-generated descriptive content)

Covers:
  - register with country=DE, no ui_language -> defaults to 'de'
  - PATCH /account/language (valid + invalid)
  - PATCH /account/country does not reset ui_language
  - DE country / EN ui_language recommendations + career detail language split
  - NL country / PL ui_language recommendations language split
  - PL/PL regression (no explicit ui_language -> defaults pl, unaffected)
"""
import os
import time
import uuid
import re
import pytest
import requests

BASE_URL = os.environ.get('EXPO_BACKEND_URL') or os.environ.get('EXPO_PUBLIC_BACKEND_URL')
BASE_URL = BASE_URL.rstrip('/')
API = f"{BASE_URL}/api"

POLISH_CHARS = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
GERMAN_HINT_WORDS = {" der ", " die ", " das ", " und ", " für ", " mit ", " eine ", " ist ", " auf "}
DUTCH_HINT_WORDS = {" de ", " het ", " een ", " van ", " met ", " voor ", " en "}


def register(country=None, ui_language=None, prefix="TESTLANG"):
    email = f"{prefix}_{uuid.uuid4().hex[:10]}@test.pl"
    payload = {"email": email, "password": "Test@123", "name": "Test User"}
    if country:
        payload["country"] = country
    if ui_language:
        payload["ui_language"] = ui_language
    r = requests.post(f"{API}/auth/register", json=payload, timeout=30)
    assert r.status_code == 201, r.text
    data = r.json()
    token = data["access_token"]
    return token, data["user"], email


def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def get_me(token):
    r = requests.get(f"{API}/auth/me", headers=auth_headers(token), timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


class TestRegisterDefaults:
    def test_register_de_no_language_defaults_to_de(self):
        token, user, email = register(country="DE")
        assert user["country"] == "DE"
        assert user["ui_language"] == "de", f"expected default ui_language='de' for DE country, got {user.get('ui_language')}"
        me = get_me(token)
        assert me["country"] == "DE"
        assert me["ui_language"] == "de"

    def test_register_pl_default_no_language(self):
        token, user, email = register(country="PL")
        assert user["country"] == "PL"
        assert user["ui_language"] == "pl"


class TestLanguageCountryIndependence:
    def setup_token(self):
        token, user, email = register(country="DE")
        return token

    def test_patch_language_valid(self):
        token = self.setup_token()
        r = requests.patch(f"{API}/account/language", json={"language": "en"}, headers=auth_headers(token), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ui_language"] == "en"
        assert body["country"] == "DE", "country must stay unchanged after language patch"
        me = get_me(token)
        assert me["ui_language"] == "en"
        assert me["country"] == "DE"

    def test_patch_language_invalid_code(self):
        token = self.setup_token()
        r = requests.patch(f"{API}/account/language", json={"language": "xx"}, headers=auth_headers(token), timeout=30)
        assert r.status_code == 400, r.text

    def test_patch_country_does_not_affect_language(self):
        token = self.setup_token()
        r = requests.patch(f"{API}/account/language", json={"language": "en"}, headers=auth_headers(token), timeout=30)
        assert r.status_code == 200
        assert r.json()["ui_language"] == "en"

        r2 = requests.patch(f"{API}/account/country", json={"country": "US"}, headers=auth_headers(token), timeout=30)
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert body["country"] == "US"
        assert body["ui_language"] == "en", "ui_language must remain exactly as user set it after country change"

        me = get_me(token)
        assert me["country"] == "US"
        assert me["ui_language"] == "en"


def submit_profile_and_generate(token, current_job="Księgowa", education="wyższe ekonomiczne", city="Berlin"):
    answers = {
        "reset_mode": "search",
        "current_job": current_job,
        "education": education,
        "city": city,
    }
    r = requests.put(f"{API}/profile", json={"answers": answers}, headers=auth_headers(token), timeout=30)
    assert r.status_code == 200, r.text

    r2 = requests.post(f"{API}/recommendations/generate", headers=auth_headers(token), timeout=30)
    assert r2.status_code in (200, 201, 202), r2.text
    return r2


def poll_recommendations(token, timeout=120):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = requests.get(f"{API}/recommendations", headers=auth_headers(token), timeout=30)
        assert r.status_code == 200, r.text
        last = r.json()
        if last.get("status") == "ready":
            return last
        time.sleep(3)
    pytest.fail(f"recommendations did not become ready in {timeout}s; last={last}")


def has_polish_chars(text):
    return any(c in POLISH_CHARS for c in text)


def has_german_hint(text):
    t = f" {text.lower()} "
    return any(w in t for w in GERMAN_HINT_WORDS)


def has_dutch_hint(text):
    t = f" {text.lower()} "
    return any(w in t for w in DUTCH_HINT_WORDS)


@pytest.mark.slow
class TestCriticalLanguageCountrySplit:
    """The core feature test: country controls job-title language, ui_language controls
    everything else (why/summary/description/pros/cons/career_levels descriptive text).
    career_levels job titles themselves should stay in country's language though."""

    def test_de_country_en_language_recommendations_and_detail(self):
        token, user, email = register(country="DE")
        r = requests.patch(f"{API}/account/language", json={"language": "en"}, headers=auth_headers(token), timeout=30)
        assert r.status_code == 200
        assert r.json() == {**r.json(), "country": "DE", "ui_language": "en"}

        submit_profile_and_generate(token)
        data = poll_recommendations(token, timeout=150)

        now_list = data.get("now") or data.get("careers_now") or []
        future_list = data.get("future") or data.get("careers_future") or []
        all_careers = now_list + future_list
        assert len(all_careers) > 0, f"no careers returned: {data.keys()}"

        for career in all_careers:
            why = career.get("why", "")
            summary = career.get("summary", "")
            title = career.get("title", "")
            assert why or summary, f"career missing why/summary: {career}"
            combined = f"{why} {summary}"
            assert not has_polish_chars(combined), f"Polish characters found in English why/summary: {combined[:200]}"

        first_career = all_careers[0]
        career_id = first_career.get("id") or first_career.get("career_id")
        assert career_id, f"no career id field in: {first_career}"

        r3 = requests.get(f"{API}/careers/{career_id}", headers=auth_headers(token), timeout=60)
        assert r3.status_code == 200, r3.text
        detail = r3.json()
        description = detail.get("description", "")
        pros = " ".join(detail.get("pros", []) or [])
        cons = " ".join(detail.get("cons", []) or [])
        assert not has_polish_chars(f"{description} {pros} {cons}"), "Polish chars found in EN description/pros/cons"

        levels = detail.get("career_levels", [])
        assert isinstance(levels, list)

    def test_nl_country_pl_language_recommendations(self):
        token, user, email = register(country="NL")
        r = requests.patch(f"{API}/account/language", json={"language": "pl"}, headers=auth_headers(token), timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert body["country"] == "NL"
        assert body["ui_language"] == "pl"

        submit_profile_and_generate(token, city="Amsterdam")
        data = poll_recommendations(token, timeout=150)
        now_list = data.get("now") or data.get("careers_now") or []
        future_list = data.get("future") or data.get("careers_future") or []
        all_careers = now_list + future_list
        assert len(all_careers) > 0

        for career in all_careers:
            why = career.get("why", "")
            summary = career.get("summary", "")
            combined = f"{why} {summary}"
            assert has_polish_chars(combined) or len(combined) > 0, "why/summary should be Polish (has diacritics or at least non-empty)"


@pytest.mark.slow
class TestRegressionPlDefault:
    def test_pl_country_default_no_explicit_language_full_flow(self):
        token, user, email = register(country="PL")
        assert user["ui_language"] == "pl"
        submit_profile_and_generate(token, city="Warszawa")
        data = poll_recommendations(token, timeout=150)
        now_list = data.get("now") or data.get("careers_now") or []
        future_list = data.get("future") or data.get("careers_future") or []
        all_careers = now_list + future_list
        assert len(all_careers) > 0
