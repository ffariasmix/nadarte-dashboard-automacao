// ============================================================
// build_resumo.mjs — G3 Prontuário 360: materializa 1 resumo por aluno no D1.
// Lê o freq_multi.json (todos os alunos, com score/faixa/presença/recência/etc.)
// + o feed do App Treino (sinais de CRM) e emite SQL para a tabela alunos_resumo.
// Refresh total por semana (DELETE + INSERT OR REPLACE). NUNCA dropa a tabela.
// Uso: node scripts/build_resumo.mjs data/freq_multi.json > resumo.sql
// ============================================================
import { readFile } from 'node:fs/promises';
import { UNIDADE_SLUG, GRUPO_CAT } from './motor.mjs';

const FILE = process.argv[2] || process.env.FREQ_LOCAL_FILE || 'data/freq_multi.json';
const data = JSON.parse(await readFile(FILE, 'utf8'));
const students = Array.isArray(data.students) ? data.students : [];

// CRM (App Treino) — sinais por aluno. Se cair, segue sem CRM.
const APP_TREINO_FEED = process.env.APP_TREINO_FEED || 'https://nadarte-apptreino.pages.dev/agenda_treino.json';
const crmMap = new Map();
try {
  const resp = await fetch(APP_TREINO_FEED + '?cb=' + Date.now());
  if (resp.ok) {
    const f = await resp.json();
    for (const c of (Array.isArray(f.crm) ? f.crm : [])) crmMap.set(`${c.unidade}|${c.matricula}`, c);
    console.error(`[resumo] CRM: ${crmMap.size} alunos com sinal · feed ${f.gerado || '?'}.`);
  } else console.error(`[resumo] App Treino HTTP ${resp.status} — sem sinais de CRM.`);
} catch (e) { console.error(`[resumo] App Treino indisponível (${e.message}) — sem sinais de CRM.`); }

// Pedido 2 — app_status do roster completo: usaApp/treinoVencido por aluno ativo (todas as modalidades).
const APP_STATUS_FEED = process.env.APP_STATUS_FEED || 'https://nadarte-apptreino.pages.dev/app_status.json';
const appMap = new Map();
try {
  const resp2 = await fetch(APP_STATUS_FEED + '?cb=' + Date.now());
  if (resp2.ok) {
    const f2 = await resp2.json();
    for (const a of (Array.isArray(f2.alunos) ? f2.alunos : [])) appMap.set(`${a.unidade}|${a.matricula}`, a);
    console.error(`[resumo] app_status: ${appMap.size} alunos · feed ${f2.gerado || '?'}.`);
  } else console.error(`[resumo] app_status HTTP ${resp2.status} — sem status de app do roster.`);
} catch (e) { console.error(`[resumo] app_status indisponível (${e.message}) — sem status de app do roster.`); }

const hoje = new Date();
function mesesDesde(iso) {
  if (!iso) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso)); if (!m) return null;
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return Math.max(0, (hoje.getUTCFullYear() - d.getUTCFullYear()) * 12 + (hoje.getUTCMonth() - (d.getUTCMonth())));
}
const esc = s => String(s == null ? '' : s).replace(/'/g, "''");
const num = v => (v == null || v === '' || Number.isNaN(Number(v))) ? 'NULL' : Number(v);
const b01 = v => (v === true ? 1 : v === false ? 0 : 'NULL');

const cols = '(unidade_id,matricula,nome,categoria_id,foto,score,faixa,recencia,presenca_wk,data_matricula,venc,tempo_casa_meses,aniv_dia,aniv_mes,professor,usa_app,treino_vencido,app_parado,crm_faixa,atualizado_em)';
const AT = hoje.toISOString().slice(0, 10);

const rows = [];
for (const s of students) {
  const slug = UNIDADE_SLUG[s.u]; if (!slug) continue;
  const mat = String(s.mat || ''); if (!mat) continue;
  const cat = GRUPO_CAT[s.grupo] || 'outros';
  const key = `${slug}|${mat}`;
  const crm = crmMap.get(key) || null;
  const app = appMap.get(key) || null;
  // usaApp/treinoVencido: preferir o roster completo (app_status); fallback no feed acionável.
  const vUsaApp = app && app.usaApp !== undefined ? app.usaApp : (crm ? crm.usaApp : undefined);
  const vTreinoV = app && app.treinoVencido !== undefined ? app.treinoVencido : (crm ? (crm.treinoVencido || crm.avaliacaoVencida) : undefined);
  const vAppPar = crm ? crm.appParado : undefined;
  const wk = Array.isArray(s.wk) ? JSON.stringify(s.wk) : '[]';
  rows.push(`('${esc(slug)}','${esc(mat)}','${esc(s.nome)}','${esc(cat)}','${esc(s.foto || '')}',${num(s.score)},'${esc(s.scoreBand || '')}','${esc(s.ult || '')}','${esc(wk)}','${esc(s.dm || '')}','${esc(s.venc || '')}',${num(mesesDesde(s.dm))},${num(s.bd)},${num(s.bm)},'${esc(s.prof || '')}',${b01(vUsaApp)},${b01(vTreinoV)},${b01(vAppPar)},'${esc(crm ? (crm.faixa || '') : '')}','${AT}')`);
}

const out = [];
out.push(`-- Prontuário 360 · resumo por aluno · ${rows.length} alunos · ${new Date().toISOString()}`);
out.push('DELETE FROM alunos_resumo;');
for (let i = 0; i < rows.length; i += 50) out.push(`INSERT OR REPLACE INTO alunos_resumo ${cols} VALUES\n` + rows.slice(i, i + 50).join(',\n') + ';');
process.stdout.write(out.join('\n') + '\n');
console.error(`[resumo] ${rows.length} alunos materializados.`);
