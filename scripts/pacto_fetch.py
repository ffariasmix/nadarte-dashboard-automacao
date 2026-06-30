#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coletor PACTO -> Dashboard Frequencia & Retencao (Nad'Arte).
--collect : valida o pipeline completo (roster ativo + demografico /v1/pessoa + acessos),
            imprime resumo PII-safe (contagens, taxa de join, cobertura de meses).
--probe   : diagnostico leve.
Env: PACTO_API_KEY, PACTO_UNIT, SAMPLE(=30), MAXPAGES(=80)
NUNCA imprime dados pessoais (so contagens e nomes de campos).
"""
import os, sys, re, json
import urllib.request, urllib.error
from collections import Counter

BASE = "https://apigw.pactosolucoes.com.br"


def http_get(path, key, timeout=55):
    req = urllib.request.Request(BASE + path, method="GET")
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, "", (e.read().decode("utf-8", "replace") if e.fp else "")
    except Exception as e:
        return -1, "", str(e)


def gj(path, key):
    st, ct, body = http_get(path, key)
    if st == 200 and "json" in (ct or "").lower():
        try:
            return json.loads(body)
        except Exception:
            return None
    return None


def content_of(o):
    if isinstance(o, list):
        return o
    if isinstance(o, dict):
        for k in ("content", "data", "rows", "list", "items", "registros", "dados", "result", "results"):
            if isinstance(o.get(k), list):
                return o[k]
    return []


def paginate(path_base, key, size=200, maxpages=80):
    sep = "&" if "?" in path_base else "?"
    out = []
    for pg in range(maxpages):
        o = gj(f"{path_base}{sep}page={pg}&size={size}", key)
        rows = content_of(o)
        out.extend(rows)
        if len(rows) < size:
            break
    return out


def ym(s):
    if not isinstance(s, str):
        return None
    m = re.search(r"(\d{4})-(\d{2})", s) or re.search(r"(\d{2})/(\d{2})/(\d{4})", s)
    if not m:
        return None
    g = m.groups()
    return f"{g[0]}-{g[1]}" if len(g[0]) == 4 else f"{g[2]}-{g[1]}"


def pcode_from_access(cod, key):
    o = gj(f"/acessos-cliente/by-pessoa/{cod}?page=0&size=1", key)
    rows = content_of(o)
    if rows and isinstance(rows[0], dict):
        pv = rows[0].get("cliente", {})
        pv = pv.get("pessoa") if isinstance(pv, dict) else None
        if isinstance(pv, dict):
            return pv.get("codigo")
        return pv
    return None


def collect():
    key = os.environ.get("PACTO_API_KEY", "").strip()
    unit = os.environ.get("PACTO_UNIT", "?")
    sample = int(os.environ.get("SAMPLE", "30"))
    maxp = int(os.environ.get("MAXPAGES", "80"))
    if not key:
        print("[collect] ERRO: sem PACTO_API_KEY"); sys.exit(1)
    print(f"[collect] unidade={unit} sample={sample} maxpages={maxp}")

    # 1) DEMOGRAFICO: /v1/pessoa -> mapa {codigo: {nascimento, sexo, tem_cpf}}
    pes = paginate("/v1/pessoa", key, size=200, maxpages=maxp)
    demo = {}
    com_nasc = com_sexo = com_cpf = 0
    for p in pes:
        if not isinstance(p, dict):
            continue
        c = p.get("codigo")
        if c is None:
            continue
        nasc, sexo, cpf = p.get("datanasc"), p.get("sexo"), p.get("cpf")
        demo[c] = {"nasc": nasc, "sexo": sexo}
        com_nasc += 1 if nasc else 0
        com_sexo += 1 if sexo else 0
        com_cpf += 1 if cpf else 0
    print(f"[pessoa] total={len(pes)} | no mapa={len(demo)} | com nascimento={com_nasc} | com sexo={com_sexo} | com cpf={com_cpf}")
    if pes and isinstance(pes[0], dict):
        print(f"[pessoa] sexo distintos (amostra): {sorted(set(str(p.get('sexo')) for p in pes[:500]))}")

    # 2) ROSTER: /clientes/simples -> ativos
    roster = paginate("/clientes/simples", key, size=200, maxpages=maxp)
    sit = Counter((r.get("situacao") or "?") for r in roster if isinstance(r, dict))
    ativos = [r for r in roster if isinstance(r, dict) and (r.get("situacao") or "").upper() == "ATIVO"]
    print(f"[roster] total lido={len(roster)} | situacao={json.dumps(dict(sit), ensure_ascii=False)} | ATIVOS={len(ativos)}")

    # 3) JOIN + ACESSOS (amostra de ativos)
    join_ok = 0
    glob_month = Counter()
    dmin = dmax = None
    tot_acc = 0
    n = 0
    for r in ativos[:sample]:
        cc = r.get("codigoCliente")
        if not cc:
            continue
        n += 1
        pcode = pcode_from_access(cc, key)
        if pcode is not None and pcode in demo:
            join_ok += 1
        # matriz mensal de acessos
        acc = paginate(f"/acessos-cliente/by-pessoa/{cc}", key, size=200, maxpages=40)
        for a in acc:
            d = ym(a.get("dtHrEntrada")) if isinstance(a, dict) else None
            if d:
                glob_month[d] += 1; tot_acc += 1
                dmin = d if dmin is None or d < dmin else dmin
                dmax = d if dmax is None or d > dmax else dmax
    print(f"[join] ativos amostrados={n} | com demografico (pessoa->/v1/pessoa)={join_ok} ({(100*join_ok//n) if n else 0}%)")
    print(f"[acessos] total na amostra={tot_acc} | cobertura={dmin}..{dmax} | meses distintos={len(glob_month)}")
    tail = sorted(glob_month)[-12:]
    print("[acessos] ult. meses (amostra): " + ", ".join(f"{m}:{glob_month[m]}" for m in tail))
    print("\n[collect] fim.")


if __name__ == "__main__":
    if "--collect" in sys.argv:
        collect()
    elif "--probe" in sys.argv:
        collect()
    else:
        print("Use --collect.")
