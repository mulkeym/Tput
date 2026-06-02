# Tput

A benchmarking tool with a web GUI for measuring the performance of RAMPART prompt evaluation and OpenAI-compatible LLM endpoints.

![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## What It Does

Tput ramps up concurrent requests linearly and measures when average latency exceeds a configurable threshold, helping you find the maximum safe concurrency for your deployment.

**Two benchmark modes:**

| Mode | Target | Key Metrics |
|------|--------|-------------|
| **RAMPART Evaluate** | `POST /v1/rampart/evaluate` | Latency (p50/p95/p99), RPS, policy violation breakdown, error rate |
| **LLM Direct** | `POST /v1/chat/completions` (streaming) | Latency, TTFT (time to first token), aggregate TPS (tokens/sec), error rate |

**Features:**
- Real-time dashboard with live Chart.js charts and WebSocket streaming
- PII/PHI data generators (SSN, names, emails, MRNs, diagnosis codes, medications, etc.) with per-request unique values
- Custom prompt builder with image paste/upload support
- Auto-discovery of available models from OpenAI-compatible endpoints
- PDF report export with dark-themed charts and tables
- Configurable latency threshold, concurrency step size, and sample rounds

## Quick Start

### Docker (recommended)

```bash
docker compose up --build
```

### Local

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 9090
```

Open [http://localhost:9090](http://localhost:9090).

## Usage

### 1. Choose a mode

Toggle between **RAMPART Evaluate** and **LLM Direct** at the top of the left panel.

### 2. Configure the connection

- **Endpoint URL** - The target endpoint (e.g., `http://192.168.1.181:8000/v1` for an LLM, or `http://localhost:8080/v1/rampart/evaluate` for RAMPART)
- **API Key** - Optional. Only sent if provided.
- **Model** - (LLM mode only) Auto-populated from the endpoint's `/v1/models` response.

### 3. Configure the benchmark

| Parameter | Default | Description |
|-----------|---------|-------------|
| Start Concurrency | 1 | Initial number of simultaneous requests |
| Step Size | 5 | Concurrency increment per level |
| Max Concurrency | 200 | Upper bound for concurrency |
| Rounds / Level | 3 | Number of sample rounds per concurrency level. Each round fires exactly `concurrency` simultaneous requests. Results are averaged across rounds. |
| Latency Threshold | 2.0s | Benchmark stops when average latency exceeds this value |

### 4. Build your prompt

**Custom text:** Type any prompt in the text area.

**Generated data:** Click the PII (blue) or PHI (green) pills to insert placeholder tags. Each concurrent request gets unique randomly generated values:

| PII Generators | PHI Generators |
|---------------|---------------|
| `{ssn}` - Social Security Number | `{mrn}` - Medical Record Number |
| `{name}` - Full name | `{diagnosis}` - ICD-10 code + description |
| `{email}` - Email address | `{medication}` - Drug + dosage |
| `{phone}` - Phone number | `{provider}` - Doctor name |
| `{address}` - Street address | `{insurance_id}` - Insurance ID |
| `{dob}` - Date of birth | `{admission_date}` - Admission date |
| `{credit_card}` - Credit card number | `{lab_result}` - Lab test + value |
| `{drivers_license}` - Driver's license | |

**Images:** Paste (Ctrl+V), drag and drop, or click the drop zone to attach an image.

### 5. Run and analyze

Click **Start Benchmark**. The dashboard updates in real time:

- **Stat cards** - Max safe concurrency, latency/TTFT, success rate, throughput/TPS, error rate
- **Latency chart** - Bar chart with p95/p99 line overlays and threshold marker. In LLM mode, a purple TPS line on the right Y-axis shows aggregate throughput scaling.
- **Percentile table** - Per-level breakdown with color-coded values
- **Policy violations** (RAMPART mode) or **Token performance** (LLM mode)
- **Error log** - Infrastructure errors with concurrency level context

### 6. Export

Click **Export PDF Report** for a formatted dark-themed report with all metrics, charts, and configuration details.

## How Concurrency Works

At each concurrency level, Tput fires `concurrency` requests simultaneously, waits for all to complete, then repeats for the configured number of rounds. This means:

- At concurrency=20 with 3 rounds: 60 total requests (20 x 3), with all 20 truly concurrent within each round
- **Latency** measures individual request time
- **TPS** (LLM mode) measures aggregate throughput: total tokens generated across all concurrent requests / wall clock time

The benchmark stops when average latency exceeds the threshold or max concurrency is reached.

## Error Tracking

Errors are infrastructure failures only. RAMPART returning `decision: "fail"` with policy violations is expected behavior, not an error.

| Error Type | Meaning |
|-----------|---------|
| `timeout` | Request exceeded 30s/60s timeout |
| `connection_error` | Connection refused, DNS failure |
| `http_NNN` | Server returned non-200 status code |

## Project Structure

```
Tput/
├── app/
│   ├── main.py           # FastAPI app, WebSocket, REST endpoints
│   ├── benchmark.py       # Async benchmark engine with concurrency ramp
│   ├── generators.py      # PII/PHI random data generation (Faker)
│   ├── prompt_builder.py  # Template rendering + RAMPART request body builder
│   ├── report.py          # PDF report generation (weasyprint + Jinja2)
│   └── static/
│       ├── index.html     # Split-panel dashboard UI
│       ├── app.js         # Chart.js, WebSocket client, interactive dashboard
│       └── style.css      # Dark theme CSS
├── tests/                 # 53 pytest tests
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Tech Stack

- **Backend:** FastAPI, uvicorn, httpx (async HTTP), websockets
- **Frontend:** Vanilla JS, Chart.js 4 (CDN)
- **Data Generation:** Faker
- **PDF Export:** weasyprint, Jinja2
- **Container:** Docker (python:3.11-slim)

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

## License

MIT
