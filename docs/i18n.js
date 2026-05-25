// Internationalization — English / Spanish toggle.
// Persisted in localStorage. Elements with data-i18n="key" get their
// textContent swapped. Chart labels use T('key') at render time.

const STRINGS = {
  // ── Header / nav ────────────────────────────────────────────────
  'site-subtitle':        { en: 'Bolivia Economic Activity Monitor',   es: 'Monitor de Actividad Económica de Bolivia' },
  'tagline':              { en: 'Tropospheric NO₂ from Sentinel-5P TROPOMI over 11 Bolivian metropolitan areas. A real-time combustion-activity proxy. Companion to',
                            es: 'NO₂ troposférico de Sentinel-5P TROPOMI sobre 11 áreas metropolitanas bolivianas. Proxy de actividad de combustión en tiempo real. Complemento de' },
  'updated':              { en: 'Updated',                             es: 'Actualizado' },

  // ── National panel ──────────────────────────────────────────────
  'national-title':       { en: "National aggregate — the paper’s indicator",
                            es: "Agregado nacional — indicador del paper" },
  'kpi-c12':              { en: 'Centered 12-month',                   es: 'Centrado 12 meses' },
  'kpi-trail':            { en: 'Trailing 12m YoY',                    es: 'Rezagado 12m interanual' },
  'kpi-asof':             { en: 'As of',                               es: 'Al' },
  'caption-monthly':      { en: '<b>Centered 12-month rolling NO₂</b>, log deviation from 2019 mean (%). This is Figure 2 from the paper, updated monthly. Population-weighted national aggregate. Dashed line = Dec 2025 (gasolinazo). 0 = 2019 baseline.',
                            es: '<b>NO₂ promedio centrado de 12 meses</b>, desviación logarítmica respecto a la media de 2019 (%). Figura 2 del paper, actualizada mensualmente. Agregado nacional ponderado por población. Línea punteada = dic. 2025 (gasolinazo). 0 = línea base 2019.' },

  // ── Trailing 12m supplement ──────────────────────────────────────
  'trailing-title':       { en: 'Trailing 12-month year-over-year',    es: 'Interanual rezagado de 12 meses' },
  'caption-trailing':     { en: '<b>Trailing 12-month YoY growth</b> in log points (%). Negative = economic activity contracting vs prior year. Dashed line = Dec 2025 (gasolinazo).',
                            es: '<b>Crecimiento interanual rezagado de 12 meses</b> en puntos logarítmicos (%). Negativo = actividad económica contrayéndose vs año anterior. Línea punteada = dic. 2025 (gasolinazo).' },

  // ── Metro section ──────────────────────────────────────────────
  'metros-title':         { en: 'Metropolitan areas',                  es: 'Áreas metropolitanas' },
  'log-pts-label':        { en: 'log pts vs 2019 at',                  es: 'pts log vs 2019 al' },

  // ── Footer ─────────────────────────────────────────────────────
  'footer':               { en: 'Data: Copernicus Sentinel-5P TROPOMI OFFL L3 NO₂ · Updated every Sunday 06:00 UTC via GitHub Actions · Code MIT, data CC-BY 4.0 ·',
                            es: 'Datos: Copernicus Sentinel-5P TROPOMI OFFL L3 NO₂ · Actualizado cada domingo 06:00 UTC vía GitHub Actions · Código MIT, datos CC-BY 4.0 ·' },

  // ── Chart labels (used via T()) ─────────────────────────────────
  'chart-trailing':       { en: 'Trailing 12m YoY',                    es: 'Rezagado 12m interanual' },
  'chart-centered':       { en: 'Centered 12-month (log dev from 2019)', es: 'Centrado 12 meses (desv. log vs 2019)' },
  'chart-yaxis-logdev':   { en: 'Log dev from 2019 (%)',               es: 'Desv. log vs 2019 (%)' },
  'chart-yaxis-yoy':      { en: 'YoY anomaly (%)',                     es: 'Anomalía interanual (%)' },
  'chart-28d-yoy':        { en: '28-day rolling YoY (%)',              es: 'Interanual móvil 28 días (%)' },
  'log-pts':              { en: 'log pts',                             es: 'pts log' },

  // ── Metro detail page ──────────────────────────────────────────
  'back-link':            { en: '← all metros',                   es: '← todas las ciudades' },
  'kpi-dept':             { en: 'Department',                          es: 'Departamento' },
  'metro-chart-c12':      { en: "Paper’s indicator: centered 12-month", es: 'Indicador del paper: centrado 12 meses' },
  'metro-chart-lvl':      { en: 'Monthly NO₂ level',             es: 'Nivel mensual de NO₂' },
  'caption-metro-c12':    { en: 'log(centered 12m NO₂ / 2019 mean) × 100. Zero = 2019 baseline.',
                            es: 'log(NO₂ centrado 12m / media 2019) × 100. Cero = línea base 2019.' },
  'caption-metro-lvl':    { en: 'Monthly mean NO₂ (mol/m²).',  es: 'NO₂ promedio mensual (mol/m²).' },
  'download-csv':         { en: 'Download CSV',                       es: 'Descargar CSV' },
};

let _lang = localStorage.getItem('smog-lang') || 'en';

function T(key) {
  const s = STRINGS[key];
  if (!s) return key;
  return s[_lang] || s.en;
}

function getLang() { return _lang; }

function setLang(lang) {
  _lang = lang;
  localStorage.setItem('smog-lang', lang);
  document.documentElement.setAttribute('lang', lang);
  applyLang();
}

function applyLang() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const mode = el.getAttribute('data-i18n-html');
    const val = T(key);
    if (mode === 'true') el.innerHTML = val;
    else el.textContent = val;
  });
  // Update lang toggle button text
  const btn = document.getElementById('lang-toggle');
  if (btn) btn.textContent = _lang === 'en' ? 'ES' : 'EN';
}

// Init on load
(function() {
  if (_lang !== 'en') document.documentElement.setAttribute('lang', _lang);
  document.addEventListener('DOMContentLoaded', () => {
    applyLang();
    const btn = document.getElementById('lang-toggle');
    if (btn) {
      btn.addEventListener('click', e => {
        e.preventDefault();
        setLang(_lang === 'en' ? 'es' : 'en');
        // Signal charts need rebuild
        if (typeof window._rebuildCharts === 'function') window._rebuildCharts();
      });
    }
  });
})();
