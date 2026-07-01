#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PROBE PACTO — diagnostico do JOIN cliente.pessoa <-> /v1/pessoa.codigo. PII-safe."""
import os, sys, json
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


def probe():
    key = os.environ.get("PACTO_API_KEY", "").strip()
    print(f"[diag] len={len(key)}")

    # 1) um codigoCliente
    st, rs = gj("/clientes/simples?page=0&size=10", key)
    cc = next((r.get("codigoCliente") for r in content(rs) if isinstance(r, dict) and r.get("codigoCliente")), None)
    print(f"[diag] codigoCliente={cc}")

    # 2) estrutura de cliente.pessoa num acesso (SO tipo/chaves, sem valores textuais)
    st, ac = gj(f"/acessos-cliente/by-pessoa/{cc}?page=0&size=2", key)
    rows = content(ac)
    if rows:
        cl = rows[0].get("cliente")
        print(f"[diag] cliente tipo={type(cl).__name__}")
        if isinstance(cl, dict):
            pv = cl.get("pessoa")
            print(f"[diag] cliente.pessoa tipo={type(pv).__name__}")
            if isinstance(pv, dict):
                print(f"[diag] cliente.pessoa chaves={sorted(pv.keys())}")
                # imprime SO campos numericos/ids (nao textuais)
                ids = {k: v for k, v in pv.items() if isinstance(v, (int, float, bool))}
                print(f"[diag] cliente.pessoa ids-numericos={json.dumps(ids)}")
            else:
                print(f"[diag] cliente.pessoa valor(num?)={pv if isinstance(pv,(int,float)) else 'nao-numerico'}")
            print(f"[diag] cliente.codigo={cl.get('codigo')} | cliente.codigoMatricula={cl.get('codigoMatricula')}")

    # 3) um codigo de /v1/pessoa (id interno, nao PII) e teste de detalhe
    st, pj = gj("/v1/pessoa?page=0&size=3", key)
    prow = content(pj)
    pk = prow[0].get("codigo") if prow and isinstance(prow[0], dict) else None
    print(f"[diag] /v1/pessoa.codigo exemplo={pk}")
    if pk is not None:
        st2, d = gj(f"/v1/pessoa/{pk}", key)
        drow = content(d)
        keys = sorted((drow[0] if drow else (d if isinstance(d, dict) else {})).keys())
        print(f"[diag] GET /v1/pessoa/{pk} -> HTTP {st2} | topo={type(d).__name__} | campos={keys}")

    print("[diag] fim.")


if __name__ == "__main__":
    probe()
