/* ===========================
   Tput — RAMPART Benchmark
   Frontend App Logic
   =========================== */

'use strict';

// ── State ──────────────────────────────────────────────────────────────────
let ws = null;
let running = false;
let imageBase64 = null;
let allLevels = [];
let maxSafeConcurrency = null;
let latencyChart = null;

// ── DOM References ──────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

const endpointEl    = $('endpoint');
const apikeyEl      = $('apikey');
const startConcEl   = $('start-conc');
const stepSizeEl    = $('step-size');
const maxConcEl     = $('max-conc');
const reqPerLevelEl = $('req-per-level');
const thresholdEl   = $('threshold');
const promptTextEl  = $('prompt-text');
const imageDropEl   = $('image-drop');
const imagePreviewEl= $('image-preview');
const previewImgEl  = $('preview-img');
const removeImageEl = $('remove-image');
const startBtnEl    = $('start-btn');
const stopBtnEl     = $('stop-btn');
const statusDotEl   = $('status-dot');
const statusTextEl  = $('status-text');
const statusDetailEl= $('status-detail');
const statMaxConcEl = $('stat-max-conc');
const statAvgLatEl  = $('stat-avg-lat');
const statSuccessEl = $('stat-success');
const statRpsEl     = $('stat-rps');
const statErrorsEl  = $('stat-errors');
const percTbodyEl   = $('perc-tbody');
const violationsEl  = $('violations-container');
const errorLogEl    = $('error-log');
const exportBtnEl   = $('export-btn');

// ── Known Generator Names ────────────────────────────────────────────────────
const KNOWN_GENERATORS = new Set([
  'ssn', 'name', 'email', 'phone', 'address', 'dob',
  'drivers_license', 'credit_card',
  'mrn', 'diagnosis', 'medication', 'provider',
  'insurance_id', 'admission_date', 'lab_result',
]);

// ── Chart Init / Reset ───────────────────────────────────────────────────────
function initChart() {
  const canvas = $('latency-chart');
  if (!canvas) return;

  if (latencyChart) {
    latencyChart.destroy();
    latencyChart = null;
  }

  const threshold = parseFloat(thresholdEl.value) || 2.0;

  const thresholdPlugin = {
    id: 'thresholdLine',
    afterDraw(chart) {
      const { ctx, chartArea, scales } = chart;
      if (!chartArea) return;
      const y = scales.y.getPixelForValue(threshold);
      ctx.save();
      ctx.strokeStyle = 'rgba(251, 191, 36, 0.6)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(chartArea.left, y);
      ctx.lineTo(chartArea.right, y);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
    },
  };

  latencyChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: [],
      datasets: [
        {
          type: 'bar',
          label: 'Avg Latency',
          data: [],
          backgroundColor: [],
          borderRadius: 3,
          order: 2,
          yAxisID: 'y',
        },
        {
          type: 'line',
          label: 'p95',
          data: [],
          borderColor: '#fbbf24',
          backgroundColor: 'transparent',
          borderWidth: 2,
          pointRadius: 3,
          pointHoverRadius: 5,
          tension: 0.35,
          order: 1,
          yAxisID: 'y',
        },
        {
          type: 'line',
          label: 'p99',
          data: [],
          borderColor: '#f87171',
          backgroundColor: 'transparent',
          borderWidth: 2,
          pointRadius: 3,
          pointHoverRadius: 5,
          tension: 0.35,
          order: 0,
          yAxisID: 'y',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 250 },
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: {
          grid: { color: '#1e293b' },
          ticks: { color: '#64748b', font: { size: 11 } },
          title: {
            display: true,
            text: 'Concurrency',
            color: '#64748b',
            font: { size: 11 },
          },
        },
        y: {
          grid: { color: '#1e293b' },
          ticks: { color: '#64748b', font: { size: 11 } },
          title: {
            display: true,
            text: 'Latency (s)',
            color: '#64748b',
            font: { size: 11 },
          },
          beginAtZero: true,
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#131a2b',
          borderColor: '#334155',
          borderWidth: 1,
          titleColor: '#94a3b8',
          bodyColor: '#e2e8f0',
          callbacks: {
            label(ctx) {
              const val = ctx.parsed.y;
              return ` ${ctx.dataset.label}: ${val !== null ? val.toFixed(3) + 's' : '—'}`;
            },
          },
        },
      },
    },
    plugins: [thresholdPlugin],
  });
}

// ── Chart: Add Data Point ────────────────────────────────────────────────────
function addChartPoint(level) {
  if (!latencyChart) return;

  const threshold = parseFloat(thresholdEl.value) || 2.0;
  const avg = level.avg_latency;
  let barColor;
  if (avg < threshold * 0.5) {
    barColor = '#4ade80';
  } else if (avg <= threshold) {
    barColor = '#fbbf24';
  } else {
    barColor = '#f87171';
  }

  const ds = latencyChart.data.datasets;
  latencyChart.data.labels.push(`${level.concurrency}`);
  ds[0].data.push(parseFloat(avg.toFixed(3)));
  ds[0].backgroundColor.push(barColor);
  ds[1].data.push(parseFloat(level.p95.toFixed(3)));
  ds[2].data.push(parseFloat(level.p99.toFixed(3)));
  latencyChart.update('none');
}

// ── Stats Update ─────────────────────────────────────────────────────────────
function updateStats(level) {
  if (maxSafeConcurrency !== null) {
    statMaxConcEl.textContent = maxSafeConcurrency;
  } else {
    statMaxConcEl.textContent = `${level.concurrency}`;
  }
  statAvgLatEl.textContent  = `${level.avg_latency.toFixed(2)}s`;
  statSuccessEl.textContent = `${level.success_rate.toFixed(1)}%`;
  statRpsEl.textContent     = `${level.rps.toFixed(1)}`;
  statErrorsEl.textContent  = `${level.error_rate.toFixed(1)}%`;
}

// ── Percentile Table ─────────────────────────────────────────────────────────
function addPercRow(level) {
  // Remove empty placeholder row if present
  const emptyRow = percTbodyEl.querySelector('.empty-row');
  if (emptyRow) emptyRow.remove();

  // De-highlight previous current row
  const prevCurrent = percTbodyEl.querySelector('tr.current');
  if (prevCurrent) prevCurrent.classList.remove('current');

  const tr = document.createElement('tr');
  tr.classList.add('current');
  tr.innerHTML = `
    <td>${level.concurrency}</td>
    <td>${level.p50.toFixed(3)}</td>
    <td>${level.p95.toFixed(3)}</td>
    <td>${level.p99.toFixed(3)}</td>
    <td>${level.avg_latency.toFixed(3)}</td>
  `;
  percTbodyEl.appendChild(tr);

  // Scroll to bottom
  const scrollParent = percTbodyEl.closest('.perc-scroll');
  if (scrollParent) scrollParent.scrollTop = scrollParent.scrollHeight;
}

// ── Violations ────────────────────────────────────────────────────────────────
let totalViolations = {};

function updateViolations(level) {
  if (!level.violations_by_policy) return;

  let anyViolation = false;
  for (const [policy, count] of Object.entries(level.violations_by_policy)) {
    if (count > 0) {
      anyViolation = true;
      totalViolations[policy] = (totalViolations[policy] || 0) + count;
    }
  }

  if (!anyViolation) return;

  // Rebuild violations UI
  const maxCount = Math.max(...Object.values(totalViolations), 1);
  violationsEl.innerHTML = '';

  for (const [policy, total] of Object.entries(totalViolations)) {
    const pct = Math.min((total / maxCount) * 100, 100);
    const item = document.createElement('div');
    item.className = 'violation-item';
    item.innerHTML = `
      <div class="violation-header">
        <span class="violation-label">${escapeHtml(policy)}</span>
        <span class="violation-count">${total}</span>
      </div>
      <div class="violation-bar">
        <div class="violation-bar-fill" style="width:${pct}%"></div>
      </div>
    `;
    violationsEl.appendChild(item);
  }
}

// ── Error Log ─────────────────────────────────────────────────────────────────
function addErrors(level) {
  if (!level.errors_by_type) return;

  let anyError = false;
  for (const [errType, count] of Object.entries(level.errors_by_type)) {
    if (count <= 0) continue;
    anyError = true;

    // Remove empty placeholder if present
    const empty = errorLogEl.querySelector('.empty-state');
    if (empty) empty.remove();

    const entry = document.createElement('div');
    entry.className = 'error-entry';
    entry.innerHTML = `
      <span class="error-conc">c=${level.concurrency}</span>
      <span class="error-msg">${escapeHtml(errType)}: ${count}</span>
    `;
    errorLogEl.appendChild(entry);
  }

  if (anyError) {
    errorLogEl.scrollTop = errorLogEl.scrollHeight;
  }
}

// ── Dashboard Reset ───────────────────────────────────────────────────────────
function resetDashboard() {
  allLevels = [];
  maxSafeConcurrency = null;
  totalViolations = {};

  statMaxConcEl.textContent = '—';
  statAvgLatEl.textContent  = '—';
  statSuccessEl.textContent = '—';
  statRpsEl.textContent     = '—';
  statErrorsEl.textContent  = '—';

  percTbodyEl.innerHTML = `
    <tr class="empty-row">
      <td colspan="5" style="text-align:center;color:var(--text-muted);padding:16px 0;">
        No data yet
      </td>
    </tr>
  `;

  violationsEl.innerHTML = `
    <div class="empty-state" style="min-height:60px;padding:12px 0;">
      <span class="empty-sub">No violations detected</span>
    </div>
  `;

  errorLogEl.innerHTML = `
    <div class="empty-state" style="min-height:60px;padding:12px 0;">
      <span class="empty-sub">No errors</span>
    </div>
  `;

  exportBtnEl.disabled = true;
  initChart();
}

// ── Status Bar ────────────────────────────────────────────────────────────────
function setStatus(state, text, detail = '') {
  statusDotEl.className = `status-dot ${state}`;
  statusTextEl.textContent = text;
  statusDetailEl.textContent = detail;
}

// ── Input Lock ────────────────────────────────────────────────────────────────
function lockInputs(locked) {
  const inputs = [
    endpointEl, apikeyEl, startConcEl, stepSizeEl,
    maxConcEl, reqPerLevelEl, thresholdEl, promptTextEl,
  ];
  inputs.forEach(el => { if (el) el.disabled = locked; });

  document.querySelectorAll('.pill').forEach(p => {
    p.style.pointerEvents = locked ? 'none' : '';
    p.style.opacity = locked ? '0.5' : '';
  });

  imageDropEl.style.pointerEvents = locked ? 'none' : '';
  imageDropEl.style.opacity = locked ? '0.5' : '';
}

// ── Detect Generators in Prompt ───────────────────────────────────────────────
function detectGenerators() {
  const text = promptTextEl.value || '';
  const matches = text.match(/\{(\w+)\}/g) || [];
  const found = new Set();
  for (const m of matches) {
    const name = m.slice(1, -1);
    if (KNOWN_GENERATORS.has(name)) found.add(name);
  }
  return Array.from(found);
}

// ── Pill Click Handlers ───────────────────────────────────────────────────────
document.querySelectorAll('.pill').forEach(pill => {
  pill.addEventListener('click', () => {
    const gen = pill.dataset.gen;
    const placeholder = `{${gen}}`;

    // Insert at cursor
    const ta = promptTextEl;
    const start = ta.selectionStart;
    const end   = ta.selectionEnd;
    const before = ta.value.substring(0, start);
    const after  = ta.value.substring(end);
    ta.value = before + placeholder + after;
    ta.selectionStart = ta.selectionEnd = start + placeholder.length;
    ta.focus();

    // Toggle active
    pill.classList.toggle('active');
  });
});

// ── Image Drop / Paste / Click ─────────────────────────────────────────────────
function loadImageFile(file) {
  if (!file || !file.type.startsWith('image/')) return;

  const reader = new FileReader();
  reader.onload = e => {
    imageBase64 = e.target.result; // data URL (includes mime prefix)
    previewImgEl.src = imageBase64;
    imagePreviewEl.classList.remove('hidden');
    imageDropEl.classList.add('hidden');
  };
  reader.readAsDataURL(file);
}

imageDropEl.addEventListener('click', () => {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/*';
  input.onchange = e => loadImageFile(e.target.files[0]);
  input.click();
});

imageDropEl.addEventListener('dragover', e => {
  e.preventDefault();
  imageDropEl.classList.add('drag-over');
});

imageDropEl.addEventListener('dragleave', () => {
  imageDropEl.classList.remove('drag-over');
});

imageDropEl.addEventListener('drop', e => {
  e.preventDefault();
  imageDropEl.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  loadImageFile(file);
});

document.addEventListener('paste', e => {
  const items = e.clipboardData?.items || [];
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      loadImageFile(item.getAsFile());
      break;
    }
  }
});

removeImageEl.addEventListener('click', () => {
  imageBase64 = null;
  previewImgEl.src = '';
  imagePreviewEl.classList.add('hidden');
  imageDropEl.classList.remove('hidden');
});

// ── WebSocket Benchmark Flow ──────────────────────────────────────────────────
startBtnEl.addEventListener('click', () => {
  if (running) return;

  const endpoint = endpointEl.value.trim();
  const apikey   = apikeyEl.value.trim();

  if (!endpoint) {
    alert('Please enter an endpoint URL.');
    endpointEl.focus();
    return;
  }

  const config = {
    endpoint,
    api_key:              apikey,
    start_concurrency:    parseInt(startConcEl.value, 10)   || 1,
    step_size:            parseInt(stepSizeEl.value, 10)    || 5,
    max_concurrency:      parseInt(maxConcEl.value, 10)     || 200,
    requests_per_level:   parseInt(reqPerLevelEl.value, 10) || 50,
    latency_threshold:    parseFloat(thresholdEl.value)     || 2.0,
  };

  const generators = detectGenerators();
  const prompt = {
    template:   promptTextEl.value,
    generators,
    image:      imageBase64 || null,
  };

  resetDashboard();
  setStatus('running', 'Running', 'Connecting…');
  lockInputs(true);
  running = true;
  startBtnEl.disabled = true;
  stopBtnEl.disabled  = false;

  const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${wsProtocol}//${location.host}/ws/benchmark`;

  ws = new WebSocket(wsUrl);

  ws.addEventListener('open', () => {
    setStatus('running', 'Running', 'Benchmark started…');
    ws.send(JSON.stringify({ action: 'start', config, prompt }));
  });

  ws.addEventListener('message', e => {
    let msg;
    try { msg = JSON.parse(e.data); } catch { return; }

    if (msg.type === 'level_result') {
      const level = msg.data;
      allLevels.push(level);

      if (!level.threshold_exceeded) {
        maxSafeConcurrency = level.concurrency;
      }

      addChartPoint(level);
      updateStats(level);
      addPercRow(level);
      updateViolations(level);
      addErrors(level);

      setStatus(
        'running',
        'Running',
        `Level ${level.level} — concurrency ${level.concurrency} complete`,
      );
    } else if (msg.type === 'complete') {
      const result = msg.data;
      if (result && result.max_safe_concurrency !== undefined) {
        maxSafeConcurrency = result.max_safe_concurrency;
        statMaxConcEl.textContent = maxSafeConcurrency ?? '—';
      }
      onComplete('Benchmark complete');
    } else if (msg.type === 'error') {
      setStatus('error', 'Error', msg.message || 'Unknown error');
      onComplete('Error');
    }
  });

  ws.addEventListener('close', () => {
    if (running) {
      setStatus('idle', 'Disconnected', 'WebSocket closed unexpectedly');
      onComplete('Disconnected');
    }
  });

  ws.addEventListener('error', () => {
    setStatus('error', 'Connection error', 'Failed to connect to the server');
    onComplete('Error');
  });
});

stopBtnEl.addEventListener('click', () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ action: 'stop' }));
    ws.close();
  }
  setStatus('idle', 'Stopped', 'Benchmark stopped by user');
  onComplete('Stopped');
});

function onComplete(label) {
  running = false;
  startBtnEl.disabled = false;
  stopBtnEl.disabled  = true;
  lockInputs(false);

  if (label === 'Benchmark complete') {
    setStatus('complete', 'Complete', `Max safe concurrency: ${maxSafeConcurrency ?? '—'}`);
  }

  if (allLevels.length > 0) {
    exportBtnEl.disabled = false;
  }

  if (ws) {
    try { ws.close(); } catch { /* ignore */ }
    ws = null;
  }
}

// ── PDF Export ────────────────────────────────────────────────────────────────
exportBtnEl.addEventListener('click', async () => {
  if (allLevels.length === 0) return;

  exportBtnEl.disabled = true;
  exportBtnEl.textContent = 'Generating…';

  try {
    const res = await fetch('/api/report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        levels: allLevels,
        config: {
          endpoint:           endpointEl.value.trim(),
          latency_threshold:  parseFloat(thresholdEl.value) || 2.0,
        },
        max_safe_concurrency: maxSafeConcurrency,
      }),
    });

    if (!res.ok) throw new Error(`Server responded ${res.status}`);

    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `tput-report-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err) {
    alert(`Export failed: ${err.message}`);
  } finally {
    exportBtnEl.disabled = false;
    exportBtnEl.textContent = '⬇ Export PDF Report';
    exportBtnEl.innerHTML = '&#8681; Export PDF Report';
  }
});

// ── Utility ───────────────────────────────────────────────────────────────────
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Init ──────────────────────────────────────────────────────────────────────
(function init() {
  initChart();
  setStatus('idle', 'Idle', 'Configure and start a benchmark run');
})();
