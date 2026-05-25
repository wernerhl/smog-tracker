// Smog Tracker dashboard — vanilla JS, Chart.js.
// Reads data/dashboard.json, renders the national panel + 11 metro cards.

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
  const r = await fetch('data/dashboard.json?_=' + Date.now());
  return r.json();
}

function setKpis(d) {
  document.getElementById('last-updated').textContent =
    'Updated ' + d.last_updated + ' · last week ' + (d.last_week || '—');
  document.getElementById('nat-yoy').textContent = fmtPct(d.national.current_yoy);
  document.getElementById('nat-trail').textContent = fmtPct(d.national.trailing_12m_yoy);
  document.getElementById('nat-week').textContent = d.last_week || '—';
  const dot = document.getElementById('nat-dot');
  dot.className = 'dot ' + (d.national.status || 'grey');
}

function nationalChart(d) {
  const ctx = document.getElementById('nat-chart');
  if (!ctx || !d.national.series.length) return;
  const labels = d.national.series.map(p => p.week);
  const vals = d.national.series.map(p => p.yoy);
  const gasolinazo = d.gasolinazo_date;
  const idxGas = labels.findIndex(l => l >= gasolinazo);

  new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'YoY anomaly (%)',
        data: vals,
        borderColor: PALETTE.teal,
        backgroundColor: 'rgba(31,111,115,0.10)',
        borderWidth: 2,
        tension: 0.25,
        pointRadius: 0,
        spanGaps: true,
        fill: true,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: c => 'YoY ' + fmtPct(c.parsed.y) } },
      },
      scales: {
        y: {
          title: { display: true, text: 'YoY anomaly (%)' },
          grid:  { color: 'rgba(120,120,120,0.12)' },
        },
        x: {
          ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 },
          grid:  { display: false },
        },
      },
    },
    plugins: [{
      id: 'overlays',
      beforeDraw(chart) {
        const { ctx, chartArea, scales } = chart;
        if (!chartArea) return;
        // ±5 % band
        const y5  = scales.y.getPixelForValue(5);
        const yN5 = scales.y.getPixelForValue(-5);
        ctx.save();
        ctx.fillStyle = 'rgba(150,150,150,0.10)';
        ctx.fillRect(chartArea.left, y5, chartArea.right - chartArea.left, yN5 - y5);
        // Red shading below −5 %
        ctx.fillStyle = 'rgba(161,61,45,0.10)';
        ctx.fillRect(chartArea.left, yN5, chartArea.right - chartArea.left,
                     chartArea.bottom - yN5);
        // 0 line
        const y0 = scales.y.getPixelForValue(0);
        ctx.strokeStyle = PALETTE.slate;
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(chartArea.left, y0); ctx.lineTo(chartArea.right, y0); ctx.stroke();
        // Gasolinazo vertical line
        if (idxGas >= 0) {
          const xGas = scales.x.getPixelForValue(idxGas);
          ctx.strokeStyle = PALETTE.rust;
          ctx.setLineDash([5, 4]);
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

function metroCard(id, m) {
  const a = document.createElement('a');
  a.className = 'metro-card';
  a.href = 'metros/' + id + '.html';
  const insuff = m.current_yoy == null;
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
      : '<div class="yoy" style="color:' + colorFor(m.status) + '">' + fmtPct(m.current_yoy) + '</div>'}
    <canvas class="spark"></canvas>
  `;
  document.getElementById('metro-grid').appendChild(a);
  const canvas = a.querySelector('canvas');
  drawSpark(canvas, m.sparkline || [], m.status);
  return a;
}

function colorFor(status) {
  if (status === 'green')  return PALETTE.green;
  if (status === 'red')    return PALETTE.rust;
  if (status === 'yellow') return PALETTE.ochre;
  return PALETTE.grey;
}

function drawSpark(canvas, vals, status) {
  if (!canvas) return;
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
        spanGaps: true,
        fill: false,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: { x: { display: false }, y: { display: false } },
      elements: { line: { capBezierPoints: false } },
    },
  });
}

(async function init() {
  try {
    const d = await loadData();
    setKpis(d);
    nationalChart(d);
    for (const [id, m] of Object.entries(d.metros)) metroCard(id, m);
  } catch (e) {
    document.querySelector('main').innerHTML =
      '<p style="color:#A13D2D">Could not load data/dashboard.json — has the pipeline run yet?</p>'
      + '<pre>' + String(e) + '</pre>';
  }
})();
