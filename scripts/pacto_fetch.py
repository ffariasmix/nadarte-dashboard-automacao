#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""716N — método EFICIENTE de frequencia: /acessos-cliente/{cod}/ultimos-meses (1 call/aluno)
+ fallback bulk. Descobre estrutura e mede cobertura 2025+. PII-safe.
Env: PACTO_KEY_716NORTE, SAMPLE(=150)"""
import os, sys, re, json
import urllib.request, urllib.error
from collections import Counter

BASE = "https://apigw.pactosolucoes.com.br"
KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()
SAMPLE = int(os.environ.get("SAMPLE", "150"))
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


def parse_um(obj):
    """Extrai {YYYY-MM: qtd} de /ultimos-meses (estrutura desconhecida -> heuristica)."""
    out = {}
    rows = content(obj)
    for r in rows:
        if not isinstance(r, dict):
            continue
        # acha um campo mes/ano e um de quantidade
        mes = None; ano = None; qtd = None
        for k, v in r.items():
            kl = k.lower()
            if mes is None and ("mes" in kl or "month" in kl) and isinstance(v, (int, str)):
                mes = v
            if ano is None and ("ano" in kl or "year" in kl) and isinstance(v, (int, str)):
                ano = v
            if qtd is None and ("qtd" in kl or "quant" in kl or "total" in kl or "count" in kl or "acesso" in kl) and isinstance(v, (int, float)):
                qtd = v
            # campo tipo "periodo":"2025-09" ou "MM/YYYY"
            if isinstance(v, str):
                m = re.search(r"(\d{4})-(\d{2})", v) or re.search(r"(\d{2})/(\d{4})", v)
                if m and mes is None and ano is None:
                    g = m.groups()
                    if len(g[0]) == 4:
                        ano, mes = g[0], g[1]
                    else:
                        mes, ano = g[0], g[1]
        if mes is not None and ano is not None:
            key = f"{int(ano):04d}-{int(mes):02d}"
            out[key] = (qtd if isinstance(qtd, (int, float)) else 1)
    return out


def main():
    if not KEY:
        print("[e] sem chave"); sys.exit(1)
    ativos = []
    for pg in range(120):
        st, o = gj(f"/clientes/simples?page={pg}&size=200")
        rows = content(o)
        if not rows:
            break
        ativos += [r for r in rows if isinstance(r, dict) and (r.get("situacao") or "").upper() == "ATIVO"]
        if len(rows) < 200:
            break
    print(f"[716N] ativos={len(ativos)} | amostra={min(SAMPLE,len(ativos))}")

    # estrutura crua do 1o (aprender o formato)
    first_cc = next((r.get("codigoCliente") for r in ativos if r.get("codigoCliente")), None)
    if first_cc:
        st, o = gj(f"/acessos-cliente/{first_cc}/ultimos-meses")
        print(f"[ultimos-meses] HTTP {st} | cru(240c): {str(o)[:240]}")

    com = 0; mensal = Counter(); n = 0
    for r in ativos[:SAMPLE]:
        cc = r.get("codigoCliente")
        if not cc:
            continue
        n += 1
        st, o = gj(f"/acessos-cliente/{cc}/ultimos-meses")
        um = parse_um(o)
        got = {k: v for k, v in um.items() if k >= CUT}
        if got:
            com += 1
            for k, v in got.items():
                mensal[k] += v
    print(f"[freq 2025+ via ultimos-meses] com >=1: {com}/{n} ({round(100*com/n) if n else 0}%)")
    print(f"[freq] acessos/mes (amostra): {json.dumps(dict(sorted(mensal.items())), ensure_ascii=False)}")
    print("\n[e] fim.")


if __name__ == "__main__":
    main()
