#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""716N — Definir "ATIVO" correto: /psec/clientes/ativos (verdade PACTO) x filtro situacao,
+ cruzamento situacao x situacaoContrato. PII-safe. Env: PACTO_KEY_716NORTE"""
import os, sys, re, json
import urllib.request, urllib.error
from collections import Counter

BASE = "https://apigw.pactosolucoes.com.br"
KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()


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
        return st, json.loads(b)
    except Exception:
        return st, b


def content(o):
    if isinstance(o, list):
        return o
    if isinstance(o, dict):
        for k in ("content", "data", "result", "results", "rows", "list", "items"):
            if isinstance(o.get(k), list):
                return o[k]
    return []


def paginate(base, maxp=130):
    sep = "&" if "?" in base else "?"
    out = []
    for pg in range(maxp):
        st, o = gj(f"{base}{sep}page={pg}&size=200")
        rows = content(o)
        if st != 200 or not rows:
            if pg == 0:
                print(f"   ({base}) HTTP {st} corpo(100c): {str(o)[:100]}")
            break
        out += rows
        if len(rows) < 200:
            break
    return out


def main():
    if not KEY:
        print("[a] sem chave"); sys.exit(1)

    # 1) VERDADE PACTO: /psec/clientes/ativos
    print("== /psec/clientes/ativos ==")
    ativos_pacto = paginate("/psec/clientes/ativos")
    print(f"   total = {len(ativos_pacto)}")
    if ativos_pacto and isinstance(ativos_pacto[0], dict):
        print(f"   campos: {sorted(ativos_pacto[0].keys())}")

    # 2) Meu filtro: /clientes/simples situacao=ATIVO + cruzamento com situacaoContrato
    print("\n== /clientes/simples (filtro situacao) ==")
    todos = paginate("/clientes/simples")
    sit = Counter(); sitc = Counter(); cross = Counter()
    ativos_meu = 0
    for r in todos:
        if not isinstance(r, dict):
            continue
        s = (r.get("situacao") or "?").upper()
        sc = (r.get("situacaoContrato") or "?")
        sit[s] += 1
        if s == "ATIVO":
            ativos_meu += 1
            sitc[str(sc)] += 1
    print(f"   total lido = {len(todos)} | ATIVO (meu filtro) = {ativos_meu}")
    print(f"   situacao geral: {json.dumps(dict(sit), ensure_ascii=False)}")
    print(f"   situacaoContrato ENTRE os ATIVO: {json.dumps(dict(sitc), ensure_ascii=False)}")

    print("\n[a] fim.")


if __name__ == "__main__":
    main()
