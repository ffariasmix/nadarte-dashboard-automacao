#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""716N — FREQUENCIA 2025+ corrigida (le paginas RECENTES: acesso vem antigo->novo). PII-safe.
Env: PACTO_KEY_716NORTE, SAMPLE(=200)"""
import os, sys, re, json
import urllib.request, urllib.error
from collections import Counter

BASE = "https://apigw.pactosolucoes.com.br"
KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()
SAMPLE = int(os.environ.get("SAMPLE", "200"))
CUT = "2025-01"


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


def rows_meta(o):
    if isinstance(o, list):
        return o, {}
    if isinstance(o, dict):
        meta = {k: o.get(k) for k in ("totalElements", "totalPages", "number", "size", "last") if k in o}
        for k in ("content", "data", "result", "results", "rows", "list", "items"):
            if isinstance(o.get(k), list):
                return o[k], meta
    return [], {}


def ym(s):
    m = re.search(r"(\d{4}-\d{2})", str(s or ""))
    return m.group(1) if m else None


def acessos_2025(cc):
    """Le a 1a pagina (p/ total) e as ULTIMAS paginas (acessos recentes)."""
    o = gj(f"/acessos-cliente/by-pessoa/{cc}?page=0&size=200")
    rows0, meta = rows_meta(o)
    total = meta.get("totalElements")
    if total is None:
        total = len(rows0)
    size = 200
    lastpage = max(0, (int(total) - 1) // size)
    got = Counter()
    pages = [0] if lastpage == 0 else list(range(lastpage, max(-1, lastpage - 3), -1))  # ultimas 3 paginas
    for p in pages:
        rows = rows0 if p == 0 else rows_meta(gj(f"/acessos-cliente/by-pessoa/{cc}?page={p}&size=200"))[0]
        page_has_old = False
        for a in rows:
            if not isinstance(a, dict):
                continue
            m = ym(a.get("dtHrEntrada"))
            if m:
                if m >= CUT:
                    got[m] += 1
                else:
                    page_has_old = True
        if page_has_old and p != 0:
            break  # ja alcancamos <2025 indo pra tras
    return got


def main():
    if not KEY:
        print("[f] sem chave"); sys.exit(1)
    ativos = []
    for pg in range(120):
        o = gj(f"/clientes/simples?page={pg}&size=200")
        rows, _ = rows_meta(o)
        if not rows:
            break
        ativos += [r for r in rows if isinstance(r, dict) and (r.get("situacao") or "").upper() == "ATIVO"]
        if len(rows) < 200:
            break
    print(f"[716N] ativos={len(ativos)} | amostra={min(SAMPLE,len(ativos))}")
    com = 0; mensal = Counter(); n = 0
    dist = Counter()  # meses ativos por aluno (quantos meses distintos com acesso em 2025+)
    for r in ativos[:SAMPLE]:
        cc = r.get("codigoCliente")
        if not cc:
            continue
        n += 1
        g = acessos_2025(cc)
        if g:
            com += 1
            for m, c in g.items():
                mensal[m] += c
            dist[min(len(g), 12)] += 1
    print(f"[freq 2025+ CORRIGIDA] com >=1 acesso: {com}/{n} ({round(100*com/n) if n else 0}%)")
    print(f"[freq] distrib meses-ativos/aluno (0..12+): {json.dumps(dict(sorted(dist.items())), ensure_ascii=False)}")
    print(f"[freq] acessos/mes (amostra): {json.dumps(dict(sorted(mensal.items())), ensure_ascii=False)}")
    print("\n[f] fim.")


if __name__ == "__main__":
    main()
