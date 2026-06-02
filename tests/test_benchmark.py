import asyncio
import json
import pytest
from unittest.mock import AsyncMock
from app.benchmark import BenchmarkConfig, BenchmarkEngine, LevelResult, classify_error, RAMPART_MODE, LLM_MODE


class TestBenchmarkConfig:
    def test_defaults(self):
        cfg = BenchmarkConfig(endpoint="http://localhost:8080/v1/rampart/evaluate", api_key="rmp_live_test")
        assert cfg.start_concurrency == 1
        assert cfg.step_size == 5
        assert cfg.max_concurrency == 200
        assert cfg.requests_per_level == 50
        assert cfg.latency_threshold == 2.0

    def test_custom_values(self):
        cfg = BenchmarkConfig(
            endpoint="http://example.com/v1/rampart/evaluate",
            api_key="rmp_live_x",
            start_concurrency=5,
            step_size=10,
            max_concurrency=100,
            requests_per_level=20,
            latency_threshold=1.0,
        )
        assert cfg.step_size == 10
        assert cfg.latency_threshold == 1.0

    def test_mode_and_model_defaults(self):
        cfg = BenchmarkConfig(endpoint="http://localhost:8080", api_key="test")
        assert cfg.mode == "rampart"
        assert cfg.model == "gpt-4"

    def test_mode_llm(self):
        cfg = BenchmarkConfig(endpoint="http://localhost:8080", api_key="test", mode="llm", model="gpt-4o")
        assert cfg.mode == LLM_MODE
        assert cfg.model == "gpt-4o"


class TestClassifyError:
    def test_timeout(self):
        import httpx
        err = httpx.ReadTimeout("timed out")
        assert classify_error(err) == "timeout"

    def test_connection_error(self):
        import httpx
        err = httpx.ConnectError("refused")
        assert classify_error(err) == "connection_error"

    def test_generic_httpx_error(self):
        import httpx
        err = httpx.HTTPError("something")
        assert classify_error(err) == "connection_error"


class TestLevelResult:
    def test_from_latencies_computes_stats(self):
        latencies = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        violations = {"No-PII-Data": 8, "No-PHI": 5}
        errors_by_type = {}
        result = LevelResult.from_latencies(
            level=1,
            concurrency=5,
            latencies=latencies,
            violations_by_policy=violations,
            errors_by_type=errors_by_type,
            total_requests=10,
            error_count=0,
            elapsed=2.0,
            threshold=2.0,
        )
        assert result.avg_latency == pytest.approx(0.55, abs=0.01)
        assert result.p50 == pytest.approx(0.55, abs=0.1)
        assert result.p99 >= result.p95 >= result.p50
        assert result.rps == pytest.approx(5.0, abs=0.1)
        assert result.success_rate == 100.0
        assert result.threshold_exceeded is False

    def test_threshold_exceeded(self):
        latencies = [2.5, 3.0, 2.8, 3.1, 2.9]
        result = LevelResult.from_latencies(
            level=5,
            concurrency=25,
            latencies=latencies,
            violations_by_policy={},
            errors_by_type={},
            total_requests=5,
            error_count=0,
            elapsed=3.0,
            threshold=2.0,
        )
        assert result.threshold_exceeded is True

    def test_to_dict_is_json_serializable(self):
        latencies = [0.5, 0.6]
        result = LevelResult.from_latencies(
            level=1, concurrency=1, latencies=latencies,
            violations_by_policy={}, errors_by_type={},
            total_requests=2, error_count=0, elapsed=1.0, threshold=2.0,
        )
        json.dumps(result.to_dict())

    def test_ttft_tps_fields_default_zero(self):
        result = LevelResult.from_latencies(
            level=1, concurrency=1, latencies=[0.5],
            violations_by_policy={}, errors_by_type={},
            total_requests=1, error_count=0, elapsed=1.0, threshold=2.0,
        )
        assert result.avg_ttft == 0.0
        assert result.p50_ttft == 0.0
        assert result.p95_ttft == 0.0
        assert result.p99_ttft == 0.0
        assert result.avg_tps == 0.0

    def test_ttft_tps_computed_from_values(self):
        ttft_values = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        tps_values = [10.0, 20.0, 30.0]
        result = LevelResult.from_latencies(
            level=1, concurrency=5, latencies=[0.5] * 10,
            violations_by_policy={}, errors_by_type={},
            total_requests=10, error_count=0, elapsed=2.0, threshold=2.0,
            ttft_values=ttft_values, tps_values=tps_values,
        )
        assert result.avg_ttft == pytest.approx(0.55, abs=0.01)
        assert result.p50_ttft == pytest.approx(0.55, abs=0.1)
        assert result.p99_ttft >= result.p95_ttft >= result.p50_ttft
        assert result.avg_tps == pytest.approx(20.0, abs=0.01)

    def test_to_dict_includes_ttft_tps_fields(self):
        ttft_values = [0.1, 0.2, 0.3]
        tps_values = [15.0, 25.0]
        result = LevelResult.from_latencies(
            level=1, concurrency=1, latencies=[0.5, 0.6, 0.7],
            violations_by_policy={}, errors_by_type={},
            total_requests=3, error_count=0, elapsed=1.0, threshold=2.0,
            ttft_values=ttft_values, tps_values=tps_values,
        )
        d = result.to_dict()
        assert "avg_ttft" in d
        assert "p50_ttft" in d
        assert "p95_ttft" in d
        assert "p99_ttft" in d
        assert "avg_tps" in d
        assert d["avg_tps"] == pytest.approx(20.0, abs=0.01)


class TestBenchmarkEngine:
    @pytest.mark.asyncio
    async def test_engine_stops_when_threshold_exceeded(self):
        call_count = 0

        async def mock_send(client, url, headers, body):
            nonlocal call_count
            call_count += 1
            return 0.1 if call_count <= 2 else 2.5, 200, "fail", {"No-PII-Data": 1}

        cfg = BenchmarkConfig(
            endpoint="http://localhost:8080/v1/rampart/evaluate",
            api_key="rmp_live_test",
            start_concurrency=1,
            step_size=1,
            max_concurrency=10,
            requests_per_level=2,
            latency_threshold=2.0,
        )
        engine = BenchmarkEngine(cfg)
        engine._send_single_request = mock_send

        results = []
        async for level_result in engine.run(
            prompt_template="test {ssn}",
            generators=["ssn"],
            image_base64=None,
        ):
            results.append(level_result)

        assert len(results) >= 2
        assert results[-1].threshold_exceeded is True
