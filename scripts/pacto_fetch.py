#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""716N — achar a fonte de acesso COMPLETA (facial+catraca+chamada), como o export.
Testa /clientes/listar-registro-de-acesso/{matricula} e /psec/alunos/lista-rapida-acessos.
PII-safe. Env: PACTO_KEY_716NORTE"""
import os, sys, re, json, urllib.parse
import urllib.request, urllib.error

BASE = "https://apigw.pactosolucoes.com.br"
KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()


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


def descreve(o):
    rows = content(o)
    if not rows:
        return f"vazio/estrutura: {str(o)[:120]}"
    r = rows[0] if isinstance(rows[0], dict) else None
    if not r:
        return f"itens={len(rows)} (nao-dict)"
    campos = sorted(r.keys())
    # valores nao-PII de interesse (meio, data, coletor)
    amostra = {}
    for k, v in r.items():
        if re.search(r"meio|ident|data|entrada|hora|coletor|sentido|situac|acesso", k, re.I) and isinstance(v, (str, int, float, bool)):
            amostra[k] = str(v)[:35]
    return f"itens={len(rows)} | campos={campos} | amostra={json.dumps(amostra, ensure_ascii=False)}"


def main():
    if not KEY:
        print("[x] sem chave"); sys.exit(1)
    # matricula ATIVA
    mat = None
    for pg in range(30):
        st, o = gj(f"/clientes/simples?page={pg}&size=50")
        for r in content(o):
            if isinstance(r, dict) and (r.get("situacao") or "").upper() == "ATIVO" and r.get("matricula"):
                mat = r["matricula"]; break
        if mat:
            break
    print(f"[x] matricula ativa: {'ok' if mat else 'nao'}")
    if not mat:
        return
    matq = urllib.parse.quote(str(mat))

    di, df = "2026-01-01", "2026-06-30"
    dib, dfb = "01/01/2026", "30/06/2026"
    variantes = [
        "",
        f"?dataInicial={di}&dataFinal={df}",
        f"?dataInicio={di}&dataFim={df}",
        f"?inicio={di}&fim={df}",
        f"?dataInicial={urllib.parse.quote(dib)}&dataFinal={urllib.parse.quote(dfb)}",
        f"?dtInicio={di}&dtFim={df}",
    ]
    print("\n### /clientes/listar-registro-de-acesso/{matricula} ###")
    for qs in variantes:
        st, o = gj(f"/clientes/listar-registro-de-acesso/{matq}{qs}")
        tag = "OK" if (st == 200 and content(o)) else ""
        print(f"  {qs or '(sem qs)':45} HTTP {st} {tag}")
        if st == 200 and content(o):
            print("     -> " + descreve(o)); break

    print("\n### /psec/alunos/lista-rapida-acessos (em massa) ###")
    for qs in variantes[1:]:
        st, o = gj(f"/psec/alunos/lista-rapida-acessos{qs}")
        tag = "OK" if (st == 200 and content(o)) else ""
        print(f"  {qs:45} HTTP {st} {tag}")
        if st == 200 and content(o):
            print("     -> " + descreve(o)); break

    print("\n[x] fim.")


if __name__ == "__main__":
    main()
