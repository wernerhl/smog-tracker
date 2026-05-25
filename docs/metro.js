// Per-metro detail page. Reads ?id=<roi> from query string OR a global ROI_ID.
// Charts: 1) YoY growth (centered + trailing) 2) monthly NO₂ level
// i18n.js must be loaded before this file.

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

let _chartC12 = null, _chartLvl = null, _metroData = null, _metroId = null;

function renderMetroPage(d, m, id) {
  document.title = m.name + ' — Smog Tracker';
  document.getElementById('metro-name').textContent = m.name;
  document.getElementById('metro-meta').textContent = m.dept + ' · ' + m.altitude;
  document.getElementById('last-updated').textContent = T('updated') + ' ' + d.last_updated;

  const dot = document.getElementById('current-dot');
  dot.className = 'dot ' + (m.status || 'grey');
  const c12El = document.getElementById('current-c12');
  c12El.textContent = fmtPct(m.centered_yoy);
  c12El.style.color = colorFor(m.status);
  const c12Date = document.getElementById('c12-date');
  if (c12Date) c12Date.textContent = m.centered_yoy_date || '—';
  const trailEl = document.getElementById('current-trail');
  if (trailEl) trailEl.textContent = fmtPct(m.trailing_yoy);

  // ---- YoY growth chart ----
  const mseries = m.monthly_series || [];
  if (mseries.length > 0) {
    const labels = mseries.map(p => p.month);
    const gasMonth = '2025-12';
    const idxGas = labels.findIndex(l => l >= gasMonth);

    if (_chartC12) _chartC12.destroy();
    _chartC12 = new Chart(document.getElementById('chart-monthly'), {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: T('chart-trailing'),
            data: mseries.map(p => p.trailing_yoy),
            borderColor: 'rgba(120,120,120,0.45)',
            borderWidth: 1, tension: 0.2, pointRadius: 0,
            spanGaps: true, fill: false, order: 2,
          },
          {
            label: T('chart-centered'),
            data: mseries.map(p => p.centered_yoy),
            borderColor: PALETTE.teal,
            backgroundColor: 'rgba(31,111,115,0.10)',
            borderWidth: 2.5, pointRadius: 0, tension: 0.3, fill: true, spanGaps: true,
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
          y: { title: { display: true, text: T('chart-yaxis-yoy') },
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

  // ---- Monthly NO₂ level chart ----
  const lvlData = mseries.filter(p => p.no2 != null);
  if (lvlData.length > 0) {
    if (_chartLvl) _chartLvl.destroy();
    _chartLvl = new Chart(document.getElementById('lvl-chart'), {
      type: 'line',
      data: {
        labels: lvlData.map(p => p.month),
        datasets: [{
          label: T('metro-chart-lvl'),
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
}

// Rebuild on language change
window._rebuildCharts = function() {
  if (_metroData && _metroData.metros[_metroId]) {
    renderMetroPage(_metroData, _metroData.metros[_metroId], _metroId);
  }
};

(async function() {
  try {
    _metroId = getRoiId();
    const url = '../data/dashboard.json?_=' + Date.now();
    console.log('[smog-tracker] fetching', url, 'for', _metroId);
    const r = await fetch(url);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    _metroData = await r.json();
    const m = _metroData.metros[_metroId];
    if (!m) {
      document.body.innerHTML = '<p style="padding:24px">Unknown metro: ' + _metroId + '</p>';
      return;
    }

    renderMetroPage(_metroData, m, _metroId);

    // ---- CSV download ----
    document.getElementById('csv-dl').addEventListener('click', e => {
      e.preventDefault();
      const mseries = m.monthly_series || [];
      const rows = [['month', 'no2_mol_m2', 'centered_yoy', 'trailing_yoy']];
      for (const p of mseries) {
        rows.push([p.month, p.no2 ?? '', p.centered_yoy ?? '', p.trailing_yoy ?? '']);
      }
      const blob = new Blob([rows.map(r => r.join(',')).join('\n')], {type: 'text/csv'});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url; link.download = _metroId + '_monthly.csv';
      link.click();
    });

    console.log('[smog-tracker] metro page rendered');
  } catch (e) {
    console.error('[smog-tracker]', e);
    document.querySelector('main').innerHTML =
      '<p style="color:#A13D2D">Could not load metro data.</p><pre>' + String(e) + '</pre>';
  }
})();
