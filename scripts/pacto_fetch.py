#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Conversor/validador PACTO -> Dashboard (716 Norte).
Junta: roster ATIVO (/clientes/simples) + demografico (cliente.pessoa) +
modalidade (/v1/contrato/matricula) + acessos (/acessos-cliente/by-pessoa),
e imprime DISTRIBUICOES PII-safe para validar contra o painel atual.
Env: PACTO_API_KEY, PACTO_UNIT, SAMPLE(=150), MAXPAGES(=90)
"""
import os, sys, re, json, datetime
import urllib.request, urllib.error
from collections import Counter

BASE = "https://apigw.pactosolucoes.com.br"
REF = datetime.date(2026, 6, 30)  # mes-base atual

CAT = {
    "Água":   ["NATAC", "NATA", "HIDRO", "BEBE", "AQUA"],
    "Lutas e Outros": ["KARATE", "MUAY", "JIU", "JUDO", "HAPKIDO", "CAPOEIRA", "BOXE", "TAEKWON", "KUNG", "LUTA"],
    "Fitness": ["TRANSITO LIVRE", "FITNESS", "MUSCULA", "DANCA", "PILATES", "AULA COLETIVA", "FUNCIONAL",
                "SPINNING", "CROSS", "ZUMBA", "RITMO", "GINASTICA", "ALONGA", "YOGA", "TREINA"],
}


def http_get(path, key, timeout=50):
    req = urllib.request.Request(BASE + path, method="GET")
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode("utf-8", "replace") if e.fp else "")
    except Exception as e:
        return -1, str(e)


def gj(path, key):
    st, body = http_get(path, key)
    try:
        return json.loads(body)
    except Exception:
        return None


def content(o):
    if isinstance(o, list):
        return o
    if isinstance(o, dict):
        for k in ("content", "data", "rows", "list", "items", "result", "results"):
            if isinstance(o.get(k), list):
                return o[k]
    return []


def deaccent(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def grupo_de(desc):
    T = deaccent(str(desc or "")).upper()
    a = any(t in T for t in CAT["Água"])
    f = any(t in T for t in CAT["Fitness"])
    l = any(t in T for t in CAT["Lutas e Outros"])
    if a and (f or l):
        return "Ambos"
    if a:
        return "Água"
    if f:
        return "Fitness"
    if l:
        return "Lutas e Outros"
    return "Fitness"


def band_de(nasc_ms):
    try:
        y = datetime.datetime.utcfromtimestamp(int(nasc_ms) / 1000).year
    except Exception:
        return "N/D"
    age = REF.year - y
    if age <= 11: return "0–11"
    if age <= 17: return "12–17"
    if age <= 29: return "18–29"
    if age <= 44: return "30–44"
    if age <= 59: return "45–59"
    return "60+"


def ym(s):
    m = re.search(r"(\d{4})-(\d{2})", s or "") if isinstance(s, str) else None
    return f"{m.group(1)}-{m.group(2)}" if m else None


def build():
    key = os.environ.get("PACTO_API_KEY", "").strip()
    unit = os.environ.get("PACTO_UNIT", "?")
    sample = int(os.environ.get("SAMPLE", "150"))
    maxp = int(os.environ.get("MAXPAGES", "90"))
    if not key:
        print("[build] ERRO: sem PACTO_API_KEY"); sys.exit(1)
    print(f"[build] unidade={unit} sample={sample}")

    # ROSTER completo -> ativos
    ativos = []
    for pg in range(maxp):
        rows = content(gj(f"/clientes/simples?page={pg}&size=200", key))
        if not rows:
            break
        for r in rows:
            if isinstance(r, dict) and (r.get("situacao") or "").upper() == "ATIVO":
                ativos.append(r)
        if len(rows) < 200:
            break
    print(f"[roster] ATIVOS totais (716N) = {len(ativos)}")

    # amostra: demografico + modalidade + acessos
    grp, sx, bd = Counter(), Counter(), Counter()
    com_demo = com_contrato = com_acesso = 0
    dmin = dmax = None
    n = 0
    for r in ativos[:sample]:
        cc = r.get("codigoCliente"); mat = r.get("matricula")
        if not cc:
            continue
        n += 1
        # 1 acesso -> demografico + confirma acesso
        ac = content(gj(f"/acessos-cliente/by-pessoa/{cc}?page=0&size=1", key))
        if ac and isinstance(ac[0], dict):
            com_acesso += 1
            pes = (ac[0].get("cliente") or {}).get("pessoa") or {}
            if isinstance(pes, dict):
                if pes.get("sexo") or pes.get("dataNascimento"):
                    com_demo += 1
                sx[str(pes.get("sexo") or "N/D")] += 1
                bd[band_de(pes.get("dataNascimento"))] += 1
            d = ym(ac[0].get("dtHrEntrada"))
            if d:
                dmin = d if dmin is None or d < dmin else dmin
                dmax = d if dmax is None or d > dmax else dmax
        # contrato -> modalidade -> grupo
        if mat:
            ct = content(gj(f"/v1/contrato/matricula/{mat}", key))
            if ct and isinstance(ct[0], dict):
                com_contrato += 1
                grp[grupo_de(ct[0].get("descricao"))] += 1
            else:
                grp["N/D"] += 1
    print(f"[amostra] n={n} | com_acesso={com_acesso} | com_demografico={com_demo} | com_contrato={com_contrato}")
    print(f"[grupo]  {json.dumps(dict(grp), ensure_ascii=False)}")
    print(f"[sexo]   {json.dumps(dict(sx), ensure_ascii=False)}")
    print(f"[faixa]  {json.dumps(dict(bd), ensure_ascii=False)}")
    print(f"[acessos] cobertura(datas 1o acesso amostra) {dmin}..{dmax}")
    print("\n[build] fim.")


if __name__ == "__main__":
    build()
