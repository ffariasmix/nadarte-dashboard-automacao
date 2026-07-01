#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerador/validador 716N — Vencimentos (TODOS ativos) + tempo de casa real (dataMatricula)
+ grupo (plano) + frequencia 2025+ (amostra). PII-safe.
Env: PACTO_KEY_716NORTE, SAMPLE(=200)
"""
import os, sys, re, json, datetime
import urllib.request, urllib.error
from collections import Counter

BASE = "https://apigw.pactosolucoes.com.br"
KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()
SAMPLE = int(os.environ.get("SAMPLE", "200"))
TODAY = datetime.date(2026, 7, 1)
CUT = "2025-01"  # frequencia confiavel a partir daqui

CAT = {
    "Água": ["NATAC", "NATA", "HIDRO", "BEBE", "AQUA"],
    "Lutas e Outros": ["KARATE", "MUAY", "JIU", "JUDO", "HAPKIDO", "CAPOEIRA", "BOXE", "TAEKWON", "KUNG", "LUTA"],
    "Fitness": ["TRANSITO LIVRE", "FITNESS", "MUSCULA", "DANCA", "PILATES", "AULA COLETIVA", "FUNCIONAL",
                "SPINNING", "CROSS", "ZUMBA", "RITMO", "GINASTICA", "ALONGA", "YOGA", "TREINA"],
}


def http_get(path, timeout=45):
    req = urllib.request.Request(BASE + path, method="GET")
    req.add_header("Authorization", "Bearer " + KEY); req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode("utf-8", "replace") if e.fp else "")
    except Exception as e:
        return -1, str(e)


def gj(path):
    st, b = http_get(path)
    try:
        return json.loads(b)
    except Exception:
        return None


def content(o):
    if isinstance(o, list):
        return o
    if isinstance(o, dict):
        for k in ("content", "data", "result", "results", "rows", "list", "items"):
            if isinstance(o.get(k), list):
                return o[k]
        if "content" in o and isinstance(o["content"], dict):
            return [o["content"]]
    return []


def to_date(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        try:
            return datetime.date(1970, 1, 1) + datetime.timedelta(milliseconds=v)
        except Exception:
            return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(v)) or re.search(r"(\d{2})/(\d{2})/(\d{4})", str(v))
    if not m:
        return None
    g = m.groups()
    try:
        return datetime.date(int(g[0]), int(g[1]), int(g[2])) if len(g[0]) == 4 else datetime.date(int(g[2]), int(g[1]), int(g[0]))
    except Exception:
        return None


def grupo(plano):
    T = str(plano or "").upper()
    a = any(t in T for t in CAT["Água"]); f = any(t in T for t in CAT["Fitness"]); l = any(t in T for t in CAT["Lutas e Outros"])
    if a and (f or l): return "Ambos"
    if a: return "Água"
    if f: return "Fitness"
    if l: return "Lutas e Outros"
    return "Fitness"


def band(nasc):
    d = to_date(nasc)
    if not d: return "N/D"
    age = TODAY.year - d.year
    for lim, lab in [(11, "0–11"), (17, "12–17"), (29, "18–29"), (44, "30–44"), (59, "45–59")]:
        if age <= lim: return lab
    return "60+"


def main():
    if not KEY:
        print("[gen] sem chave 716N"); sys.exit(1)
    # ROSTER ativo (com fimContrato p/ vencimentos)
    ativos = []
    for pg in range(120):
        rows = content(gj(f"/clientes/simples?page={pg}&size=200"))
        if not rows:
            break
        ativos += [r for r in rows if isinstance(r, dict) and (r.get("situacao") or "").upper() == "ATIVO"]
        if len(rows) < 200:
            break
    print(f"[716N] ATIVOS = {len(ativos)}")

    # ===== VENCIMENTOS — TODOS os ativos (fimContrato do roster) =====
    venc = Counter(); sem_fim = 0
    for r in ativos:
        d = to_date(r.get("fimContrato"))
        if not d:
            sem_fim += 1; continue
        dias = (d - TODAY).days
        if dias < 0: venc["vencido"] += 1
        elif dias <= 30: venc["<=30 dias"] += 1
        elif dias <= 60: venc["31-60 dias"] += 1
        elif dias <= 90: venc["61-90 dias"] += 1
        else: venc[">90 dias"] += 1
    print(f"[VENCIMENTOS] (todos {len(ativos)}) {json.dumps(dict(venc), ensure_ascii=False)} | sem fimContrato={sem_fim}")

    # ===== AMOSTRA: tempo de casa real + grupo + frequencia 2025+ =====
    tenure = Counter(); grp = Counter(); bnd = Counter()
    freq25 = Counter(); com_freq25 = 0; n = 0
    for r in ativos[:SAMPLE]:
        mat = r.get("matricula"); cc = r.get("codigoCliente")
        if not mat:
            continue
        n += 1
        dp = content(gj(f"/clientes/{mat}/dados-pessoais"))
        if dp and isinstance(dp[0], dict):
            dm = to_date(dp[0].get("dataMatricula"))
            if dm:
                y = dm.year
                tenure["<2010" if y < 2010 else ("2010-2014" if y < 2015 else ("2015-2019" if y < 2020 else ("2020-2023" if y < 2024 else "2024+")))] += 1
            bnd[band(dp[0].get("nascimento"))] += 1
        lc = content(gj(f"/clientes/{mat}/linha-tempo/contratos"))
        plano = lc[0].get("plano") if lc and isinstance(lc[0], dict) else None
        grp[grupo(plano)] += 1
        # frequencia 2025+
        acc = content(gj(f"/acessos-cliente/by-pessoa/{cc}?page=0&size=200")) if cc else []
        meses = set()
        for a in acc:
            m = re.search(r"(\d{4}-\d{2})", str(a.get("dtHrEntrada") or "")) if isinstance(a, dict) else None
            if m and m.group(1) >= CUT:
                meses.add(m.group(1)); freq25[m.group(1)] += 1
        if meses:
            com_freq25 += 1
    print(f"[amostra] n={n}")
    print(f"[tempo de casa REAL - dataMatricula] {json.dumps(dict(sorted(tenure.items())), ensure_ascii=False)}")
    print(f"[grupo] {json.dumps(dict(grp), ensure_ascii=False)}")
    print(f"[faixa etaria] {json.dumps(dict(bnd), ensure_ascii=False)}")
    print(f"[frequencia 2025+] com >=1 acesso: {com_freq25}/{n}")
    print(f"[frequencia 2025+] acessos/mes (amostra): {json.dumps(dict(sorted(freq25.items())), ensure_ascii=False)}")
    print("\n[gen] fim.")


if __name__ == "__main__":
    main()
