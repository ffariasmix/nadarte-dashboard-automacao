#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Motor de reconstrucao do freq_multi.json — Dashboard Frequencia & Retencao Nad'Arte.
Implementa secoes 4-8 do runbook. Le os .bin (xlsx decodificados) listados em data/manifest.json
e produz data/freq_multi.json (JSON valido, minificado, ensure_ascii=False).

Janela de meses, mes-base, faixa-etaria de referencia e junMax sao DINAMICOS
(derivados dos arquivos), entao o pipeline segue valendo quando entrar Jul, Ago, etc.

Uso: python3 build_freq_multi.py <data_dir>
  <data_dir> contem os arquivos <fileId>.bin e manifest.json (id -> titulo).
"""
import sys, os, io, re, json, unicodedata, datetime, calendar
from collections import defaultdict, Counter
import openpyxl

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else "data"

# ---- constantes do runbook ----
SHEET_TO_UNIT = {"Lago Norte":"LagoNorte","905 Sul":"905Sul","604 Norte":"604Norte",
                 "716 Norte":"716Norte","Lago Sul":"LagoSul"}
UDPS = {"716Norte":7,"905Sul":7,"604Norte":6,"LagoNorte":6,"LagoSul":6}
UNIDADES = [{"key":"REDE","label":"Rede (todas)"},
            {"key":"716Norte","label":"716 Norte"},{"key":"905Sul","label":"905 Sul"},
            {"key":"604Norte","label":"604 Norte"},{"key":"LagoNorte","label":"Lago Norte"},
            {"key":"LagoSul","label":"Lago Sul"}]
TICKETS = {"716Norte":275.00,"905Sul":268.00,"604Norte":273.80,"LagoNorte":299.60,"LagoSul":266.60}
TICKET_NATAL = 245.20
UNIT_KEYS = ["716Norte","905Sul","604Norte","LagoNorte","LagoSul"]
ABBR = {1:"Jan",2:"Fev",3:"Mar",4:"Abr",5:"Mai",6:"Jun",7:"Jul",8:"Ago",9:"Set",10:"Out",11:"Nov",12:"Dez"}

CAT_TOKENS = {
 "agua": ["NATAC","NATA","HIDRO","BEBE","AQUA"],
 "lutas":["KARATE","MUAY","JIU","JUDO","HAPKIDO","CAPOEIRA","BOXE","TAEKWON","KUNG","LUTA"],
 "fit":  ["TRANSITO LIVRE","FITNESS","MUSCULA","DANCA","PILATES","AULA COLETIVA","FUNCIONAL",
          "SPINNING","CROSS","ZUMBA","RITMO","GINASTICA","ALONGA","YOGA","TREINA"],
}

def deaccent(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
def up(s):
    return deaccent(str(s or "")).upper().strip()
def norm_mat(v):
    d = re.sub(r"\D","", str(v if v is not None else "")); d = d.lstrip("0")
    return d if d else ("0" if re.search(r"\d", str(v or "")) else "")
def norm_doc(v):
    return re.sub(r"\D","", str(v if v is not None else ""))
def norm_nome(v):
    return up(v)
NAME2CPF = {}  # (unit, nome_normalizado) -> cpf  (ponte: resolve linhas/meses sem CPF)
def skey(unit, doc_val, nome_val):
    # chave canonica: CPF quando conhecido (na linha OU via ponte por nome); senao Nome. Sempre por unidade.
    cpf = norm_doc(doc_val); n = norm_nome(nome_val)
    if len(cpf) < 11 and n:
        cpf = NAME2CPF.get((unit, n), "")
    if len(cpf) >= 11:
        return f"{unit}|C|{cpf}"
    return f"{unit}|N|{n}" if n else ""

TOK_ORDER = ["agua","fit","lutas"]  # prioridade por token: agua > fit > lutas > outros
def tok_cat(T):
    for cat in TOK_ORDER:
        if any(k in T for k in CAT_TOKENS[cat]): return cat
    return "other"
def classify_grupo(mod):
    # 1 categoria por token, por prioridade; tokens nao reconhecidos = "outros".
    toks = [up(t) for t in re.split(r"[;,]", str(mod or "")) if up(t)]
    if not toks: return "Fitness"
    g = {tok_cat(t) for t in toks}
    has_a="agua" in g; has_f="fit" in g; has_l="lutas" in g
    if has_a and (has_f or has_l): return "Ambos"
    if has_a: return "Água"
    if has_f: return "Fitness"
    return "Lutas e Outros"

def parse_birth(v):
    if v is None or v == "": return (0,0,0)
    if isinstance(v,(datetime.datetime,datetime.date)): return (v.month, v.day, v.year)
    s = str(v).strip()
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if m:
        d,mo,y = int(m.group(1)),int(m.group(2)),int(m.group(3))
        if y < 100: y += 2000 if y < 50 else 1900
        return (mo,d,y)
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m: return (int(m.group(2)), int(m.group(3)), int(m.group(1)))
    return (0,0,0)

def band_of(ref, by,bm,bd):
    if not by: return "N/D"
    age = ref.year - by - ((ref.month, ref.day) < (bm, bd))
    if age <= 11: return "0–11"
    if age <= 17: return "12–17"
    if age <= 29: return "18–29"
    if age <= 44: return "30–44"
    if age <= 59: return "45–59"
    return "60+"
def sexo_of(v):
    s = up(v)
    if s.startswith("M"): return "M"
    if s.startswith("F"): return "F"
    return "N/D"
def load_wb(path):
    return openpyxl.load_workbook(io.BytesIO(open(path,"rb").read()), read_only=True, data_only=True)
def detect_header(rows, tokens, scan=8):
    for i in range(min(scan, len(rows))):
        cells = rows[i]; names = [up(c) for c in cells]
        if sum(1 for tk in tokens if any(tk in n for n in names)) >= 2:
            colmap = {up(c):ci for ci,c in enumerate(cells) if c is not None and str(c).strip()!=""}
            return i, colmap
    return None, None
def find_col(colmap, *cands):
    # 1) match EXATO (evita que "MATRICULA" capture "DATA MATRICULA", etc.)
    for cand in cands:
        cu = up(cand)
        if cu in colmap: return colmap[cu]
    # 2) match por substring (tolerante a variacoes de cabecalho)
    for cand in cands:
        cu = up(cand)
        for name,ci in colmap.items():
            if cu in name: return ci
    return None
def parse_dt(v):
    if isinstance(v,(datetime.datetime,datetime.date)):
        return datetime.date(v.year,v.month,v.day)
    s=str(v or "").strip()
    m=re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m: return datetime.date(int(m.group(1)),int(m.group(2)),int(m.group(3)))
    m=re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m: return datetime.date(int(m.group(3)),int(m.group(2)),int(m.group(1)))
    return None

# ---- carregar manifest e classificar arquivos ----
manifest = json.load(open(os.path.join(DATA_DIR,"manifest.json")))
alunos_files = {}   # (year,month) -> path
catraca_files = {}  # unit_key -> path
for fid,title in manifest.items():
    path = os.path.join(DATA_DIR, fid+".bin")
    m = re.match(r"\s*(\d{1,2})\.\s*Alunos Ativos.*\((\w+)\.(\d{4})\)", title)
    if m:
        alunos_files[(int(m.group(3)), int(m.group(1)))] = path; continue
    mc = re.search(r"Acessos Catr?ata Unidade (.+?) \(Nad", title)
    if mc:
        uname = mc.group(1).strip()
        catraca_files[SHEET_TO_UNIT.get(uname, uname.replace(" ",""))] = path
assert alunos_files and catraca_files, "faltam arquivos de alunos ou catraca"

# timeline de meses = uniao (alunos + catraca), ordenada
month_keys = set(alunos_files.keys())
SHEET_MONTH = re.compile(r"^\s*(\d{1,2})\.\s*\w+\.?(\d{4})?")
for unit,path in catraca_files.items():
    for sn in load_wb(path).sheetnames:
        mm=SHEET_MONTH.match(sn)
        if mm:
            yr=int(mm.group(2)) if mm.group(2) else max(y for (y,_) in alunos_files)
            month_keys.add((yr,int(mm.group(1))))
ORDERED = sorted(month_keys)
POS = {mk:i for i,mk in enumerate(ORDERED)}
NMONTHS = len(ORDERED)
MESES = [f"{ABBR[mn]}.{str(yr)[2:]}" for (yr,mn) in ORDERED]
base_key = max(alunos_files.keys())
base_pos = POS[base_key]
by_, bm_ = base_key
BAND_REF = datetime.date(by_, bm_, calendar.monthrange(by_, bm_)[1])  # ultimo dia do mes-base
print(f"[info] meses={MESES} base={MESES[base_pos]} bandref={BAND_REF}", file=sys.stderr)

# ---- pre-pass: ponte nome->CPF (alguns meses/unidades vem sem a coluna CPF) ----
for mk, path in alunos_files.items():
    wb = load_wb(path)
    for sn in wb.sheetnames:
        unit = SHEET_TO_UNIT.get(sn.strip())
        if not unit: continue
        rows = [r for r in wb[sn].iter_rows(values_only=True)]
        hidx, colmap = detect_header(rows, ["MATRICULA","DOCUMENTO","NASCIMENTO"])
        if hidx is None: continue
        cD=find_col(colmap,"DOCUMENTO","CPF"); cN=find_col(colmap,"NOME")
        if cD is None or cN is None: continue
        for r in rows[hidx+1:]:
            if r is None: continue
            cpf = norm_doc(r[cD]) if cD<len(r) else ""
            nome = norm_nome(r[cN]) if (cN<len(r) and r[cN] is not None) else ""
            if len(cpf)>=11 and nome:
                NAME2CPF.setdefault((unit,nome), cpf)
print(f"[info] ponte nome->CPF: {len(NAME2CPF)} nomes mapeados", file=sys.stderr)

# ---- parse alunos: active[(pos,unit)] = set(mat); attrs[pos][(unit,mat)] ----
active = defaultdict(set); attrs = defaultdict(dict)
for mk, path in alunos_files.items():
    pos = POS[mk]; wb = load_wb(path)
    for sn in wb.sheetnames:
        unit = SHEET_TO_UNIT.get(sn.strip())
        if not unit: continue
        rows = [r for r in wb[sn].iter_rows(values_only=True)]
        hidx, colmap = detect_header(rows, ["MATRICULA","DOCUMENTO","NASCIMENTO"])
        if hidx is None: continue
        c_mat=find_col(colmap,"MATRICULA"); c_nome=find_col(colmap,"NOME")
        c_doc=find_col(colmap,"DOCUMENTO","CPF")
        c_nasc=find_col(colmap,"NASCIMENTO"); c_sexo=find_col(colmap,"SEXO"); c_mod=find_col(colmap,"MODALIDADE")
        c_dm=find_col(colmap,"DATA MATRICULA","DATA DE MATRICULA","DT MATRICULA","DATA MATR")
        for r in rows[hidx+1:]:
            if r is None: continue
            nome_v = str(r[c_nome]).strip() if (c_nome is not None and c_nome<len(r) and r[c_nome] is not None) else ""
            doc_v = r[c_doc] if (c_doc is not None and c_doc<len(r)) else None
            key = skey(unit, doc_v, nome_v)
            if not key: continue
            mat = norm_mat(r[c_mat]) if (c_mat is not None and c_mat<len(r)) else ""
            active[(pos,unit)].add(key)
            nasc = r[c_nasc] if (c_nasc is not None and c_nasc<len(r)) else None
            bm,bd,by = parse_birth(nasc)
            mod = r[c_mod] if (c_mod is not None and c_mod<len(r)) else ""
            attrs[pos][(unit,key)] = {
                "nome": nome_v, "mat": mat,
                "grupo": classify_grupo(mod), "mod": str(mod or "").strip(),
                "sexo": sexo_of(r[c_sexo]) if (c_sexo is not None and c_sexo<len(r)) else "N/D",
                "band": band_of(BAND_REF,by,bm,bd), "bm":bm,"bd":bd,"by":by,
                "dm": (parse_dt(r[c_dm]).isoformat() if (c_dm is not None and c_dm<len(r) and parse_dt(r[c_dm])) else ""),
            }

# ---- parse catraca: acc[(unit,pos)][mat]; ancora; junMax (ult. data do mes-base) ----
acc = defaultdict(lambda: defaultdict(int)); anchor = {}; max_base_date=None
first_acc = {}  # key -> 1a data de acesso (catraca) de todos os tempos na janela
for unit, path in catraca_files.items():
    wb = load_wb(path); total=0; people=set()
    for sn in wb.sheetnames:
        mm=SHEET_MONTH.match(sn)
        if not mm: continue
        yr=int(mm.group(2)) if mm.group(2) else by_
        mk=(yr,int(mm.group(1)))
        if mk not in POS: continue
        pos=POS[mk]
        rows = [r for r in wb[sn].iter_rows(values_only=True)]
        hidx, colmap = detect_header(rows, ["MAT. CLIENTE","CPF","DATA ENTRADA"])
        if hidx is None: continue
        c_cpf=find_col(colmap,"CPF"); c_nome=find_col(colmap,"NOME"); c_dt=find_col(colmap,"DATA ENTRADA")
        if c_cpf is None and c_nome is None: continue
        for r in rows[hidx+1:]:
            if r is None: continue
            cpf_v = r[c_cpf] if (c_cpf is not None and c_cpf<len(r)) else None
            nome_v = str(r[c_nome]).strip() if (c_nome is not None and c_nome<len(r) and r[c_nome] is not None) else ""
            key = skey(unit, cpf_v, nome_v)
            if not key: continue
            acc[(unit,pos)][key]+=1; total+=1; people.add(key)
            if c_dt is not None and c_dt<len(r):
                d=parse_dt(r[c_dt])
                if d:
                    if pos==base_pos and (max_base_date is None or d>max_base_date): max_base_date=d
                    if key not in first_acc or d<first_acc[key]: first_acc[key]=d
    anchor[unit]=(total,len(people))
print("[info] catraca anchor:", {u:anchor[u] for u in UNIT_KEYS}, file=sys.stderr)
JUN_MAX = max_base_date.strftime("%d/%m/%Y") if max_base_date else ""
print(f"[info] junMax(ult. data mes-base) = {JUN_MAX}", file=sys.stderr)

# ---- ledger de identidade (perpetuo) + first-seen por aluno: regra de 'novo' SEMPRE pelo historico completo, nunca pela janela filtrada ----
def ym_of(pos):
    yr,mn = ORDERED[pos]; return f"{yr:04d}-{mn:02d}"
YM2POS = {ym_of(i):i for i in range(NMONTHS)}
first_seen_ym = {}
for (pos,unit), keys in active.items():
    slabel = ym_of(pos)
    for k in keys:
        if k not in first_seen_ym or slabel < first_seen_ym[k]:
            first_seen_ym[k] = slabel
# ledger persistente fora de data/ (LEDGER_PATH) para perpetuar entre execucoes; mantem a 1a aparicao mais antiga
LEDGER_PATH = os.environ.get("LEDGER_PATH", os.path.join(DATA_DIR,"ledger.json"))
ledger = {}
try: ledger = json.load(open(LEDGER_PATH))
except Exception: ledger = {}
for k, slabel in first_seen_ym.items():
    if k not in ledger or slabel < ledger[k]:
        ledger[k] = slabel
try:
    with open(LEDGER_PATH,"w") as f: json.dump(ledger,f,ensure_ascii=False,separators=(",",":"))
except Exception as e:
    print(f"[WARN] nao salvou ledger: {e}", file=sys.stderr)
def fs_index(key):
    ym = ledger.get(key)
    if not ym: return base_pos
    return YM2POS.get(ym, -1)  # -1 = 1a aparicao ANTES da janela (base arquivada): nunca 'novo'
print(f"[info] ledger: {len(ledger)} pessoas (1a aparicao registrada / perpetuo)", file=sys.stderr)

# ---- montar students (apenas ativos do mes-base) ----
students=[]
for (pos,unit),keys in active.items():
    if pos!=base_pos: continue
    for key in keys:
        a = attrs[base_pos].get((unit,key),{})
        ac = [acc[(unit,mm)].get(key,0) for mm in range(NMONTHS)]
        act= [1 if key in active[(mm,unit)] else 0 for mm in range(NMONTHS)]
        students.append({
            "u":unit,"mat":a.get("mat",""),"nome":a.get("nome",""),
            "grupo":a.get("grupo","Fitness"),"mod":a.get("mod","")[:40],
            "sexo":a.get("sexo","N/D"),"band":a.get("band","N/D"),"dps":UDPS[unit],
            "bm":a.get("bm"),"bd":a.get("bd"),"by":a.get("by"),"ac":ac,"active":act,"fs":fs_index(key),"fa":(first_acc[key].isoformat() if key in first_acc else ""),"dm":a.get("dm",""),
        })
students.sort(key=lambda s:(s["u"],int(s["mat"]) if str(s["mat"]).isdigit() else 0))

# ---- churn set-based (secao 8) ----
def profile(mats, pos, unit):
    cat=Counter(); sex=Counter(); bnd=Counter()
    for mat in mats:
        a=attrs[pos].get((unit,mat))
        if not a: continue
        cat[a["grupo"]]+=1; sex[a["sexo"]]+=1; bnd[a["band"]]+=1
    return dict(cat),dict(sex),dict(bnd)
def merge(d,e):
    for k,v in e.items(): d[k]=d.get(k,0)+v
def pre(lst):
    n=len(lst); mean=round(sum(lst)/n,1) if n else 0
    zero=round(100*sum(1 for x in lst if x==0)/n) if n else 0
    return mean,zero

trans_pairs=[(i,i+1) for i in range(NMONTHS-1)]
churn={}; unit_data={}
for unit in UNIT_KEYS:
    trans=[]; ev=[]; ret=[]
    for a,b in trans_pairs:
        A=active[(a,unit)]; B=active[(b,unit)]
        perdas=A-B; novos=B-A; retidos=A&B
        cC,cS,cB=profile(perdas,a,unit)
        trans.append({"de":MESES[a],"para":MESES[b],"perdas":len(perdas),"novos":len(novos),
                      "transf":0,"transfIn":0,"retidos":len(retidos),"base":len(A),
                      "byCat":cC,"bySex":cS,"byBand":cB})
        for mat in perdas: ev.append(acc[(unit,a)].get(mat,0))
        for mat in retidos: ret.append(acc[(unit,a)].get(mat,0))
    cm,cz=pre(ev); rm,rz=pre(ret)
    churn[unit]={"trans":trans,"pre":{"churnMean":cm,"churnZeroPct":cz,"retMean":rm,"retZeroPct":rz}}
    unit_data[unit]=(trans,ev,ret)
rede=[]; rede_ev=[]; rede_ret=[]
for i,(a,b) in enumerate(trans_pairs):
    perdas=novos=retidos=base=0; cC={};cS={};cB={}
    for unit in UNIT_KEYS:
        t=unit_data[unit][0][i]
        perdas+=t["perdas"]; novos+=t["novos"]; retidos+=t["retidos"]; base+=t["base"]
        merge(cC,t["byCat"]); merge(cS,t["bySex"]); merge(cB,t["byBand"])
    rede.append({"de":MESES[a],"para":MESES[b],"perdas":perdas,"novos":novos,"transf":0,"transfIn":0,
                 "retidos":retidos,"base":base,"byCat":cC,"bySex":cS,"byBand":cB})
for unit in UNIT_KEYS: rede_ev+=unit_data[unit][1]; rede_ret+=unit_data[unit][2]
cm,cz=pre(rede_ev); rm,rz=pre(rede_ret)
churn["REDE"]={"trans":rede,"pre":{"churnMean":cm,"churnZeroPct":cz,"retMean":rm,"retZeroPct":rz}}

# ---- consistencia base(a)+novos-perdas==base(b) ----
warns=[]
for unit in ["REDE"]+UNIT_KEYS:
    tr=churn[unit]["trans"]
    for i in range(len(tr)-1):
        exp=tr[i]["base"]+tr[i]["novos"]-tr[i]["perdas"]
        if exp!=tr[i+1]["base"]:
            warns.append(f"{unit} {tr[i]['de']}->{tr[i]['para']}: {exp}!={tr[i+1]['base']}")
print(("[WARN] consistencia churn:\n  "+"\n  ".join(warns)) if warns else "[ok] consistencia churn fecha", file=sys.stderr)

# ---- Fundacao v2: fluxos retido/saiu/novo/voltou (usa ledger/ym_of definidos acima) ----
def flows_for(scope):
    units = UNIT_KEYS if scope=="REDE" else [scope]
    rows=[]
    for a,b in trans_pairs:
        ymb=ym_of(b); A=set(); B=set()
        for u in units: A|=active[(a,u)]; B|=active[(b,u)]
        saiu=A-B; entrou=B-A; retido=A&B
        novo=sum(1 for k in entrou if ledger.get(k,ymb)>=ymb)   # 1a aparicao no proprio mes b
        voltou=sum(1 for k in entrou if ledger.get(k,ymb)<ymb)  # ja existia antes (retornante)
        rows.append({"de":MESES[a],"para":MESES[b],"base":len(A),
                     "retido":len(retido),"saiu":len(saiu),"novo":novo,"voltou":voltou,
                     "churnPct":round(100*len(saiu)/len(A),1) if A else 0,
                     "retPct":round(100*len(retido)/len(A),1) if A else 0})
    return rows
flow={u:flows_for(u) for u in UNIT_KEYS}; flow["REDE"]=flows_for("REDE")

# ---- GATE DE VALIDACAO DE DADOS (premissa: nunca publicar dado quebrado) ----
def all_active(m):
    s=set()
    for unit in UNIT_KEYS: s |= active[(m,unit)]
    return s
MIN_ACTIVE=500; MIN_OVERLAP=0.60; MIN_ACC=500
month_active=[all_active(m) for m in range(NMONTHS)]
errs=[]
for m in range(NMONTHS):
    if len(month_active[m])<MIN_ACTIVE:
        errs.append(f"mes {MESES[m]}: {len(month_active[m])} alunos ativos (<{MIN_ACTIVE}) - falha de leitura/juncao")
for m in range(NMONTHS-1):
    A,B=month_active[m],month_active[m+1]
    ratio=len(A&B)/(min(len(A),len(B)) or 1)
    if ratio<MIN_OVERLAP:
        errs.append(f"overlap REDE {MESES[m]}->{MESES[m+1]}: {ratio:.0%} (<{MIN_OVERLAP:.0%}) - chave suspeita")
for unit in UNIT_KEYS:
    for m in range(NMONTHS-1):
        A=active[(m,unit)]; B=active[(m+1,unit)]
        if not A or not B: continue
        ratio=len(A&B)/(min(len(A),len(B)) or 1)
        if ratio<MIN_OVERLAP:
            errs.append(f"overlap {unit} {MESES[m]}->{MESES[m+1]}: {ratio:.0%} (<{MIN_OVERLAP:.0%}) - juncao suspeita na unidade")
for m in range(NMONTHS):
    tot=sum(sum(acc[(unit,m)].values()) for unit in UNIT_KEYS)
    if tot<MIN_ACC:
        errs.append(f"acessos {MESES[m]}: {tot} (<{MIN_ACC}) - catraca vazia/nao juntou")
if errs:
    print("[ERRO VALIDACAO] dados nao confiaveis, NAO publicando:\n  "+"\n  ".join(errs), file=sys.stderr)
    sys.exit(1)
print("[ok] gate de validacao passou (overlaps e volumes plausiveis)", file=sys.stderr)

meta={}
try: meta=json.load(open(os.path.join(DATA_DIR,"meta.json")))
except Exception: pass

out = {"students":students,"meses":MESES,"unidades":UNIDADES,"udps":UDPS,
       "churn":churn,"tickets":TICKETS,"ticketNatal":TICKET_NATAL,
       "baseMonth":MESES[base_pos],"junMax":JUN_MAX,"flow":flow,
       "baseUpdated":meta.get("baseUpdated",""),
       "baseUpdatedBy":meta.get("baseUpdatedBy","") or meta.get("baseUpdatedByName","")}
with open(os.path.join(DATA_DIR,"freq_multi.json"),"w") as f:
    json.dump(out,f,ensure_ascii=False,separators=(", ",": "))
print(f"[ok] freq_multi.json: {len(students)} students; baseMonth={MESES[base_pos]}; junMax={JUN_MAX}", file=sys.stderr)
