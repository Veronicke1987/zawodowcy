"""
Backend test for the 6TH iteration of the recommendations-prompt quality fix
(run_recommendations(), /app/backend/server.py ~L1051-1170, prompt text ~L1089-1119).

Context: iteration 5 fixed low-qualification profiles (forbid specjalista/koordynator/
konsultant/analityk/kierownik/menedżer + require >=half common/physical jobs) but this
introduced a REGRESSION for HIGH-qualification profiles: a user with engineering studies +
"Informatyka w biznesie / Zarządzanie" + SAP postgrad certificate + current position
"Wdrożeniowiec T2 Płatnika" in IT/HR industry started getting low-skill physical jobs
(international driver, warehouse worker, dog sitter) because the "half must be common jobs"
rule applied unconditionally to everyone.

Iteration 6 fix: prompt FIRST assesses qualification level from the WHOLE profile, then
branches: (a) high qualification -> match at same/higher level, specjalista/analityk/
konsultant/kierownik projektu/wdrożeniowiec words ARE fine, no regression to physical work
below their level; (b) basic education/no experience -> unchanged iteration-5 behavior.

COST LIMIT: exactly 2 real /recommendations/generate calls in this file (1 per scenario),
per agent-to-agent cost guidance.
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

# Low-skill/physical jobs that would be a bad match for a high-qualification IT/HR/SAP profile.
LOW_SKILL_PHYSICAL_KEYWORDS = [
    "kierowca", "magazynier", "pracownik magazynu", "opiekun zwierząt", "opiekun psów",
    "opiekunka zwierząt", "sprzątając", "sprzątacz", "ochroniarz", "kasjer", "pracownik produkcji",
    "pracownik budowlany", "kelner", "kucharz", "sprzedawca", "recepcjonist",
]

# Words the OLD (iter5) prompt forbade for basic-education users (still must be forbidden there).
HIGH_QUAL_WORDS = ["specjalist", "koordynator", "konsultant", "analityk", "kierownik", "menedżer", "manager"]

# Common/physical/entry-level jobs expected for a basic-education profile (iter5 behavior,
# must persist). Stems used (not exact words) since the LLM phrases these in many equivalent
# ways, e.g. "pracownik ochrony"/"ochroniarz", "pracownik magazynu"/"magazynier".
COMMON_JOB_KEYWORDS = [
    "sprzedaw", "magazyn", "kierowc", "opiekun", "ochron", "produkcj",
    "sprzątając", "sprzątacz", "kucharz", "kelner", "budowlan", "recepcj",
    "instruktor", "trener", "fitness",
]


def register_and_login(api_client, suffix):
    email = f"TEST_recs_iter72_{suffix}_{uuid.uuid4().hex[:8]}@test.pl"
    payload = {"email": email, "password": "Test12345!", "name": "TEST Iter72", "country": "PL"}
    resp = api_client.post(f"{API}/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    return session


def generate_and_wait(auth_client):
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
    return doc


class TestHighQualificationRegression:
    """MAIN TEST: high-qualification profile must NOT get low-skill physical jobs."""

    @pytest.fixture(scope="class")
    def auth_client(self):
        session = requests.Session()
        return register_and_login(session, "highqual")

    def test_save_high_qualification_profile(self, auth_client):
        answers = {
            "reset_mode": "search",
            "education": "Studia inżynierskie (magisterskie)",
            "education_field": "Informatyka w biznesie / Zarządzanie",
            "certificates": ["Studia podyplomowe SAP"],
            "certificates_other": "Podyplomówka SAP (wdrożenia ERP)",
            "current_job": "Wdrożeniowiec T2 Płatnika",
            "industry": "IT i HR",
            "skills": ["Excel", "ERP", "SAP"],
            "interests": ["IT"],
            "languages": ["angielski"],
        }
        resp = auth_client.put(f"{API}/profile", json={"answers": answers})
        assert resp.status_code == 200, resp.text

        get_resp = auth_client.get(f"{API}/profile")
        assert get_resp.status_code == 200
        saved = get_resp.json()
        assert saved["answers"]["current_job"] == "Wdrożeniowiec T2 Płatnika"
        assert saved["answers"]["education_field"] == "Informatyka w biznesie / Zarządzanie"

    def test_generate_and_check_no_low_skill_jobs(self, auth_client):
        doc = generate_and_wait(auth_client)

        now_items = doc.get("now") or []
        future_items = doc.get("future") or []
        assert len(now_items) == 4, f"expected 4 'now' items, got {len(now_items)}"
        assert len(future_items) == 4, f"expected 4 'future' items, got {len(future_items)}"

        all_items = now_items + future_items
        all_titles = [it.get("title", "") for it in all_items]
        print(f"HIGH-QUAL ALL 8 titles: {all_titles}")

        violations = [t for t in all_titles if any(k in t.lower() for k in LOW_SKILL_PHYSICAL_KEYWORDS)]
        print(f"Low-skill physical job violations: {violations}")
        self.violations = violations

        assert not violations, (
            f"REGRESSION: high-qualification profile (SAP postgrad, IT wdrożeniowiec) got low-skill "
            f"physical job titles below their qualification level: {violations}. Full titles: {all_titles}"
        )

        # Sanity: every title should have real fields populated
        for it in all_items:
            assert it.get("title")
            assert it.get("salary")
            assert it.get("demand") in ("high", "medium", "low")
            assert it.get("ai_risk") in ("high", "medium", "low")


class TestBasicEducationNoRegression:
    """REGRESSION CHECK: basic-education profile must still behave like iteration 5."""

    @pytest.fixture(scope="class")
    def auth_client(self):
        session = requests.Session()
        return register_and_login(session, "basicedu")

    def test_save_basic_education_profile(self, auth_client):
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

    def test_generate_and_check_no_high_qual_words_and_half_common(self, auth_client):
        doc = generate_and_wait(auth_client)

        now_items = doc.get("now") or []
        future_items = doc.get("future") or []
        assert len(now_items) == 4
        assert len(future_items) == 4

        all_items = now_items + future_items
        all_titles = [it.get("title", "") for it in all_items]
        print(f"BASIC-EDU ALL 8 titles: {all_titles}")

        buzzword_violations = [
            t for t in all_titles if any(b in t.lower() for b in HIGH_QUAL_WORDS)
        ]
        print(f"High-qualification-word violations (must be empty): {buzzword_violations}")
        self.buzzword_violations = buzzword_violations
        assert not buzzword_violations, (
            f"REGRESSION: basic-education profile got forbidden high-qualification words: {buzzword_violations}"
        )

        common_count = sum(1 for t in all_titles if any(k in t.lower() for k in COMMON_JOB_KEYWORDS))
        print(f"Common/physical job count: {common_count}/8")
        self.common_count = common_count
        assert common_count >= 4, (
            f"REGRESSION: expected at least half (4/8) common/physical jobs for basic-education "
            f"profile, got {common_count}/8. Titles: {all_titles}"
        )
