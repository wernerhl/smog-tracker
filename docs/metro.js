// Per-metro detail page. Reads ?id=<roi> from query string OR a global ROI_ID.
// Charts: yearly raw NO₂ overlay (current vs previous), YoY anomaly time series.
// Table: last 12 weeks. CSV download button.

const PALETTE = {
  teal:  '#1F6F73',
  rust:  '#A13D2D',
  slate: '#3B4A54',
  ochre: '#C08A3E',
  grey:  '#b8b8b3',
  green: '#2f8d4e',
};
const fmtPct = v => v == null ? '—' : (v >= 0 ? '+' : '') + v.toFixed(1) + '%';
const fmtNo2 = v => v == null ? '—' : v.toExponential(2);

function getRoiId() {
  if (typeof window.ROI_ID === 'string') return window.ROI_ID;
  const u = new URL(window.location.href);
  return u.searchParams.get('id') || '';
}
function colorFor(s) {
  if (s === 'green') return PALETTE.green;
  if (s === 'red') return PALETTE.rust;
  if (s === 'yellow') return PALETTE.ochre;
  return PALETTE.grey;
}

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

(async function() {
  const id = getRoiId();
  const r = await fetch('../data/dashboard.json?_=' + Date.now());
  const d = await r.json();
  const m = d.metros[id];
  if (!m) {
    document.body.innerHTML = '<p style="padding:24px">Unknown metro: ' + id + '</p>';
    return;
  }
  document.title = m.name + ' — Smog Tracker';
  document.getElementById('metro-name').textContent = m.name;
  document.getElementById('metro-meta').textContent = m.dept + ' · ' + m.altitude;
  document.getElementById('last-updated').textContent =
    'Updated ' + d.last_updated + ' · last week ' + (d.last_week || '—');
  const dot = document.getElementById('current-dot');
  dot.className = 'dot ' + (m.status || 'grey');
  document.getElementById('current-yoy').textContent = fmtPct(m.current_yoy);
  document.getElementById('current-yoy').style.color = colorFor(m.status);

  // ---- raw NO₂ time series ----
  const lvl = m.level_series.filter(p => p.no2 != null);
  new Chart(document.getElementById('lvl-chart'), {
    type: 'line',
    data: {
      labels: lvl.map(p => p.week),
      datasets: [{
        label: 'Weekly NO₂',
        data: lvl.map(p => p.no2),
        borderColor: PALETTE.teal,
        backgroundColor: 'rgba(31,111,115,0.08)',
        borderWidth: 2, pointRadius: 0, tension: 0.25, fill: true, spanGaps: true,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: c => 'NO₂ ' + fmtNo2(c.parsed.y) + ' mol/m²' } },
      },
      scales: {
        y: { title: { display: true, text: 'mol/m²' }, grid: { color: 'rgba(120,120,120,0.12)' } },
        x: { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }, grid: { display: false } },
      },
    }
  });

  // ---- YoY anomaly chart ----
  const series = m.series;
  const gasolinazo = d.gasolinazo_date;
  const idxGas = series.findIndex(p => p.week >= gasolinazo);
  new Chart(document.getElementById('yoy-chart'), {
    type: 'line',
    data: {
      labels: series.map(p => p.week),
      datasets: [{
        label: 'YoY anomaly (%)',
        data: series.map(p => p.yoy),
        borderColor: PALETTE.teal,
        backgroundColor: 'rgba(31,111,115,0.10)',
        borderWidth: 2, pointRadius: 0, tension: 0.25, fill: true, spanGaps: true,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: c => 'YoY ' + fmtPct(c.parsed.y) } },
      },
      scales: {
        y: { title: { display: true, text: 'YoY anomaly (%)' },
             grid: { color: 'rgba(120,120,120,0.12)' } },
        x: { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }, grid: { display: false } },
      },
    },
    plugins: [{
      id: 'overlays',
      beforeDraw(chart) {
        const { ctx, chartArea, scales } = chart;
        if (!chartArea) return;
        const y5 = scales.y.getPixelForValue(5);
        const yN5 = scales.y.getPixelForValue(-5);
        ctx.save();
        ctx.fillStyle = 'rgba(150,150,150,0.10)';
        ctx.fillRect(chartArea.left, y5, chartArea.right - chartArea.left, yN5 - y5);
        ctx.fillStyle = 'rgba(161,61,45,0.10)';
        ctx.fillRect(chartArea.left, yN5, chartArea.right - chartArea.left, chartArea.bottom - yN5);
        const y0 = scales.y.getPixelForValue(0);
        ctx.strokeStyle = PALETTE.slate; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(chartArea.left, y0); ctx.lineTo(chartArea.right, y0); ctx.stroke();
        if (idxGas >= 0) {
          const xGas = scales.x.getPixelForValue(idxGas);
          ctx.strokeStyle = PALETTE.rust; ctx.setLineDash([5, 4]);
          ctx.beginPath(); ctx.moveTo(xGas, chartArea.top); ctx.lineTo(xGas, chartArea.bottom); ctx.stroke();
          ctx.setLineDash([]);
        }
        ctx.restore();
      }
    }]
  });

  // ---- recent-weeks table ----
  const tbody = document.getElementById('recent-tbody');
  for (const row of m.recent_weeks.slice().reverse()) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${row.week}</td>
      <td>${fmtNo2(row.no2)}</td>
      <td style="color:${colorFor(row.status)}">${fmtPct(row.yoy)}</td>
      <td><span class="dot ${row.status || 'grey'}"></span></td>
    `;
    tbody.appendChild(tr);
  }

  // ---- CSV download ----
  document.getElementById('csv-dl').addEventListener('click', e => {
    e.preventDefault();
    const rows = [['week', 'no2_mol_m2', 'yoy_pct', 'status']];
    for (const w of m.level_series) {
      const a = m.series.find(s => s.week === w.week);
      const t = m.recent_weeks.find(r => r.week === w.week);
      rows.push([w.week, w.no2 ?? '', a?.yoy ?? '', t?.status ?? '']);
    }
    const blob = new Blob([rows.map(r => r.join(',')).join('\n')], {type: 'text/csv'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url; link.download = id + '_weekly.csv';
    link.click();
  });
})();
