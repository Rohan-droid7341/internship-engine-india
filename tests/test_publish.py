"""The machine-readable outputs: Atom feed parses, JSON API round-trips."""

import json
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta

from intern_engine import paths, publish

_RECENT_TS = (datetime.now(UTC) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

STORE = {
    "a": {
        "id": "a",
        "company": "Stripe",
        "title": "SWE Intern",
        "season": "Summer 2027",
        "category": "Software",
        "location": "SF",
        "url": "https://stripe.com/jobs/1",
        "posted_at": _RECENT_TS,
        "first_seen_at": _RECENT_TS,
        "sponsorship": "no-sponsorship",
        "salary": None,
        "source": "greenhouse",
        "is_open": True,
    },
    "b": {
        "id": "b",
        "company": "Old Co",
        "title": "Closed Intern",
        "season": "Fall 2026",
        "category": "Software",
        "location": "NY",
        "url": "https://old.co",
        "first_seen_at": "2026-05-01T00:00:00Z",
        "sponsorship": "unknown",
        "source": "lever",
        "is_open": False,
    },
}


def _redirect(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "DOCS_DIR", str(tmp_path))
    monkeypatch.setattr(paths, "FEED_PATH", str(tmp_path / "feed.xml"))
    monkeypatch.setattr(paths, "API_DIR", str(tmp_path / "api"))


class TestFeed:
    def test_only_open_roles_and_valid_xml(self, monkeypatch, tmp_path):
        _redirect(monkeypatch, tmp_path)
        n = publish.write_feed(STORE)
        assert n == 1
        tree = ET.parse(tmp_path / "feed.xml")
        ns = {"a": "http://www.w3.org/2005/Atom"}
        entries = tree.getroot().findall("a:entry", ns)
        assert len(entries) == 1
        title = entries[0].find("a:title", ns).text
        assert "Stripe" in title


class TestApi:
    def test_jobs_json_shape(self, monkeypatch, tmp_path):
        _redirect(monkeypatch, tmp_path)
        publish.write_api(STORE, {"open_total": 1})
        with open(tmp_path / "api" / "jobs.json", encoding="utf-8") as f:
            data = json.load(f)
        assert data["count"] == 1
        job = data["jobs"][0]
        assert job["company"] == "Stripe"
        assert "is_open" not in job  # only open roles ship, flag is redundant


class TestGenerators:
    def test_readme_generation(self, monkeypatch, tmp_path):
        from intern_engine import readme

        readme_file = tmp_path / "README.md"
        monkeypatch.setattr(paths, "README_PATH", str(readme_file))
        monkeypatch.setattr(paths, "DOCS_DIR", str(tmp_path))

        india_store = {
            "ind1": {
                "id": "ind1",
                "company": "Swiggy",
                "title": "Software Engineering Intern",
                "season": "Summer 2027",
                "category": "Software",
                "location": "Bengaluru, Karnataka, India",
                "url": "https://swiggy.com/careers/1",
                "posted_at": "2026-09-10T00:00:00Z",
                "first_seen_at": "2026-09-11T00:00:00Z",
                "salary": None,
                "stipend": "₹60,000/month",
                "source": "custom",
                "is_open": True,
            }
        }
        res = readme.generate(india_store)
        assert res["open"] == 1
        assert readme_file.exists()
        content = readme_file.read_text(encoding="utf-8")
        assert "Swiggy" in content
        assert "## Summer 2027  (1 open)" in content
        assert "₹60,000/month" in content
        assert "India" in content

    def test_readme_region_of_foreign_remote(self):
        from intern_engine.readme import _region_of
        assert _region_of({"location": "Bengaluru, India"}) == "Primary"
        assert _region_of({"location": "Remote, India"}) == "Primary"
        assert _region_of({"location": "Remote (London, UK)"}) == "International"
        assert _region_of({"location": "Remote - Germany"}) == "International"
