#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PROBE 716N — Data Matricula + histórico de contrato (tenure/vencimentos). PII-safe."""
import os, sys, re, json
import urllib.request, urllib.error

BASE = "https://apigw.pactosolucoes.com.br"
KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()
KEYWORDS = re.compile(r"matric|data|nasc|plano|modalidade|venc|inicio|fim|contrato|situac|cadastr|desde|termin", re.I)
PII = re.compile(r"nome|cpf|email|telefone|rg|foto|senha", re.I)


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


def walk(obj, prefix="", out=None, depth=0):
    """coleta (chave-caminho, valor) para chaves de interesse, sem PII, ate profundidade 3."""
    if out is None:
        out = []
    if depth > 3:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else k
            if KEYWORDS.search(k) and not PII.search(k) and isinstance(v, (str, int, float, bool)):
                out.append((p, str(v)[:40]))
            walk(v, p, out, depth + 1)
    elif isinstance(obj, list) and obj:
        walk(obj[0], prefix + "[0]", out, depth + 1)
    return out


def keys_top(obj):
    if isinstance(obj, dict):
        for kk in ("content", "data", "result", "results"):
            if isinstance(obj.get(kk), list) and obj[kk]:
                return sorted(obj[kk][0].keys()) if isinstance(obj[kk][0], dict) else "list"
        return sorted(obj.keys())
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        return sorted(obj[0].keys())
    return type(obj).__name__


def probe(mat, cc):
    eps = [
        ("aluno_completo",   f"/psec/alunos/obter-aluno-completo-por-matricula/{mat}"),
        ("dados_pessoais",   f"/clientes/{mat}/dados-pessoais"),
        ("dados_plano",      f"/clientes/{mat}/dados-plano"),
        ("linha_contratos",  f"/clientes/{mat}/linha-tempo/contratos"),
        ("contratos_bymat",  f"/contratos/by-matricula/{mat}"),
        ("aluno_simples",    f"/psec/alunos/{mat}/obter-aluno-simples"),
    ]
    for label, path in eps:
        st, obj = gj(path)
        print(f"\n=== {label}  GET {path[:60]} -> HTTP {st} ===")
        if st == 200 and not isinstance(obj, str):
            print(f"   chaves: {keys_top(obj)}")
            hits = walk(obj)
            # dedup
            seen = set(); uniq = []
            for k, v in hits:
                if k not in seen:
                    seen.add(k); uniq.append((k, v))
            print(f"   campos-chave (nao-PII): {uniq[:25]}")
        else:
            print(f"   corpo(120c): {str(obj)[:120]}")


def main():
    if not KEY:
        print("[p] sem chave 716N"); sys.exit(1)
    # acha um ATIVO
    mat = cc = None
    for pg in range(30):
        st, o = gj(f"/clientes/simples?page={pg}&size=50")
        rows = o.get("content") if isinstance(o, dict) else (o if isinstance(o, list) else [])
        rows = rows or (o if isinstance(o, list) else [])
        for r in (rows or []):
            if isinstance(r, dict) and (r.get("situacao") or "").upper() == "ATIVO":
                mat = r.get("matricula"); cc = r.get("codigoCliente"); break
        if mat:
            break
    print(f"[p] matricula ATIVO ok={bool(mat)}")
    if mat:
        probe(mat, cc)
    print("\n[p] fim.")


if __name__ == "__main__":
    main()
