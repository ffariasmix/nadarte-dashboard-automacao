#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""716N — testar /psec/alunos/lista-rapida-acessos (feed em massa, inclui facial).
Params: tipo=1, limite alto, empresaId (HEADER). PII-safe (campos, meios, datas)."""
import os, sys, re, json
import urllib.request, urllib.error
from collections import Counter

BASE = "https://apigw.pactosolucoes.com.br"
KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()


def http_get(path, headers=None, timeout=60):
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


def content(o):
    if isinstance(o, list):
        return o
    if isinstance(o, dict):
        for k in ("content", "data", "result", "results", "rows", "list", "items"):
            if isinstance(o.get(k), list):
                return o[k]
    return []


def find_dates_meios(rows):
    meios = Counter(); datas = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        for k, v in r.items():
            if isinstance(v, str):
                if re.search(r"meio|ident", k, re.I) and not re.search(r"\d", v):
                    meios[v[:30]] += 1
                m = re.search(r"(\d{4}-\d{2}-\d{2})", v) or re.search(r"(\d{2}/\d{2}/\d{4})", v)
                if m and re.search(r"data|entrada|hora|acesso|dt", k, re.I):
                    datas.append((k, m.group(1)))
    return meios, datas


def main():
    if not KEY:
        print("[m] sem chave"); sys.exit(1)
    print("### /psec/alunos/lista-rapida-acessos ###")
    for hdr in [{"empresaId": 1}, {}, {"empresaId": 0}]:
        for lim in [50, 5000]:
            st, o = gj(f"/psec/alunos/lista-rapida-acessos?tipo=1&limite={lim}", headers=hdr)
            rows = content(o)
            print(f"\n  header={hdr} limite={lim} -> HTTP {st} | itens={len(rows)}")
            if st == 200 and rows and isinstance(rows[0], dict):
                print(f"    campos: {sorted(rows[0].keys())}")
                meios, datas = find_dates_meios(rows)
                print(f"    meios (amostra): {json.dumps(dict(meios), ensure_ascii=False)[:300]}")
                if datas:
                    ds = sorted(set(d for _, d in datas))
                    print(f"    campo-data ex: {datas[0]} | intervalo: {ds[0]}..{ds[-1]} (n={len(datas)})")
                else:
                    print(f"    (sem campo de data reconhecido) 1a linha crua(200c): {json.dumps(rows[0], ensure_ascii=False)[:200]}")
                return  # achou, para
            elif st != 200:
                print(f"    corpo(140c): {str(o)[:140]}")
    print("\n[m] fim.")


if __name__ == "__main__":
    main()
