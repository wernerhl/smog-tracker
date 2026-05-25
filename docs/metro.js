// Per-metro detail page. Reads ?id=<roi> from query string OR a global ROI_ID.
// Charts: 1) monthly centered-12m (paper's indicator) 2) monthly NO₂ level

console.log('[smog-tracker] metro.js loaded');

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
    document.getElementById('last-updated').textContent = 'Updated ' + d.last_updated;

    const dot = document.getElementById('current-dot');
    dot.className = 'dot ' + (m.status || 'grey');
    const c12El = document.getElementById('current-c12');
    c12El.textContent = fmtDev(m.centered_12m) + ' log pts';
    c12El.style.color = colorFor(m.status);
    const c12Date = document.getElementById('c12-date');
    if (c12Date) c12Date.textContent = m.centered_12m_date || '—';
    const trailEl = document.getElementById('current-trail');
    if (trailEl) trailEl.textContent = fmtPct(m.trailing_yoy);

    // ---- Monthly chart (paper's indicator) ----
    const mseries = m.monthly_series || [];
    if (mseries.length > 0) {
      const labels = mseries.map(p => p.month);
      const gasMonth = '2025-12';
      const idxGas = labels.findIndex(l => l >= gasMonth);

      new Chart(document.getElementById('chart-monthly'), {
        type: 'line',
        data: {
          labels,
          datasets: [{
            label: 'Centered 12m (log dev from 2019)',
            data: mseries.map(p => p.log_dev_2019),
            borderColor: PALETTE.teal,
            backgroundColor: 'rgba(31,111,115,0.10)',
            borderWidth: 2.5, pointRadius: 0, tension: 0.3, fill: true, spanGaps: true,
          }],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: c => fmtDev(c.parsed.y) + ' log pts' } },
          },
          scales: {
            y: { title: { display: true, text: 'Log dev from 2019 (%)' },
                 grid: { color: 'rgba(120,120,120,0.12)' } },
            x: { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }, grid: { display: false } },
          },
        },
        plugins: [{
          id: 'monthlyOverlays',
          beforeDraw(chart) {
            const { ctx, chartArea, scales } = chart;
            if (!chartArea || !scales.y) return;
            ctx.save();
            const y0 = scales.y.getPixelForValue(0);
            ctx.strokeStyle = PALETTE.slate; ctx.lineWidth = 1.5;
            ctx.beginPath(); ctx.moveTo(chartArea.left, y0); ctx.lineTo(chartArea.right, y0); ctx.stroke();
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

    // ---- Monthly NO₂ level chart ----
    const lvlData = mseries.filter(p => p.no2 != null);
    if (lvlData.length > 0) {
      new Chart(document.getElementById('lvl-chart'), {
        type: 'line',
        data: {
          labels: lvlData.map(p => p.month),
          datasets: [{
            label: 'Monthly NO₂',
            data: lvlData.map(p => p.no2),
            borderColor: PALETTE.teal,
            backgroundColor: 'rgba(31,111,115,0.10)',
            borderWidth: 2, pointRadius: 0, tension: 0.25, fill: true, spanGaps: true,
          }],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: c => fmtNo2(c.parsed.y) + ' mol/m²' } },
          },
          scales: {
            y: { title: { display: true, text: 'mol/m²' }, grid: { color: 'rgba(120,120,120,0.12)' } },
            x: { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }, grid: { display: false } },
          },
        },
      });
    }

    // ---- CSV download ----
    document.getElementById('csv-dl').addEventListener('click', e => {
      e.preventDefault();
      const rows = [['month', 'no2_mol_m2', 'log_dev_2019']];
      for (const p of mseries) {
        rows.push([p.month, p.no2 ?? '', p.log_dev_2019 ?? '']);
      }
      const blob = new Blob([rows.map(r => r.join(',')).join('\n')], {type: 'text/csv'});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url; link.download = id + '_monthly.csv';
      link.click();
    });

    console.log('[smog-tracker] metro page rendered');
  } catch (e) {
    console.error('[smog-tracker]', e);
    document.querySelector('main').innerHTML =
      '<p style="color:#A13D2D">Could not load metro data.</p><pre>' + String(e) + '</pre>';
  }
})();
