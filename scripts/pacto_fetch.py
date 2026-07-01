#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PROBE PACTO — endpoint de CONTRATO p/ achar a MODALIDADE. PII-safe (nomes de campos + modalidade, que nao e PII)."""
import os, sys, json, re
import urllib.request, urllib.error

BASE = "https://apigw.pactosolucoes.com.br"


def http_get(path, key, timeout=45):
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
        return st, json.loads(body)
    except Exception:
        return st, None


def content(o):
    if isinstance(o, list):
        return o
    if isinstance(o, dict):
        for k in ("content", "data", "rows", "list", "items", "result", "results"):
            if isinstance(o.get(k), list):
                return o[k]
    return []


def dump(label, obj):
    rows = content(obj)
    r = rows[0] if rows else (obj if isinstance(obj, dict) else None)
    if not isinstance(r, dict):
        print(f"    ({label}) sem objeto"); return
    print(f"    campos ({len(r)}): {sorted(r.keys())}")
    # destaca campos que parecem plano/modalidade/atividade (nomes + valores curtos nao-PII)
    interesse = [k for k in r if re.search(r"modalidade|plano|atividade|produto|servico|descri|tipo|categoria|nome", k, re.I)]
    for k in interesse:
        v = r.get(k)
        if isinstance(v, (str, int, float, bool)) and not re.search(r"pessoa|cliente|cpf|email|telefone", k, re.I):
            print(f"      {k} = {str(v)[:60]}")
        elif isinstance(v, dict):
            print(f"      {k} (dict) chaves: {sorted(v.keys())}")
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            print(f"      {k} (list[dict]) chaves: {sorted(v[0].keys())}")


def probe():
    key = os.environ.get("PACTO_API_KEY", "").strip()
    print(f"[diag] len={len(key)}")

    # matricula de exemplo do roster
    st, rs = gj("/clientes/simples?page=0&size=10", key)
    mat = next((r.get("matricula") for r in content(rs) if isinstance(r, dict) and r.get("matricula")), None)
    print(f"[diag] matricula exemplo capturada: {'sim' if mat else 'nao'}")

    # 1) contratos por matricula
    if mat:
        st, c = gj(f"/v1/contrato/matricula/{mat}", key)
        print(f"\n=== /v1/contrato/matricula/{{mat}} -> HTTP {st} ===")
        dump("por_matricula", c)

    # 2) contratos paginados (bulk)
    st, c2 = gj("/v1/contrato?page=0&size=3", key)
    print(f"\n=== /v1/contrato?page=0&size=3 -> HTTP {st} ===")
    dump("bulk", c2)

    print("\n[diag] fim.")


if __name__ == "__main__":
    probe()
