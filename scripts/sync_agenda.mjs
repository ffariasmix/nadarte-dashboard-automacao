// ============================================================
// Gera o SQL das iniciativas da semana para a Agenda Tática,
// lendo o freq_multi.json LOCAL (já gerado pelo pipeline do dashboard).
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
function anivSemana(bd,bm){ if(!bd||!bm) return false; const h=new Date();
  for(let d=0;d<7;d++){ const t=new Date(h); t.setDate(h.getDate()+d); if(t.getDate()===bd&&(t.getMonth()+1)===bm) return true; } return false; }
function tenure(dm){ if(!dm) return 0; const y=new Date(dm).getFullYear(); return y?(new Date().getFullYear()-y):0; }
function esc(s){ return String(s==null?'':s).replace(/'/g,"''"); }
function semanaISO(d=new Date()){ const dt=new Date(Date.UTC(d.getFullYear(),d.getMonth(),d.getDate())); const day=dt.getUTCDay()||7; dt.setUTCDate(dt.getUTCDate()+4-day); const y0=new Date(Date.UTC(dt.getUTCFullYear(),0,1)); const wk=Math.ceil((((dt-y0)/86400000)+1)/7); return `${dt.getUTCFullYear()}-W${String(wk).padStart(2,'0')}`; }
function prazo(){ const d=new Date(); d.setDate(d.getDate()+5); return d.toISOString().slice(0,10); }
function serie(ac,meses){ return meses.map((m,i)=>`${m}:${ac[i]??0}`).slice(-4).join(' · '); }

const data = JSON.parse(await readFile(FILE,'utf8'));
const students = data.students || [];
const meses = data.meses || [];
const tickets = data.tickets || {};
const semana = semanaISO();

const buckets = {};
const push=(slug,tipo,it)=>{ const k=`${slug}|${tipo}`; (buckets[k]||(buckets[k]=[])).push(it); };
const mk=(slug,cat,tipo,s,desc,rank=0)=>({ unidade_id:slug, categoria_id:cat, tipo, titulo:TITULO[tipo], prioridade:PRIO[tipo], aluno_nome:s.nome, matricula:String(s.mat||''), descricao:desc, rank });

for(const s of students){
  const slug=UNIDADE_SLUG[s.u]; if(!slug) continue;
  const cat=GRUPO_CAT[s.grupo]||'fitness';
  const mod=s.mod?` (${s.mod})`:'';
  if(anivSemana(s.bd,s.bm)) push(slug,'aniversario',mk(slug,cat,'aniversario',s,'Contato positivo de relacionamento, sem venda.'));
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
    rows.push(`('${id}','${esc(it.unidade_id)}','${esc(it.categoria_id)}','${esc(it.titulo)}','${esc(it.descricao)}','${esc(it.tipo)}','${esc(it.prioridade)}','${esc(it.aluno_nome)}','${esc(it.matricula)}','${semana}','${prazo()}','freq','pendente')`);
  }
}

const cols='(id,unidade_id,categoria_id,titulo,descricao,tipo,prioridade,aluno_nome,matricula,semana_ref,prazo,origem,status)';
const out=[];
out.push(`-- Sync Agenda · semana ${semana} · ${rows.length} iniciativas · ${new Date().toISOString()}`);
out.push(`DELETE FROM iniciativas WHERE origem='freq' AND semana_ref='${semana}' AND status='pendente';`);
for(let i=0;i<rows.length;i+=50){ out.push(`INSERT INTO iniciativas ${cols} VALUES\n`+rows.slice(i,i+50).join(',\n')+';'); }
process.stdout.write(out.join('\n')+'\n');
console.error(`[sync_agenda] semana ${semana}: ${rows.length} iniciativas.`);
