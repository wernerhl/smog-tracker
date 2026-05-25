// Per-metro detail page. Reads ?id=<roi> from query string OR a global ROI_ID.
// Two charts (level + YoY) each show 28-day rolling (teal) + 7-day raw (thin gray).

console.log('[smog-tracker] metro.js loaded');

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

function overlayPlugin(idxGas) {
  return {
    id: 'overlays',
    beforeDraw(chart) {
      const { ctx, chartArea, scales } = chart;
      if (!chartArea) return;
      if (!scales.y || scales.y.min == null) return;
      const y5  = scales.y.getPixelForValue(5);
      const yN5 = scales.y.getPixelForValue(-5);
      ctx.save();
      // Only draw the bands on a YoY-scale chart (i.e. values around zero).
      if (Math.abs(scales.y.min) < 100 && Math.abs(scales.y.max) < 100) {
        ctx.fillStyle = 'rgba(150,150,150,0.10)';
        ctx.fillRect(chartArea.left, y5, chartArea.right - chartArea.left, yN5 - y5);
        ctx.fillStyle = 'rgba(161,61,45,0.10)';
        ctx.fillRect(chartArea.left, yN5, chartArea.right - chartArea.left, chartArea.bottom - yN5);
        const y0 = scales.y.getPixelForValue(0);
        ctx.strokeStyle = PALETTE.slate; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(chartArea.left, y0); ctx.lineTo(chartArea.right, y0); ctx.stroke();
      }
      if (idxGas >= 0) {
        const xGas = scales.x.getPixelForValue(idxGas);
        ctx.strokeStyle = PALETTE.rust; ctx.setLineDash([5, 4]);
        ctx.beginPath(); ctx.moveTo(xGas, chartArea.top); ctx.lineTo(xGas, chartArea.bottom); ctx.stroke();
        ctx.setLineDash([]);
      }
      ctx.restore();
    }
  };
}

(async function() {
  try {
    const id = getRoiId();
    const url = '../data/dashboard.json?_=' + Date.now();
    console.log('[smog-tracker] fetching', url, 'for', id);
    const r = await fetch(url);
    if (!r.ok) throw new Error('HTTP ' + r.status);
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
    const yoyEl = document.getElementById('current-yoy');
    yoyEl.textContent = fmtPct(m.current_yoy_28d);
    yoyEl.style.color = colorFor(m.status);
    const yoy7El = document.getElementById('current-yoy-7d');
    if (yoy7El) yoy7El.textContent = fmtPct(m.current_yoy_7d);

    // ---- raw NO₂ time series (level) ----
    const lvl = m.level_series || [];
    new Chart(document.getElementById('lvl-chart'), {
      type: 'line',
      data: {
        labels: lvl.map(p => p.week),
        datasets: [
          {
            label: '7-day raw NO₂',
            data: lvl.map(p => p.no2_7d),
            borderColor: 'rgba(120,120,120,0.45)',
            borderWidth: 1, pointRadius: 0, tension: 0.15, fill: false, spanGaps: false,
            order: 2,
          },
          {
            label: '28-day rolling NO₂',
            data: lvl.map(p => p.no2_28d),
            borderColor: PALETTE.teal,
            backgroundColor: 'rgba(31,111,115,0.10)',
            borderWidth: 2.5, pointRadius: 0, tension: 0.25, fill: true, spanGaps: false,
            order: 1,
          },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: true, position: 'top', labels: { boxWidth: 14 } },
          tooltip: { callbacks: { label: c => c.dataset.label + ': ' + fmtNo2(c.parsed.y) + ' mol/m²' } },
        },
        scales: {
          y: { title: { display: true, text: 'mol/m²' }, grid: { color: 'rgba(120,120,120,0.12)' } },
          x: { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }, grid: { display: false } },
        },
      }
    });

    // ---- YoY chart with gasolinazo line + ±5% band ----
    const series = m.series || [];
    const labels = series.map(p => p.week);
    const idxGas = labels.findIndex(l => l >= d.gasolinazo_date);
    new Chart(document.getElementById('yoy-chart'), {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: '7-day raw YoY',
            data: series.map(p => p.yoy_7d),
            borderColor: 'rgba(120,120,120,0.45)',
            borderWidth: 1, pointRadius: 0, tension: 0.15, fill: false, spanGaps: false,
            order: 2,
          },
          {
            label: '28-day rolling YoY',
            data: series.map(p => p.yoy_28d),
            borderColor: PALETTE.teal,
            backgroundColor: 'rgba(31,111,115,0.10)',
            borderWidth: 2.5, pointRadius: 0, tension: 0.25, fill: true, spanGaps: false,
            order: 1,
          },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: true, position: 'top', labels: { boxWidth: 14 } },
          tooltip: { callbacks: { label: c => c.dataset.label + ': ' + fmtPct(c.parsed.y) } },
        },
        scales: {
          y: { title: { display: true, text: 'YoY anomaly (%)' },
               grid: { color: 'rgba(120,120,120,0.12)' } },
          x: { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }, grid: { display: false } },
        },
      },
      plugins: [overlayPlugin(idxGas)],
    });

    // ---- recent-weeks table ----
    const tbody = document.getElementById('recent-tbody');
    for (const row of m.recent_weeks.slice().reverse()) {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${row.week}</td>
        <td>${fmtNo2(row.no2_28d)}</td>
        <td style="color:${colorFor(row.status)}">${fmtPct(row.yoy_28d)}</td>
        <td style="color:var(--muted)">${fmtPct(row.yoy_7d)}</td>
        <td><span class="dot ${row.status || 'grey'}"></span></td>
      `;
      tbody.appendChild(tr);
    }

    // ---- CSV download ----
    document.getElementById('csv-dl').addEventListener('click', e => {
      e.preventDefault();
      const rows = [['week', 'no2_28d_mol_m2', 'no2_7d_mol_m2', 'yoy_28d_pct', 'yoy_7d_pct', 'status']];
      for (const w of m.level_series) {
        const a = m.series.find(s => s.week === w.week) || {};
        const t = m.recent_weeks.find(r => r.week === w.week) || {};
        rows.push([w.week, w.no2_28d ?? '', w.no2_7d ?? '',
                   a.yoy_28d ?? '', a.yoy_7d ?? '', t.status ?? '']);
      }
      const blob = new Blob([rows.map(r => r.join(',')).join('\n')], {type: 'text/csv'});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url; link.download = id + '_weekly.csv';
      link.click();
    });
    console.log('[smog-tracker] metro page rendered');
  } catch (e) {
    console.error('[smog-tracker]', e);
    document.querySelector('main').innerHTML =
      '<p style="color:#A13D2D">Could not load metro data.</p><pre>' + String(e) + '</pre>';
  }
})();
