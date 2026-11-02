"""
Tests the country-market-localization fix: AI-generated career detail, roadmap milestones,
job_links, and recommendations must reflect the user's SELECTED COUNTRY (job portals,
employment-agency equivalent, universities/institutions, currency format, software examples)
instead of always defaulting to Poland-specific content (Comarch/Symfonia, Krakow universities,
urzad pracy/KFS, zl currency, pracuj.pl/olx.pl links), regardless of ui_language.

Main reported bug: country=GB + ui_language=pl -> AI still suggested Polish software/unis/currency.
"""
import os
import re
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

POLAND_LEAKAGE_TERMS = ["comarch", "symfonia", "krak\u00f3w", "krakow", "warszaw",
                         "urz\u0105d pracy", "urzad pracy", "kfs", "bon szkoleniowy", " zl ", " z\u0142"]


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def register_fresh_user(session, country="PL"):
    uid = uuid.uuid4().hex[:8]
    email = f"TEST_ctrymkt_{uid}@test.pl"
    r = session.post(f"{API}/auth/register", json={"name": "Test Market", "email": email, "password": "test123", "country": country})
    assert r.status_code == 201, r.text
    data = r.json()
    session.headers.update({"Authorization": f"Bearer {data['access_token']}"})
    return email, data


def set_country(session, country):
    r = session.patch(f"{API}/account/country", json={"country": country})
    assert r.status_code == 200, r.text
    assert r.json()["country"] == country


def set_language(session, lang):
    r = session.patch(f"{API}/account/language", json={"language": lang})
    assert r.status_code == 200, r.text
    assert r.json()["ui_language"] == lang


def submit_minimal_profile(session):
    answers = {
        "current_job": "Sprzedawca w sklepie",
        "education": "Wyksztalcenie srednie",
        "certificates": [],
        "languages": ["angielski"],
        "languages_level": "B1",
        "reset_mode": "search",
    }
    r = session.put(f"{API}/profile", json={"answers": answers})
    assert r.status_code == 200, r.text


def poll_recommendations(session, timeout=90):
    r = session.post(f"{API}/recommendations/generate")
    assert r.status_code == 200, r.text
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = session.get(f"{API}/recommendations")
        assert r.status_code == 200
        data = r.json()
        if data.get("status") in ("ready", "error"):
            return data
        time.sleep(3)
    pytest.fail("recommendations generation timed out")


def poll_roadmap(session, path_id, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = session.get(f"{API}/roadmap", params={"path_id": path_id})
        assert r.status_code == 200
        data = r.json()
        if data.get("status") in ("ready", "error"):
            return data
        time.sleep(3)
    pytest.fail("roadmap generation timed out")


def check_no_poland_leakage(text_blob: str, country_code: str):
    low = " " + text_blob.lower() + " "
    found = [t for t in POLAND_LEAKAGE_TERMS if t in low]
    assert not found, f"Poland-specific leakage found for country={country_code}: {found}\n---blob---\n{text_blob[:3000]}"


def flatten_detail_text(detail: dict) -> str:
    parts = []
    for v in detail.values():
        if isinstance(v, list):
            parts.extend(str(x) for x in v)
        else:
            parts.append(str(v))
    return " | ".join(parts)


def flatten_roadmap_text(milestones: list) -> str:
    parts = []
    for m in milestones:
        parts.append(str(m.get("title", "")))
        parts.append(str(m.get("description", "")))
        parts.append(str(m.get("salary", "")))
        parts.extend(str(r) for r in m.get("requirements", []))
        for t in m.get("tasks", []):
            parts.append(str(t.get("title", "")))
            parts.append(str(t.get("description", "")))
    return " | ".join(parts)


class TestGBPolishLanguageExactReportedBug:
    """EXACT reported scenario: country=GB, ui_language=pl."""

    @pytest.fixture(scope="class")
    def gb_session_with_career(self):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        email, data = register_fresh_user(s, country="GB")
        set_language(s, "pl")
        submit_minimal_profile(s)
        rec = poll_recommendations(s)
        assert rec["status"] == "ready", f"recommendations failed: {rec}"
        all_careers = (rec.get("now") or []) + (rec.get("future") or [])
        assert len(all_careers) > 0, "no careers returned"
        return s, rec, all_careers

    def test_recommendations_ready_and_country_tagged(self, gb_session_with_career):
        s, rec, careers = gb_session_with_career
        for c in careers:
            assert c.get("country") == "GB"

    def test_recommendations_no_poland_leakage_and_gbp_currency(self, gb_session_with_career):
        s, rec, careers = gb_session_with_career
        blob = " | ".join(f"{c.get('title','')} {c.get('salary','')} {c.get('summary','')} {c.get('why','')}" for c in careers)
        check_no_poland_leakage(blob, "GB")
        assert "£" in blob, f"Expected GBP currency symbol in salary fields, got: {blob[:2000]}"

    def test_career_detail_no_poland_leakage(self, gb_session_with_career):
        s, rec, careers = gb_session_with_career
        career = careers[0]
        r = s.get(f"{API}/careers/{career['id']}")
        assert r.status_code == 200, r.text
        body = r.json()
        detail = body["detail"]
        blob = flatten_detail_text(detail)
        check_no_poland_leakage(blob, "GB")

    def test_career_detail_job_links_are_uk_portals(self, gb_session_with_career):
        s, rec, careers = gb_session_with_career
        career = careers[0]
        r = s.get(f"{API}/careers/{career['id']}")
        assert r.status_code == 200
        links = r.json()["job_links"]
        labels = [l["label"] for l in links]
        urls = " ".join(l["url"] for l in links)
        assert "Pracuj.pl" not in labels and "OLX Praca" not in labels, f"Polish portals leaked into GB job_links: {labels}"
        assert "pracuj.pl" not in urls.lower() and "olx.pl" not in urls.lower() and "pl.indeed.com" not in urls.lower(), urls
        assert any(l in labels for l in ["Reed", "TotalJobs"]), f"Expected UK-specific portal (Reed/TotalJobs), got {labels}"
        assert "uk.indeed.com" in urls or "United%20Kingdom" in urls, urls

    def test_roadmap_milestones_no_poland_leakage(self, gb_session_with_career):
        s, rec, careers = gb_session_with_career
        career = careers[0]
        r = s.post(f"{API}/roadmap", json={"career_id": career["id"]})
        assert r.status_code == 200, r.text
        path_id = r.json()["path_id"]
        road = poll_roadmap(s, path_id)
        assert road["status"] == "ready", f"roadmap failed: {road}"
        milestones = road.get("milestones", [])
        assert len(milestones) > 0
        blob = flatten_roadmap_text(milestones)
        check_no_poland_leakage(blob, "GB")


class TestUSMarketSpotCheck:
    @pytest.fixture(scope="class")
    def us_session_with_career(self):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        email, data = register_fresh_user(s, country="US")
        submit_minimal_profile(s)
        rec = poll_recommendations(s)
        assert rec["status"] == "ready", f"recommendations failed: {rec}"
        all_careers = (rec.get("now") or []) + (rec.get("future") or [])
        assert len(all_careers) > 0
        return s, rec, all_careers

    def test_us_no_poland_leakage_and_usd_currency(self, us_session_with_career):
        s, rec, careers = us_session_with_career
        blob = " | ".join(f"{c.get('title','')} {c.get('salary','')} {c.get('summary','')}" for c in careers)
        check_no_poland_leakage(blob, "US")
        assert "$" in blob, f"Expected USD currency symbol, got: {blob[:1500]}"

    def test_us_job_links_are_us_portals(self, us_session_with_career):
        s, rec, careers = us_session_with_career
        career = careers[0]
        r = s.get(f"{API}/careers/{career['id']}")
        assert r.status_code == 200
        links = r.json()["job_links"]
        labels = [l["label"] for l in links]
        assert any(l in labels for l in ["ZipRecruiter", "Glassdoor"]), labels
        urls = " ".join(l["url"] for l in links)
        assert "www.indeed.com" in urls and "pl.indeed.com" not in urls


class TestNLMarketSpotCheck:
    @pytest.fixture(scope="class")
    def nl_session_with_career(self):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        email, data = register_fresh_user(s, country="NL")
        submit_minimal_profile(s)
        rec = poll_recommendations(s)
        assert rec["status"] == "ready", f"recommendations failed: {rec}"
        all_careers = (rec.get("now") or []) + (rec.get("future") or [])
        assert len(all_careers) > 0
        return s, rec, all_careers

    def test_nl_no_poland_leakage_and_eur_currency(self, nl_session_with_career):
        s, rec, careers = nl_session_with_career
        blob = " | ".join(f"{c.get('title','')} {c.get('salary','')} {c.get('summary','')}" for c in careers)
        check_no_poland_leakage(blob, "NL")
        assert "€" in blob, f"Expected EUR currency symbol, got: {blob[:1500]}"

    def test_nl_job_links_are_nl_portals(self, nl_session_with_career):
        s, rec, careers = nl_session_with_career
        career = careers[0]
        r = s.get(f"{API}/careers/{career['id']}")
        assert r.status_code == 200
        links = r.json()["job_links"]
        labels = [l["label"] for l in links]
        assert "Nationale Vacaturebank" in labels, labels


class TestPLRegression:
    """Confirm country=PL still uses Polish-specific content/links/currency as expected."""

    @pytest.fixture(scope="class")
    def pl_session_with_career(self):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        email, data = register_fresh_user(s, country="PL")
        submit_minimal_profile(s)
        rec = poll_recommendations(s)
        assert rec["status"] == "ready", f"recommendations failed: {rec}"
        all_careers = (rec.get("now") or []) + (rec.get("future") or [])
        assert len(all_careers) > 0
        return s, rec, all_careers

    def test_pl_job_links_are_polish_portals(self, pl_session_with_career):
        s, rec, careers = pl_session_with_career
        career = careers[0]
        r = s.get(f"{API}/careers/{career['id']}")
        assert r.status_code == 200
        links = r.json()["job_links"]
        labels = [l["label"] for l in links]
        assert "Pracuj.pl" in labels and "OLX Praca" in labels, labels

    def test_pl_currency_is_zloty(self, pl_session_with_career):
        s, rec, careers = pl_session_with_career
        blob = " | ".join(f"{c.get('salary','')}" for c in careers)
        assert "z\u0142" in blob or "zl" in blob.lower(), f"Expected zl currency for PL, got: {blob}"
