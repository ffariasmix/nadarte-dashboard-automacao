// ============================================================
// Gera o SQL das iniciativas da Agenda Tática para a SEMANA SEGUINTE,
// lendo o freq_multi.json LOCAL (já gerado pelo pipeline do dashboard).
//
// Regra de negócio:
//   - Roda toda SEXTA 10:00 (BRT) — ver cron no build-deploy.yml.
//   - Olha para a SEMANA SEGUINTE, janela útil SEGUNDA a SEXTA
//     (sábado e domingo NÃO entram).
//   - semana_ref = semana ISO da próxima segunda; prazo = próxima sexta.
//
// Uso:  node scripts/sync_agenda.mjs data/freq_multi.json > agenda_week.sql
// ============================================================
import { readFile } from 'node:fs/promises';

const FILE = process.argv[2] || process.env.FREQ_LOCAL_FILE || 'data/freq_multi.json';

const UNIDADE_SLUG = { '716Norte':'716-norte','905Sul':'905-sul','604Norte':'604-norte','LagoNorte':'lago-norte','LagoSul':'lago-sul','Natal':'natal-rn' };
const GRUPO_CAT = { 'Água':'agua','Agua':'agua','Fitness':'fitness','Ambos':'ambos','Lutas e Outros':'lutas' };
const META_MES = { agua:6, lutas:6, fitness:12, ambos:12 };
const CAP = { em_risco:40, sumiu:20, caiu_ritmo:30, resgate:15, aniversario:9999 };
const TITULO = { em_risco:'Em risco de parar', sumiu:'Sumiu no mês', caiu_ritmo:'Aluno caiu de ritmo', aniversario:'Aniversariante da semana', resgate:'Resgate de alto valor' };
const PRIO = { em_risco:'Alta', sumiu:'Alta', caiu_ritmo:'Média', aniversario:'Baixa', resgate:'Alta' };

function classificar(ac,cat){
  if(!Array.isArray(ac)||ac.length<4) return null;
  const f=ac.slice(0,-1), n=f.length, ult=f[n-1], ant=f[n-2], base=f.slice(0,n-1);
  const media=base.reduce((a,b)=>a+b,0)/(base.length||1), tinha=media>=(META_MES[cat]||6)*0.5;
  if(ult===0&&ant===0) return 'em_risco';
  if(ult===0&&ant>0) return 'sumiu';
  if(tinha&&ult>0&&ult<media*0.6) return 'caiu_ritmo';
  return null;
}
// Segunda e sexta da SEMANA SEGUINTE (janela útil, ignora sábado/domingo).
function proxSemanaMonFri(base=new Date()){
  const d=new Date(Date.UTC(base.getUTCFullYear(),base.getUTCMonth(),base.getUTCDate()));
  const dow=(d.getUTCDay()+6)%7;               // 0=segunda ... 6=domingo
  const seg=new Date(d); seg.setUTCDate(d.getUTCDate()-dow+7); // segunda da semana seguinte
  const sex=new Date(seg); sex.setUTCDate(seg.getUTCDate()+4); // sexta da semana seguinte
  return { seg, sex };
}
// Aniversário caindo entre segunda e sexta da janela (sem sábado/domingo).
function anivNaJanela(bd,bm,ini,fim){ if(!bd||!bm) return false;
  for(let t=new Date(ini); t<=fim; t.setUTCDate(t.getUTCDate()+1)){
    if(t.getUTCDate()===bd && (t.getUTCMonth()+1)===bm) return true; } return false; }
function tenure(dm){ if(!dm) return 0; const y=new Date(dm).getFullYear(); return y?(new Date().getFullYear()-y):0; }
function esc(s){ return String(s==null?'':s).replace(/'/g,"''"); }
function semanaISO(d=new Date()){ const dt=new Date(Date.UTC(d.getUTCFullYear(),d.getUTCMonth(),d.getUTCDate())); const day=dt.getUTCDay()||7; dt.setUTCDate(dt.getUTCDate()+4-day); const y0=new Date(Date.UTC(dt.getUTCFullYear(),0,1)); const wk=Math.ceil((((dt-y0)/86400000)+1)/7); return `${dt.getUTCFullYear()}-W${String(wk).padStart(2,'0')}`; }
function serie(ac,meses){ return meses.map((m,i)=>`${m}:${ac[i]??0}`).slice(-4).join(' · '); }

const data = JSON.parse(await readFile(FILE,'utf8'));
const students = data.students || [];
const meses = data.meses || [];
const tickets = data.tickets || {};

const { seg: PROX_SEG, sex: PROX_SEX } = proxSemanaMonFri();
const semana = semanaISO(PROX_SEG);            // semana ISO da próxima segunda
const PRAZO = PROX_SEX.toISOString().slice(0,10); // sexta da semana seguinte

const buckets = {};
const push=(slug,tipo,it)=>{ const k=`${slug}|${tipo}`; (buckets[k]||(buckets[k]=[])).push(it); };
const mk=(slug,cat,tipo,s,desc,rank=0)=>({ unidade_id:slug, categoria_id:cat, tipo, titulo:TITULO[tipo], prioridade:PRIO[tipo], aluno_nome:s.nome, matricula:String(s.mat||''), descricao:desc, rank });

for(const s of students){
  const slug=UNIDADE_SLUG[s.u]; if(!slug) continue;
  const cat=GRUPO_CAT[s.grupo]||'fitness';
  const mod=s.mod?` (${s.mod})`:'';
  if(anivNaJanela(s.bd,s.bm,PROX_SEG,PROX_SEX)) push(slug,'aniversario',mk(slug,cat,'aniversario',s,'Contato positivo de relacionamento, sem venda.'));
  const tipo=classificar(s.ac,cat);
  if(tipo){
    let d;
    if(tipo==='em_risco') d=`Parou há 2+ meses${mod}. ${serie(s.ac,meses)}. Resgate urgente.`;
    else if(tipo==='sumiu') d=`Zerou o último mês fechado tendo vindo antes${mod}. ${serie(s.ac,meses)}. Contato antes de virar cancelamento.`;
    else d=`Caiu de ritmo${mod}. ${serie(s.ac,meses)}. Recolocar na rotina.`;
    push(slug,tipo,mk(slug,cat,tipo,s,d,tenure(s.dm)));
    if(tipo==='em_risco'||tipo==='sumiu'){
      const tk=tickets[s.u]; push(slug,'resgate',mk(slug,'comercial','resgate',s,`Cliente em risco com mais tempo de casa${tk?` · ticket ref. R$ ${tk}`:''}. Abordagem consultiva do comercial.`,tenure(s.dm)));
    }
  }
}

const rows=[];
for(const k of Object.keys(buckets)){
  const tipo=k.split('|')[1];
  let arr=buckets[k];
  if(['resgate','em_risco','sumiu'].includes(tipo)) arr.sort((a,b)=>(b.rank||0)-(a.rank||0));
  arr=arr.slice(0, CAP[tipo]||9999);
  for(const it of arr){
    const id=crypto.randomUUID();
    rows.push(`('${id}','${esc(it.unidade_id)}','${esc(it.categoria_id)}','${esc(it.titulo)}','${esc(it.descricao)}','${esc(it.tipo)}','${esc(it.prioridade)}','${esc(it.aluno_nome)}','${esc(it.matricula)}','${semana}','${PRAZO}','freq','pendente')`);
  }
}

const cols='(id,unidade_id,categoria_id,titulo,descricao,tipo,prioridade,aluno_nome,matricula,semana_ref,prazo,origem,status)';
const out=[];
out.push(`-- Sync Agenda · semana-alvo ${semana} (${PROX_SEG.toISOString().slice(0,10)} a ${PRAZO}) · ${rows.length} iniciativas · ${new Date().toISOString()}`);
out.push(`DELETE FROM iniciativas WHERE origem='freq' AND semana_ref='${semana}' AND status='pendente';`);
for(let i=0;i<rows.length;i+=50){ out.push(`INSERT INTO iniciativas ${cols} VALUES\n`+rows.slice(i,i+50).join(',\n')+';'); }
process.stdout.write(out.join('\n')+'\n');
console.error(`[sync_agenda] semana-alvo ${semana} (${PROX_SEG.toISOString().slice(0,10)} a ${PRAZO}): ${rows.length} iniciativas.`);
