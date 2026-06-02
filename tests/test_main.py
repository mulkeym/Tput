from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


class TestStaticRoutes:
    def test_index_returns_html(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Tput" in resp.text

    def test_static_css(self):
        resp = client.get("/static/style.css")
        assert resp.status_code == 200

    def test_static_js(self):
        resp = client.get("/static/app.js")
        assert resp.status_code == 200


class TestGenerateDataEndpoint:
    def test_returns_generated_values(self):
        resp = client.post("/api/generate-data", json={"generators": ["ssn", "name"]})
        assert resp.status_code == 200
        data = resp.json()
        assert "ssn" in data
        assert "name" in data

    def test_empty_generators(self):
        resp = client.post("/api/generate-data", json={"generators": []})
        assert resp.status_code == 200
        assert resp.json() == {}


class TestReportEndpoint:
    def test_report_returns_pdf(self):
        resp = client.post("/api/report", json={
            "endpoint": "http://test.com",
            "config": {"step_size": 5, "requests_per_level": 50, "latency_threshold": 2.0},
            "levels": [
                {
                    "type": "level_result",
                    "level": 1,
                    "concurrency": 1,
                    "avg_latency": 0.1,
                    "p50": 0.08,
                    "p95": 0.15,
                    "p99": 0.18,
                    "rps": 10.0,
                    "success_rate": 100.0,
                    "error_count": 0,
                    "error_rate": 0.0,
                    "errors_by_type": {},
                    "total_requests": 50,
                    "violations_by_policy": {},
                    "threshold_exceeded": False,
                }
            ],
            "max_safe_concurrency": 1,
            "total_requests": 50,
            "total_errors": 0,
            "prompt_template": "test",
            "generators": [],
            "mode": "rampart",
        })
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:5] == b"%PDF-"
