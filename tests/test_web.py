"""Tests for the web FastAPI application."""

from starlette.testclient import TestClient

from web.app import app

client = TestClient(app)


def test_homepage():
    res = client.get("/")
    assert res.status_code == 200
    assert "Internships" in res.text
    assert "<table" in res.text


def test_all_jobs():
    res = client.get("/all")
    assert res.status_code == 200
    assert "Internships" in res.text


def test_stats_page():
    res = client.get("/stats")
    assert res.status_code == 200
    assert "Metrics" in res.text


def test_companies_page():
    res = client.get("/companies")
    assert res.status_code == 200
    assert "Tracked Companies" in res.text


def test_api_jobs():
    res = client.get("/api/jobs")
    assert res.status_code == 200
    data = res.json()
    assert "jobs" in data
    assert "count" in data


def test_api_stats():
    res = client.get("/api/stats")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, dict)


def test_api_history():
    res = client.get("/api/history")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)


def test_api_subscribe_invalid():
    res = client.post("/api/subscribe", json={"email": "notanemail"})
    assert res.status_code == 400
    assert "valid email" in res.json()["message"]


def test_unsubscribe_page_missing_token():
    res = client.get("/unsubscribe")
    assert res.status_code == 400
    assert "Missing unsubscribe token" in res.text


def test_unsubscribe_page_with_token_no_db():
    res = client.get("/unsubscribe?t=00000000-0000-0000-0000-000000000000")
    assert res.status_code in (503, 200)
    assert "Unsubscribe" in res.text



def test_web_stale_filter():
    from web.app import _is_stale
    assert not _is_stale({"posted_at": "2026-11-01T00:00:00Z"})
    assert _is_stale({"posted_at": "2026-06-01T00:00:00Z"})
