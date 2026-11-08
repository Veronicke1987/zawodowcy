"""
Regression test for the high-qualification blocklist safety net in run_recommendations()
(server.py ~line 1051-1186). Reported bug: users with high education repeatedly got
low-skill titles (opiekun osob starszych, opiekun zwierzat) from "Wygeneruj nowe propozycje"
(regenerate) despite prompt-only instructions. Fix under test: deterministic code-side
LOW_SKILL_BLOCKLIST check + is_high_qual + one forced retry with stricter prompt.

This test calls POST /api/recommendations/generate 4 times in a row (simulating 4x
"Generate new" clicks) for a high-qualification profile and asserts ZERO blocklist
violations in any of the 4 result sets (title text only, per instructions).
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL").rstrip("/")

HIGH_QUAL_ANSWERS = {
    "education": "Licencjat / inżynier",
    "education_field": "Informatyka w biznesie / Zarządzanie",
    "certificates": "Studia podyplomowe SAP",
    "current_job": "Wdrożeniowiec T2 Płatnika",
    "industry": "IT / HR",
    "tools": "Excel, ERP, SAP",
    "interests": "IT, technologie, systemy ERP",
    "reset_mode": "search",
}

# Keywords from the PRD description (blocklist as described in review request)
BLOCKLIST = [
    "opiekun", "kierowca", "magazynier", "sprzątacz", "sprząta", "kelner", "kucharz",
    "ochroniarz", "kasjer", "sprzedawca", "recepcjonist", "asystent",
    "wsparcie biurowe", "wsparcie administracyjne", "pracownik produkcji",
    "pracownik magazynu", "pracownik fizyczny", "pracownik ochrony",
]


@pytest.fixture(scope="module")
def auth_session():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    email = f"TEST_highqual_{uuid.uuid4().hex[:8]}@test.pl"
    password = "Test@12345"
    r = session.post(f"{BASE_URL}/api/auth/register", json={
        "email": email, "password": password, "name": "TEST HighQual", "country": "PL",
    })
    assert r.status_code == 201, f"register failed: {r.status_code} {r.text}"
    token = r.json()["access_token"]
    session.headers.update({"Authorization": f"Bearer {token}"})

    r2 = session.put(f"{BASE_URL}/api/profile", json={"answers": HIGH_QUAL_ANSWERS})
    assert r2.status_code == 200, f"profile save failed: {r2.status_code} {r2.text}"

    yield session

    # cleanup: no delete-account endpoint used; TEST_ prefixed user left in DB per instructions
    # (no destructive cleanup script run, as instructed)


def poll_until_ready(session, timeout=90):
    start = time.time()
    last = None
    while time.time() - start < timeout:
        r = session.get(f"{BASE_URL}/api/recommendations")
        assert r.status_code == 200
        doc = r.json()
        last = doc
        if doc.get("status") in ("ready", "error"):
            return doc
        time.sleep(3)
    pytest.fail(f"recommendations job did not finish within {timeout}s, last={last}")


class TestHighQualBlocklist:
    """4x consecutive 'Generate new' simulation for a high-qualification profile."""

    def test_four_consecutive_regenerations_no_blocklist_violation(self, auth_session):
        violations_report = []
        for i in range(4):
            gen = auth_session.post(f"{BASE_URL}/api/recommendations/generate")
            assert gen.status_code == 200, f"call {i+1}: generate failed {gen.status_code} {gen.text}"
            assert gen.json().get("status") == "pending"

            doc = poll_until_ready(auth_session)
            assert doc.get("status") == "ready", f"call {i+1}: job ended with status={doc.get('status')} error={doc.get('error')}"

            now_items = doc.get("now") or []
            future_items = doc.get("future") or []
            assert len(now_items) > 0, f"call {i+1}: 'now' category empty"
            assert len(future_items) > 0, f"call {i+1}: 'future' category empty"

            titles = [it.get("title", "") for it in now_items + future_items]
            assert all(titles), f"call {i+1}: some career missing 'title' field"

            call_violations = [t for t in titles if any(b in t.lower() for b in BLOCKLIST)]
            if call_violations:
                violations_report.append({"call": i + 1, "titles": titles, "violations": call_violations})

            print(f"Call {i+1}/4 titles: {titles}")

        assert not violations_report, f"BLOCKLIST VIOLATIONS FOUND: {violations_report}"
