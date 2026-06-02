import json
from app.report import render_report_html, generate_pdf
from app.benchmark import LevelResult


def _make_level(level, concurrency, avg, p50, p95, p99, exceeded=False):
    return LevelResult(
        level=level,
        concurrency=concurrency,
        avg_latency=avg,
        p50=p50,
        p95=p95,
        p99=p99,
        rps=concurrency * 2.0,
        success_rate=100.0,
        error_count=0,
        error_rate=0.0,
        errors_by_type={},
        total_requests=50,
        violations_by_policy={"No-PII-Data": 45},
        threshold_exceeded=exceeded,
    )


class TestRenderReportHtml:
    def test_html_contains_summary(self):
        levels = [
            _make_level(1, 1, 0.1, 0.08, 0.15, 0.18),
            _make_level(2, 6, 0.5, 0.4, 0.8, 0.9),
            _make_level(3, 11, 2.1, 1.8, 2.5, 3.0, exceeded=True),
        ]
        html = render_report_html(
            endpoint="http://localhost:8080/v1/rampart/evaluate",
            config={"step_size": 5, "requests_per_level": 50, "latency_threshold": 2.0},
            levels=levels,
            max_safe_concurrency=6,
            total_requests=150,
            total_errors=0,
            prompt_template="Test {ssn}",
            generators=["ssn"],
        )
        assert "http://localhost:8080" in html
        assert "Max Safe Concurrency" in html
        assert "6" in html
        assert "No-PII-Data" in html

    def test_html_contains_percentile_data(self):
        levels = [_make_level(1, 1, 0.1, 0.08, 0.15, 0.18)]
        html = render_report_html(
            endpoint="http://test.com",
            config={"step_size": 5, "requests_per_level": 50, "latency_threshold": 2.0},
            levels=levels,
            max_safe_concurrency=1,
            total_requests=50,
            total_errors=0,
            prompt_template="test",
            generators=[],
        )
        assert "p50" in html.lower() or "P50" in html


class TestGeneratePdf:
    def test_pdf_is_bytes(self):
        levels = [_make_level(1, 1, 0.1, 0.08, 0.15, 0.18)]
        pdf_bytes = generate_pdf(
            endpoint="http://test.com",
            config={"step_size": 5, "requests_per_level": 50, "latency_threshold": 2.0},
            levels=levels,
            max_safe_concurrency=1,
            total_requests=50,
            total_errors=0,
            prompt_template="test",
            generators=[],
        )
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 100
        assert pdf_bytes[:5] == b"%PDF-"
