// ============================================================
// Motor Multi-Fonte (núcleo) — Agenda Tática Nad'Arte
// Puro, sem I/O. Decisões: 1 aluno=1 card · máx 2 principais + aniversário ·
// score explicável · teto/unidade · Alerta(Crítico) · Reserva(alto acima do teto).
// ============================================================

export const PTS = { em_risco:90, sumiu:80, caiu_ritmo:55, crm_app_parado:52, crm_risco:42, crm_venc_tec:30, crm_morno:21, crm_semapp:18 };
export const TITULO = {
  em_risco:'Em risco de parar', sumiu:'Sumiu no mês', caiu_ritmo:'Caiu de ritmo',
  reengajar:'Reengajar (app/treino)', aniversario:'Aniversariante da semana',
  ocupacao_ocioso:'Horário ocioso', ocupacao_pico:'Horário de pico' };
const META_MES = { agua:6, lutas:6, fitness:12, ambos:12, ambos_af:12, ambos_al:9, ambos_fl:12, ambos_afl:12, outros:6 };

// acessos mensais -> tipo de churn (mesma lógica do dashboard/sync)
export function classifFreq(ac, cat){
  if(!Array.isArray(ac)||ac.length<4) return null;
  const f=ac.slice(0,-1), n=f.length, ult=f[n-1], ant=f[n-2], base=f.slice(0,n-1);
  const media=base.reduce((a,b)=>a+b,0)/(base.length||1), tinha=media>=(META_MES[cat]||6)*0.5;
  if(ult===0&&ant===0) return 'em_risco';
  if(ult===0&&ant>0) return 'sumiu';
  if(tinha&&ult>0&&ult<media*0.6) return 'caiu_ritmo';
  return null;
}
export function score(pts){ if(!pts.length) return 0; const m=Math.max(...pts);
  return Math.min(100, Math.round(m + 0.30*(pts.reduce((a,b)=>a+b,0)-m))); }
// faixas da auditoria (churn). Relacionamento é trilha à parte (não é risco).
export function faixa(s){ return s>=85?'Crítico':s>=70?'Alto':s>=45?'Moderado':'Acompanhamento'; }

// motor: candidatos por cliente já normalizados -> blocos por unidade
// freq: [{unidade,matricula,nome,cat,foto,tipo}]  · crm: [{unidade,matricula,nome,faixa,usaApp,...}]
// aniv: [{unidade,matricula,nome}] · ocup: [{unidade,dia,hora,media,media_unidade,status}] · cfg:{cap,alertaMin,reservaMin}
export function motor({freq=[], crm=[], aniv=[], ocup=[], cfg={}}){
  const cap=cfg.cap??120, alertaMin=cfg.alertaMin??70, reservaMin=cfg.reservaMin??70, alertaTop=cfg.alertaTop??15;
  const K=c=>`${c.unidade}|${c.matricula}`;
  const cli=new Map();
  const get=c=>{const k=K(c); if(!cli.has(k)) cli.set(k,{unidade:c.unidade,matricula:c.matricula,nome:c.nome,cat:c.cat,foto:c.foto||'',pts:[],tipos:[],motivos:[],fontes:new Set()}); return cli.get(k);};
  for(const s of freq){ if(!s.tipo) continue; const o=get(s); if(s.foto)o.foto=s.foto; o.cat=o.cat||s.cat;
    o.pts.push(PTS[s.tipo]); o.tipos.push(s.tipo); o.fontes.add('frequencia');
    o.motivos.push(s.tipo==='em_risco'?'parou 2+ meses':s.tipo==='sumiu'?'zerou o último mês':'ritmo caiu'); }
  for(const s of crm){ const o=get(s); let u=false;
    if(s.faixa==='risco'){o.pts.push(PTS.crm_risco);o.motivos.push('CRM: faixa risco');u=true;}
    else if(s.faixa==='morno'){o.pts.push(PTS.crm_morno);o.motivos.push('CRM: faixa morno');u=true;}
    if(s.treinoVencido||s.avaliacaoVencida){o.pts.push(PTS.crm_venc_tec);o.motivos.push('treino/avaliação vencidos');u=true;}
    if(s.appParado){o.pts.push(PTS.crm_app_parado);o.motivos.push('vem à academia mas parou o treino no app');u=true;}
    if(s.usaApp===false){o.pts.push(PTS.crm_semapp);o.motivos.push('não usa o app');u=true;}
    if(u)o.fontes.add('crm'); }

  const churnKeys=new Set(cli.keys());
  const itens=[...cli.values()].map(o=>{ const s=score(o.pts);
    const tp=o.tipos.includes('em_risco')?'em_risco':o.tipos.includes('sumiu')?'sumiu':o.tipos.includes('caiu_ritmo')?'caiu_ritmo':'reengajar';
    return {unidade:o.unidade,matricula:o.matricula,nome:o.nome,cat:o.cat,foto:o.foto,tipo:tp,titulo:TITULO[tp],
      score:s,faixa:faixa(s),fontePrincipal:o.fontes.has('frequencia')?'frequencia':'crm',motivos:o.motivos.join(' · ')}; });

  const out={alerta:[],ativa:[],reserva:[],relacionamento:[],operacional:[],descartadas:0};
  const porU={}; for(const it of itens){(porU[it.unidade]||(porU[it.unidade]=[])).push(it);}
  for(const u of Object.keys(porU)){
    const arr=porU[u].sort((a,b)=>b.score-a.score||a.nome.localeCompare(b.nome));
    let aN=0;
    arr.forEach((it,i)=>{ if(i<cap){ if(it.score>=alertaMin && aN<alertaTop){ it.bloco='alerta'; aN++; out.alerta.push(it); } else { it.bloco='ativa'; out.ativa.push(it); } }
      else if(it.score>=reservaMin){ it.bloco='reserva'; out.reserva.push(it); }
      else out.descartadas++; });
  }
  // aniversário (fora do teto). Já é churn -> vira contexto; senão bloco relacionamento.
  for(const a of aniv){ const k=`${a.unidade}|${a.matricula}`;
    if(!churnKeys.has(k)) out.relacionamento.push({unidade:a.unidade,matricula:a.matricula,nome:a.nome,tipo:'aniversario',titulo:TITULO.aniversario,bloco:'relacionamento',faixa:'Relacionamento',motivos:'aniversário na semana'}); }
  // bloco OPERACIONAL (Ocupação) — não-nominal, por horário. Não passa por dedup/score/teto.
  for(const c of ocup){ if(!c || !c.unidade) continue;
    const pico = c.status==='pico'; const tp = pico?'ocupacao_pico':'ocupacao_ocioso';
    out.operacional.push({unidade:c.unidade,tipo:tp,titulo:TITULO[tp],bloco:'operacional',
      hora:c.hora,media:c.media,mediaUnidade:c.media_unidade,
      motivos:`${c.hora}h · ~${c.media} entradas/dia vs média ${c.media_unidade}/h (seg–sex)`}); }
  return out;
}

// Adaptador: DATA da Frequência (dashboard) -> candidatos do motor
const UNIDADE_SLUG={'716Norte':'716-norte','905Sul':'905-sul','604Norte':'604-norte','LagoNorte':'lago-norte','LagoSul':'lago-sul','Natal':'natal-rn'};
const GRUPO_CAT={'Água':'agua','Agua':'agua','Fitness':'fitness','Luta':'lutas','Lutas':'lutas','Lutas e Outros':'lutas','Ambos':'ambos',
 'Ambos (Água + Fitness)':'ambos_af','Ambos (Agua + Fitness)':'ambos_af','Ambos (Água + Luta)':'ambos_al','Ambos (Agua + Luta)':'ambos_al',
 'Ambos (Fitness + Luta)':'ambos_fl','Ambos (Água + Fitness + Luta)':'ambos_afl','Ambos (Agua + Fitness + Luta)':'ambos_afl','Outros':'outros'};
const SEM_CATRACA={'lago-norte':{agua:true}};   // água sem catraca -> não gera churn por frequência
const medeFreq=(slug,cat)=>!(SEM_CATRACA[slug]&&SEM_CATRACA[slug][cat]);
function anivNaJanela(bd,bm,ini,fim){ if(!bd||!bm)return false; for(let t=new Date(ini);t<=fim;t.setUTCDate(t.getUTCDate()+1)){ if(t.getUTCDate()===bd&&(t.getUTCMonth()+1)===bm)return true; } return false; }

export function fromFrequencia(DATA, seg, dom){
  const students=DATA.students||[]; const freq=[], aniv=[];
  for(const s of students){ const slug=UNIDADE_SLUG[s.u]; if(!slug) continue;
    const cat=GRUPO_CAT[s.grupo]||'outros';
    const base={unidade:slug,matricula:String(s.mat||''),nome:s.nome,cat,foto:s.foto||''};
    const tipo=medeFreq(slug,cat)?classifFreq(s.ac,cat):null;
    freq.push({...base,tipo});
    if(anivNaJanela(s.bd,s.bm,seg,dom)) aniv.push({unidade:slug,matricula:String(s.mat||''),nome:s.nome}); }
  return {freq,aniv};
}
