# Tput — RAMPART Benchmark Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python benchmarking tool with a web GUI that measures the maximum concurrency RAMPART's `/v1/rampart/evaluate` endpoint can handle before average latency exceeds a configurable threshold.

**Architecture:** FastAPI backend with async httpx for concurrent requests, WebSocket for real-time streaming to a vanilla JS frontend with Chart.js. Linear concurrency ramp with per-level statistics. PDF export via weasyprint.

**Tech Stack:** Python 3.10+, FastAPI, uvicorn, httpx, websockets, Faker, weasyprint, Jinja2, Chart.js (CDN)

**Spec:** `docs/superpowers/specs/2026-06-02-tput-benchmark-design.md`

---

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `app/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create requirements.txt**

```
fastapi>=0.100
uvicorn[standard]>=0.23
httpx>=0.27
websockets>=12.0
faker>=20.0
weasyprint>=60.0
jinja2>=3.1
pytest>=8.0
pytest-asyncio>=0.23
```

- [ ] **Step 2: Create package init files**

Create `app/__init__.py` (empty file).
Create `tests/__init__.py` (empty file).

- [ ] **Step 3: Create tests/conftest.py**

```python
import pytest


@pytest.fixture
def sample_generators():
    """List of generator names for testing."""
    return ["name", "ssn", "email", "mrn", "diagnosis"]
```

- [ ] **Step 4: Install dependencies**

Run: `cd /Users/michaelmulkey/Documents/Repositories/Tput && pip install -r requirements.txt`
Expected: All packages install successfully.

- [ ] **Step 5: Commit**

```bash
git init
git add requirements.txt app/__init__.py tests/__init__.py tests/conftest.py
git commit -m "chore: scaffold Tput project with dependencies"
```

---

### Task 2: PII/PHI Data Generators

**Files:**
- Create: `app/generators.py`
- Create: `tests/test_generators.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_generators.py`:

```python
import re
from app.generators import generate_value, GENERATOR_REGISTRY, generate_all


class TestGenerateValue:
    def test_ssn_format(self):
        val = generate_value("ssn")
        assert re.match(r"^\d{3}-\d{2}-\d{4}$", val)

    def test_name_is_two_words(self):
        val = generate_value("name")
        parts = val.strip().split()
        assert len(parts) >= 2

    def test_email_has_at_sign(self):
        val = generate_value("email")
        assert "@" in val

    def test_phone_format(self):
        val = generate_value("phone")
        # Should contain digits
        digits = re.sub(r"\D", "", val)
        assert len(digits) == 10

    def test_address_nonempty(self):
        val = generate_value("address")
        assert len(val) > 10

    def test_dob_date_format(self):
        val = generate_value("dob")
        assert re.match(r"^\d{2}/\d{2}/\d{4}$", val)

    def test_drivers_license_nonempty(self):
        val = generate_value("drivers_license")
        assert len(val) > 3

    def test_credit_card_format(self):
        val = generate_value("credit_card")
        digits = re.sub(r"\D", "", val)
        assert len(digits) >= 13

    def test_mrn_format(self):
        val = generate_value("mrn")
        assert val.startswith("MRN-")
        assert len(val) == 10  # MRN-XXXXXX

    def test_diagnosis_has_code(self):
        val = generate_value("diagnosis")
        # Should contain a dot-separated ICD code like "J18.9"
        assert re.search(r"[A-Z]\d+\.\d+", val)

    def test_medication_nonempty(self):
        val = generate_value("medication")
        assert len(val) > 3

    def test_provider_starts_with_dr(self):
        val = generate_value("provider")
        assert val.startswith("Dr.")

    def test_insurance_id_format(self):
        val = generate_value("insurance_id")
        assert re.match(r"^[A-Z]+-\d+$", val)

    def test_admission_date_format(self):
        val = generate_value("admission_date")
        assert re.match(r"^\d{2}/\d{2}/\d{4}$", val)

    def test_lab_result_has_value(self):
        val = generate_value("lab_result")
        assert re.search(r"\d", val)

    def test_unknown_generator_raises(self):
        try:
            generate_value("nonexistent_type")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass


class TestGenerateAll:
    def test_returns_dict_with_requested_keys(self):
        result = generate_all(["name", "ssn", "mrn"])
        assert "name" in result
        assert "ssn" in result
        assert "mrn" in result

    def test_each_call_produces_unique_values(self):
        results = [generate_all(["ssn"]) for _ in range(20)]
        ssns = [r["ssn"] for r in results]
        # At least some should differ (extremely unlikely all 20 match)
        assert len(set(ssns)) > 1


class TestRegistryCompleteness:
    def test_all_pii_types_registered(self):
        pii_types = ["ssn", "name", "email", "phone", "address", "dob",
                     "drivers_license", "credit_card"]
        for t in pii_types:
            assert t in GENERATOR_REGISTRY

    def test_all_phi_types_registered(self):
        phi_types = ["mrn", "diagnosis", "medication", "provider",
                     "insurance_id", "admission_date", "lab_result"]
        for t in phi_types:
            assert t in GENERATOR_REGISTRY
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/michaelmulkey/Documents/Repositories/Tput && python -m pytest tests/test_generators.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.generators'`

- [ ] **Step 3: Implement generators.py**

Create `app/generators.py`:

```python
import random
import string
from faker import Faker

fake = Faker()

# Common ICD-10 codes with descriptions
ICD10_CODES = [
    ("J18.9", "Pneumonia, unspecified organism"),
    ("I10", "Essential hypertension"),
    ("E11.9", "Type 2 diabetes mellitus without complications"),
    ("M54.5", "Low back pain"),
    ("J06.9", "Acute upper respiratory infection"),
    ("K21.0", "Gastro-esophageal reflux disease with esophagitis"),
    ("F32.9", "Major depressive disorder, single episode"),
    ("N39.0", "Urinary tract infection, site not specified"),
    ("J44.1", "Chronic obstructive pulmonary disease with acute exacerbation"),
    ("G43.909", "Migraine, unspecified, not intractable"),
]

MEDICATIONS = [
    ("Amoxicillin", "500mg"),
    ("Lisinopril", "10mg"),
    ("Metformin", "850mg"),
    ("Omeprazole", "20mg"),
    ("Atorvastatin", "40mg"),
    ("Amlodipine", "5mg"),
    ("Metoprolol", "25mg"),
    ("Sertraline", "50mg"),
    ("Albuterol", "90mcg"),
    ("Prednisone", "10mg"),
    ("Levothyroxine", "50mcg"),
    ("Gabapentin", "300mg"),
]

INSURANCE_PREFIXES = ["BCB", "UHC", "AET", "CIG", "HUM", "KAI", "ANT", "MOL"]

LAB_TESTS = [
    ("HbA1c", "{:.1f}", "%", 4.0, 14.0),
    ("Glucose", "{:.0f}", "mg/dL", 60, 400),
    ("WBC", "{:.1f}", "x10^3/uL", 2.0, 20.0),
    ("Hemoglobin", "{:.1f}", "g/dL", 7.0, 18.0),
    ("Creatinine", "{:.2f}", "mg/dL", 0.5, 5.0),
    ("Potassium", "{:.1f}", "mEq/L", 2.5, 6.5),
    ("TSH", "{:.2f}", "mIU/L", 0.1, 10.0),
    ("Cholesterol", "{:.0f}", "mg/dL", 120, 350),
]


def _gen_ssn() -> str:
    area = random.randint(100, 899)
    group = random.randint(1, 99)
    serial = random.randint(1, 9999)
    return f"{area:03d}-{group:02d}-{serial:04d}"


def _gen_name() -> str:
    return fake.name()


def _gen_email() -> str:
    return fake.email()


def _gen_phone() -> str:
    return fake.phone_number()


def _gen_address() -> str:
    return fake.address().replace("\n", ", ")


def _gen_dob() -> str:
    return fake.date_of_birth(minimum_age=18, maximum_age=90).strftime("%m/%d/%Y")


def _gen_drivers_license() -> str:
    state = fake.state_abbr()
    num = "".join(random.choices(string.digits, k=8))
    return f"{state}-{num}"


def _gen_credit_card() -> str:
    return fake.credit_card_number()


def _gen_mrn() -> str:
    num = random.randint(0, 999999)
    return f"MRN-{num:06d}"


def _gen_diagnosis() -> str:
    code, desc = random.choice(ICD10_CODES)
    return f"{code} - {desc}"


def _gen_medication() -> str:
    drug, dose = random.choice(MEDICATIONS)
    return f"{drug} {dose}"


def _gen_provider() -> str:
    return f"Dr. {fake.first_name()} {fake.last_name()}"


def _gen_insurance_id() -> str:
    prefix = random.choice(INSURANCE_PREFIXES)
    num = random.randint(1000000, 9999999)
    return f"{prefix}-{num}"


def _gen_admission_date() -> str:
    return fake.date_between(start_date="-2y", end_date="today").strftime("%m/%d/%Y")


def _gen_lab_result() -> str:
    test_name, fmt, unit, low, high = random.choice(LAB_TESTS)
    value = random.uniform(low, high)
    return f"{test_name} {fmt.format(value)} {unit}"


GENERATOR_REGISTRY: dict[str, callable] = {
    # PII
    "ssn": _gen_ssn,
    "name": _gen_name,
    "email": _gen_email,
    "phone": _gen_phone,
    "address": _gen_address,
    "dob": _gen_dob,
    "drivers_license": _gen_drivers_license,
    "credit_card": _gen_credit_card,
    # PHI
    "mrn": _gen_mrn,
    "diagnosis": _gen_diagnosis,
    "medication": _gen_medication,
    "provider": _gen_provider,
    "insurance_id": _gen_insurance_id,
    "admission_date": _gen_admission_date,
    "lab_result": _gen_lab_result,
}


def generate_value(gen_type: str) -> str:
    """Generate a single random value for the given type."""
    if gen_type not in GENERATOR_REGISTRY:
        raise ValueError(f"Unknown generator type: {gen_type}")
    return GENERATOR_REGISTRY[gen_type]()


def generate_all(gen_types: list[str]) -> dict[str, str]:
    """Generate one random value for each requested type."""
    return {t: generate_value(t) for t in gen_types}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/michaelmulkey/Documents/Repositories/Tput && python -m pytest tests/test_generators.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/generators.py tests/test_generators.py
git commit -m "feat: add PII/PHI random data generators"
```

---

### Task 3: Prompt Builder

**Files:**
- Create: `app/prompt_builder.py`
- Create: `tests/test_prompt_builder.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_prompt_builder.py`:

```python
import re
import json
from app.prompt_builder import render_prompt, build_request_body


class TestRenderPrompt:
    def test_no_placeholders_returns_same_text(self):
        text = "Hello, can you help me with something?"
        result = render_prompt(text, [])
        assert result == text

    def test_placeholders_get_replaced(self):
        text = "My name is {name} and SSN is {ssn}"
        result = render_prompt(text, ["name", "ssn"])
        assert "{name}" not in result
        assert "{ssn}" not in result
        # SSN pattern should appear
        assert re.search(r"\d{3}-\d{2}-\d{4}", result)

    def test_unknown_placeholder_left_as_is(self):
        text = "Value is {unknown_thing}"
        result = render_prompt(text, [])
        assert "{unknown_thing}" in result

    def test_multiple_calls_produce_different_data(self):
        text = "SSN: {ssn}"
        results = [render_prompt(text, ["ssn"]) for _ in range(20)]
        assert len(set(results)) > 1


class TestBuildRequestBody:
    def test_text_only_request(self):
        body = build_request_body("What is the weather?", image_base64=None)
        assert body["request"]["model"] == "gpt-4"
        msg = body["request"]["messages"][0]
        assert msg["role"] == "user"
        assert msg["content"] == "What is the weather?"

    def test_image_request_uses_content_array(self):
        body = build_request_body(
            "Describe this image",
            image_base64="data:image/png;base64,abc123"
        )
        msg = body["request"]["messages"][0]
        assert isinstance(msg["content"], list)
        assert len(msg["content"]) == 2
        assert msg["content"][0]["type"] == "text"
        assert msg["content"][0]["text"] == "Describe this image"
        assert msg["content"][1]["type"] == "image_url"
        assert msg["content"][1]["image_url"]["url"] == "data:image/png;base64,abc123"

    def test_body_is_json_serializable(self):
        body = build_request_body("test", image_base64=None)
        json.dumps(body)  # Should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/michaelmulkey/Documents/Repositories/Tput && python -m pytest tests/test_prompt_builder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.prompt_builder'`

- [ ] **Step 3: Implement prompt_builder.py**

Create `app/prompt_builder.py`:

```python
from app.generators import generate_all


def render_prompt(template: str, generators: list[str]) -> str:
    """Replace {placeholder} tags in template with generated values.

    Only placeholders matching names in `generators` are replaced.
    Unknown placeholders are left as-is.
    """
    if not generators:
        return template

    values = generate_all(generators)
    result = template
    for key, val in values.items():
        result = result.replace("{" + key + "}", val)
    return result


def build_request_body(
    text: str,
    image_base64: str | None = None,
) -> dict:
    """Build a RAMPART-compatible evaluate request body."""
    if image_base64:
        content = [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": image_base64}},
        ]
    else:
        content = text

    return {
        "request": {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": content}
            ],
        }
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/michaelmulkey/Documents/Repositories/Tput && python -m pytest tests/test_prompt_builder.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/prompt_builder.py tests/test_prompt_builder.py
git commit -m "feat: add prompt builder with template rendering and image support"
```

---

### Task 4: Benchmark Engine

**Files:**
- Create: `app/benchmark.py`
- Create: `tests/test_benchmark.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_benchmark.py`:

```python
import asyncio
import json
import pytest
from unittest.mock import AsyncMock
from app.benchmark import BenchmarkConfig, BenchmarkEngine, LevelResult, classify_error


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
        json.dumps(result.to_dict())  # Should not raise


class TestBenchmarkEngine:
    @pytest.mark.asyncio
    async def test_engine_stops_when_threshold_exceeded(self):
        """Mock the HTTP calls so the engine runs through its logic."""
        call_count = 0

        async def mock_send(client, url, headers, body):
            nonlocal call_count
            call_count += 1
            # Simulate increasing latency per concurrency level
            # Level 1 (conc=1): ~0.1s, Level 2 (conc=2): ~2.5s
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

        # Should have stopped after threshold exceeded
        assert len(results) >= 2
        assert results[-1].threshold_exceeded is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/michaelmulkey/Documents/Repositories/Tput && python -m pytest tests/test_benchmark.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.benchmark'`

- [ ] **Step 3: Implement benchmark.py**

Create `app/benchmark.py`:

```python
import asyncio
import time
from dataclasses import dataclass, field
from typing import AsyncIterator

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
    """Classify an exception into an error type string."""
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
    errors_by_type: dict[str, int]
    total_requests: int
    violations_by_policy: dict[str, int]
    threshold_exceeded: bool

    @staticmethod
    def from_latencies(
        level: int,
        concurrency: int,
        latencies: list[float],
        violations_by_policy: dict[str, int],
        errors_by_type: dict[str, int],
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

    async def _send_single_request(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict,
        body: dict,
    ) -> tuple[float, int, str, dict]:
        """Send one request, return (latency, status_code, decision, violations_dict).

        This method can be replaced in tests with a mock.
        """
        start = time.monotonic()
        resp = await client.post(url, json=body, headers=headers, timeout=30.0)
        latency = time.monotonic() - start
        status = resp.status_code

        decision = "unknown"
        violations = {}
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
        generators: list[str],
        image_base64: str | None,
    ) -> AsyncIterator[LevelResult]:
        """Run the benchmark, yielding a LevelResult after each concurrency level."""
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
                latencies: list[float] = []
                violations_agg: dict[str, int] = {}
                errors_by_type: dict[str, int] = {}
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
                            # 200 or 400 (policy block) are both "successful" evaluations
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/michaelmulkey/Documents/Repositories/Tput && python -m pytest tests/test_benchmark.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/benchmark.py tests/test_benchmark.py
git commit -m "feat: add benchmark engine with async concurrency ramp"
```

---

### Task 5: PDF Report Generation

**Files:**
- Create: `app/report.py`
- Create: `tests/test_report.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_report.py`:

```python
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
        assert "6" in html  # max safe concurrency value
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/michaelmulkey/Documents/Repositories/Tput && python -m pytest tests/test_report.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.report'`

- [ ] **Step 3: Implement report.py**

Create `app/report.py`:

```python
from datetime import datetime, timezone
from jinja2 import Template
from weasyprint import HTML

from app.benchmark import LevelResult

REPORT_TEMPLATE = Template("""
<!DOCTYPE html>
<html>
<head>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Helvetica Neue', Arial, sans-serif;
    background: #0f1219;
    color: #e2e8f0;
    padding: 40px;
    font-size: 12px;
  }
  h1 { color: #38bdf8; font-size: 24px; margin-bottom: 4px; }
  h2 { color: #38bdf8; font-size: 16px; margin: 24px 0 12px; text-transform: uppercase; letter-spacing: 0.5px; }
  .subtitle { color: #64748b; font-size: 11px; margin-bottom: 20px; }
  .summary-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin-bottom: 24px;
  }
  .stat-card {
    background: #131a2b;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 14px;
  }
  .stat-label { color: #64748b; font-size: 9px; text-transform: uppercase; letter-spacing: 0.5px; }
  .stat-value { font-size: 22px; font-weight: 700; margin-top: 4px; }
  .green { color: #4ade80; }
  .amber { color: #fbbf24; }
  .red { color: #f87171; }
  .cyan { color: #38bdf8; }
  table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 16px;
  }
  th {
    text-align: left;
    color: #64748b;
    font-size: 9px;
    text-transform: uppercase;
    padding: 6px 8px;
    border-bottom: 1px solid #1e293b;
  }
  td {
    padding: 6px 8px;
    border-bottom: 1px solid #1e293b;
    color: #cbd5e1;
  }
  .chart-container {
    background: #131a2b;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 16px;
  }
  .bar-chart {
    display: flex;
    align-items: flex-end;
    gap: 4px;
    height: 120px;
    padding-top: 8px;
  }
  .bar-wrapper {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    height: 100%;
    justify-content: flex-end;
  }
  .bar {
    width: 80%;
    border-radius: 3px 3px 0 0;
    min-height: 2px;
  }
  .bar-label {
    color: #64748b;
    font-size: 8px;
    margin-top: 4px;
    text-align: center;
  }
  .violation-row {
    display: flex;
    justify-content: space-between;
    margin-bottom: 4px;
  }
  .violation-bar-bg {
    background: #1e293b;
    border-radius: 3px;
    height: 6px;
    margin-bottom: 8px;
  }
  .violation-bar-fill {
    height: 100%;
    border-radius: 3px;
  }
  .config-block {
    background: #131a2b;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 14px;
    font-family: monospace;
    font-size: 11px;
    color: #94a3b8;
    white-space: pre-wrap;
  }
  @page { size: A4; margin: 20mm; }
</style>
</head>
<body>

<h1>Tput Benchmark Report</h1>
<div class="subtitle">{{ timestamp }} &mdash; {{ endpoint }}</div>

<h2>Summary</h2>
<div class="summary-grid">
  <div class="stat-card">
    <div class="stat-label">Max Safe Concurrency</div>
    <div class="stat-value green">{{ max_safe_concurrency }}</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Total Requests</div>
    <div class="stat-value cyan">{{ total_requests }}</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Total Errors</div>
    <div class="stat-value {% if total_errors > 0 %}red{% else %}green{% endif %}">{{ total_errors }}</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Latency Threshold</div>
    <div class="stat-value amber">{{ config.latency_threshold }}s</div>
  </div>
</div>

<h2>Latency vs Concurrency</h2>
<div class="chart-container">
  <div class="bar-chart">
    {% for level in levels %}
    <div class="bar-wrapper">
      <div class="bar" style="height: {{ (level.avg_latency / max_latency * 100) | round }}%;
        background: {% if level.avg_latency > config.latency_threshold %}#f87171{% elif level.avg_latency > config.latency_threshold * 0.5 %}#fbbf24{% else %}#38bdf8{% endif %};"></div>
      <div class="bar-label">{{ level.concurrency }}</div>
    </div>
    {% endfor %}
  </div>
</div>

<h2>Latency Percentiles</h2>
<table>
  <thead>
    <tr><th>Level</th><th>Concurrency</th><th>P50</th><th>P95</th><th>P99</th><th>Avg</th><th>RPS</th><th>Errors</th></tr>
  </thead>
  <tbody>
    {% for level in levels %}
    <tr>
      <td>{{ level.level }}</td>
      <td>{{ level.concurrency }}</td>
      <td>{{ "%.3f" | format(level.p50) }}s</td>
      <td>{{ "%.3f" | format(level.p95) }}s</td>
      <td>{{ "%.3f" | format(level.p99) }}s</td>
      <td style="color: {% if level.avg_latency > config.latency_threshold %}#f87171{% elif level.avg_latency > config.latency_threshold * 0.5 %}#fbbf24{% else %}#4ade80{% endif %}">{{ "%.3f" | format(level.avg_latency) }}s</td>
      <td>{{ "%.1f" | format(level.rps) }}</td>
      <td>{{ level.error_count }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

{% if all_violations %}
<h2>Policy Violations</h2>
{% for policy_id, count in all_violations.items() %}
<div class="violation-row">
  <span>{{ policy_id }}</span>
  <span style="color: {% if count > 0 %}#f87171{% else %}#4ade80{% endif %}">{{ count }}</span>
</div>
<div class="violation-bar-bg">
  <div class="violation-bar-fill" style="width: {{ (count / total_requests * 100) | round }}%; background: {% if count > 0 %}#f87171{% else %}#4ade80{% endif %};"></div>
</div>
{% endfor %}
{% endif %}

{% if all_errors %}
<h2>Errors by Type</h2>
<table>
  <thead><tr><th>Type</th><th>Count</th></tr></thead>
  <tbody>
    {% for etype, count in all_errors.items() %}
    <tr><td>{{ etype }}</td><td style="color: #f87171;">{{ count }}</td></tr>
    {% endfor %}
  </tbody>
</table>
{% endif %}

<h2>Configuration</h2>
<div class="config-block">Endpoint: {{ endpoint }}
Step Size: {{ config.step_size }}
Requests per Level: {{ config.requests_per_level }}
Latency Threshold: {{ config.latency_threshold }}s
Prompt Template: {{ prompt_template }}
Generators: {{ generators | join(", ") if generators else "None" }}</div>

</body>
</html>
""")


def render_report_html(
    endpoint: str,
    config: dict,
    levels: list[LevelResult],
    max_safe_concurrency: int,
    total_requests: int,
    total_errors: int,
    prompt_template: str,
    generators: list[str],
) -> str:
    """Render the benchmark report as an HTML string."""
    # Aggregate violations and errors across all levels
    all_violations: dict[str, int] = {}
    all_errors: dict[str, int] = {}
    for lvl in levels:
        for pid, cnt in lvl.violations_by_policy.items():
            all_violations[pid] = all_violations.get(pid, 0) + cnt
        for etype, cnt in lvl.errors_by_type.items():
            all_errors[etype] = all_errors.get(etype, 0) + cnt

    max_latency = max((lvl.avg_latency for lvl in levels), default=1.0)
    if max_latency == 0:
        max_latency = 1.0

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    return REPORT_TEMPLATE.render(
        timestamp=timestamp,
        endpoint=endpoint,
        config=config,
        levels=levels,
        max_safe_concurrency=max_safe_concurrency,
        total_requests=total_requests,
        total_errors=total_errors,
        max_latency=max_latency,
        all_violations=all_violations,
        all_errors=all_errors,
        prompt_template=prompt_template,
        generators=generators,
    )


def generate_pdf(
    endpoint: str,
    config: dict,
    levels: list[LevelResult],
    max_safe_concurrency: int,
    total_requests: int,
    total_errors: int,
    prompt_template: str,
    generators: list[str],
) -> bytes:
    """Generate a PDF report and return it as bytes."""
    html_str = render_report_html(
        endpoint=endpoint,
        config=config,
        levels=levels,
        max_safe_concurrency=max_safe_concurrency,
        total_requests=total_requests,
        total_errors=total_errors,
        prompt_template=prompt_template,
        generators=generators,
    )
    return HTML(string=html_str).write_pdf()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/michaelmulkey/Documents/Repositories/Tput && python -m pytest tests/test_report.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/report.py tests/test_report.py
git commit -m "feat: add PDF report generation with dark theme"
```

---

### Task 6: Dark Theme CSS

**Files:**
- Create: `app/static/style.css`

- [ ] **Step 1: Create the static directory**

Run: `mkdir -p /Users/michaelmulkey/Documents/Repositories/Tput/app/static`

- [ ] **Step 2: Write style.css**

Create `app/static/style.css`:

```css
/* === Reset & Base === */
*, *::before, *::after {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  --bg-main: #0f1219;
  --bg-panel: #131a2b;
  --bg-input: #1e293b;
  --border: #334155;
  --border-subtle: #1e293b;
  --accent: #38bdf8;
  --accent-hover: #0ea5e9;
  --success: #4ade80;
  --warning: #fbbf24;
  --error: #f87171;
  --purple: #c084fc;
  --text-primary: #e2e8f0;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;

  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  font-size: 13px;
  color: var(--text-primary);
}

body {
  background: var(--bg-main);
  height: 100vh;
  overflow: hidden;
}

/* === Layout === */
.app {
  display: flex;
  height: 100vh;
}

.left-panel {
  width: 38%;
  min-width: 340px;
  max-width: 480px;
  background: var(--bg-panel);
  border-right: 1px solid var(--border-subtle);
  padding: 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.right-panel {
  flex: 1;
  background: var(--bg-main);
  padding: 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* === Section Headers === */
.section-label {
  color: var(--accent);
  font-weight: 700;
  font-size: 11px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  margin-bottom: 8px;
}

/* === Inputs === */
label {
  display: block;
  color: var(--text-muted);
  font-size: 10px;
  margin-bottom: 3px;
}

input[type="text"],
input[type="number"],
input[type="password"],
textarea {
  width: 100%;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 10px;
  color: var(--text-primary);
  font-family: inherit;
  font-size: 12px;
  outline: none;
  transition: border-color 0.2s;
}

input:focus, textarea:focus {
  border-color: var(--accent);
}

textarea {
  resize: vertical;
  min-height: 80px;
  line-height: 1.5;
}

.input-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.input-row.full {
  grid-template-columns: 1fr;
}

.input-group {
  margin-bottom: 6px;
}

/* === Generator Pills === */
.pill-container {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 8px;
}

.pill {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 4px 10px;
  font-size: 10px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
}

.pill:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.pill.pii { border-color: #334155; }
.pill.pii:hover, .pill.pii.active {
  background: rgba(56, 189, 248, 0.1);
  border-color: var(--accent);
  color: var(--accent);
}

.pill.phi { border-color: #2d5a3e; color: var(--success); }
.pill.phi:hover, .pill.phi.active {
  background: rgba(74, 222, 128, 0.1);
  border-color: var(--success);
  color: var(--success);
}

/* === Image Drop Zone === */
.image-drop {
  margin-top: 8px;
  background: var(--bg-input);
  border: 1px dashed var(--border);
  border-radius: 6px;
  padding: 16px;
  text-align: center;
  color: var(--text-muted);
  font-size: 11px;
  cursor: pointer;
  transition: border-color 0.2s;
}

.image-drop:hover, .image-drop.dragover {
  border-color: var(--accent);
}

.image-drop .icon { font-size: 24px; margin-bottom: 4px; }

.image-preview {
  margin-top: 8px;
  position: relative;
}

.image-preview img {
  max-width: 100%;
  max-height: 120px;
  border-radius: 6px;
  border: 1px solid var(--border);
}

.image-preview .remove-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  background: var(--error);
  color: white;
  border: none;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  cursor: pointer;
  font-size: 12px;
  line-height: 20px;
  text-align: center;
}

/* === Buttons === */
.btn-primary {
  width: 100%;
  background: linear-gradient(135deg, #0ea5e9, #38bdf8);
  border: none;
  border-radius: 8px;
  padding: 12px;
  color: var(--bg-main);
  font-weight: 700;
  font-size: 14px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.btn-primary:hover { opacity: 0.9; }
.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 16px;
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 0.2s;
}

.btn-secondary:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.btn-stop {
  width: 100%;
  background: linear-gradient(135deg, #dc2626, #f87171);
  border: none;
  border-radius: 8px;
  padding: 12px;
  color: white;
  font-weight: 700;
  font-size: 14px;
  cursor: pointer;
}

/* === Status Bar === */
.status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
}

.status-dot.running {
  background: var(--success);
  animation: pulse 1.5s ease-in-out infinite;
}

.status-dot.complete { background: var(--accent); }
.status-dot.error { background: var(--error); }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.status-text {
  font-size: 11px;
  font-weight: 600;
}

.status-text.running { color: var(--success); }
.status-text.idle { color: var(--text-muted); }
.status-text.complete { color: var(--accent); }

.status-detail {
  color: var(--text-muted);
  font-size: 11px;
}

/* === Stat Cards === */
.stat-cards {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
}

.stat-card {
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 12px;
}

.stat-card .label {
  color: var(--text-muted);
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}

.stat-card .value {
  font-size: 22px;
  font-weight: 700;
}

.stat-card .value.green { color: var(--success); }
.stat-card .value.amber { color: var(--warning); }
.stat-card .value.cyan { color: var(--accent); }
.stat-card .value.purple { color: var(--purple); }
.stat-card .value.red { color: var(--error); }

/* === Chart Container === */
.chart-container {
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 16px;
  flex: 1;
  min-height: 200px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.chart-title {
  color: var(--accent);
  font-weight: 700;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.chart-legend {
  display: flex;
  gap: 12px;
  font-size: 9px;
}

.chart-legend span::before {
  content: '';
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 4px;
  vertical-align: middle;
}

.legend-avg::before { background: var(--accent); }
.legend-p95::before { background: var(--warning); }
.legend-p99::before { background: var(--error); }

/* === Bottom Grid === */
.bottom-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

/* === Percentile Table === */
.panel {
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 14px;
}

.panel-title {
  color: var(--accent);
  font-weight: 700;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 10px;
}

.perc-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
}

.perc-table th {
  text-align: right;
  color: var(--text-muted);
  font-size: 9px;
  text-transform: uppercase;
  padding: 4px 6px;
}

.perc-table th:first-child { text-align: left; }

.perc-table td {
  text-align: right;
  padding: 5px 6px;
  border-top: 1px solid var(--border-subtle);
  color: var(--text-secondary);
}

.perc-table td:first-child { text-align: left; }

.perc-table tr.current { background: rgba(30, 41, 59, 0.4); }

/* === Violation Bars === */
.violation-item { margin-bottom: 10px; }

.violation-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
  font-size: 11px;
}

.violation-header .name { color: var(--text-primary); }
.violation-header .count { font-weight: 600; }

.violation-bar {
  background: var(--bg-input);
  border-radius: 3px;
  height: 6px;
}

.violation-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}

/* === Error Log === */
.error-log {
  max-height: 150px;
  overflow-y: auto;
  font-size: 11px;
}

.error-entry {
  display: flex;
  gap: 12px;
  padding: 4px 0;
  border-bottom: 1px solid var(--border-subtle);
  color: var(--text-secondary);
}

.error-entry .timestamp { color: var(--text-muted); min-width: 70px; }
.error-entry .type { color: var(--error); min-width: 100px; }
.error-entry .level { color: var(--text-muted); }

/* === Export Row === */
.export-row {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

/* === Empty State === */
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 300px;
  color: var(--text-muted);
  font-size: 14px;
  flex-direction: column;
  gap: 8px;
}

.empty-state .icon { font-size: 48px; opacity: 0.3; }

/* === Scrollbar === */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
```

- [ ] **Step 3: Commit**

```bash
git add app/static/style.css
git commit -m "feat: add dark theme CSS for split-panel dashboard"
```

---

### Task 7: Frontend HTML

**Files:**
- Create: `app/static/index.html`

- [ ] **Step 1: Write index.html**

Create `app/static/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Tput — RAMPART Benchmark</title>
  <link rel="stylesheet" href="/static/style.css">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
</head>
<body>
<div class="app">

  <!-- LEFT PANEL -->
  <div class="left-panel">

    <!-- Connection -->
    <div>
      <div class="section-label">Connection</div>
      <div class="input-group">
        <label for="endpoint">Endpoint URL</label>
        <input type="text" id="endpoint" placeholder="https://rampart.example.com/v1/rampart/evaluate">
      </div>
      <div class="input-group">
        <label for="apikey">API Key</label>
        <input type="password" id="apikey" placeholder="rmp_live_...">
      </div>
    </div>

    <!-- Benchmark Config -->
    <div>
      <div class="section-label">Benchmark Config</div>
      <div class="input-row">
        <div>
          <label for="start-conc">Start Concurrency</label>
          <input type="number" id="start-conc" value="1" min="1">
        </div>
        <div>
          <label for="step-size">Step Size</label>
          <input type="number" id="step-size" value="5" min="1">
        </div>
      </div>
      <div class="input-row">
        <div>
          <label for="max-conc">Max Concurrency</label>
          <input type="number" id="max-conc" value="200" min="1">
        </div>
        <div>
          <label for="req-per-level">Requests / Level</label>
          <input type="number" id="req-per-level" value="50" min="1">
        </div>
      </div>
      <div class="input-row full">
        <div>
          <label for="threshold">Latency Threshold (seconds)</label>
          <input type="number" id="threshold" value="2.0" min="0.1" step="0.1">
        </div>
      </div>
    </div>

    <!-- Prompt Builder -->
    <div style="flex:1;display:flex;flex-direction:column;">
      <div class="section-label">Prompt Builder</div>

      <div class="pill-container">
        <span class="pill pii" data-gen="ssn">+ SSN</span>
        <span class="pill pii" data-gen="name">+ Name</span>
        <span class="pill pii" data-gen="email">+ Email</span>
        <span class="pill pii" data-gen="phone">+ Phone</span>
        <span class="pill pii" data-gen="address">+ Address</span>
        <span class="pill pii" data-gen="dob">+ DOB</span>
        <span class="pill pii" data-gen="credit_card">+ Credit Card</span>
        <span class="pill phi" data-gen="mrn">+ MRN</span>
        <span class="pill phi" data-gen="diagnosis">+ Diagnosis</span>
        <span class="pill phi" data-gen="medication">+ Medication</span>
        <span class="pill phi" data-gen="provider">+ Provider</span>
        <span class="pill phi" data-gen="insurance_id">+ Insurance</span>
        <span class="pill phi" data-gen="lab_result">+ Lab Result</span>
      </div>

      <textarea id="prompt-text" placeholder="Type your prompt here. Click pills above to insert {placeholders} for auto-generated data."></textarea>

      <div class="image-drop" id="image-drop">
        <div class="icon">&#128444;</div>
        Paste (Ctrl+V) or drag &amp; drop an image
      </div>
      <div class="image-preview" id="image-preview" style="display:none;">
        <img id="preview-img" src="" alt="preview">
        <button class="remove-btn" id="remove-image">&times;</button>
      </div>
    </div>

    <!-- Action Button -->
    <button class="btn-primary" id="start-btn">Start Benchmark</button>
    <button class="btn-stop" id="stop-btn" style="display:none;">Stop Benchmark</button>
  </div>

  <!-- RIGHT PANEL -->
  <div class="right-panel">

    <!-- Status Bar -->
    <div class="status-bar">
      <div class="status-indicator">
        <div class="status-dot" id="status-dot"></div>
        <span class="status-text idle" id="status-text">Ready</span>
      </div>
      <span class="status-detail" id="status-detail"></span>
    </div>

    <!-- Stat Cards -->
    <div class="stat-cards">
      <div class="stat-card">
        <div class="label">Max Safe Concurrency</div>
        <div class="value green" id="stat-max-conc">—</div>
      </div>
      <div class="stat-card">
        <div class="label">Avg Latency</div>
        <div class="value amber" id="stat-avg-lat">—</div>
      </div>
      <div class="stat-card">
        <div class="label">Success Rate</div>
        <div class="value cyan" id="stat-success">—</div>
      </div>
      <div class="stat-card">
        <div class="label">Throughput</div>
        <div class="value purple" id="stat-rps">—</div>
      </div>
      <div class="stat-card">
        <div class="label">Error Rate</div>
        <div class="value red" id="stat-errors">—</div>
      </div>
    </div>

    <!-- Chart -->
    <div class="chart-container">
      <div class="chart-header">
        <span class="chart-title">Latency vs Concurrency</span>
        <div class="chart-legend">
          <span class="legend-avg">Avg</span>
          <span class="legend-p95">p95</span>
          <span class="legend-p99">p99</span>
        </div>
      </div>
      <canvas id="latency-chart"></canvas>
    </div>

    <!-- Bottom Grid -->
    <div class="bottom-grid">
      <!-- Percentile Table -->
      <div class="panel">
        <div class="panel-title">Latency Percentiles</div>
        <table class="perc-table">
          <thead>
            <tr><th>Level</th><th>p50</th><th>p95</th><th>p99</th><th>Avg</th></tr>
          </thead>
          <tbody id="perc-tbody"></tbody>
        </table>
      </div>

      <!-- Violations + Errors -->
      <div class="panel">
        <div class="panel-title">Policy Violations</div>
        <div id="violations-container"></div>
        <div class="panel-title" style="margin-top:14px;">Error Log</div>
        <div class="error-log" id="error-log">
          <div style="color:var(--text-muted);font-size:11px;">No errors</div>
        </div>
      </div>
    </div>

    <!-- Export -->
    <div class="export-row">
      <button class="btn-secondary" id="export-btn" disabled>Export PDF Report</button>
    </div>
  </div>

</div>
<script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add app/static/index.html
git commit -m "feat: add split-panel HTML layout for benchmark dashboard"
```

---

### Task 8: Frontend JavaScript

**Files:**
- Create: `app/static/app.js`

- [ ] **Step 1: Write app.js**

Create `app/static/app.js`:

```javascript
(function () {
  "use strict";

  // --- State ---
  let ws = null;
  let running = false;
  let imageBase64 = null;
  let allLevels = [];
  let maxSafeConcurrency = null;
  let latencyChart = null;
  const threshold = () => parseFloat(document.getElementById("threshold").value) || 2.0;

  // --- DOM refs ---
  const $ = (id) => document.getElementById(id);
  const startBtn = $("start-btn");
  const stopBtn = $("stop-btn");
  const statusDot = $("status-dot");
  const statusText = $("status-text");
  const statusDetail = $("status-detail");
  const exportBtn = $("export-btn");
  const promptText = $("prompt-text");
  const imageDrop = $("image-drop");
  const imagePreview = $("image-preview");
  const previewImg = $("preview-img");
  const removeImageBtn = $("remove-image");

  // --- Chart Setup ---
  function initChart() {
    const ctx = $("latency-chart").getContext("2d");
    latencyChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: [],
        datasets: [
          {
            label: "Avg Latency",
            data: [],
            backgroundColor: [],
            borderRadius: 3,
            order: 2,
          },
          {
            label: "p95",
            data: [],
            type: "line",
            borderColor: "#fbbf24",
            backgroundColor: "transparent",
            pointRadius: 3,
            pointBackgroundColor: "#fbbf24",
            borderWidth: 2,
            order: 1,
          },
          {
            label: "p99",
            data: [],
            type: "line",
            borderColor: "#f87171",
            backgroundColor: "transparent",
            pointRadius: 3,
            pointBackgroundColor: "#f87171",
            borderWidth: 2,
            order: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 300 },
        scales: {
          x: {
            ticks: { color: "#64748b", font: { size: 10 } },
            grid: { color: "#1e293b" },
            title: { display: true, text: "Concurrency", color: "#64748b" },
          },
          y: {
            ticks: { color: "#64748b", font: { size: 10 }, callback: (v) => v + "s" },
            grid: { color: "#1e293b" },
            title: { display: true, text: "Latency (s)", color: "#64748b" },
          },
        },
        plugins: {
          legend: { display: false },
          annotation: {
            annotations: {
              thresholdLine: {
                type: "line",
                yMin: threshold(),
                yMax: threshold(),
                borderColor: "#f8717188",
                borderWidth: 2,
                borderDash: [6, 4],
                label: {
                  display: true,
                  content: threshold() + "s threshold",
                  position: "end",
                  color: "#f87171",
                  font: { size: 9 },
                  backgroundColor: "transparent",
                },
              },
            },
          },
        },
      },
      plugins: [
        {
          id: "thresholdLine",
          beforeDraw(chart) {
            const yScale = chart.scales.y;
            const th = threshold();
            const y = yScale.getPixelForValue(th);
            if (y == null) return;
            const ctx = chart.ctx;
            ctx.save();
            ctx.strokeStyle = "#f8717188";
            ctx.lineWidth = 2;
            ctx.setLineDash([6, 4]);
            ctx.beginPath();
            ctx.moveTo(chart.chartArea.left, y);
            ctx.lineTo(chart.chartArea.right, y);
            ctx.stroke();
            ctx.restore();

            ctx.save();
            ctx.fillStyle = "#f87171";
            ctx.font = "9px Inter, system-ui, sans-serif";
            ctx.fillText(th + "s threshold", chart.chartArea.right - 70, y - 5);
            ctx.restore();
          },
        },
      ],
    });
  }

  function barColor(avgLat) {
    const th = threshold();
    if (avgLat > th) return "#f87171";
    if (avgLat > th * 0.5) return "#fbbf24";
    return "#38bdf8";
  }

  function addChartPoint(level) {
    latencyChart.data.labels.push(level.concurrency.toString());
    latencyChart.data.datasets[0].data.push(level.avg_latency);
    latencyChart.data.datasets[0].backgroundColor.push(barColor(level.avg_latency));
    latencyChart.data.datasets[1].data.push(level.p95);
    latencyChart.data.datasets[2].data.push(level.p99);
    latencyChart.update();
  }

  // --- Stat Cards ---
  function updateStats(level) {
    $("stat-avg-lat").textContent = level.avg_latency.toFixed(3) + "s";
    $("stat-success").textContent = level.success_rate.toFixed(1) + "%";
    $("stat-rps").textContent = level.rps.toFixed(1) + "/s";
    $("stat-errors").textContent = level.error_rate.toFixed(1) + "%";

    if (!level.threshold_exceeded) {
      maxSafeConcurrency = level.concurrency;
    }
    $("stat-max-conc").textContent = maxSafeConcurrency != null ? maxSafeConcurrency : "—";
  }

  // --- Percentile Table ---
  function addPercRow(level) {
    const tbody = $("perc-tbody");
    // Remove "current" from previous rows
    tbody.querySelectorAll("tr.current").forEach((r) => r.classList.remove("current"));

    const tr = document.createElement("tr");
    tr.className = "current";

    function latColor(val) {
      const th = threshold();
      if (val > th) return "color:#f87171";
      if (val > th * 0.5) return "color:#fbbf24";
      return "color:#4ade80";
    }

    tr.innerHTML = `
      <td>${level.concurrency}</td>
      <td style="${latColor(level.p50)}">${level.p50.toFixed(3)}s</td>
      <td style="${latColor(level.p95)}">${level.p95.toFixed(3)}s</td>
      <td style="${latColor(level.p99)}">${level.p99.toFixed(3)}s</td>
      <td style="${latColor(level.avg_latency)};font-weight:600">${level.avg_latency.toFixed(3)}s</td>
    `;
    tbody.appendChild(tr);
    tr.scrollIntoView({ block: "nearest" });
  }

  // --- Violations ---
  const cumulativeViolations = {};

  function updateViolations(level) {
    for (const [pid, cnt] of Object.entries(level.violations_by_policy)) {
      cumulativeViolations[pid] = (cumulativeViolations[pid] || 0) + cnt;
    }
    const container = $("violations-container");
    container.innerHTML = "";

    const totalReqs = allLevels.reduce((s, l) => s + l.total_requests, 0);

    for (const [pid, cnt] of Object.entries(cumulativeViolations)) {
      const pct = totalReqs > 0 ? (cnt / totalReqs) * 100 : 0;
      const color = cnt > 0 ? "#f87171" : "#4ade80";
      container.innerHTML += `
        <div class="violation-item">
          <div class="violation-header">
            <span class="name">${pid}</span>
            <span class="count" style="color:${color}">${cnt} / ${totalReqs}</span>
          </div>
          <div class="violation-bar">
            <div class="violation-bar-fill" style="width:${Math.min(pct, 100)}%;background:${color}"></div>
          </div>
        </div>
      `;
    }
  }

  // --- Error Log ---
  let hasErrors = false;

  function addErrors(level) {
    if (level.error_count === 0) return;
    if (!hasErrors) {
      $("error-log").innerHTML = "";
      hasErrors = true;
    }
    const log = $("error-log");
    for (const [etype, cnt] of Object.entries(level.errors_by_type)) {
      for (let i = 0; i < cnt; i++) {
        const entry = document.createElement("div");
        entry.className = "error-entry";
        entry.innerHTML = `
          <span class="timestamp">${new Date().toLocaleTimeString()}</span>
          <span class="type">${etype}</span>
          <span class="level">@ concurrency ${level.concurrency}</span>
        `;
        log.appendChild(entry);
      }
    }
    log.scrollTop = log.scrollHeight;
  }

  // --- Status ---
  function setStatus(state, text, detail) {
    statusDot.className = "status-dot " + state;
    statusText.className = "status-text " + state;
    statusText.textContent = text;
    statusDetail.textContent = detail || "";
  }

  // --- Pills ---
  document.querySelectorAll(".pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      const gen = pill.dataset.gen;
      const placeholder = "{" + gen + "}";
      const ta = promptText;
      const start = ta.selectionStart;
      const end = ta.selectionEnd;
      ta.value = ta.value.substring(0, start) + placeholder + ta.value.substring(end);
      ta.focus();
      ta.selectionStart = ta.selectionEnd = start + placeholder.length;
      pill.classList.toggle("active");
    });
  });

  // --- Image Handling ---
  function handleImage(file) {
    if (!file || !file.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      imageBase64 = e.target.result;
      previewImg.src = imageBase64;
      imagePreview.style.display = "block";
      imageDrop.style.display = "none";
    };
    reader.readAsDataURL(file);
  }

  imageDrop.addEventListener("dragover", (e) => {
    e.preventDefault();
    imageDrop.classList.add("dragover");
  });
  imageDrop.addEventListener("dragleave", () => imageDrop.classList.remove("dragover"));
  imageDrop.addEventListener("drop", (e) => {
    e.preventDefault();
    imageDrop.classList.remove("dragover");
    if (e.dataTransfer.files.length) handleImage(e.dataTransfer.files[0]);
  });
  imageDrop.addEventListener("click", () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*";
    input.onchange = () => { if (input.files.length) handleImage(input.files[0]); };
    input.click();
  });

  document.addEventListener("paste", (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
      if (item.type.startsWith("image/")) {
        handleImage(item.getAsFile());
        break;
      }
    }
  });

  removeImageBtn.addEventListener("click", () => {
    imageBase64 = null;
    imagePreview.style.display = "none";
    imageDrop.style.display = "";
  });

  // --- Collect active generators from prompt text ---
  function detectGenerators() {
    const text = promptText.value;
    const allGens = [
      "ssn", "name", "email", "phone", "address", "dob", "credit_card",
      "mrn", "diagnosis", "medication", "provider", "insurance_id", "lab_result",
    ];
    return allGens.filter((g) => text.includes("{" + g + "}"));
  }

  // --- WebSocket Benchmark ---
  function resetDashboard() {
    allLevels = [];
    maxSafeConcurrency = null;
    Object.keys(cumulativeViolations).forEach((k) => delete cumulativeViolations[k]);
    hasErrors = false;

    $("stat-max-conc").textContent = "—";
    $("stat-avg-lat").textContent = "—";
    $("stat-success").textContent = "—";
    $("stat-rps").textContent = "—";
    $("stat-errors").textContent = "—";
    $("perc-tbody").innerHTML = "";
    $("violations-container").innerHTML = "";
    $("error-log").innerHTML = '<div style="color:var(--text-muted);font-size:11px;">No errors</div>';
    exportBtn.disabled = true;

    if (latencyChart) latencyChart.destroy();
    initChart();
  }

  startBtn.addEventListener("click", () => {
    const endpoint = $("endpoint").value.trim();
    const apiKey = $("apikey").value.trim();
    if (!endpoint || !apiKey) {
      alert("Please enter endpoint URL and API key.");
      return;
    }
    if (!promptText.value.trim()) {
      alert("Please enter a prompt.");
      return;
    }

    resetDashboard();
    running = true;
    startBtn.style.display = "none";
    stopBtn.style.display = "";
    setStatus("running", "RUNNING", "Starting...");

    // Disable config inputs
    document.querySelectorAll(".left-panel input, .left-panel textarea").forEach((el) => el.disabled = true);

    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${proto}//${location.host}/ws/benchmark`);

    ws.onopen = () => {
      const msg = {
        action: "start",
        config: {
          endpoint,
          api_key: apiKey,
          start_concurrency: parseInt($("start-conc").value) || 1,
          step_size: parseInt($("step-size").value) || 5,
          max_concurrency: parseInt($("max-conc").value) || 200,
          requests_per_level: parseInt($("req-per-level").value) || 50,
          latency_threshold: parseFloat($("threshold").value) || 2.0,
        },
        prompt: {
          text: promptText.value,
          image_base64: imageBase64,
          generators: detectGenerators(),
        },
      };
      ws.send(JSON.stringify(msg));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === "level_result") {
        allLevels.push(data);
        setStatus("running", `RUNNING — Level ${data.level}`, `Concurrency: ${data.concurrency}`);
        addChartPoint(data);
        updateStats(data);
        addPercRow(data);
        updateViolations(data);
        addErrors(data);
      } else if (data.type === "complete") {
        running = false;
        maxSafeConcurrency = data.max_safe_concurrency;
        $("stat-max-conc").textContent = maxSafeConcurrency;
        setStatus("complete", "COMPLETE", `Max safe concurrency: ${maxSafeConcurrency}`);
        stopBtn.style.display = "none";
        startBtn.style.display = "";
        exportBtn.disabled = false;
        document.querySelectorAll(".left-panel input, .left-panel textarea").forEach((el) => el.disabled = false);
      } else if (data.type === "error") {
        setStatus("error", "ERROR", data.message);
        running = false;
        stopBtn.style.display = "none";
        startBtn.style.display = "";
        document.querySelectorAll(".left-panel input, .left-panel textarea").forEach((el) => el.disabled = false);
      }
    };

    ws.onclose = () => {
      if (running) {
        setStatus("error", "DISCONNECTED", "WebSocket connection closed");
        running = false;
        stopBtn.style.display = "none";
        startBtn.style.display = "";
        document.querySelectorAll(".left-panel input, .left-panel textarea").forEach((el) => el.disabled = false);
      }
    };
  });

  stopBtn.addEventListener("click", () => {
    if (ws) ws.close();
    running = false;
    setStatus("idle", "STOPPED", "Benchmark stopped by user");
    stopBtn.style.display = "none";
    startBtn.style.display = "";
    exportBtn.disabled = allLevels.length === 0;
    document.querySelectorAll(".left-panel input, .left-panel textarea").forEach((el) => el.disabled = false);
  });

  // --- PDF Export ---
  exportBtn.addEventListener("click", async () => {
    exportBtn.disabled = true;
    exportBtn.textContent = "Generating...";
    try {
      const resp = await fetch("/api/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          endpoint: $("endpoint").value,
          config: {
            step_size: parseInt($("step-size").value) || 5,
            requests_per_level: parseInt($("req-per-level").value) || 50,
            latency_threshold: parseFloat($("threshold").value) || 2.0,
          },
          levels: allLevels,
          max_safe_concurrency: maxSafeConcurrency,
          total_requests: allLevels.reduce((s, l) => s + l.total_requests, 0),
          total_errors: allLevels.reduce((s, l) => s + l.error_count, 0),
          prompt_template: promptText.value,
          generators: detectGenerators(),
        }),
      });
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `tput-report-${new Date().toISOString().slice(0, 19).replace(/:/g, "-")}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert("Failed to generate PDF: " + e.message);
    } finally {
      exportBtn.disabled = false;
      exportBtn.textContent = "Export PDF Report";
    }
  });

  // --- Init ---
  initChart();
})();
```

- [ ] **Step 2: Commit**

```bash
git add app/static/app.js
git commit -m "feat: add frontend JS with Chart.js, WebSocket, and interactive dashboard"
```

---

### Task 9: FastAPI Application (main.py)

**Files:**
- Create: `app/main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_main.py`:

```python
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
        })
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:5] == b"%PDF-"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/michaelmulkey/Documents/Repositories/Tput && python -m pytest tests/test_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: Implement main.py**

Create `app/main.py`:

```python
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.benchmark import BenchmarkConfig, BenchmarkEngine, LevelResult
from app.generators import generate_all
from app.report import generate_pdf

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Tput — RAMPART Benchmark")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


class GenerateRequest(BaseModel):
    generators: list[str]


@app.post("/api/generate-data")
async def generate_data(req: GenerateRequest):
    return generate_all(req.generators)


class ReportRequest(BaseModel):
    endpoint: str
    config: dict
    levels: list[dict]
    max_safe_concurrency: int
    total_requests: int
    total_errors: int
    prompt_template: str
    generators: list[str]


@app.post("/api/report")
async def export_report(req: ReportRequest):
    level_objects = []
    for lvl in req.levels:
        level_objects.append(LevelResult(
            level=lvl["level"],
            concurrency=lvl["concurrency"],
            avg_latency=lvl["avg_latency"],
            p50=lvl["p50"],
            p95=lvl["p95"],
            p99=lvl["p99"],
            rps=lvl["rps"],
            success_rate=lvl["success_rate"],
            error_count=lvl["error_count"],
            error_rate=lvl["error_rate"],
            errors_by_type=lvl.get("errors_by_type", {}),
            total_requests=lvl["total_requests"],
            violations_by_policy=lvl.get("violations_by_policy", {}),
            threshold_exceeded=lvl["threshold_exceeded"],
        ))

    pdf_bytes = generate_pdf(
        endpoint=req.endpoint,
        config=req.config,
        levels=level_objects,
        max_safe_concurrency=req.max_safe_concurrency,
        total_requests=req.total_requests,
        total_errors=req.total_errors,
        prompt_template=req.prompt_template,
        generators=req.generators,
    )
    return Response(content=pdf_bytes, media_type="application/pdf")


@app.websocket("/ws/benchmark")
async def benchmark_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        msg = json.loads(raw)

        if msg.get("action") != "start":
            await websocket.send_json({"type": "error", "message": "Unknown action"})
            return

        cfg_data = msg["config"]
        config = BenchmarkConfig(
            endpoint=cfg_data["endpoint"],
            api_key=cfg_data["api_key"],
            start_concurrency=cfg_data.get("start_concurrency", 1),
            step_size=cfg_data.get("step_size", 5),
            max_concurrency=cfg_data.get("max_concurrency", 200),
            requests_per_level=cfg_data.get("requests_per_level", 50),
            latency_threshold=cfg_data.get("latency_threshold", 2.0),
        )

        prompt_data = msg["prompt"]
        prompt_template = prompt_data["text"]
        generators = prompt_data.get("generators", [])
        image_base64 = prompt_data.get("image_base64")

        engine = BenchmarkEngine(config)
        all_levels = []
        max_safe = config.start_concurrency

        async for level_result in engine.run(prompt_template, generators, image_base64):
            all_levels.append(level_result)
            if not level_result.threshold_exceeded:
                max_safe = level_result.concurrency
            await websocket.send_json(level_result.to_dict())

        total_reqs = sum(l.total_requests for l in all_levels)
        total_errs = sum(l.error_count for l in all_levels)

        await websocket.send_json({
            "type": "complete",
            "max_safe_concurrency": max_safe,
            "total_requests": total_reqs,
            "total_errors": total_errs,
        })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/michaelmulkey/Documents/Repositories/Tput && python -m pytest tests/test_main.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_main.py
git commit -m "feat: add FastAPI app with WebSocket benchmark and PDF export endpoints"
```

---

### Task 10: Full Test Suite & Smoke Test

**Files:**
- Modify: existing test files (no new files)

- [ ] **Step 1: Run the entire test suite**

Run: `cd /Users/michaelmulkey/Documents/Repositories/Tput && python -m pytest tests/ -v`
Expected: All tests PASS across all 4 test files.

- [ ] **Step 2: Start the server and verify it loads**

Run: `cd /Users/michaelmulkey/Documents/Repositories/Tput && timeout 5 python -m uvicorn app.main:app --host 127.0.0.1 --port 9090 || true`
Expected: Server starts and shows "Uvicorn running on http://127.0.0.1:9090". The `timeout 5` kills it after 5 seconds — enough to verify it boots.

- [ ] **Step 3: Final commit with all tests passing**

Run: `cd /Users/michaelmulkey/Documents/Repositories/Tput && python -m pytest tests/ -v`
If all pass, no additional commit needed. If any fixes were required, commit them:

```bash
git add -A
git commit -m "fix: resolve issues found during integration testing"
```
