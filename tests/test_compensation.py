"""Tests for compensation intelligence module (seeded benchmarks + Gemini search grounding)."""

import asyncio
import json

from intern_engine import compensation, enrich, store
from intern_engine.models import Job


def _run(coro):
    return asyncio.run(coro)


class TestCompensationBenchmarks:
    def test_normalize_company(self):
        assert compensation.normalize_company("Google, Inc.") == "google"
        assert compensation.normalize_company("Amazon Web Services Ltd.") == "amazonwebservices"
        assert compensation.normalize_company("Flipkart Private Limited") == "flipkart"
        assert compensation.normalize_company("Swiggy India Pvt Ltd") == "swiggy"
        assert compensation.normalize_company("CRED") == "cred"

    def test_seeded_benchmark_lookup(self):
        res = _run(
            compensation.lookup_compensation(
                company="Amazon",
                company_slug="amazon",
                title="Software Development Engineer Intern",
                category="Software",
            )
        )
        assert res is not None
        assert "₹" in res["stipend"]
        assert "LPA" in res["ctc"]
        assert "LeetCode" in res["source"] or "Levels.fyi" in res["source"]

    def test_seeded_prefix_match(self):
        res = _run(
            compensation.lookup_compensation(
                company="Google India",
                company_slug="googleindia",
                title="SWE Intern",
                category="Software",
            )
        )
        assert res is not None
        assert "₹1.1L" in res["stipend"]
        assert res["confidence"] == "high"

    def test_unknown_company_without_api_key_returns_none(self):
        res = _run(
            compensation.lookup_compensation(
                company="Completely Unknown Tiny Firm 123",
                company_slug="unknown123",
                title="Intern",
                category="Software",
                client=None,
                api_key=None,
            )
        )
        assert res is None


class TestCompensationCache:
    def test_cache_save_and_load(self, tmp_path):
        cache_file = str(tmp_path / "comp_cache.json")
        test_cache = {
            "testco:software": {
                "stipend": "₹40k/mo",
                "ctc": "15 LPA",
                "source": "AmbitionBox",
                "confidence": "medium",
            }
        }
        compensation._cache = test_cache
        compensation._dirty = True
        compensation.save_cache(cache_file)

        compensation._cache = None
        loaded = compensation.load_cache(cache_file)
        assert "testco:software" in loaded
        assert loaded["testco:software"]["stipend"] == "₹40k/mo"


class TestGeminiGroundingParsing:
    def test_parse_gemini_json_with_grounding_metadata(self):
        raw_text = """```json
        {
            "stipend": "₹60,000/mo",
            "ctc": "20–25 LPA",
            "source": "AmbitionBox",
            "confidence": "high"
        }
        ```"""
        grounding_meta = {
            "groundingChunks": [
                {
                    "web": {
                        "uri": "https://www.ambitionbox.com/salaries/swiggy-salaries/intern",
                        "title": "Swiggy Intern Salaries in India",
                    }
                }
            ]
        }
        parsed = compensation._parse_gemini_json(raw_text, grounding_meta)
        assert parsed is not None
        assert parsed["stipend"] == "₹60,000/mo"
        assert parsed["ctc"] == "20–25 LPA"
        assert parsed["source"] == "AmbitionBox"
        assert parsed["confidence"] == "high"

    def test_query_gemini_grounded_mock(self):
        class MockClient:
            def __init__(self):
                self.calls = 0

            async def post_json(self, url, **kwargs):
                self.calls += 1
                return {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": json.dumps(
                                            {
                                                "stipend": "₹50k/mo",
                                                "ctc": "18 LPA",
                                                "source": "Glassdoor",
                                                "confidence": "medium",
                                            }
                                        )
                                    }
                                ]
                            },
                            "groundingMetadata": {
                                "groundingChunks": [
                                    {"web": {"uri": "https://www.glassdoor.co.in/salaries"}}
                                ]
                            },
                        }
                    ]
                }

        client = MockClient()
        res = _run(
            compensation.query_gemini_grounded(
                company="NewStartup",
                title="Backend Intern",
                category="Software",
                client=client,
                api_key="fake-key",
            )
        )
        assert client.calls == 1
        assert res is not None
        assert res["stipend"] == "₹50k/mo"
        assert res["ctc"] == "18 LPA"
        assert res["source"] == "Glassdoor"


class TestEnrichmentIntegration:
    def test_enrich_backfills_compensation_from_seed(self):
        class DummyNet:
            def __init__(self):
                self.client = None

            async def get_json(self, url, **kwargs):
                return {}

        job = Job(
            id="ashby:google:1",
            source="ashby",
            company="Google",
            company_slug="google",
            title="Software Engineering Intern",
            location="Bengaluru, India",
            url="https://google.com/jobs/1",
            category="Software",
        )
        enriched, _ = _run(enrich.enrich_jobs([job], {}, DummyNet()))
        assert job.id in enriched
        assert job.estimated_stipend is not None
        assert "₹" in job.estimated_stipend
        assert job.estimated_ctc is not None
        assert job.pay_source is not None

    def test_store_persists_estimated_compensation(self):
        existing = {}
        job_row = {
            "id": "ashby:google:1",
            "source": "ashby",
            "company": "Google",
            "company_slug": "google",
            "title": "Software Engineering Intern",
            "location": "Bengaluru, India",
            "url": "https://google.com/jobs/1",
            "category": "Software",
            "estimated_stipend": "₹1.1L–1.35L/mo",
            "estimated_ctc": "35–55 LPA",
            "pay_source": "Levels.fyi",
        }
        store.upsert(existing, [job_row], {"ashby:google"})
        record = existing["ashby:google:1"]
        assert record["estimated_stipend"] == "₹1.1L–1.35L/mo"
        assert record["estimated_ctc"] == "35–55 LPA"
        assert record["pay_source"] == "Levels.fyi"
