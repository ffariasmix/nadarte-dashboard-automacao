#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""716N — VALIDACAO FINAL do pipeline correto:
roster ATIVO -> /clientes/{matricula}/dados-pessoais (codPessoa+cpf+dataMatricula)
-> /acessos-cliente/by-pessoa/{codPessoa}. Confere acc.cliente.codigo==codigoCliente e
mede cobertura real (2026 / ult.90d). PII-safe: cpf mascarado, sem nomes."""
import os, sys, json, time
from datetime import datetime, timezone, timedelta
import urllib.request, urllib.error

BASE = "https://apigw.pactosolucoes.com.br"
KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()
NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)
D90 = NOW - timedelta(days=90)


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
        for k in ("content", "data", "result", "results", "rows", "list", "items", "clientes", "acessos"):
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


def unwrap(o):
    """dados-pessoais retorna {content:{...}} ou {...}."""
    if isinstance(o, dict):
        c = o.get("content")
        if isinstance(c, dict):
            return c
        return o
    return {}


def to_dt(v):
    if v is None:
        return None
    try:
        if isinstance(v, (int, float)) or (isinstance(v, str) and str(v).isdigit()):
            n = int(v)
            if n > 10_000_000_000:
                n //= 1000
            return datetime.fromtimestamp(n, tz=timezone.utc)
        s = str(v)[:19].replace("T", " ")
        for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
            try:
                return datetime.strptime(s, f).replace(tzinfo=timezone.utc)
            except Exception:
                pass
    except Exception:
        return None
    return None


def main():
    if not KEY:
        print("[v] sem chave"); sys.exit(1)

    # roster ATIVO
    todos = []
    for pg in range(0, 70):
        st, o = gj(f"/clientes/simples?page={pg}&size=200")
        r = lst(o)
        if not r:
            break
        todos.extend([c for c in r if isinstance(c, dict)])
        if len(r) < 200:
            break
    ativos = [c for c in todos if str(gv(c, "situacao") or "").upper() == "ATIVO"]
    print(f"[roster] total={len(todos)} ATIVO={len(ativos)}")

    N = 70
    step = max(1, len(ativos) // N)
    sample = ativos[::step][:N]

    res_dp = 0        # dados-pessoais ok
    tem_codpessoa = 0
    tem_cpf = 0
    confere = 0       # acc.cliente.codigo == codigoCliente
    nao_confere = 0
    com_acesso = com_2026 = com_90d = 0
    meios26 = {}
    total_acc = 0
    dmin = dmax = None
    exemplos = []

    for c in sample:
        C = gv(c, "codigoCliente", "codigo")
        M = gv(c, "matricula")
        st, o = gj(f"/clientes/{M}/dados-pessoais")
        dp = unwrap(o) if st == 200 else {}
        cp = gv(dp, "codigoPessoa", "codPessoa")
        cpf = gv(dp, "cpf")
        if dp:
            res_dp += 1
        if cp:
            tem_codpessoa += 1
        if cpf:
            tem_cpf += 1
        if not cp:
            continue

        st, o = gj(f"/acessos-cliente/by-pessoa/{cp}?page=0&size=300")
        acc = lst(o) if st == 200 else []
        if acc:
            a0 = acc[0]
            cli = gv(a0, "cliente") or {}
            acc_cli = gv(cli, "codigo")
            if str(acc_cli) == str(C):
                confere += 1
            else:
                nao_confere += 1
            if len(exemplos) < 6:
                exemplos.append(f"    codCli={C} matr={M} codPessoa={cp} -> acc.cliente.codigo={acc_cli} {'OK' if str(acc_cli)==str(C) else 'DIVERGE'}")
            com_acesso += 1
            total_acc += len(acc)
            h26 = h90 = False
            for a in acc:
                dt = to_dt(gv(a, "dtHrEntrada") or gv(a, "dataDeAcesso") or gv(a, "dataRegistro"))
                if dt:
                    dmin = dt if (dmin is None or dt < dmin) else dmin
                    dmax = dt if (dmax is None or dt > dmax) else dmax
                    if dt.year == 2026:
                        h26 = True
                        m = str(gv(a, "meioIdentificacaoEntradaApresentar") or gv(a, "meioIdentificacaoEntrada") or "?")
                        meios26[m] = meios26.get(m, 0) + 1
                    if dt >= D90:
                        h90 = True
            com_2026 += 1 if h26 else 0
            com_90d += 1 if h90 else 0
        time.sleep(0.03)

    n = len(sample)
    print(f"\n[ponte dados-pessoais] amostra={n}")
    print(f"  dados-pessoais 200: {res_dp}  | com codigoPessoa: {tem_codpessoa}  | com cpf: {tem_cpf}")
    print(f"\n[validacao id] by-pessoa(codPessoa): confere={confere}  diverge={nao_confere}")
    for e in exemplos:
        print(e)
    print(f"\n[cobertura REAL]")
    print(f"  com >=1 acesso: {com_acesso}/{n} ({100*com_acesso/max(1,n):.0f}%)")
    print(f"  acesso em 2026: {com_2026}/{n} ({100*com_2026/max(1,n):.0f}%)")
    print(f"  acesso ult.90d: {com_90d}/{n} ({100*com_90d/max(1,n):.0f}%)")
    print(f"  total registros: {total_acc}")
    if dmin and dmax:
        print(f"  intervalo: {dmin.date()} -> {dmax.date()}")
    print(f"  meios 2026: { {k: meios26[k] for k in sorted(meios26, key=lambda x:-meios26[x])[:6]} }")
    print("\n[v] fim.")


if __name__ == "__main__":
    main()
