#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pacto_fetch.py — Coletor PACTO (ZillyonWeb) -> arquivos no formato do motor.

Substitui/complementa o drive_download.py: para cada unidade, puxa da API
  1) roster ATIVO (dedupe por codigoCliente),
  2) /clientes/{matricula}/dados-pessoais  -> codPessoa + CPF + dataMatricula + demografia,
  3) /acessos-cliente/by-pessoa/{codPessoa} -> historico de acessos (inclui facial),
e ESCREVE, em <data_dir>, planilhas .bin (xlsx) + manifest.json + meta.json IDENTICAS
ao que o build_freq_multi.py ja le hoje (Alunos Ativos por mes; Acessos Catraca por unidade).
A juncao aluno x acesso e por CPF (chave que existe nas duas bases).

Modos:
  - producao:   le PACTO_KEY_<UNIT> do ambiente (GitHub Secrets). 1 chave por unidade.
  - PACTO_SELFTEST=1: nao chama API; gera dados sinteticos no MESMO formato (teste de formato/gate).
  - PACTO_ONLY=716Norte: limita a coleta a 1 unidade (canario).

Uso: python3 pacto_fetch.py <data_dir>
PII fica apenas nos .bin (gitignored/efemeros no CI), nunca em log.
"""
import os, sys, json, time, random, datetime, calendar
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
import openpyxl

WORKERS = int(os.environ.get("PACTO_WORKERS", "4"))

BASE = "https://apigw.pactosolucoes.com.br"
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else "data"
WINDOW_START = (2025, 1)         # catraca: emite meses a partir daqui
NOW = datetime.date.today()
ABBR = {1:"Jan",2:"Fev",3:"Mar",4:"Abr",5:"Mai",6:"Jun",7:"Jul",8:"Ago",9:"Set",10:"Out",11:"Nov",12:"Dez"}

# unidade -> (label do motor, nome do Secret). Natal fora ate ago/2026 (confirmar).
UNITS = [
    ("716Norte",  "716 Norte",  "PACTO_KEY_716NORTE"),
    ("905Sul",    "905 Sul",    "PACTO_KEY_905SUL"),
    ("604Norte",  "604 Norte",  "PACTO_KEY_604NORTE"),
    ("LagoNorte", "Lago Norte", "PACTO_KEY_LAGONORTE"),
    ("LagoSul",   "Lago Sul",   "PACTO_KEY_LAGOSUL"),
]

# ------------------------- HTTP -------------------------
def http_get(key, path, timeout=30, tries=5):
    for i in range(tries):
        req = urllib.request.Request(BASE + path, method="GET")
        req.add_header("Authorization", "Bearer " + key)
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            code = e.code
            body = e.read().decode("utf-8", "replace") if e.fp else ""
            if code in (429, 500, 502, 503, 504) and i < tries - 1:
                # backoff exponencial c/ jitter (rate-limit da PACTO)
                time.sleep(min(12.0, 0.8 * (2 ** i)) + random.uniform(0, 0.4)); continue
            return code, body
        except Exception as e:
            if i < tries - 1:
                time.sleep(min(8.0, 0.8 * (2 ** i))); continue
            return -1, str(e)
    return -1, ""

def gj(key, path):
    st, b = http_get(key, path)
    try:
        return st, json.loads(b)
    except Exception:
        return st, b

def lst(o):
    if isinstance(o, list):
        return o
    if isinstance(o, dict):
        for k in ("content","data","result","results","rows","list","items","clientes","acessos"):
            v = o.get(k)
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                for k2 in ("lista","content","items","rows"):
                    if isinstance(v.get(k2), list):
                        return v[k2]
    return []

def gv(d, *names):
    if not isinstance(d, dict):
        return None
    low = {k.lower(): k for k in d}
    for n in names:
        if n.lower() in low:
            return d[low[n.lower()]]
    return None

def unwrap(o):
    if isinstance(o, dict):
        c = o.get("content")
        if isinstance(c, dict):
            return c
        return o
    return {}

def to_date(v):
    if v is None:
        return None
    try:
        if isinstance(v, (int, float)) or (isinstance(v, str) and str(v).isdigit()):
            n = int(v)
            if n > 10_000_000_000:
                n //= 1000
            return datetime.datetime.fromtimestamp(n, tz=datetime.timezone.utc).date()
        s = str(v)[:19].replace("T", " ")
        for f in ("%Y-%m-%d %H:%M:%S","%Y-%m-%d","%d/%m/%Y %H:%M:%S","%d/%m/%Y"):
            try:
                return datetime.datetime.strptime(s, f).date()
            except Exception:
                pass
    except Exception:
        return None
    return None

# ------------------------- COLETA -------------------------
def roster_ativos(key):
    """paginacao robusta: dedupe por codigoCliente, para quando pagina nao traz codigo novo."""
    seen = set(); out = []
    for pg in range(0, 120):
        st, o = gj(key, f"/clientes/simples?page={pg}&size=200")
        r = lst(o)
        if not r:
            break
        novos = 0
        for c in r:
            if not isinstance(c, dict):
                continue
            cc = gv(c, "codigoCliente", "codigo")
            if cc is None or cc in seen:
                continue
            seen.add(cc); novos += 1
            if str(gv(c, "situacao") or "").upper() == "ATIVO":
                out.append(c)
        if novos == 0:
            break
        if len(r) < 200:
            break
    return out

def fetch_client(key, c):
    """1 cliente -> (aluno_row, [(ym, acc_row)]). dados-pessoais (codPessoa+cpf) + 1 chamada de acesso."""
    try:
        M = gv(c, "matricula")
        nome = gv(c, "nome") or ""
        modc = gv(c, "categoria") or ""
        st, o = gj(key, f"/clientes/{M}/dados-pessoais")
        dp = unwrap(o) if st == 200 else {}
        cp  = gv(dp, "codigoPessoa", "codPessoa")
        cpf = gv(dp, "cpf") or ""
        aluno = {
            "mat": M, "nome": nome, "cpf": cpf,
            "nasc": to_date(gv(dp, "dataNascimento", "datanasc", "nascimento")),
            "sexo": gv(dp, "sexo") or "",
            "mod": gv(dp, "descricao") or gv(dp, "categoria") or modc,
            "dm": to_date(gv(dp, "dataMatricula")),
        }
        accrows = []
        if cp:
            st, o = gj(key, f"/acessos-cliente/by-pessoa/{cp}?page=0&size=1000")
            for a in (lst(o) if st == 200 else []):
                d = to_date(gv(a, "dtHrEntrada") or gv(a, "dataDeAcesso") or gv(a, "dataRegistro"))
                if not d:
                    continue
                ym = (d.year, d.month)
                if ym < WINDOW_START or ym > (NOW.year, NOW.month):
                    continue
                accrows.append((ym, {"cpf": cpf, "nome": nome, "data": d}))
        return aluno, accrows
    except Exception:
        return {"mat": gv(c, "matricula"), "nome": gv(c, "nome") or "", "cpf": "",
                "nasc": None, "sexo": "", "mod": "", "dm": None}, []

def coleta_unidade(unit_key, unit_label, key):
    """retorna (alunos_rows, catraca) para a unidade. Coleta PARALELA (I/O bound)."""
    ativos = roster_ativos(key)
    alunos_rows = []
    catraca = {}   # (year,month) -> list of {cpf,nome,data}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for aluno, accrows in ex.map(lambda c: fetch_client(key, c), ativos):
            alunos_rows.append(aluno)
            for ym, row in accrows:
                catraca.setdefault(ym, []).append(row)
    print(f"[t] {unit_key}: coleta de {len(ativos)} ativos em {time.time()-t0:.0f}s", file=sys.stderr)
    return alunos_rows, catraca

# ------------------------- ESCRITA (formato do motor) -------------------------
AL_HEADER = ["MATRICULA","NOME","DOCUMENTO","NASCIMENTO","SEXO","MODALIDADE","DATA MATRICULA"]
CT_HEADER = ["MAT. CLIENTE","NOME","CPF","DATA ENTRADA"]

def write_alunos_wb(path, unit_label_to_rows):
    wb = openpyxl.Workbook(); wb.remove(wb.active)
    for label, rows in unit_label_to_rows.items():
        ws = wb.create_sheet(title=label[:31])
        ws.append(AL_HEADER)
        for r in rows:
            ws.append([r["mat"], r["nome"], r["cpf"], r["nasc"], r["sexo"], r["mod"], r["dm"]])
    wb.save(path)

def write_catraca_wb(path, sheets):
    """sheets: {(year,month): [ {cpf,nome,data} ]}"""
    wb = openpyxl.Workbook(); wb.remove(wb.active)
    for (yr, mn) in sorted(sheets.keys()):
        ws = wb.create_sheet(title=f"{mn}. {ABBR[mn]}.{yr}"[:31])
        ws.append(CT_HEADER)
        for r in sheets[(yr, mn)]:
            ws.append(["", r["nome"], r["cpf"], r["data"]])
    wb.save(path)

# ------------------------- SELFTEST (sintetico) -------------------------
def selftest_data():
    """gera 5 unidades x 2 meses, ~640 ativos/unid, overlap ~85%, acessos suficientes."""
    random.seed(7)
    months = [(2026, 5), (2026, 6)]
    alunos_by_month = {m: {} for m in months}
    catraca_by_unit = {}
    for uk, ulabel, _ in UNITS:
        base_ids = list(range(1000, 1000 + 640))   # cpfs sinteticos
        prev = set()
        cat = {}
        for mi, m in enumerate(months):
            # 85% de retencao + alguns novos
            if mi == 0:
                cur = set(base_ids[:600])
            else:
                keep = set(random.sample(sorted(prev), int(len(prev) * 0.85)))
                novos = set(base_ids[600:640])
                cur = keep | novos
            prev = cur
            rows = []
            for cid in sorted(cur):
                cpf = f"{uk[:3].upper()}{cid:08d}"[:11].ljust(11, "0")
                rows.append({
                    "mat": str(cid), "nome": f"ALUNO {uk} {cid}", "cpf": cpf,
                    "nasc": datetime.date(1990, ((cid % 12) + 1), ((cid % 27) + 1)),
                    "sexo": "M" if cid % 2 else "F",
                    "mod": random.choice(["TRANSITO LIVRE","MUSCULACAO","NATACAO","MUAY THAI"]),
                    "dm": datetime.date(2024, 1, 1),
                })
                # acessos no mes (>=1 p/ maioria)
                naccess = random.choice([0, 2, 4, 8, 12])
                for _ in range(naccess):
                    day = random.randint(1, calendar.monthrange(m[0], m[1])[1])
                    cat.setdefault(m, []).append({"cpf": cpf, "nome": f"ALUNO {uk} {cid}",
                                                  "data": datetime.date(m[0], m[1], day)})
            alunos_by_month[m][ulabel] = rows
        catraca_by_unit[(uk, ulabel)] = cat
    return months, alunos_by_month, catraca_by_unit

# ------------------------- MAIN -------------------------
def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    manifest = {}
    fid = 0
    def nextfid():
        nonlocal fid; fid += 1; return f"api{fid:04d}"

    if os.environ.get("PACTO_SELFTEST") == "1":
        months, alunos_by_month, catraca_by_unit = selftest_data()
        for (yr, mn) in months:
            f = nextfid(); path = os.path.join(DATA_DIR, f + ".bin")
            write_alunos_wb(path, alunos_by_month[(yr, mn)])
            manifest[f] = f"{mn}. Alunos Ativos Rede ({ABBR[mn]}.{yr})"
        for (uk, ulabel), sheets in catraca_by_unit.items():
            f = nextfid(); path = os.path.join(DATA_DIR, f + ".bin")
            write_catraca_wb(path, sheets)
            manifest[f] = f"Acessos Catrata Unidade {ulabel} (Nad'Arte)"
        json.dump(manifest, open(os.path.join(DATA_DIR, "manifest.json"), "w"), ensure_ascii=False)
        json.dump({"baseUpdated": NOW.isoformat(), "baseUpdatedBy": "selftest"},
                  open(os.path.join(DATA_DIR, "meta.json"), "w"), ensure_ascii=False)
        print(f"[selftest] escrito {len(manifest)} arquivos em {DATA_DIR}", file=sys.stderr)
        return

    only = os.environ.get("PACTO_ONLY", "").strip()
    cur_ym = (NOW.year, NOW.month)
    alunos_cur = {}         # label -> rows (mes corrente)

    targets = [(uk, ulabel, secret) for (uk, ulabel, secret) in UNITS if not only or uk == only]

    def run_unit(t):
        uk, ulabel, secret = t
        key = os.environ.get(secret, "").strip()
        if not key:
            print(f"[skip] {uk}: sem secret {secret}", file=sys.stderr); return None
        try:
            alunos_rows, catraca = coleta_unidade(uk, ulabel, key)
            return (uk, ulabel, alunos_rows, catraca)
        except Exception as e:
            print(f"[ERRO] {uk}: {e}", file=sys.stderr); return None

    # unidades EM PARALELO (chaves independentes -> rate-limit por chave respeitado)
    results = []
    with ThreadPoolExecutor(max_workers=max(1, len(targets))) as ex:
        for r in ex.map(run_unit, targets):
            if r:
                results.append(r)

    for uk, ulabel, alunos_rows, catraca in results:
        alunos_cur[ulabel] = alunos_rows
        f = nextfid(); write_catraca_wb(os.path.join(DATA_DIR, f + ".bin"), catraca)
        manifest[f] = f"Acessos Catrata Unidade {ulabel} (Nad'Arte)"
        tot_acc = sum(len(v) for v in catraca.values())
        ncpf = sum(1 for r in alunos_rows if len(str(r["cpf"] or "")) >= 11)
        ndm = sum(1 for r in alunos_rows if r["dm"])
        na = max(1, len(alunos_rows))
        print(f"[ok] {uk}: ativos={len(alunos_rows)} cpf={100*ncpf//na}% dataMatr={100*ndm//na}% "
              f"acessos={tot_acc} meses={sorted(catraca.keys())}", file=sys.stderr)
    if alunos_cur:
        f = nextfid(); write_alunos_wb(os.path.join(DATA_DIR, f + ".bin"), alunos_cur)
        manifest[f] = f"{cur_ym[1]}. Alunos Ativos Rede ({ABBR[cur_ym[1]]}.{cur_ym[0]})"
    json.dump(manifest, open(os.path.join(DATA_DIR, "manifest.json"), "w"), ensure_ascii=False)
    print(f"[fim] manifest com {len(manifest)} arquivos", file=sys.stderr)


if __name__ == "__main__":
    main()
