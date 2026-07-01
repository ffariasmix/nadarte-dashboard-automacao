#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""716N — decidir id/ponte de frequencia. Roster tem matricula+codigoCliente (sem cpf/codPessoa).
Testa: (A) rotulo dos meios; (B) relacao codigoCliente x pessoa.codigo; (C) recuperar 'vazios'
via endpoints por matricula. PII-safe: sem cpf/nome."""
import os, sys, json, time
import urllib.request, urllib.error

BASE = "https://apigw.pactosolucoes.com.br"
KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()


def http_get(path, headers=None, timeout=45):
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
        for k in ("content", "data", "result", "results", "rows", "list", "items", "alunos", "acessos", "clientes"):
            v = o.get(k)
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                for k2 in ("lista", "content", "items", "rows"):
                    if isinstance(v.get(k2), list):
                        return v[k2]
    return []


def gv(d, *names):
    if not isinstance(d, dict):
        return None
    low = {k.lower(): k for k in d}
    for n in names:
        if n.lower() in low:
            return d[low[n.lower()]]
    return None


def main():
    if not KEY:
        print("[v] sem chave"); sys.exit(1)

    # roster ATIVO
    todos = []
    for pg in range(0, 60):
        st, o = gj(f"/clientes/simples?page={pg}&size=200")
        r = lst(o)
        if not r:
            break
        todos.extend([c for c in r if isinstance(c, dict)])
        if len(r) < 200:
            break
    ativos = [c for c in todos if str(gv(c, "situacao") or "").upper() == "ATIVO"]
    print(f"[roster] total={len(todos)} ATIVO={len(ativos)}")

    # amostra espalhada
    N = 50
    step = max(1, len(ativos) // N)
    sample = ativos[::step][:N]

    # ---- A) rotulo dos meios + B) relacao de ids ----
    labels = {}
    vazios = []
    comdata = 0
    rel_lines = []
    for c in sample:
        cc = gv(c, "codigoCliente", "codigo")
        mat = gv(c, "matricula")
        st, o = gj(f"/acessos-cliente/by-pessoa/{cc}?page=0&size=50")
        acc = lst(o) if st == 200 else []
        if acc:
            comdata += 1
            a0 = acc[0]
            for a in acc:
                code = str(gv(a, "meioIdentificacaoEntrada"))
                lab = gv(a, "meioIdentificacaoEntradaApresentar")
                if lab and code not in labels:
                    labels[code] = str(lab)
            cli = gv(a0, "cliente") or {}
            pes = gv(a0, "pessoa") or {}
            if len(rel_lines) < 8:
                rel_lines.append(
                    f"    usei codigoCliente={cc} matr={mat} | acc.cliente.codigo={gv(cli,'codigo')} acc.pessoa.codigo={gv(pes,'codigo')} acc.matricula={gv(a0,'matricula')}"
                )
        else:
            vazios.append(c)
        time.sleep(0.03)

    print(f"\n[A] meios (codigo->rotulo): {labels}")
    print(f"\n[B] relacao de ids (amostra):")
    for l in rel_lines:
        print(l)
    print(f"\n[cobertura by-pessoa(codigoCliente)] amostra={len(sample)} | com_dados={comdata} ({100*comdata/max(1,len(sample)):.0f}%) | vazios={len(vazios)}")

    # ---- C) recuperar VAZIOS por matricula ----
    if vazios:
        alvos = vazios[:12]
        print(f"\n[C] tentando recuperar {len(alvos)} 'vazios' por endpoints com matricula:")
        variantes = [
            "/clientes/listar-registro-de-acesso/{m}",
            "/clientes/listar-registro-de-acesso/{m}?dataInicial=01/01/2025&dataFinal=01/07/2026",
            "/clientes/listar-registro-de-acesso/{m}?dataInicio=2025-01-01&dataFim=2026-07-01",
            "/clientes/listar-registro-de-acesso/{m}?page=0&size=50",
            "/acessos-cliente/by-pessoa/{m}?page=0&size=50",  # by matricula (teste)
        ]
        recuperados = {v: 0 for v in variantes}
        status_amostra = {}
        for c in alvos:
            mat = gv(c, "matricula")
            for v in variantes:
                st, o = gj(v.format(m=mat))
                status_amostra.setdefault(v, st)
                if st == 200 and lst(o):
                    recuperados[v] += 1
                time.sleep(0.03)
        for v in variantes:
            print(f"    {status_amostra.get(v)}  recuperou={recuperados[v]}/{len(alvos)}  <- {v}")

    print("\n[v] fim.")


if __name__ == "__main__":
    main()
