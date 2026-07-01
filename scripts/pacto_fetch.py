#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""716N — cobertura de catraca: 2025+ vs 2026 (estado atual). PII-safe.
Env: PACTO_KEY_716NORTE, SAMPLE(=200)"""
import os, sys, re, json
import urllib.request, urllib.error
from collections import Counter

BASE = "https://apigw.pactosolucoes.com.br"
KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()
SAMPLE = int(os.environ.get("SAMPLE", "200"))


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
        meta = {k: o.get(k) for k in ("totalElements", "totalPages") if k in o}
        for k in ("content", "data", "result", "results", "rows", "list", "items"):
            if isinstance(o.get(k), list):
                return o[k], meta
    return [], {}


def ym(s):
    m = re.search(r"(\d{4}-\d{2})", str(s or ""))
    return m.group(1) if m else None


def meses_recentes(cc):
    o = gj(f"/acessos-cliente/by-pessoa/{cc}?page=0&size=200")
    rows0, meta = rows_meta(o)
    total = meta.get("totalElements") or len(rows0)
    lastpage = max(0, (int(total) - 1) // 200)
    meses = Counter()
    pages = [0] if lastpage == 0 else list(range(lastpage, max(-1, lastpage - 3), -1))
    for p in pages:
        rows = rows0 if p == 0 else rows_meta(gj(f"/acessos-cliente/by-pessoa/{cc}?page={p}&size=200"))[0]
        for a in rows:
            if isinstance(a, dict):
                m = ym(a.get("dtHrEntrada"))
                if m and m >= "2025-01":
                    meses[m] += 1
    return meses


def main():
    if not KEY:
        print("[26] sem chave"); sys.exit(1)
    ativos = []
    for pg in range(120):
        rows, _ = rows_meta(gj(f"/clientes/simples?page={pg}&size=200"))
        if not rows:
            break
        ativos += [r for r in rows if isinstance(r, dict) and (r.get("situacao") or "").upper() == "ATIVO"]
        if len(rows) < 200:
            break
    print(f"[716N] ativos={len(ativos)} | amostra={min(SAMPLE,len(ativos))}")

    n = 0; c25 = 0; c26 = 0
    m26 = Counter(); freq26 = Counter()  # freq26: nº de meses de 2026 com acesso, por aluno
    for r in ativos[:SAMPLE]:
        cc = r.get("codigoCliente")
        if not cc:
            continue
        n += 1
        meses = meses_recentes(cc)
        if any(k >= "2025-01" for k in meses):
            c25 += 1
        m2026 = [k for k in meses if k >= "2026-01"]
        if m2026:
            c26 += 1
            for k in m2026:
                m26[k] += meses[k]
            freq26[min(len(m2026), 7)] += 1
    print(f"[cobertura 2025+] com >=1 acesso: {c25}/{n} ({round(100*c25/n) if n else 0}%)")
    print(f"[cobertura 2026 ] com >=1 acesso: {c26}/{n} ({round(100*c26/n) if n else 0}%)")
    print(f"[2026] distrib de meses-ativos/aluno (1..7): {json.dumps(dict(sorted(freq26.items())), ensure_ascii=False)}")
    print(f"[2026] acessos/mes (amostra): {json.dumps(dict(sorted(m26.items())), ensure_ascii=False)}")
    print("\n[26] fim.")


if __name__ == "__main__":
    main()
