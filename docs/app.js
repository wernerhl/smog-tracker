// Smog Tracker dashboard — vanilla JS + Chart.js.
// One national chart: YoY growth of centered + trailing 12-month NO₂.
// i18n.js must be loaded before this file.

console.log('[smog-tracker] app.js loaded');

const PALETTE = {
  teal:  '#1F6F73',
  rust:  '#A13D2D',
  slate: '#3B4A54',
  ochre: '#C08A3E',
  grey:  '#b8b8b3',
  green: '#2f8d4e',
};

const fmtDev = v => v == null ? '—' : (v >= 0 ? '+' : '') + v.toFixed(1);
const fmtPct = v => v == null ? '—' : (v >= 0 ? '+' : '') + v.toFixed(1) + '%';

// ---------- theme toggle (persisted) ----------
(function initTheme() {
  const saved = localStorage.getItem('smog-theme');
  if (saved) document.documentElement.setAttribute('data-theme', saved);
  document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('theme-toggle');
    if (!btn) return;
    btn.addEventListener('click', e => {
      e.preventDefault();
      const cur = document.documentElement.getAttribute('data-theme');
      const next = cur === 'dark' ? '' : 'dark';
      if (next) document.documentElement.setAttribute('data-theme', next);
      else document.documentElement.removeAttribute('data-theme');
      localStorage.setItem('smog-theme', next);
    });
  });
})();

function colorFor(status) {
  if (status === 'green')  return PALETTE.green;
  if (status === 'red')    return PALETTE.rust;
  if (status === 'yellow') return PALETTE.ochre;
  return PALETTE.grey;
}

// ---------- Chart instances (for rebuild on lang change) ----------
let _chartMonthly = null;
let _dashData = null;

// ---------- YoY growth chart ----------
function monthlyChart(d) {
  const ctx = document.getElementById('chart-monthly');
  if (!ctx) return;
  const series = d.national.monthly_series || [];
  if (!series.length) return;
  const labels = series.map(p => p.month);
  const c12vals = series.map(p => p.centered_yoy);
  const trailvals = series.map(p => p.trailing_yoy);
  const gasMonth = '2025-12';
  const idxGas = labels.findIndex(l => l >= gasMonth);

  if (_chartMonthly) _chartMonthly.destroy();
  _chartMonthly = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: T('chart-trailing'),
          data: trailvals,
          borderColor: 'rgba(120,120,120,0.45)',
          borderWidth: 1, tension: 0.2, pointRadius: 0,
          spanGaps: true, fill: false, order: 2,
        },
        {
          label: T('chart-centered'),
          data: c12vals,
          borderColor: PALETTE.teal,
          backgroundColor: 'rgba(31,111,115,0.10)',
          borderWidth: 2.5, tension: 0.3, pointRadius: 0,
          spanGaps: true, fill: true, order: 1,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: true, position: 'top', labels: { boxWidth: 14 } },
        tooltip: {
          callbacks: {
            label: c => c.dataset.label + ': ' + fmtPct(c.parsed.y),
          },
        },
      },
      scales: {
        y: { title: { display: true, text: T('chart-yaxis-yoy') },
             grid: { color: 'rgba(120,120,120,0.12)' } },
        x: { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 10 },
             grid: { display: false } },
      },
    },
    plugins: [{
      id: 'monthlyOverlays',
      beforeDraw(chart) {
        const { ctx, chartArea, scales } = chart;
        if (!chartArea || !scales.y) return;
        ctx.save();
        // Zero line
        const y0 = scales.y.getPixelForValue(0);
        ctx.strokeStyle = PALETTE.slate; ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(chartArea.left, y0); ctx.lineTo(chartArea.right, y0); ctx.stroke();
        // Red shading below zero
        ctx.fillStyle = 'rgba(161,61,45,0.08)';
        ctx.fillRect(chartArea.left, y0, chartArea.right - chartArea.left, chartArea.bottom - y0);
        // Gasolinazo
        if (idxGas >= 0) {
          const xGas = scales.x.getPixelForValue(idxGas);
          ctx.strokeStyle = PALETTE.rust; ctx.setLineDash([5, 4]);
          ctx.beginPath(); ctx.moveTo(xGas, chartArea.top); ctx.lineTo(xGas, chartArea.bottom); ctx.stroke();
          ctx.setLineDash([]);
          ctx.fillStyle = PALETTE.rust; ctx.font = '11px sans-serif';
          ctx.fillText('gasolinazo', xGas + 4, chartArea.top + 12);
        }
        ctx.restore();
      }
    }],
  });
}

// ---------- Metro cards ----------
function renderMetros(d) {
  const grid = document.getElementById('metro-grid');
  if (!grid) return;
  grid.innerHTML = '';
  for (const [id, m] of Object.entries(d.metros)) metroCard(id, m);
}

function metroCard(id, m) {
  const a = document.createElement('a');
  a.className = 'metro-card';
  a.href = 'metros/' + id + '.html';
  const valColor = colorFor(m.status);
  const dateLabel = m.centered_yoy_date || '—';
  a.innerHTML = `
    <div class="top">
      <div>
        <div class="name">${m.name}</div>
        <div class="meta">${m.dept} · ${m.altitude}</div>
      </div>
      <span class="dot ${m.status || 'grey'}" title="${m.status || 'no data'}"></span>
    </div>
    <div class="yoy" style="color:${valColor}">${fmtPct(m.trailing_yoy)}</div>
    <div class="metro-sublabel">${T('kpi-trail')} ${dateLabel}</div>
    <div class="spark-wrap"><canvas class="spark"></canvas></div>
  `;
  document.getElementById('metro-grid').appendChild(a);
  const canvas = a.querySelector('canvas');
  drawSpark(canvas, m.sparkline_28d || [], m.status);
  return a;
}

function drawSpark(canvas, vals, status) {
  if (!canvas || !vals.length) return;
  new Chart(canvas, {
    type: 'line',
    data: {
      labels: vals.map((_, i) => i),
      datasets: [{
        data: vals,
        borderColor: colorFor(status),
        borderWidth: 1.5, tension: 0.3, pointRadius: 0,
        spanGaps: true, fill: false,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: { x: { display: false }, y: { display: false } },
    },
  });
}

// ---------- Rebuild on language change ----------
window._rebuildCharts = function() {
  if (!_dashData) return;
  setKpis(_dashData);
  monthlyChart(_dashData);
  renderMetros(_dashData);
};

function setKpis(d) {
  const lastUp = document.getElementById('last-updated');
  if (lastUp) lastUp.textContent = T('updated') + ' ' + d.last_updated;

  const c12El = document.getElementById('nat-c12');
  if (c12El) {
    c12El.textContent = fmtPct(d.national.centered_yoy);
    c12El.style.color = colorFor(d.national.status);
  }
  const dotEl = document.getElementById('nat-dot');
  if (dotEl) dotEl.className = 'dot ' + (d.national.status || 'grey');
  const trailEl = document.getElementById('nat-trail');
  if (trailEl) trailEl.textContent = fmtPct(d.national.trailing_yoy);
  const dateEl = document.getElementById('nat-date');
  if (dateEl) dateEl.textContent = d.national.trailing_yoy_date || '—';
}

// ---------- Init ----------
(async function init() {
  try {
    const url = './data/dashboard.json?_=' + Date.now();
    console.log('[smog-tracker] fetching', url);
    const r = await fetch(url);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    _dashData = await r.json();
    console.log('[smog-tracker] dashboard loaded', _dashData.national);

    setKpis(_dashData);
    monthlyChart(_dashData);
    renderMetros(_dashData);
    console.log('[smog-tracker] init complete');
  } catch (e) {
    console.error('[smog-tracker]', e);
    const main = document.querySelector('main');
    if (main) main.innerHTML =
      '<p style="color:#A13D2D">Could not load <code>data/dashboard.json</code> — has the pipeline run yet?</p>'
      + '<pre style="background:#0001;padding:10px;border-radius:6px;">' + String(e) + '</pre>';
  }
})();
