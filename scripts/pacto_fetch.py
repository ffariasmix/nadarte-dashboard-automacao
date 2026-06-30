#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROBE PACTO — busca endpoint de CADASTRO COMPLETO (CPF, nascimento, sexo, modalidade, matricula).
NAO imprime dados pessoais (so nomes de campos). Uso: python scripts/pacto_fetch.py --probe
Env: PACTO_API_KEY (Bearer), PACTO_UNIT
"""
import os, sys, re, json, datetime
import urllib.request, urllib.error

BASE = "https://apigw.pactosolucoes.com.br"
DATE_HINT = ("data", "date", "dt", "nasc", "matric", "cadastr", "venc", "inicio", "fim")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}")


def http_get(path, key, timeout=45):
    req = urllib.request.Request(BASE + path, method="GET")
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace") if e.fp else ""
        return e.code, (e.headers.get("Content-Type", "") if e.headers else ""), body
    except Exception as e:
        return -1, "", "EXC: " + str(e)


def parse_date(v):
    if not isinstance(v, str):
        return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", v) or re.search(r"(\d{2})/(\d{2})/(\d{4})", v)
    return v if m else None


def describe(obj):
    rows = obj if isinstance(obj, list) else None
    page = None
    if isinstance(obj, dict):
        page = {k: obj[k] for k in ("totalElements", "totalPages", "size", "number") if k in obj}
        for k in ("content", "data", "rows", "list", "items", "registros", "dados", "result", "results"):
            if isinstance(obj.get(k), list):
                rows = obj[k]; break
        if rows is None:
            print(f"    objeto chaves: {sorted(obj.keys())}"); return
    if page:
        print(f"    paginacao: {json.dumps(page, ensure_ascii=False)}")
    print(f"    itens: {len(rows)}")
    if rows and isinstance(rows[0], dict):
        first = rows[0]
        print(f"    campos ({len(first)}): {sorted(first.keys())}")
        print(f"    tipos: {json.dumps({k: type(v).__name__ for k,v in first.items()}, ensure_ascii=False)}")
        df = {}
        for k in first:
            if any(h in k.lower() for h in DATE_HINT):
                vals = [r.get(k) for r in rows if isinstance(r, dict) and parse_date(r.get(k))]
                if vals:
                    df[k] = f"ex: {vals[0]}"
        if df:
            print(f"    campos-data (exemplo): {json.dumps(df, ensure_ascii=False)}")


def try_json(label, path, key):
    print(f"\n=== {label}  GET {path} ===")
    status, ctype, body = http_get(path, key)
    print(f"  HTTP {status} {ctype.split(';')[0]}")
    if status == 200 and "json" in ctype.lower():
        try:
            describe(json.loads(body))
        except Exception as e:
            print(f"  (JSON invalido: {e})")
    else:
        print(f"  corpo(140c): {body[:140].replace(chr(10),' ')}")


def probe():
    key = os.environ.get("PACTO_API_KEY", "").strip()
    if not key:
        print("[probe] ERRO: PACTO_API_KEY ausente."); sys.exit(1)
    print(f"[probe] unidade={os.environ.get('PACTO_UNIT','?')} (ApiKey len={len(key)})")
    qs = "?page=0&size=3"
    for label, p in [
        ("clientes_geral",            "/clientes/geral" + qs),
        ("clientes_geral_de_clientes","/clientes/geral-de-clientes" + qs),
        ("clientes_relatorio",        "/clientes/relatorio" + qs),
        ("clientes_aniversariantes",  "/clientes/aniversariantes" + qs),
        ("clientes_cancelados",       "/clientes/cancelados" + qs),
        ("clientes_trancados",        "/clientes/trancados" + qs),
        ("clientes_bare",             "/clientes" + qs),
        ("clientes_completo",         "/clientes/completo" + qs),
        ("clientes_detalhado",        "/clientes/detalhado" + qs),
    ]:
        try_json(label, p, key)
    print("\n[probe] fim.")


if __name__ == "__main__":
    if "--probe" in sys.argv:
        probe()
    else:
        print("Use --probe.")
