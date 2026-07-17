// ============================================================
// Gera o SQL da Agenda pelo MOTOR (dedup 1 aluno=1 card, score, blocos),
// lendo o freq_multi.json LOCAL (Node — sem limite de tamanho).
// Roda na sexta (Actions). Semana-alvo: SEGUINTE, Seg→Dom.
// Uso:  node scripts/sync_agenda.mjs data/freq_multi.json > agenda_week.sql
// ============================================================
import { readFile } from 'node:fs/promises';
import { fromFrequencia, motor, UNIDADE_SLUG } from './motor.mjs';

const FILE = process.argv[2] || process.env.FREQ_LOCAL_FILE || 'data/freq_multi.json';
const data = JSON.parse(await readFile(FILE, 'utf8'));

function semanaVigenteMonDom(base = new Date()) {
  const d = new Date(Date.UTC(base.getUTCFullYear(), base.getUTCMonth(), base.getUTCDate()));
  const dow = (d.getUTCDay() + 6) % 7;
  const seg = new Date(d); seg.setUTCDate(d.getUTCDate() - dow);   // segunda-feira da semana VIGENTE (Build diário)
  const dom = new Date(seg); dom.setUTCDate(seg.getUTCDate() + 6);
  return { seg, dom };
}
function semISO(d) {
  const dt = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  const day = dt.getUTCDay() || 7; dt.setUTCDate(dt.getUTCDate() + 4 - day);
  const y0 = new Date(Date.UTC(dt.getUTCFullYear(), 0, 1));
  const wk = Math.ceil((((dt - y0) / 86400000) + 1) / 7);
  return `${dt.getUTCFullYear()}-W${String(wk).padStart(2, '0')}`;
}

const { seg, dom } = semanaVigenteMonDom();
const semana = semISO(seg);
const PRAZO = dom.toISOString().slice(0, 10);

const { freq, aniv } = fromFrequencia(data, seg, dom);

// Item 6 — funde os candidatos do App Treino (CRM) no MESMO motor (dedup 1 aluno=1 card).
// Feed publicado pelo repo App Treino (public/agenda_treino.json, servido pelo pages.dev).
// Se o feed cair, a sincronização segue normalmente só com os sinais de frequência.
const APP_TREINO_FEED = process.env.APP_TREINO_FEED || 'https://nadarte-apptreino.pages.dev/agenda_treino.json';
let crm = [];
try {
  const resp = await fetch(APP_TREINO_FEED + '?cb=' + Date.now());
  if (resp.ok) { const f = await resp.json(); crm = Array.isArray(f.crm) ? f.crm : [];
    console.error(`[sync_agenda] App Treino CRM: ${crm.length} candidatos · feed ${f.gerado || '?'}.`); }
  else console.error(`[sync_agenda] App Treino feed HTTP ${resp.status} — seguindo só com frequência.`);
} catch (e) { console.error(`[sync_agenda] App Treino feed indisponível (${e.message}) — seguindo só com frequência.`); }

// Bloco Operacional (Ocupação) — feed LOCAL gerado por build_ocupacao.py no mesmo Build.
// Se não existir, a agenda segue sem o bloco operacional.
const OCUP_FILE = process.env.OCUP_LOCAL_FILE || 'data/agenda_ocupacao.json';
let ocup = [];
try {
  const f = JSON.parse(await readFile(OCUP_FILE, 'utf8'));
  ocup = Array.isArray(f.ocup) ? f.ocup : [];
  console.error(`[sync_agenda] Ocupação: ${ocup.length} slots · feed ${f.gerado || '?'} (âncora ${f.ancora || '?'}).`);
} catch (e) { console.error(`[sync_agenda] feed de ocupação ausente (${e.message}) — seguindo sem bloco operacional.`); }

const r = motor({ freq, crm, aniv, ocup, cfg: { cap: Number(process.env.TETO_UNIDADE || 120) } });
const itens = [...r.alerta, ...r.ativa, ...r.reserva, ...r.relacionamento];

// F — valor em risco: venc (por aluno, do freq_multi) + valor_mensal (ticket médio da unidade).
const TICKETS = data.tickets || {};
const SLUG2KEY = Object.fromEntries(Object.entries(UNIDADE_SLUG).map(([k, v]) => [v, k]));
const valorUnidade = (slug) => { const t = TICKETS[SLUG2KEY[slug]]; return (t == null || Number.isNaN(Number(t))) ? 'NULL' : Number(t); };

const esc = s => String(s == null ? '' : s).replace(/'/g, "''");
const PRIO_FAIXA = { 'Crítico': 'Alta', 'Alto': 'Alta', 'Moderado': 'Média', 'Acompanhamento': 'Baixa', 'Relacionamento': 'Baixa' };
const TITULO_TIPO = { em_risco: 'Em risco de parar', sumiu: 'Sumiu no mês', caiu_ritmo: 'Caiu de ritmo', reengajar: 'Reengajar (app/treino)', aniversario: 'Aniversariante da semana' };
// 1º nome, capitalizado (nomes podem vir em CAIXA ALTA). Fallback neutro se vazio.
function primeiroNome(nome) {
  const p = String(nome || '').trim().split(/\s+/)[0];
  return p ? p.charAt(0).toUpperCase() + p.slice(1).toLowerCase() : 'Este aluno';
}
function descricaoHumana(it) {
  const ctx = it.motivos ? ` Sinais: ${it.motivos}.` : '';
  const n = primeiroNome(it.nome);
  if (it.tipo === 'em_risco') return `${n} vinha treinando e o ritmo caiu bastante nas últimas semanas.${ctx} Faça um contato de cuidado para entender se precisa de apoio para retomar a rotina.`;
  if (it.tipo === 'sumiu') return `${n} vinha treinando e parou no último mês.${ctx} Um contato acolhedor agora ajuda a evitar que se afaste.`;
  if (it.tipo === 'caiu_ritmo') return `A presença de ${n} diminuiu em relação ao ritmo habitual.${ctx} Vale um incentivo leve para recolocar na rotina.`;
  if (it.tipo === 'reengajar') return `${n} continua vindo à academia, mas largou o treino no app.${ctx} Recoloque no programa: mostrar um treino novo e o valor do acompanhamento antes que a frequência também caia.`;
  if (it.tipo === 'aniversario') return `${n} é aniversariante da semana — um contato positivo de relacionamento, sem venda.`;
  return `Contato de cuidado com ${n}.${ctx}`;
}
// Bloco operacional (Ocupação): tarefa por HORÁRIO, não por aluno.
const DIA_EXT = { sem: 'seg a sex', sab: 'aos sábados', dom: 'aos domingos' };
function descricaoOperacional(it) {
  const dlab = it.diaLabel || 'seg–sex';
  const dext = DIA_EXT[it.dia] || 'seg a sex';
  if (it.tipo === 'ocupacao_pico')
    return `Horário de maior fluxo: ${it.hora}h ${dext} com ~${it.media} entradas/dia (média da unidade ${it.mediaUnidade}/h, ${dlab}). Avaliar reforço de recepção/equipe e evitar manutenção nesse horário; fique de olho no conforto e na lotação.`;
  return `Horário de baixa procura: ${it.hora}h ${dext} com ~${it.media} entradas/dia (média da unidade ${it.mediaUnidade}/h, ${dlab}). Oportunidade: aula experimental, ação de captação/relacionamento ou manutenção programada nesse horário. (Estimativa de fluxo pela entrada na catraca, não ocupação simultânea.)`;
}

const cols = '(id,unidade_id,categoria_id,titulo,descricao,tipo,prioridade,aluno_nome,matricula,semana_ref,prazo,origem,status,foto,score,faixa,bloco,motivos,apoio_comercial,venc,valor_mensal)';
const rows = itens.map(it => {
  const prio = PRIO_FAIXA[it.faixa] || 'Média';
  const apoio = it.faixa === 'Crítico' ? 1 : 0;
  const sc = (it.score == null ? 'NULL' : Number(it.score));
  return `('${crypto.randomUUID()}','${esc(it.unidade)}','${esc(it.cat || 'outros')}','${esc(TITULO_TIPO[it.tipo] || it.titulo)}','${esc(descricaoHumana(it))}','${esc(it.tipo)}','${esc(prio)}','${esc(it.nome)}','${esc(it.matricula)}','${semana}','${PRAZO}','motor','pendente','${esc(it.foto || '')}',${sc},'${esc(it.faixa || '')}','${esc(it.bloco || '')}','${esc(it.motivos || '')}',${apoio},'${esc(it.venc || '')}',${valorUnidade(it.unidade)})`;
});

// Linhas do bloco OPERACIONAL (Ocupação): não-nominal (sem aluno/matrícula/score/faixa).
const opRows = (r.operacional || []).map(it => {
  const pico = it.tipo === 'ocupacao_pico';
  const diaPfx = (it.dia && it.dia !== 'sem') ? (it.diaLabel || it.dia) + ' ' : '';
  const titulo = `Horário ${pico ? 'de pico' : 'ocioso'} · ${diaPfx}${it.hora}h`;
  return `('${crypto.randomUUID()}','${esc(it.unidade)}','operacional','${esc(titulo)}','${esc(descricaoOperacional(it))}','${esc(it.tipo)}','Média','','','${semana}','${PRAZO}','motor','pendente','',NULL,'','operacional','${esc(it.motivos || '')}',0,'',NULL)`;
});
rows.push(...opRows);

const out = [];
out.push(`-- Motor · semana-alvo ${semana} (${seg.toISOString().slice(0,10)} a ${PRAZO}) · ${rows.length} iniciativas · ${new Date().toISOString()}`);
out.push(`DELETE FROM iniciativas WHERE semana_ref='${semana}' AND origem IN ('motor','freq') AND status='pendente';`);
// Housekeeping: remove cards PENDENTES do motor de outras semanas (resíduo antigo).
// Preserva os REALIZADOS (histórico de contatos) em qualquer semana.
out.push(`DELETE FROM iniciativas WHERE origem='motor' AND status='pendente' AND semana_ref<>'${semana}';`);
for (let i = 0; i < rows.length; i += 50) out.push(`INSERT INTO iniciativas ${cols} VALUES\n` + rows.slice(i, i + 50).join(',\n') + ';');
process.stdout.write(out.join('\n') + '\n');
console.error(`[motor] semana ${semana} (prazo ${PRAZO}): ${rows.length} · alerta ${r.alerta.length} · ativa ${r.ativa.length} · reserva ${r.reserva.length} · relac ${r.relacionamento.length} · operacional ${(r.operacional||[]).length} · descartadas ${r.descartadas}`);
