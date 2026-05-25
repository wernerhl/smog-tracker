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
  ‘national-title’:       { en: ‘National aggregate — year-over-year growth’,
                            es: ‘Agregado nacional — crecimiento interanual’ },
  ‘kpi-c12-yoy’:          { en: ‘Centered 12m YoY’,                    es: ‘Centrado 12m interanual’ },
  'kpi-trail':            { en: 'Trailing 12m YoY',                    es: 'Rezagado 12m interanual' },
  'kpi-asof':             { en: 'As of',                               es: 'Al' },
  'caption-monthly':      { en: '<b>Year-over-year growth</b> of 12-month rolling NO₂ (%). Population-weighted national aggregate. Zero = no change vs prior year. Dashed line = Dec 2025 (gasolinazo).',
                            es: '<b>Crecimiento interanual</b> del NO₂ promedio de 12 meses (%). Agregado nacional ponderado por población. Cero = sin cambio vs año anterior. Línea punteada = dic. 2025 (gasolinazo).' },

  // ── Metro section ──────────────────────────────────────────────
  'metros-title':         { en: 'Metropolitan areas',                  es: 'Áreas metropolitanas' },

  // ── Footer ─────────────────────────────────────────────────────
  'footer':               { en: 'Data: Copernicus Sentinel-5P TROPOMI OFFL L3 NO₂ · Updated every Sunday 06:00 UTC via GitHub Actions · Code MIT, data CC-BY 4.0 ·',
                            es: 'Datos: Copernicus Sentinel-5P TROPOMI OFFL L3 NO₂ · Actualizado cada domingo 06:00 UTC vía GitHub Actions · Código MIT, datos CC-BY 4.0 ·' },

  // ── Chart labels (used via T()) ─────────────────────────────────
  'chart-trailing':       { en: 'Trailing 12m YoY',                    es: 'Rezagado 12m interanual' },
  'chart-centered':       { en: 'Centered 12m YoY',                    es: 'Centrado 12m interanual' },
  'chart-yaxis-yoy':      { en: 'YoY anomaly (%)',                     es: 'Anomalía interanual (%)' },

  // ── Metro detail page ──────────────────────────────────────────
  'back-link':            { en: '← all metros',                   es: '← todas las ciudades' },
  ‘kpi-dept’:             { en: ‘Department’,                          es: ‘Departamento’ },
  ‘metro-chart-c12’:      { en: ‘Year-over-year growth’,               es: ‘Crecimiento interanual’ },
  'metro-chart-lvl':      { en: 'Monthly NO₂ level',             es: 'Nivel mensual de NO₂' },
  'caption-metro-c12':    { en: 'YoY growth of centered and trailing 12-month NO₂ (%). Zero = no change vs prior year.',
                            es: 'Crecimiento interanual del NO₂ centrado y rezagado de 12 meses (%). Cero = sin cambio vs año anterior.' },
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
