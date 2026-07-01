#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PROBE PACTO — CONTRATO de aluno ATIVO p/ achar MODALIDADE. PII-safe."""
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


def deep_find_keys(obj, pat, prefix="", out=None, depth=0):
    if out is None:
        out = []
    if depth > 4:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else k
            if re.search(pat, k, re.I) and isinstance(v, (str, int, float)):
                out.append((p, str(v)[:50]))
            deep_find_keys(v, pat, p, out, depth + 1)
    elif isinstance(obj, list) and obj:
        deep_find_keys(obj[0], pat, prefix + "[0]", out, depth + 1)
    return out


def probe():
    key = os.environ.get("PACTO_API_KEY", "").strip()
    print(f"[diag] len={len(key)}")

    # varre paginas do roster ate achar um ATIVO, pega matricula
    mat = None
    for pg in range(0, 40):
        st, rs = gj(f"/clientes/simples?page={pg}&size=50", key)
        rows = content(rs)
        if not rows:
            break
        for r in rows:
            if isinstance(r, dict) and (r.get("situacao") or "").upper() == "ATIVO" and r.get("matricula"):
                mat = r["matricula"]; break
        if mat:
            break
    print(f"[diag] matricula ATIVO encontrada: {'sim' if mat else 'nao'} (pagina {pg})")

    if mat:
        st, c = gj(f"/v1/contrato/matricula/{mat}", key)
        print(f"\n=== /v1/contrato/matricula/{{ativo}} -> HTTP {st} ===")
        rows = content(c)
        print(f"    itens: {len(rows)}")
        r = rows[0] if rows else None
        if isinstance(r, dict):
            print(f"    campos ({len(r)}): {sorted(r.keys())}")
            for k, v in r.items():
                if isinstance(v, dict):
                    print(f"      {k} (dict) chaves: {sorted(v.keys())}")
                elif isinstance(v, list) and v and isinstance(v[0], dict):
                    print(f"      {k} (list) chaves: {sorted(v[0].keys())}")
            hits = deep_find_keys(r, r"modalidade|plano|atividade|produto|descri|nomePlano|nomeContrato")
            print(f"    campos modalidade/plano (valor): {hits[:20]}")
        elif isinstance(c, dict):
            print(f"    topo chaves: {sorted(c.keys())}")
            hits = deep_find_keys(c, r"modalidade|plano|atividade|produto|descri")
            print(f"    modalidade/plano encontrados: {hits[:20]}")
    print("\n[diag] fim.")


if __name__ == "__main__":
    probe()
