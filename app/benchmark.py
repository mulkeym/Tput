from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Dict, List, Optional

import httpx

logger = logging.getLogger("tput")

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
    user: str = ""


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
        aggregate_tps: float = 0.0,
    ) -> "LevelResult":
        if ttft_values is None:
            ttft_values = []

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
            avg_tps=aggregate_tps,
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

    async def _send_single_request(self, client, url, headers, body, timeout):
        start = time.monotonic()
        resp = await client.post(url, json=body, headers=headers, timeout=timeout)
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

    async def _send_streaming_request(self, client, url, headers, body, timeout):
        """Send a streaming request. Returns (latency, ttft, token_count, status)."""
        start = time.monotonic()
        ttft = None
        total_tokens = 0

        async with client.stream("POST", url, json=body, headers=headers, timeout=timeout) as resp:
            status = resp.status_code
            if status != 200:
                await resp.aread()
                total_time = time.monotonic() - start
                return total_time, total_time, 0, status

            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                if line.strip() == "data: [DONE]":
                    break
                if ttft is None:
                    ttft = time.monotonic() - start
                try:
                    chunk = json.loads(line[6:])
                    choices = chunk.get("choices", [])
                    if choices and choices[0].get("delta", {}).get("content"):
                        total_tokens += 1
                except (json.JSONDecodeError, KeyError, IndexError):
                    pass

        total_time = time.monotonic() - start
        if ttft is None:
            ttft = total_time

        return total_time, ttft, total_tokens, status

    async def run(
        self,
        prompt_template: str,
        generators: List[str],
        image_base64: Optional[str],
    ) -> AsyncIterator[LevelResult]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        # Auto-append /chat/completions for LLM mode if not already present
        endpoint = self.config.endpoint.rstrip("/")
        if self.config.mode == LLM_MODE and not endpoint.endswith("/chat/completions"):
            endpoint = endpoint + "/chat/completions"

        level = 0
        concurrency = self.config.start_concurrency
        mode = self.config.mode

        max_conn = self.config.max_concurrency + 10
        pool_limits = httpx.Limits(
            max_connections=max_conn,
            max_keepalive_connections=max_conn,
            keepalive_expiry=30,
        )
        # Separate connect vs read/write timeouts so pool contention
        # doesn't eat into the server-response budget.
        rampart_timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=60.0)
        llm_timeout = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=60.0)
        timeout = llm_timeout if mode == LLM_MODE else rampart_timeout

        rounds = self.config.requests_per_level  # number of sample rounds

        async with httpx.AsyncClient(limits=pool_limits) as client:
            while concurrency <= self.config.max_concurrency:
                level += 1
                latencies: List[float] = []
                violations_agg: Dict[str, int] = {}
                errors_by_type: Dict[str, int] = {}
                error_count = 0
                ttft_values: List[float] = []
                total_tokens_all: List[int] = []
                total_requests = 0

                level_start = time.monotonic()

                for _round in range(rounds):
                    # Each round fires exactly `concurrency` simultaneous requests

                    if mode == LLM_MODE:
                        async def do_llm_request():
                            nonlocal error_count
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
                            if self.config.user:
                                body["user"] = self.config.user
                            try:
                                lat, ttft, tokens, status = await self._send_streaming_request(
                                    client, endpoint, headers, body, timeout
                                )
                                latencies.append(lat)
                                ttft_values.append(ttft)
                                total_tokens_all.append(tokens)
                                if status != 200:
                                    error_count += 1
                                    etype = f"http_{status}"
                                    errors_by_type[etype] = errors_by_type.get(etype, 0) + 1
                            except Exception as exc:
                                error_count += 1
                                etype = classify_error(exc)
                                errors_by_type[etype] = errors_by_type.get(etype, 0) + 1

                        tasks = [asyncio.create_task(do_llm_request()) for _ in range(concurrency)]
                    else:
                        async def do_rampart_request():
                            nonlocal error_count
                            text = render_prompt(prompt_template, generators)
                            body = build_request_body(text, image_base64, user=self.config.user or None)
                            try:
                                lat, status, decision, viols = await self._send_single_request(
                                    client, endpoint, headers, body, timeout
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

                        tasks = [asyncio.create_task(do_rampart_request()) for _ in range(concurrency)]

                    await asyncio.gather(*tasks)
                    total_requests += concurrency

                elapsed = time.monotonic() - level_start

                # Aggregate TPS = total tokens generated / total wall time
                agg_tps = sum(total_tokens_all) / elapsed if elapsed > 0 else 0.0

                result = LevelResult.from_latencies(
                    level=level,
                    concurrency=concurrency,
                    latencies=latencies,
                    violations_by_policy=violations_agg,
                    errors_by_type=errors_by_type,
                    total_requests=total_requests,
                    error_count=error_count,
                    elapsed=elapsed,
                    threshold=self.config.latency_threshold,
                    ttft_values=ttft_values,
                    aggregate_tps=agg_tps,
                )
                yield result

                if result.threshold_exceeded:
                    return

                concurrency += self.config.step_size
