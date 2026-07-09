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

# --- Classificador de modalidade (texto do plano -> 7 baldes) ---
# Fonte: guia "Pacto API - Modalidades e Categorias". A modalidade vem da descricao
# do contrato (GET /v1/contrato/matricula/{mat}), nao do cadastro (que vem vazio).
AGUA_TK = ("NATAC","NATA","HIDRO","BEBE","AQUA")
LUTA_TK = ("KARATE","MUAY","JIU","JUDO","HAPKIDO","CAPOEIRA","BOXE","TAEKWON","KUNG","LUTA")
FIT_TK  = ("TRANSITO LIVRE"," TL ","LIVRE ACESSO","FITNESS","MUSCULA","DANCA","PILATES",
           "AULA COLETIVA","FUNCIONAL","SPINNING","CROSS","ZUMBA","RITMO","GINASTICA",
           "ALONGA","YOGA","TREINA")

# Rotulos canonicos das categorias (identicos aos usados no dashboard)
CAT_FIT="Fitness"; CAT_AGUA="Água"; CAT_LUTA="Luta"
CAT_AF="Ambos (Água + Fitness)"; CAT_AL="Ambos (Água + Luta)"
CAT_FL="Ambos (Fitness + Luta)"; CAT_AFL="Ambos (Água + Fitness + Luta)"
CAT_OUT="Outros"

# LAGO NORTE: a catraca fica so no ambiente fitness. So passam pela catraca as categorias
# que incluem Fitness; alunos exclusivos de Agua/Luta ficam de fora da analise de frequencia.
LAGO_UNIT = "LagoNorte"
LAGO_FIT_CATS = {CAT_FIT, CAT_AF, CAT_FL, CAT_AFL}
LAGO_EXCLUDED = set()   # (unit,key) excluidos por nao passar pela catraca

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

def _tok_cat(tok):
    # prioridade agua > fit > luta; padding com espacos evita casar "TL" dentro de palavra
    t = " " + up(tok) + " "
    if any(k in t for k in AGUA_TK): return "agua"
    if any(k in t for k in FIT_TK):  return "fit"
    if any(k in t for k in LUTA_TK): return "lutas"
    return "outros"
def classify_grupo(mod):
    # texto da(s) descricao(oes) de contrato -> 7 baldes (+ Outros). Tokeniza por ; , + /
    u = up(mod)
    if "TODAS AS MODALIDADES" in u or "TODAS MODALIDADES" in u:
        return CAT_AFL
    toks = [t for t in re.split(r"[;,+/]", str(mod or "")) if t.strip()]
    b = set(_tok_cat(t) for t in toks); b.discard("outros")
    A = "agua" in b; F = "fit" in b; L = "lutas" in b
    if A and F and L: return CAT_AFL
    if A and F: return CAT_AF
    if A and L: return CAT_AL
    if F and L: return CAT_FL
    if A: return CAT_AGUA
    if F: return CAT_FIT
    if L: return CAT_LUTA
    return CAT_OUT

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
    if m:
        try: return datetime.date(int(m.group(1)),int(m.group(2)),int(m.group(3)))
        except ValueError: pass
    m=re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        d,mo,y = int(m.group(1)),int(m.group(2)),int(m.group(3))
        if mo>12 and d<=12: d,mo = mo,d      # tolera MM/DD/AAAA invertido
        try: return datetime.date(y,mo,d)
        except ValueError: pass
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
        c_foto=find_col(colmap,"FOTO"); c_prof=find_col(colmap,"PROF NOME","PROFESSOR"); c_prole=find_col(colmap,"PROF TIPO","PROF FOTO")
        for r in rows[hidx+1:]:
            if r is None: continue
            nome_v = str(r[c_nome]).strip() if (c_nome is not None and c_nome<len(r) and r[c_nome] is not None) else ""
            doc_v = r[c_doc] if (c_doc is not None and c_doc<len(r)) else None
            mat = norm_mat(r[c_mat]) if (c_mat is not None and c_mat<len(r)) else ""
            key = mat if mat else skey(unit, doc_v, nome_v)   # chave = (unidade+matricula); fallback CPF/nome
            if not key: continue
            mod = r[c_mod] if (c_mod is not None and c_mod<len(r)) else ""
            grupo = classify_grupo(mod)
            # LAGO NORTE: catraca so no acesso fitness. Aluno sem Fitness (Agua/Luta puros) nao
            # passa pela catraca -> apareceria "sumido" por artefato. Excluir da analise.
            if unit == LAGO_UNIT and grupo not in LAGO_FIT_CATS:
                LAGO_EXCLUDED.add((unit, key)); continue
            active[(pos,unit)].add(key)
            nasc = r[c_nasc] if (c_nasc is not None and c_nasc<len(r)) else None
            bm,bd,by = parse_birth(nasc)
            _cell=lambda ci: (str(r[ci]).strip() if (ci is not None and ci<len(r) and r[ci] is not None) else "")
            attrs[pos][(unit,key)] = {
                "nome": nome_v, "mat": mat,
                "grupo": grupo, "mod": str(mod or "").strip(),
                "sexo": sexo_of(r[c_sexo]) if (c_sexo is not None and c_sexo<len(r)) else "N/D",
                "band": band_of(BAND_REF,by,bm,bd), "bm":bm,"bd":bd,"by":by,
                "dm": (parse_dt(r[c_dm]).isoformat() if (c_dm is not None and c_dm<len(r) and parse_dt(r[c_dm])) else ""),
                "foto": _cell(c_foto), "prof": _cell(c_prof), "profRole": _cell(c_prole),
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
        c_mat=find_col(colmap,"MAT. CLIENTE","MAT CLIENTE"); c_cpf=find_col(colmap,"CPF"); c_nome=find_col(colmap,"NOME"); c_dt=find_col(colmap,"DATA ENTRADA")
        if c_mat is None and c_cpf is None and c_nome is None: continue
        for r in rows[hidx+1:]:
            if r is None: continue
            mat_v = norm_mat(r[c_mat]) if (c_mat is not None and c_mat<len(r)) else ""
            cpf_v = r[c_cpf] if (c_cpf is not None and c_cpf<len(r)) else None
            nome_v = str(r[c_nome]).strip() if (c_nome is not None and c_nome<len(r) and r[c_nome] is not None) else ""
            key = mat_v if mat_v else skey(unit, cpf_v, nome_v)   # chave = matricula; fallback CPF/nome
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
for (pos,unit),keys in list(active.items()):   # snapshot: nao mutar 'active' durante a iteracao
    if pos!=base_pos: continue
    for key in keys:
        a = attrs[base_pos].get((unit,key),{})
        ac = [acc.get((unit,mm),{}).get(key,0) for mm in range(NMONTHS)]
        act= [1 if key in active.get((mm,unit),()) else 0 for mm in range(NMONTHS)]  # .get: nao cria chave em defaultdict
        students.append({
            "u":unit,"mat":a.get("mat",""),"nome":a.get("nome",""),
            "grupo":a.get("grupo","Outros"),"mod":a.get("mod","")[:40],
            "sexo":a.get("sexo","N/D"),"band":a.get("band","N/D"),"dps":UDPS[unit],
            "bm":a.get("bm"),"bd":a.get("bd"),"by":a.get("by"),"ac":ac,"active":act,"fs":fs_index(key),"fa":(first_acc[key].isoformat() if key in first_acc else ""),"dm":a.get("dm",""),
            "foto":a.get("foto",""),"prof":a.get("prof",""),"profRole":a.get("profRole",""),
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
# Os gates de integridade so ABORTAM para os meses RECENTES (janela historica de 2022+
# tem, de forma legitima, chain menor, mais churn e catraca parcial nos meses antigos).
# Meses fora da janela recente viram nota informativa ([hist]), nunca erro.
GATE_MONTHS = int(os.environ.get("PACTO_GATE_MONTHS", "6"))
GATE_START = max(0, NMONTHS - GATE_MONTHS)   # so enforce dos ultimos GATE_MONTHS meses
month_active=[all_active(m) for m in range(NMONTHS)]
errs=[]; hist=[]
def _flag(m, msg):
    (errs if m >= GATE_START else hist).append(msg)
for m in range(NMONTHS):
    if len(month_active[m])<MIN_ACTIVE:
        _flag(m, f"mes {MESES[m]}: {len(month_active[m])} alunos ativos (<{MIN_ACTIVE})")
for m in range(NMONTHS-1):
    A,B=month_active[m],month_active[m+1]
    ratio=len(A&B)/(min(len(A),len(B)) or 1)
    if ratio<MIN_OVERLAP:
        _flag(m, f"overlap REDE {MESES[m]}->{MESES[m+1]}: {ratio:.0%} (<{MIN_OVERLAP:.0%})")
for unit in UNIT_KEYS:
    for m in range(NMONTHS-1):
        A=active[(m,unit)]; B=active[(m+1,unit)]
        if not A or not B: continue
        ratio=len(A&B)/(min(len(A),len(B)) or 1)
        if ratio<MIN_OVERLAP:
            _flag(m, f"overlap {unit} {MESES[m]}->{MESES[m+1]}: {ratio:.0%} (<{MIN_OVERLAP:.0%})")
for m in range(NMONTHS):
    tot=sum(sum(acc[(unit,m)].values()) for unit in UNIT_KEYS)
    if tot<MIN_ACC:
        _flag(m, f"acessos {MESES[m]}: {tot} (<{MIN_ACC})")
if hist:
    print(f"[hist] {len(hist)} avisos em meses antigos (fora dos ultimos {GATE_MONTHS}; nao abortam):\n  "+"\n  ".join(hist), file=sys.stderr)
if errs:
    print("[ERRO VALIDACAO] dados nao confiaveis nos meses recentes, NAO publicando:\n  "+"\n  ".join(errs), file=sys.stderr)
    sys.exit(1)
print(f"[ok] gate de validacao passou (recentes: ultimos {GATE_MONTHS} meses)", file=sys.stderr)

meta={}
try: meta=json.load(open(os.path.join(DATA_DIR,"meta.json")))
except Exception: pass

# ---- TICKET dinamico: faturamento real (API, ultimo mes fechado) / alunos ativos ----
_ativos_un = {}
for _s in students: _ativos_un[_s["u"]] = _ativos_un.get(_s["u"], 0) + 1
tickets_out = dict(TICKETS); ticket_mes = ""  # fallback = valores fixos
try:
    _fj = json.load(open(os.path.join(DATA_DIR, "faturamento.json")))
    _fat = _fj.get("faturamento", {})
    for _u in UNIT_KEYS:
        if _fat.get(_u) and _ativos_un.get(_u):
            tickets_out[_u] = round(float(_fat[_u]) / _ativos_un[_u], 2)
    _ym = _fj.get("mes", "")
    if _ym and "-" in _ym:
        _yy, _mm = _ym.split("-"); ticket_mes = f"{ABBR[int(_mm)]}/{_yy}"
    print(f"[ticket] dinamico (faturamento {_fj.get('mes')}): {tickets_out}", file=sys.stderr)
except Exception as _e:
    print(f"[ticket] valores fixos (sem faturamento.json): {_e}", file=sys.stderr)

out = {"students":students,"meses":MESES,"unidades":UNIDADES,"udps":UDPS,
       "churn":churn,"tickets":tickets_out,"ticketNatal":TICKET_NATAL,"ticketMes":ticket_mes,
       "baseMonth":MESES[base_pos],"junMax":JUN_MAX,"flow":flow,
       "lagoUnit":LAGO_UNIT,"lagoExcluded":len(LAGO_EXCLUDED),
       "lagoFitCats":sorted(LAGO_FIT_CATS),
       "baseUpdated":meta.get("baseUpdated",""),
       "baseUpdatedBy":meta.get("baseUpdatedBy","") or meta.get("baseUpdatedByName","")}
print(f"[lago] excluidos por nao passar pela catraca (Agua/Luta puros): {len(LAGO_EXCLUDED)}", file=sys.stderr)
with open(os.path.join(DATA_DIR,"freq_multi.json"),"w") as f:
    json.dump(out,f,ensure_ascii=False,separators=(", ",": "))
print(f"[ok] freq_multi.json: {len(students)} students; baseMonth={MESES[base_pos]}; junMax={JUN_MAX}", file=sys.stderr)
