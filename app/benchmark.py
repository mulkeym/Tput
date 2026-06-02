from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Dict, List, Optional

import httpx

from app.prompt_builder import render_prompt, build_request_body

RAMPART_MODE = "rampart"
LLM_MODE = "llm"


@dataclass
class BenchmarkConfig:
    endpoint: str
    api_key: str
    start_concurrency: int = 1
    step_size: int = 5
    max_concurrency: int = 200
    requests_per_level: int = 50
    latency_threshold: float = 2.0
    mode: str = "rampart"
    model: str = "gpt-4"


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
    avg_ttft: float = 0.0
    p50_ttft: float = 0.0
    p95_ttft: float = 0.0
    p99_ttft: float = 0.0
    avg_tps: float = 0.0

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
        ttft_values: List[float] = None,
        tps_values: List[float] = None,
    ) -> "LevelResult":
        if ttft_values is None:
            ttft_values = []
        if tps_values is None:
            tps_values = []

        if latencies:
            sorted_lat = sorted(latencies)
            n = len(sorted_lat)
            avg = sum(sorted_lat) / n
            p50 = sorted_lat[int(n * 0.50)]
            p95 = sorted_lat[min(int(n * 0.95), n - 1)]
            p99 = sorted_lat[min(int(n * 0.99), n - 1)]
        else:
            avg = p50 = p95 = p99 = 0.0

        if ttft_values:
            sorted_ttft = sorted(ttft_values)
            nt = len(sorted_ttft)
            avg_ttft = sum(sorted_ttft) / nt
            p50_ttft = sorted_ttft[int(nt * 0.50)]
            p95_ttft = sorted_ttft[min(int(nt * 0.95), nt - 1)]
            p99_ttft = sorted_ttft[min(int(nt * 0.99), nt - 1)]
        else:
            avg_ttft = p50_ttft = p95_ttft = p99_ttft = 0.0

        avg_tps = sum(tps_values) / len(tps_values) if tps_values else 0.0

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
            avg_ttft=avg_ttft,
            p50_ttft=p50_ttft,
            p95_ttft=p95_ttft,
            p99_ttft=p99_ttft,
            avg_tps=avg_tps,
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
            "avg_ttft": round(self.avg_ttft, 4),
            "p50_ttft": round(self.p50_ttft, 4),
            "p95_ttft": round(self.p95_ttft, 4),
            "p99_ttft": round(self.p99_ttft, 4),
            "avg_tps": round(self.avg_tps, 2),
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

    async def _send_streaming_request(self, client, url, headers, body):
        """Send a streaming chat completion request. Returns (latency, ttft, tps, status)."""
        start = time.monotonic()
        ttft = None
        total_tokens = 0

        async with client.stream("POST", url, json=body, headers=headers, timeout=60.0) as resp:
            status = resp.status_code
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                if line.strip() == "data: [DONE]":
                    break
                if ttft is None:
                    ttft = time.monotonic() - start
                # Count token chunks
                try:
                    chunk = json.loads(line[6:])
                    choices = chunk.get("choices", [])
                    if choices and choices[0].get("delta", {}).get("content"):
                        total_tokens += 1  # Each content chunk ~= 1 token
                except (json.JSONDecodeError, KeyError, IndexError):
                    pass

        total_time = time.monotonic() - start
        if ttft is None:
            ttft = total_time

        # tokens per second (exclude TTFT from generation time)
        gen_time = total_time - ttft
        tps = total_tokens / gen_time if gen_time > 0 and total_tokens > 0 else 0.0

        return total_time, ttft, tps, status

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
        mode = self.config.mode

        async with httpx.AsyncClient() as client:
            while concurrency <= self.config.max_concurrency:
                level += 1
                sem = asyncio.Semaphore(concurrency)
                latencies: List[float] = []
                violations_agg: Dict[str, int] = {}
                errors_by_type: Dict[str, int] = {}
                error_count = 0
                ttft_values: List[float] = []
                tps_values: List[float] = []

                if mode == LLM_MODE:
                    async def do_request():
                        nonlocal error_count
                        async with sem:
                            text = render_prompt(prompt_template, generators)
                            if image_base64:
                                content = [
                                    {"type": "text", "text": text},
                                    {"type": "image_url", "image_url": {"url": image_base64}},
                                ]
                            else:
                                content = text
                            body = {
                                "model": self.config.model,
                                "messages": [{"role": "user", "content": content}],
                                "stream": True,
                            }
                            try:
                                lat, ttft, tps, status = await self._send_streaming_request(
                                    client, self.config.endpoint, headers, body
                                )
                                latencies.append(lat)
                                ttft_values.append(ttft)
                                tps_values.append(tps)
                                if status not in (200, 400):
                                    error_count += 1
                                    etype = f"http_{status}" if status >= 500 else "http_other"
                                    errors_by_type[etype] = errors_by_type.get(etype, 0) + 1
                            except Exception as exc:
                                error_count += 1
                                etype = classify_error(exc)
                                errors_by_type[etype] = errors_by_type.get(etype, 0) + 1
                else:
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
                    ttft_values=ttft_values,
                    tps_values=tps_values,
                )
                yield result

                if result.threshold_exceeded:
                    return

                concurrency += self.config.step_size
