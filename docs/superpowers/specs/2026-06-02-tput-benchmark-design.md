# Tput — RAMPART Benchmark Tool Design Spec

## Overview

Tput is a Python-based benchmarking tool with a web GUI that measures the maximum concurrency RAMPART can handle before average latency exceeds a configurable threshold (default 2s). It targets the `POST /v1/rampart/evaluate` endpoint.

## Tech Stack

- **Backend:** FastAPI + uvicorn
- **HTTP Client:** httpx (async, connection pooling)
- **Real-time:** WebSocket (FastAPI native)
- **Frontend:** Vanilla HTML/JS + Chart.js (CDN)
- **PDF Export:** weasyprint (HTML-to-PDF)
- **Data Generation:** Faker + custom formatters

No Node.js or npm required. Single `pip install` to run.

## Project Structure

```
Tput/
├── app/
│   ├── main.py           # FastAPI app, serves UI, WebSocket endpoint
│   ├── benchmark.py      # Benchmark engine (async concurrency ramp)
│   ├── prompt_builder.py # Prompt construction with image support
│   ├── generators.py     # Random PII/PHI data generation
│   ├── report.py         # PDF report generation (weasyprint)
│   └── static/
│       ├── index.html    # Single-page split-panel UI
│       ├── app.js        # Dashboard logic, Chart.js, WebSocket client
│       └── style.css     # Dark theme styles
├── requirements.txt
└── README.md
```

## Architecture

### Request Flow

1. User opens `http://localhost:9090` — loads the split-panel UI
2. Left panel: configure endpoint URL, API key, benchmark params, build prompt
3. User clicks "Start Benchmark" — browser opens WebSocket connection
4. Backend runs benchmark engine asynchronously
5. Results stream to browser via WebSocket after each concurrency level
6. Right panel updates live with charts, stats, tables
7. Benchmark stops when avg latency > threshold or max concurrency reached
8. User clicks "Export PDF" for a formatted report

### Components

#### `main.py` — FastAPI Application
- `GET /` — serves `index.html`
- `GET /static/*` — serves JS/CSS
- `WS /ws/benchmark` — WebSocket endpoint for benchmark streaming
- `POST /api/report` — generates and returns PDF report
- `POST /api/generate-data` — returns generated PII/PHI data for prompt preview

#### `benchmark.py` — Benchmark Engine
- Linear ramp algorithm using `asyncio.Semaphore` for concurrency control
- Configurable parameters:
  - `start_concurrency` (default: 1)
  - `step_size` (default: 5)
  - `max_concurrency` (default: 200)
  - `requests_per_level` (default: 50)
  - `latency_threshold` (default: 2.0s)
- At each concurrency level:
  - Fire `requests_per_level` requests with concurrency capped by semaphore
  - Each request gets unique generated data (when PII/PHI generators are active)
  - Collect per-request: latency, HTTP status, RAMPART decision, violations list
  - Compute: avg latency, p50/p95/p99, RPS, success rate, error count, violation breakdown
- Sends level results via WebSocket as JSON
- Stops when avg latency exceeds threshold; reports previous level as max safe concurrency
- Tracks errors separately: timeouts, connection refused, HTTP 5xx

#### `generators.py` — Random Data Generation
Uses `Faker` library + custom formatters. Each request in a batch gets unique values.

**PII generators:**
| Type | Format | Example |
|------|--------|---------|
| SSN | XXX-XX-XXXX | 483-29-7761 |
| Full name | First Last | John Martinez |
| Email | user@domain.com | j.martinez@gmail.com |
| Phone | (XXX) XXX-XXXX | (555) 234-8901 |
| Address | Full street address | 1234 Oak Ave, Austin, TX 78701 |
| Date of birth | MM/DD/YYYY | 03/14/1985 |
| Driver's license | State-format | TX-12345678 |
| Credit card | XXXX-XXXX-XXXX-XXXX | 4532-1234-5678-9012 |

**PHI generators:**
| Type | Format | Example |
|------|--------|---------|
| MRN | MRN-XXXXXX | MRN-004821 |
| Diagnosis (ICD-10) | Code + description | J18.9 - Pneumonia |
| Medication + dosage | Drug + dose | Amoxicillin 500mg |
| Provider name | Dr. First Last | Dr. Sarah Chen |
| Insurance ID | Prefix-XXXXXXX | BCB-8827341 |
| Admission date | MM/DD/YYYY | 03/14/2025 |
| Lab result | Test + value + unit | HbA1c 7.2% |

**Template system:** Users build prompts with placeholder tags like `{name}`, `{ssn}`, `{mrn}`. Each request replaces placeholders with freshly generated values. When no placeholders are used (pure custom text), the same prompt is sent identically.

#### `prompt_builder.py` — Prompt Construction
- Accepts custom text with optional template variables
- Supports image attachment (paste or file upload)
- Images encoded as base64 data URIs
- Builds RAMPART-compatible request body:
  ```json
  {
    "request": {
      "model": "gpt-4",
      "messages": [
        {
          "role": "user",
          "content": "text" | [
            {"type": "text", "text": "..."},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
          ]
        }
      ]
    }
  }
  ```
- When content is text-only, uses string format
- When image is attached, uses multipart content array format

#### `report.py` — PDF Report Generation
Renders an HTML template with dark theme styling via weasyprint. Includes:
1. **Header** — timestamp, endpoint URL, benchmark configuration
2. **Summary** — max safe concurrency, total requests, total errors, success rate
3. **Latency chart** — HTML/CSS bar chart rendered inline (no Chart.js dependency in PDF)
4. **Percentiles table** — all concurrency levels with p50/p95/p99/avg, color-coded
5. **Policy violation summary** — counts by policy ID
6. **Error summary** — counts by error type (timeout, connection refused, HTTP 5xx)
7. **Config appendix** — prompt template used, which generators were enabled

## UI Design

### Layout: Split Panel
- **Left panel (38%):** Connection config, benchmark parameters, prompt builder, start button
- **Right panel (62%):** Live dashboard with charts, stats, tables

### Color Scheme: Dark Mode
- Background: `#0f1219` (main), `#131a2b` (cards), `#1e293b` (inputs/borders)
- Primary accent: `#38bdf8` (cyan)
- Success: `#4ade80` (green)
- Warning: `#fbbf24` (amber)
- Error: `#f87171` (red)
- Secondary: `#c084fc` (purple, for throughput)
- Text: `#e2e8f0` (primary), `#94a3b8` (secondary), `#64748b` (muted)

### Left Panel Components

**Connection section:**
- Endpoint URL text input
- API Key text input (masked)

**Benchmark Config section:**
- Start Concurrency (number input, default 1)
- Step Size (number input, default 5)
- Max Concurrency (number input, default 200)
- Requests per Level (number input, default 50)
- Latency Threshold (number input, default 2.0s)

**Prompt Builder section:**
- PII tag pills (blue): + SSN, + Name, + Email, + Phone, + Address, + DOB
- PHI tag pills (green): + MRN, + Diagnosis, + Medication, + Insurance
- Clicking a pill inserts the corresponding `{placeholder}` into the text area
- Text area for custom prompt with template variables highlighted
- Image drop zone: paste (Ctrl+V) or drag-and-drop, shows thumbnail preview

**Start Benchmark button:** Full-width cyan gradient

### Right Panel Components

**Status bar:** Running/stopped indicator, current level, concurrency count

**Stat cards (5 across):**
- Max Safe Concurrency (green)
- Avg Latency (amber)
- Success Rate (cyan)
- Throughput RPS (purple)
- Error Rate (red)

**Latency vs Concurrency chart:**
- Bar chart (Chart.js) with bars colored by zone: green (<50% threshold), amber (50-100%), red (>100%)
- Dashed red horizontal line at threshold
- Legend: Avg, p95, p99 lines overlaid
- X-axis: concurrency level, Y-axis: latency in seconds

**Percentiles table:**
- Columns: Level, p50, p95, p99, Avg
- Values color-coded: green (<1s), amber (1-2s), red (>2s)
- Current level row highlighted

**Policy Violations panel:**
- Horizontal progress bars per policy ID
- Shows "X / total" count
- Color-coded by proportion

**Error Log panel:**
- Recent errors with timestamp, error type, concurrency level
- Error types: Timeout, Connection Refused, HTTP 5xx

**Export PDF button:** Bottom-right

## Error Tracking

"Errors" are infrastructure failures only — not RAMPART policy blocks (which are expected behavior).

**Tracked error types:**
- `timeout` — request exceeded httpx timeout
- `connection_error` — connection refused, DNS failure, etc.
- `http_5xx` — server returned 500, 502, 503, etc.
- `http_other` — unexpected non-200/non-400 status codes

RAMPART returning 400 with `decision: "fail"` and violations is a successful evaluation, not an error.

**Per-level error metrics:**
- Error count and rate
- Breakdown by error type

**Dashboard display:**
- Error Rate stat card (red, shows percentage)
- Error Log panel with recent errors

## WebSocket Protocol

### Client → Server (start benchmark)
```json
{
  "action": "start",
  "config": {
    "endpoint": "https://...",
    "api_key": "rmp_live_...",
    "start_concurrency": 1,
    "step_size": 5,
    "max_concurrency": 200,
    "requests_per_level": 50,
    "latency_threshold": 2.0
  },
  "prompt": {
    "text": "Look up records for {name}, SSN {ssn}...",
    "image_base64": "data:image/png;base64,...",  // optional
    "generators": ["name", "ssn", "mrn", "diagnosis"]
  }
}
```

### Server → Client (level result)
```json
{
  "type": "level_result",
  "level": 3,
  "concurrency": 11,
  "avg_latency": 0.79,
  "p50": 0.68,
  "p95": 1.10,
  "p99": 1.35,
  "rps": 13.9,
  "success_rate": 100.0,
  "error_count": 0,
  "error_rate": 0.0,
  "errors_by_type": {},
  "total_requests": 50,
  "violations_by_policy": {
    "No-PII-Data": 47,
    "No-PHI": 42
  },
  "threshold_exceeded": false
}
```

### Server → Client (benchmark complete)
```json
{
  "type": "complete",
  "max_safe_concurrency": 16,
  "total_requests": 250,
  "total_errors": 0,
  "all_levels": [ ... ]
}
```

### Server → Client (error during run)
```json
{
  "type": "error",
  "message": "Connection to endpoint failed",
  "details": "..."
}
```

## Dependencies (requirements.txt)

```
fastapi>=0.100
uvicorn>=0.23
httpx>=0.27
websockets>=12.0
faker>=20.0
weasyprint>=60.0
jinja2>=3.1
```

Chart.js loaded from CDN in the HTML — no npm install needed.

## Running

```bash
cd Tput
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 9090
```

Open `http://localhost:9090` in a browser.
