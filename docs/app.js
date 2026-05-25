// Smog Tracker dashboard — vanilla JS + Chart.js.
// Headline = 28-day rolling YoY. Thin gray = 7-day raw YoY (context only).
// Loads docs/data/dashboard.json relative to index.html.

console.log('[smog-tracker] app.js loaded');

const PALETTE = {
  teal:  '#1F6F73',
  rust:  '#A13D2D',
  slate: '#3B4A54',
  ochre: '#C08A3E',
  grey:  '#b8b8b3',
  green: '#2f8d4e',
};

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

async function loadData() {
  const url = './data/dashboard.json?_=' + Date.now();
  console.log('[smog-tracker] fetching', url);
  const r = await fetch(url);
  if (!r.ok) throw new Error('HTTP ' + r.status + ' loading ' + url);
  const d = await r.json();
  console.log('[smog-tracker] dashboard.json loaded',
              'national.current_yoy_28d =', d.national?.current_yoy_28d,
              ' metros =', Object.keys(d.metros || {}).length);
  return d;
}

function setKpis(d) {
  const last = document.getElementById('last-updated');
  if (last) last.textContent =
    'Updated ' + d.last_updated + ' · last week ' + (d.last_week || '—');
  const yoy = document.getElementById('nat-yoy');
  if (yoy) yoy.textContent = fmtPct(d.national.current_yoy_28d);
  const yoy7 = document.getElementById('nat-yoy-7d');
  if (yoy7) yoy7.textContent = fmtPct(d.national.current_yoy_7d);
  const trail = document.getElementById('nat-trail');
  if (trail) trail.textContent = fmtPct(d.national.trailing_12m_yoy);
  const week = document.getElementById('nat-week');
  if (week) week.textContent = d.last_week || '—';
  const dot = document.getElementById('nat-dot');
  if (dot) dot.className = 'dot ' + (d.national.status || 'grey');
}

function nationalChart(d) {
  const ctx = document.getElementById('nat-chart');
  if (!ctx) return;
  const series = d.national.series || [];
  if (!series.length) return;
  const labels = series.map(p => p.week);
  const vals28 = series.map(p => (p.yoy_28d == null ? null : p.yoy_28d));
  const vals7  = series.map(p => (p.yoy_7d  == null ? null : p.yoy_7d));
  const gasolinazo = d.gasolinazo_date;
  const idxGas = labels.findIndex(l => l >= gasolinazo);

  new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: '7-day raw YoY',
          data: vals7,
          borderColor: 'rgba(120,120,120,0.45)',
          borderWidth: 1,
          tension: 0.15,
          pointRadius: 0,
          spanGaps: false,
          fill: false,
          order: 2,
        },
        {
          label: '28-day rolling YoY',
          data: vals28,
          borderColor: PALETTE.teal,
          backgroundColor: 'rgba(31,111,115,0.10)',
          borderWidth: 2.5,
          tension: 0.25,
          pointRadius: 0,
          spanGaps: false,
          fill: true,
          order: 1,
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
        y: { title: { display: true, text: 'YoY anomaly (%)' },
             grid: { color: 'rgba(120,120,120,0.12)' } },
        x: { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 },
             grid: { display: false } },
      },
    },
    plugins: [{
      id: 'overlays',
      beforeDraw(chart) {
        const { ctx, chartArea, scales } = chart;
        if (!chartArea) return;
        const y5  = scales.y.getPixelForValue(5);
        const yN5 = scales.y.getPixelForValue(-5);
        ctx.save();
        ctx.fillStyle = 'rgba(150,150,150,0.10)';
        ctx.fillRect(chartArea.left, y5, chartArea.right - chartArea.left, yN5 - y5);
        ctx.fillStyle = 'rgba(161,61,45,0.10)';
        ctx.fillRect(chartArea.left, yN5, chartArea.right - chartArea.left,
                     chartArea.bottom - yN5);
        const y0 = scales.y.getPixelForValue(0);
        ctx.strokeStyle = PALETTE.slate; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(chartArea.left, y0); ctx.lineTo(chartArea.right, y0); ctx.stroke();
        if (idxGas >= 0) {
          const xGas = scales.x.getPixelForValue(idxGas);
          ctx.strokeStyle = PALETTE.rust; ctx.setLineDash([5, 4]);
          ctx.beginPath(); ctx.moveTo(xGas, chartArea.top); ctx.lineTo(xGas, chartArea.bottom); ctx.stroke();
          ctx.setLineDash([]);
          ctx.fillStyle = PALETTE.rust;
          ctx.font = '11px sans-serif';
          ctx.fillText('gasolinazo', xGas + 4, chartArea.top + 12);
        }
        ctx.restore();
      }
    }]
  });
}

function colorFor(status) {
  if (status === 'green')  return PALETTE.green;
  if (status === 'red')    return PALETTE.rust;
  if (status === 'yellow') return PALETTE.ochre;
  return PALETTE.grey;
}

function metroCard(id, m) {
  const a = document.createElement('a');
  a.className = 'metro-card';
  a.href = 'metros/' + id + '.html';
  const insuff = m.current_yoy_28d == null;
  a.innerHTML = `
    <div class="top">
      <div>
        <div class="name">${m.name}</div>
        <div class="meta">${m.dept} · ${m.altitude}</div>
      </div>
      <span class="dot ${m.status || 'grey'}" title="${m.status || 'no data'}"></span>
    </div>
    ${insuff
      ? '<div class="insuff">insufficient data</div>'
      : '<div class="yoy" style="color:' + colorFor(m.status) + '">' + fmtPct(m.current_yoy_28d) + '</div>'}
    <div class="spark-wrap"><canvas class="spark"></canvas></div>
  `;
  document.getElementById('metro-grid').appendChild(a);
  const canvas = a.querySelector('canvas');
  drawSpark(canvas, m.sparkline || [], m.status);
  return a;
}

function drawSpark(canvas, vals, status) {
  if (!canvas || !vals.length) return;
  const ctx = canvas.getContext('2d');
  new Chart(ctx, {
    type: 'line',
    data: {
      labels: vals.map((_, i) => i),
      datasets: [{
        data: vals,
        borderColor: colorFor(status),
        borderWidth: 1.5,
        tension: 0.3,
        pointRadius: 0,
        spanGaps: false,
        fill: false,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: { x: { display: false }, y: { display: false } },
    },
  });
}

(async function init() {
  try {
    const d = await loadData();
    setKpis(d);
    nationalChart(d);
    const grid = document.getElementById('metro-grid');
    if (grid) {
      grid.innerHTML = '';
      for (const [id, m] of Object.entries(d.metros)) metroCard(id, m);
    }
    console.log('[smog-tracker] init complete');
  } catch (e) {
    console.error('[smog-tracker]', e);
    const main = document.querySelector('main');
    if (main) main.innerHTML =
      '<p style="color:#A13D2D">Could not load <code>data/dashboard.json</code> — has the pipeline run yet?</p>'
      + '<pre style="background:#0001;padding:10px;border-radius:6px;">' + String(e) + '</pre>';
  }
})();
