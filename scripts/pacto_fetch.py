#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""716N — achar empresaId que retorna acessos em /psec/alunos/lista-rapida-acessos. PII-safe."""
import os, sys, re, json
import urllib.request, urllib.error

BASE = "https://apigw.pactosolucoes.com.br"
KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()


def http_get(path, headers=None, timeout=45):
    req = urllib.request.Request(BASE + path, method="GET")
    req.add_header("Authorization", "Bearer " + KEY); req.add_header("Accept", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, str(v))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode("utf-8", "replace") if e.fp else "")
    except Exception as e:
        return -1, str(e)


def gj(path, headers=None):
    st, b = http_get(path, headers)
    try:
        return st, json.loads(b)
    except Exception:
        return st, b


def lst(o):
    if isinstance(o, list):
        return o
    if isinstance(o, dict):
        for k in ("content", "data", "result", "results", "rows", "list", "items", "alunos", "acessos"):
            if isinstance(o.get(k), list):
                return o[k]
    return []


def main():
    if not KEY:
        print("[v] sem chave"); sys.exit(1)
    # 1) estrutura crua com empresaId=1 (p/ ver o shape)
    st, o = gj("/psec/alunos/lista-rapida-acessos?tipo=1&limite=5", headers={"empresaId": 1})
    print(f"[shape] empresaId=1 -> HTTP {st} | cru(220c): {str(o)[:220]}")

    # 2) varre empresaId 1..12
    print("\n[varredura empresaId]")
    achou = None
    for e in range(1, 13):
        st, o = gj("/psec/alunos/lista-rapida-acessos?tipo=1&limite=20", headers={"empresaId": e})
        rows = lst(o)
        marca = "  <<< TEM ACESSOS" if rows else ""
        print(f"  empresaId={e:2} -> HTTP {st} | itens={len(rows)}{marca}")
        if rows and achou is None:
            achou = e
    if achou:
        st, o = gj("/psec/alunos/lista-rapida-acessos?tipo=1&limite=20", headers={"empresaId": achou})
        rows = lst(o)
        if rows and isinstance(rows[0], dict):
            print(f"\n[achou empresaId={achou}] campos: {sorted(rows[0].keys())}")
            print(f"   1a linha(260c): {json.dumps(rows[0], ensure_ascii=False)[:260]}")
    print("\n[v] fim.")


if __name__ == "__main__":
    main()
