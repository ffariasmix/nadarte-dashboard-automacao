#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""716N — PROBE: achar endpoint de ACESSOS POR PERIODO (unidade inteira), p/ evitar coleta aluno-a-aluno.
PII-safe: imprime status, contagem e presenca de campos (nunca cpf/nome)."""
import os, sys, json
import urllib.request, urllib.error

BASE = "https://apigw.pactosolucoes.com.br"
KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()
D1BR, D2BR = "01/06/2026", "01/07/2026"
D1ISO, D2ISO = "2026-06-01", "2026-07-01"


def http_get(path, headers=None, timeout=40):
    req = urllib.request.Request(BASE + path, method="GET")
    req.add_header("Authorization", "Bearer " + KEY)
    req.add_header("Accept", "application/json")
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


def lst(o):
    if isinstance(o, list):
        return o
    if isinstance(o, dict):
        for k in ("content", "data", "result", "results", "rows", "list", "items", "acessos", "registros"):
            v = o.get(k)
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                for k2 in ("lista", "content", "items", "rows"):
                    if isinstance(v.get(k2), list):
                        return v[k2]
    return []


def has(d, *names):
    if not isinstance(d, dict):
        return False
    low = {k.lower() for k in d}
    return any(n.lower() in low for n in names)


def probe(label, path, headers=None):
    st, o = gj(path, headers)
    rows = lst(o)
    info = ""
    if rows and isinstance(rows[0], dict):
        r0 = rows[0]
        campos = []
        if has(r0, "cpf"): campos.append("cpf")
        if has(r0, "matricula", "mat", "matriculaCliente"): campos.append("matricula")
        if has(r0, "dtHrEntrada", "dataDeAcesso", "dataEntrada", "data"): campos.append("data")
        info = f" campos={campos} chaves={sorted(r0.keys())[:10]}"
    elif st == 200 and not rows:
        info = f" (200 sem lista) cru={str(o)[:120]}"
    elif st != 200:
        info = f" cru={str(o)[:120]}"
    mark = "  <<<<< TEM DADOS" if rows else ""
    print(f"  [{st}] n={len(rows)} {label}{mark}{info}")


def main():
    if not KEY:
        print("[v] sem chave"); sys.exit(1)
    print("[PROBE acessos-por-periodo] janela", D1BR, "->", D2BR)

    cands = [
        ("acessos-cliente?ini/fim BR",     f"/acessos-cliente?dataInicial={D1BR}&dataFinal={D2BR}&page=0&size=50", None),
        ("acessos-cliente?inicio/fim ISO", f"/acessos-cliente?dataInicio={D1ISO}&dataFim={D2ISO}&page=0&size=50", None),
        ("acessos-cliente/periodo BR",     f"/acessos-cliente/periodo?dataInicial={D1BR}&dataFinal={D2BR}&page=0&size=50", None),
        ("acessos-cliente/listar BR",      f"/acessos-cliente/listar?dataInicial={D1BR}&dataFinal={D2BR}&page=0&size=50", None),
        ("acessos-cliente/relatorio BR",   f"/acessos-cliente/relatorio?dataInicial={D1BR}&dataFinal={D2BR}&page=0&size=50", None),
        ("clientes/listar-registro ?datas BR", f"/clientes/listar-registro-de-acesso?dataInicial={D1BR}&dataFinal={D2BR}&page=0&size=50", None),
        ("clientes/listar-registro ?datas ISO",f"/clientes/listar-registro-de-acesso?dataInicio={D1ISO}&dataFim={D2ISO}&page=0&size=50", None),
        ("acessos?datas BR",               f"/acessos?dataInicial={D1BR}&dataFinal={D2BR}&page=0&size=50", None),
        ("v1/acesso?datas BR",             f"/v1/acesso?dataInicial={D1BR}&dataFinal={D2BR}&page=0&size=50", None),
        ("relatorios/acessos BR",          f"/relatorios/acessos?dataInicial={D1BR}&dataFinal={D2BR}&page=0&size=50", None),
        ("psec/acessos?datas BR e1",       f"/psec/acessos?dataInicial={D1BR}&dataFinal={D2BR}&page=0&size=50", {"empresaId": 1}),
        ("psec/alunos/lista-rapida limite2000 e1", "/psec/alunos/lista-rapida-acessos?tipo=1&limite=2000", {"empresaId": 1}),
        ("acessos-cliente/por-periodo BR", f"/acessos-cliente/por-periodo?dataInicial={D1BR}&dataFinal={D2BR}&page=0&size=50", None),
        ("acessos-cliente/consulta BR",    f"/acessos-cliente/consulta?dataInicial={D1BR}&dataFinal={D2BR}&page=0&size=50", None),
        ("psec/relatorios/acessos e1",     f"/psec/relatorios/acessos?dataInicial={D1BR}&dataFinal={D2BR}&page=0&size=50", {"empresaId": 1}),
    ]
    for label, path, hdr in cands:
        probe(label, path, hdr)

    print("\n[v] fim.")


if __name__ == "__main__":
    main()
