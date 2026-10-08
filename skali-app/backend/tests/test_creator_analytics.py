"""Tests for Creator Analytics module (new feature)."""
import os
import pytest
import requests
from pymongo import MongoClient
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://import-assistant-7.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code}: {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def creator_token():
    return _login("creator@skali.test", "Test1234!")


@pytest.fixture(scope="module")
def fan_token():
    return _login("fan@skali.test", "Test1234!")


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


class TestMeCreatorAccount:
    def test_me_has_creator_account_flag_creator(self, creator_token):
        r = requests.get(f"{API}/me", headers=_auth(creator_token), timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "creator_account" in data, f"missing creator_account in /me: {list(data)}"
        assert data["creator_account"] is True

    def test_me_has_creator_account_flag_fan(self, fan_token):
        r = requests.get(f"{API}/me", headers=_auth(fan_token), timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "creator_account" in data
        assert data["creator_account"] is False


class TestAnalyticsEndpoint:
    def test_creator_can_get_analytics(self, creator_token):
        r = requests.get(f"{API}/creator/analytics", headers=_auth(creator_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        for section in ("overview", "subscribers", "shop", "finance", "health"):
            assert section in d, f"missing {section}"
        # overview fields
        ov = d["overview"]
        for k in ("revenue_this_month", "new_subs_this_month", "tips_this_month",
                  "pending_payout", "revenue_growth_pct", "trend", "sample"):
            assert k in ov
        # finance fees breakdown
        f = d["finance"]
        for k in ("payouts", "fees", "fee_rate", "tax_docs", "sample"):
            assert k in f
        for k in ("gross", "vat", "psp_fee", "skali_fee", "creator_net"):
            assert k in f["fees"]
        # health
        h = d["health"]
        assert "settings" in h

    def test_fan_denied_403(self, fan_token):
        r = requests.get(f"{API}/creator/analytics", headers=_auth(fan_token), timeout=30)
        assert r.status_code == 403, r.text


class TestExports:
    def test_csv_export(self, creator_token):
        r = requests.get(f"{API}/creator/analytics/export.csv", headers=_auth(creator_token), timeout=30)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        assert "section,date_or_month" in r.text

    def test_csv_requires_creator(self, fan_token):
        r = requests.get(f"{API}/creator/analytics/export.csv", headers=_auth(fan_token), timeout=30)
        assert r.status_code == 403

    def test_pdf_export(self, creator_token):
        r = requests.get(f"{API}/creator/analytics/export.pdf", headers=_auth(creator_token), timeout=30)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"

    def test_pdf_requires_creator(self, fan_token):
        r = requests.get(f"{API}/creator/analytics/export.pdf", headers=_auth(fan_token), timeout=30)
        assert r.status_code == 403


class TestHealthSettings:
    def test_toggle_hidden_persists(self, creator_token):
        # Hide
        r = requests.put(f"{API}/creator/health/settings",
                         headers={**_auth(creator_token), "Content-Type": "application/json"},
                         json={"hidden": True}, timeout=30)
        assert r.status_code in (200, 204)
        # Verify hidden
        r = requests.get(f"{API}/creator/analytics", headers=_auth(creator_token), timeout=30)
        assert r.status_code == 200
        h = r.json()["health"]
        assert h["settings"].get("hidden") is True
        assert h.get("metrics") in (None, {})
        # Unhide
        r = requests.put(f"{API}/creator/health/settings",
                         headers={**_auth(creator_token), "Content-Type": "application/json"},
                         json={"hidden": False}, timeout=30)
        assert r.status_code in (200, 204)
        r = requests.get(f"{API}/creator/analytics", headers=_auth(creator_token), timeout=30)
        h = r.json()["health"]
        assert h["settings"].get("hidden") is False
        assert h.get("metrics") is not None


class TestRealDataPath:
    def test_tips_from_transactions(self, creator_token):
        # get creator id
        r = requests.get(f"{API}/me", headers=_auth(creator_token), timeout=30)
        cid = r.json()["id"]

        client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        db = client[os.environ.get("DB_NAME", "test_database")]
        # Insert sample tip transaction
        now = datetime.now(timezone.utc).isoformat()
        doc = {"creator_id": cid, "product": "tip", "creator_net": 5.0,
               "gross": 6.0, "status": "settled", "created_at": now,
               "_test_marker": "TEST_analytics"}
        try:
            db.transactions.insert_one(doc)
            r = requests.get(f"{API}/creator/analytics", headers=_auth(creator_token), timeout=30)
            assert r.status_code == 200
            ov = r.json()["overview"]
            assert "tips" not in ov["sample"], f"tips still sample: {ov['sample']}"
            assert ov["tips_this_month"] >= 5.0
        finally:
            db.transactions.delete_many({"_test_marker": "TEST_analytics"})
