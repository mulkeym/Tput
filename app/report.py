import os as _os

# weasyprint requires GTK/Pango system libraries; on macOS with Homebrew they
# live in /opt/homebrew/lib which may not be on the dynamic-linker search path.
# Prepend it so cffi can locate libgobject, libpango, etc.
_brew_lib = "/opt/homebrew/lib"
_dyld_key = "DYLD_LIBRARY_PATH"
if _brew_lib not in _os.environ.get(_dyld_key, ""):
    _os.environ[_dyld_key] = (
        _brew_lib + (":" + _os.environ[_dyld_key] if _os.environ.get(_dyld_key) else "")
    )

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
{% if mode == "llm" %}
<table>
  <thead>
    <tr><th>Level</th><th>Concurrency</th><th>P50</th><th>P95</th><th>P99</th><th>Avg</th><th>TTFT p50</th><th>TPS</th><th>Errors</th></tr>
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
      <td>{{ "%.3f" | format(level.p50_ttft) }}s</td>
      <td>{{ "%.1f" | format(level.avg_tps) }}</td>
      <td>{{ level.error_count }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% else %}
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
{% endif %}

{% if mode == "llm" %}
<h2>Token Performance</h2>
<table>
  <thead>
    <tr><th>Level</th><th>Concurrency</th><th>Avg TTFT</th><th>P50 TTFT</th><th>P95 TTFT</th><th>P99 TTFT</th><th>Avg TPS</th></tr>
  </thead>
  <tbody>
    {% for level in levels %}
    <tr>
      <td>{{ level.level }}</td>
      <td>{{ level.concurrency }}</td>
      <td>{{ "%.3f" | format(level.avg_ttft) }}s</td>
      <td>{{ "%.3f" | format(level.p50_ttft) }}s</td>
      <td>{{ "%.3f" | format(level.p95_ttft) }}s</td>
      <td>{{ "%.3f" | format(level.p99_ttft) }}s</td>
      <td>{{ "%.1f" | format(level.avg_tps) }} tok/s</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% else %}
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


def render_report_html(endpoint, config, levels, max_safe_concurrency,
                       total_requests, total_errors, prompt_template, generators,
                       mode="rampart"):
    all_violations = {}
    all_errors = {}
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
        timestamp=timestamp, endpoint=endpoint, config=config,
        levels=levels, max_safe_concurrency=max_safe_concurrency,
        total_requests=total_requests, total_errors=total_errors,
        max_latency=max_latency, all_violations=all_violations,
        all_errors=all_errors, prompt_template=prompt_template,
        generators=generators, mode=mode,
    )


def generate_pdf(endpoint, config, levels, max_safe_concurrency,
                 total_requests, total_errors, prompt_template, generators,
                 mode="rampart"):
    html_str = render_report_html(
        endpoint=endpoint, config=config, levels=levels,
        max_safe_concurrency=max_safe_concurrency,
        total_requests=total_requests, total_errors=total_errors,
        prompt_template=prompt_template, generators=generators,
        mode=mode,
    )
    return HTML(string=html_str).write_pdf()
