// ============================================================
// Gera o SQL das iniciativas da Agenda Tática para a SEMANA SEGUINTE,
// lendo o freq_multi.json LOCAL (já gerado pelo pipeline do dashboard).
//
// Regra de negócio:
//   - Roda toda SEXTA 10:00 (BRT) — ver cron no build-deploy.yml.
//   - Olha para a SEMANA SEGUINTE, janela SEGUNDA a DOMINGO
//     (semana inteira, incluindo sábado e domingo).
//   - semana_ref = semana ISO da próxima segunda; prazo = próximo domingo.
//
// Uso:  node scripts/sync_agenda.mjs data/freq_multi.json > agenda_week.sql
// ============================================================
import { readFile } from 'node:fs/promises';

const FILE = process.argv[2] || process.env.FREQ_LOCAL_FILE || 'data/freq_multi.json';

const UNIDADE_SLUG = { '716Norte':'716-norte','905Sul':'905-sul','604Norte':'604-norte','LagoNorte':'lago-norte','LagoSul':'lago-sul','Natal':'natal-rn' };
const GRUPO_CAT = { 'Água':'agua','Agua':'agua','Fitness':'fitness','Luta':'lutas','Lutas':'lutas','Lutas e Outros':'lutas','Ambos':'ambos','Ambos (Água + Fitness)':'ambos_af','Ambos (Agua + Fitness)':'ambos_af','Ambos (Água + Luta)':'ambos_al','Ambos (Agua + Luta)':'ambos_al','Ambos (Fitness + Luta)':'ambos_fl','Ambos (Água + Fitness + Luta)':'ambos_afl','Ambos (Agua + Fitness + Luta)':'ambos_afl','Outros':'outros' };
const META_MES = { agua:6, lutas:6, fitness:12, ambos:12 };
const CAP = { em_risco:40, sumiu:20, caiu_ritmo:30, resgate:15, aniversario:9999 };
const TITULO = { em_risco:'Em risco de parar', sumiu:'Sumiu no mês', caiu_ritmo:'Aluno caiu de ritmo', aniversario:'Aniversariante da semana', resgate:'Resgate de alto valor' };
const PRIO = { em_risco:'Alta', sumiu:'Alta', caiu_ritmo:'Média', aniversario:'Baixa', resgate:'Alta' };
// Onda 2: score vem do build (fonte única). Prioridade P0-P3 mapeada p/ o vocabulário da Agenda; SLA por prioridade.
const SLA = { P0:'48h', P1:'96h', P2:'esta semana', P3:'—' };  // ajustado à capacidade (~40 P0/unidade/semana)
const PRIO_FROM_SCORE = { P0:'Alta', P1:'Alta', P2:'Média', P3:'Baixa' };

// ── Mapa de capacidade: "esta unidade MEDE frequência nesta categoria?" ──
// Sem catraca ≠ zero visitas. Onde não há medição, NÃO classificamos churn por
// frequência (evita falsos "em risco/sumiu/caiu ritmo"). Ex.: Lago Norte não tem
// catraca na piscina → aluno de água PURO (cat 'agua') não gera registro. "Ambos"
// (água + musculação) segue medido pela catraca da musculação, então não entra aqui.
// Chave = slug da unidade → { categoria: true=SEM catraca }. Ausência = mede.
const SEM_CATRACA = { 'lago-norte': { agua:true } };
const medeFreq = (slug,cat)=> !(SEM_CATRACA[slug] && SEM_CATRACA[slug][cat]);

function classificar(ac,cat){
  if(!Array.isArray(ac)||ac.length<4) return null;
  const f=ac.slice(0,-1), n=f.length, ult=f[n-1], ant=f[n-2], base=f.slice(0,n-1);
  const media=base.reduce((a,b)=>a+b,0)/(base.length||1), tinha=media>=(META_MES[cat]||6)*0.5;
  if(ult===0&&ant===0) return 'em_risco';
  if(ult===0&&ant>0) return 'sumiu';
  if(tinha&&ult>0&&ult<media*0.6) return 'caiu_ritmo';
  return null;
}
// Segunda e domingo da SEMANA SEGUINTE (semana inteira).
function proxSemanaMonDom(base=new Date()){
  const d=new Date(Date.UTC(base.getUTCFullYear(),base.getUTCMonth(),base.getUTCDate()));
  const dow=(d.getUTCDay()+6)%7;               // 0=segunda ... 6=domingo
  const seg=new Date(d); seg.setUTCDate(d.getUTCDate()-dow+7); // segunda da semana seguinte
  const dom=new Date(seg); dom.setUTCDate(seg.getUTCDate()+6); // domingo da semana seguinte
  return { seg, dom };
}
// Aniversário caindo entre segunda e domingo da janela (semana inteira).
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

const { seg: PROX_SEG, dom: PROX_DOM } = proxSemanaMonDom();
const semana = semanaISO(PROX_SEG);            // semana ISO da próxima segunda
const PRAZO = PROX_DOM.toISOString().slice(0,10); // domingo da semana seguinte

const buckets = {};
const push=(slug,tipo,it)=>{ const k=`${slug}|${tipo}`; (buckets[k]||(buckets[k]=[])).push(it); };
const mk=(slug,cat,tipo,s,desc,rank=0)=>{
  const isRisk = tipo!=='aniversario';
  const sp=s.scorePrio, scv=s.score, cf=s.scoreConf;
  const prioridade = (isRisk&&sp)?(PRIO_FROM_SCORE[sp]||PRIO[tipo]):PRIO[tipo];
  const tag = (isRisk&&scv!=null)?`[Score ${scv} · ${sp} · conf. ${cf} · SLA ${SLA[sp]||'—'}] `:'';
  const rk = (isRisk&&scv!=null)?scv:rank;   // ordena a fila da Agenda pelo score (mais alto primeiro)
  return { unidade_id:slug, categoria_id:cat, tipo, titulo:TITULO[tipo], prioridade, aluno_nome:s.nome, matricula:String(s.mat||''), descricao:tag+desc, rank:rk, venc:(s.venc||''), valor_mensal:(tickets[s.u]||''), foto:(s.foto||'') };
};

for(const s of students){
  const slug=UNIDADE_SLUG[s.u]; if(!slug) continue;
  const cat=GRUPO_CAT[s.grupo]||'outros';
  const mod=s.mod?` (${s.mod})`:'';
  if(anivNaJanela(s.bd,s.bm,PROX_SEG,PROX_DOM)) push(slug,'aniversario',mk(slug,cat,'aniversario',s,'Contato positivo de relacionamento, sem venda.'));
  // Sem catraca nessa categoria (ex.: água pura no Lago Norte) → só aniversário,
  // nunca churn por frequência. Aniversário acima segue valendo para todos.
  const tipo=medeFreq(slug,cat)?classificar(s.ac,cat):null;
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
    rows.push(`('${id}','${esc(it.unidade_id)}','${esc(it.categoria_id)}','${esc(it.titulo)}','${esc(it.descricao)}','${esc(it.tipo)}','${esc(it.prioridade)}','${esc(it.aluno_nome)}','${esc(it.matricula)}','${semana}','${PRAZO}','freq','pendente','${esc(it.venc)}',${it.valor_mensal!==''&&it.valor_mensal!=null?Number(it.valor_mensal):'NULL'},'${esc(it.foto)}')`);
  }
}

const cols='(id,unidade_id,categoria_id,titulo,descricao,tipo,prioridade,aluno_nome,matricula,semana_ref,prazo,origem,status,venc,valor_mensal,foto)';
const out=[];
out.push(`-- Sync Agenda · semana-alvo ${semana} (${PROX_SEG.toISOString().slice(0,10)} a ${PRAZO}) · ${rows.length} iniciativas · ${new Date().toISOString()}`);
out.push(`DELETE FROM iniciativas WHERE origem='freq' AND semana_ref='${semana}' AND status='pendente';`);
for(let i=0;i<rows.length;i+=50){ out.push(`INSERT INTO iniciativas ${cols} VALUES\n`+rows.slice(i,i+50).join(',\n')+';'); }
process.stdout.write(out.join('\n')+'\n');
console.error(`[sync_agenda] semana-alvo ${semana} (${PROX_SEG.toISOString().slice(0,10)} a ${PRAZO}): ${rows.length} iniciativas.`);
