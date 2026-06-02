from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import AsyncIterator, Dict, List, Optional

import httpx

from app.prompt_builder import render_prompt, build_request_body


@dataclass
class BenchmarkConfig:
    endpoint: str
    api_key: str
    start_concurrency: int = 1
    step_size: int = 5
    max_concurrency: int = 200
    requests_per_level: int = 50
    latency_threshold: float = 2.0


def classify_error(exc: Exception) -> str:
    if isinstance(exc, (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)):
        return "timeout"
    if isinstance(exc, (httpx.ConnectError, httpx.HTTPError)):
        return "connection_error"
    return "connection_error"


@dataclass
class LevelResult:
    level: int
    concurrency: int
    avg_latency: float
    p50: float
    p95: float
    p99: float
    rps: float
    success_rate: float
    error_count: int
    error_rate: float
    errors_by_type: Dict[str, int]
    total_requests: int
    violations_by_policy: Dict[str, int]
    threshold_exceeded: bool

    @staticmethod
    def from_latencies(
        level: int,
        concurrency: int,
        latencies: List[float],
        violations_by_policy: Dict[str, int],
        errors_by_type: Dict[str, int],
        total_requests: int,
        error_count: int,
        elapsed: float,
        threshold: float,
    ) -> "LevelResult":
        if latencies:
            sorted_lat = sorted(latencies)
            n = len(sorted_lat)
            avg = sum(sorted_lat) / n
            p50 = sorted_lat[int(n * 0.50)]
            p95 = sorted_lat[min(int(n * 0.95), n - 1)]
            p99 = sorted_lat[min(int(n * 0.99), n - 1)]
        else:
            avg = p50 = p95 = p99 = 0.0

        rps = total_requests / elapsed if elapsed > 0 else 0.0
        success_rate = ((total_requests - error_count) / total_requests * 100) if total_requests > 0 else 0.0
        error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0.0

        return LevelResult(
            level=level,
            concurrency=concurrency,
            avg_latency=avg,
            p50=p50,
            p95=p95,
            p99=p99,
            rps=rps,
            success_rate=success_rate,
            error_count=error_count,
            error_rate=error_rate,
            errors_by_type=errors_by_type,
            total_requests=total_requests,
            violations_by_policy=violations_by_policy,
            threshold_exceeded=avg > threshold,
        )

    def to_dict(self) -> dict:
        return {
            "type": "level_result",
            "level": self.level,
            "concurrency": self.concurrency,
            "avg_latency": round(self.avg_latency, 4),
            "p50": round(self.p50, 4),
            "p95": round(self.p95, 4),
            "p99": round(self.p99, 4),
            "rps": round(self.rps, 2),
            "success_rate": round(self.success_rate, 2),
            "error_count": self.error_count,
            "error_rate": round(self.error_rate, 2),
            "errors_by_type": self.errors_by_type,
            "total_requests": self.total_requests,
            "violations_by_policy": self.violations_by_policy,
            "threshold_exceeded": self.threshold_exceeded,
        }


class BenchmarkEngine:
    def __init__(self, config: BenchmarkConfig):
        self.config = config

    async def _send_single_request(self, client, url, headers, body):
        start = time.monotonic()
        resp = await client.post(url, json=body, headers=headers, timeout=30.0)
        latency = time.monotonic() - start
        status = resp.status_code
        decision = "unknown"
        violations: Dict[str, int] = {}
        try:
            data = resp.json()
            if "decision" in data:
                decision = data["decision"]
            if "violations" in data:
                for v in data["violations"]:
                    pid = v.get("policy_id", "unknown")
                    violations[pid] = violations.get(pid, 0) + 1
            elif "error" in data and "violations" in data.get("error", {}):
                for v in data["error"]["violations"]:
                    pid = v.get("policy_id", "unknown")
                    violations[pid] = violations.get(pid, 0) + 1
        except Exception:
            pass
        return latency, status, decision, violations

    async def run(
        self,
        prompt_template: str,
        generators: List[str],
        image_base64: Optional[str],
    ) -> AsyncIterator[LevelResult]:
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        level = 0
        concurrency = self.config.start_concurrency

        async with httpx.AsyncClient() as client:
            while concurrency <= self.config.max_concurrency:
                level += 1
                sem = asyncio.Semaphore(concurrency)
                latencies: List[float] = []
                violations_agg: Dict[str, int] = {}
                errors_by_type: Dict[str, int] = {}
                error_count = 0

                async def do_request():
                    nonlocal error_count
                    async with sem:
                        text = render_prompt(prompt_template, generators)
                        body = build_request_body(text, image_base64)
                        try:
                            lat, status, decision, viols = await self._send_single_request(
                                client, self.config.endpoint, headers, body
                            )
                            latencies.append(lat)
                            for pid, cnt in viols.items():
                                violations_agg[pid] = violations_agg.get(pid, 0) + cnt
                            if status not in (200, 400):
                                error_count += 1
                                etype = f"http_{status}" if status >= 500 else "http_other"
                                errors_by_type[etype] = errors_by_type.get(etype, 0) + 1
                        except Exception as exc:
                            error_count += 1
                            etype = classify_error(exc)
                            errors_by_type[etype] = errors_by_type.get(etype, 0) + 1

                level_start = time.monotonic()
                tasks = [asyncio.create_task(do_request()) for _ in range(self.config.requests_per_level)]
                await asyncio.gather(*tasks)
                elapsed = time.monotonic() - level_start

                result = LevelResult.from_latencies(
                    level=level,
                    concurrency=concurrency,
                    latencies=latencies,
                    violations_by_policy=violations_agg,
                    errors_by_type=errors_by_type,
                    total_requests=self.config.requests_per_level,
                    error_count=error_count,
                    elapsed=elapsed,
                    threshold=self.config.latency_threshold,
                )
                yield result

                if result.threshold_exceeded:
                    return

                concurrency += self.config.step_size
