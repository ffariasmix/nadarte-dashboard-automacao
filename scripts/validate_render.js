// Render headless do dashboard em jsdom com stub do Chart.js (secao 11 do runbook).
// Uso: node validate_render.js <arquivo.html> [expectedBase]
const fs = require('fs');
const { JSDOM, VirtualConsole } = require('jsdom');

const file = process.argv[2];
const expectedBase = process.argv[3] ? parseInt(process.argv[3], 10) : null;
let html = fs.readFileSync(file, 'utf8');

// Stub do Chart.js: precisa de getDatasetMeta()->{data:[]}, register, update, destroy.
function makeChartStub(win) {
  function Chart(ctx, cfg) { this.ctx = ctx; this.config = cfg; this.data = (cfg && cfg.data) || {}; }
  Chart.prototype.getDatasetMeta = function () { return { data: [] }; };
  Chart.prototype.update = function () {};
  Chart.prototype.destroy = function () {};
  Chart.prototype.resize = function () {};
  Chart.register = function () {};
  Chart.defaults = { font: {}, plugins: {}, set: function(){}, scale: {} };
  win.Chart = Chart;
}

const errors = [];
const vc = new VirtualConsole();
vc.on('jsdomError', e => errors.push('jsdomError: ' + (e && (e.message || e))));
vc.on('error', (...a) => errors.push('console.error: ' + a.join(' ')));

const dom = new JSDOM(html, {
  runScripts: 'dangerously',
  pretendToBeVisual: true,
  virtualConsole: vc,
  beforeParse(win) {
    makeChartStub(win);
    // canvas getContext stub
    win.HTMLCanvasElement.prototype.getContext = function () {
      return {
        canvas: this, fillRect(){}, clearRect(){}, getImageData(){return {data:[]};},
        putImageData(){}, createImageData(){return [];}, setTransform(){}, drawImage(){},
        save(){}, fillText(){}, restore(){}, beginPath(){}, moveTo(){}, lineTo(){},
        closePath(){}, stroke(){}, translate(){}, scale(){}, rotate(){}, arc(){},
        fill(){}, measureText(){return {width:0};}, transform(){}, rect(){}, clip(){},
        createLinearGradient(){return {addColorStop(){}};}, setLineDash(){},
      };
    };
    win.matchMedia = win.matchMedia || function(){ return { matches:false, addListener(){}, removeListener(){}, addEventListener(){}, removeEventListener(){} }; };
    win.requestAnimationFrame = win.requestAnimationFrame || (cb => setTimeout(cb, 0));
    // capturar window.onerror
    win.addEventListener('error', e => errors.push('window.error: ' + (e.message || e.error)));
  }
});

// dar tempo para handlers DOMContentLoaded
setTimeout(() => {
  const doc = dom.window.document;
  const win = dom.window;
  const tabs = doc.querySelectorAll('[data-tab]').length;
  const foot = (doc.getElementById('footMeta') || {}).textContent || '';
  const verbadge = (doc.querySelector('.verbadge') || {}).textContent || '';
  // KPI "Base de alunos" renderizada no DOM dos kpis (ex "Base de alunos4469...")
  const kpisText = (doc.getElementById('kpis') || {}).textContent || '';
  const bm = kpisText.match(/Base de alunos\s*([\d. ]+)/);
  const baseRendered = bm ? parseInt(bm[1].replace(/[. \s]/g, ''), 10) : null;

  let ok = true;
  const line = (cond, msg) => { if (!cond) ok = false; console.log((cond ? 'PASS ' : 'FALL ') + msg); };

  line(errors.length === 0, `zero erros de console/jsdom (achei ${errors.length})`);
  line(tabs === 9, `9 abas presentes (achei ${tabs})`);
  line(baseRendered !== null, `KPI "Base de alunos" renderizada (${baseRendered})`);
  if (expectedBase !== null) line(baseRendered === expectedBase, `Base = ${expectedBase} (renderizou ${baseRendered})`);
  line(/dados até/.test(foot) && /v\d/.test(foot), `rodape com carimbo: "${foot}"`);
  line(/v\d/.test(verbadge), `selo de versao: "${verbadge}"`);

  if (errors.length) { console.log('--- ERROS ---'); errors.slice(0,20).forEach(e=>console.log('  '+e)); }
  console.log('kpisText(trim)=' + kpisText.replace(/\s+/g,' ').trim().slice(0,160));
  console.log(ok ? '\nRESULTADO: VALIDACAO OK' : '\nRESULTADO: FALHOU');
  process.exit(ok ? 0 : 1);
}, 1500);
