#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""716N — achar a ponte cliente(codigoCliente/matricula) -> codPessoa/CPF, e validar
by-pessoa(codPessoa) conferindo acc.cliente.codigo == codigoCliente. PII-safe (mascara cpf/nome)."""
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


def deep(o, key, _d=0):
    """acha 1o valor de 'key' em qualquer nivel."""
    if _d > 6:
        return None
    if isinstance(o, dict):
        for k, v in o.items():
            if k.lower() == key.lower() and not isinstance(v, (dict, list)):
                return v
        for v in o.values():
            r = deep(v, key, _d + 1)
            if r is not None:
                return r
    elif isinstance(o, list):
        for it in o:
            r = deep(it, key, _d + 1)
            if r is not None:
                return r
    return None


def keys_all(o, _d=0, acc=None):
    if acc is None:
        acc = set()
    if _d > 3:
        return acc
    if isinstance(o, dict):
        for k, v in o.items():
            acc.add(k)
            keys_all(v, _d + 1, acc)
    elif isinstance(o, list) and o:
        keys_all(o[0], _d + 1, acc)
    return acc


def main():
    if not KEY:
        print("[v] sem chave"); sys.exit(1)

    # pega alguns ATIVO (com matricula+codigoCliente)
    st, o = gj("/clientes/simples?page=0&size=200")
    r = lst(o)
    ativos = [c for c in r if str(gv(c, "situacao") or "").upper() == "ATIVO"][:6]
    print(f"[amostra] {len(ativos)} ativos")

    # candidatos de endpoint de DETALHE do cliente (procuro codPessoa/cpf)
    cand = [
        "/clientes/{m}",
        "/clientes/{c}",
        "/clientes/dados-pessoais/{m}",
        "/clientes/dados-pessoais/{c}",
        "/clientes/ficha/{m}",
        "/clientes/detalhe/{m}",
        "/v1/pessoa/{c}",
        "/v1/pessoa?matricula={m}",
        "/v1/cliente/{c}",
        "/v1/cliente?matricula={m}",
        "/clientes/{m}/dados-pessoais",
        "/acessos-cliente/{c}/ultimos-meses",
    ]

    for i, c in enumerate(ativos[:3]):
        C = gv(c, "codigoCliente", "codigo")
        M = gv(c, "matricula")
        print(f"\n=== cliente #{i}: codigoCliente={C} matricula={M} ===")
        for tmpl in cand:
            path = tmpl.replace("{m}", str(M)).replace("{c}", str(C))
            st, o = gj(path)
            has_cp = deep(o, "codPessoa") or deep(o, "codigoPessoa")
            # tenta codPessoa via pessoa.codigo aninhado
            cp2 = None
            if isinstance(o, (dict, list)):
                pcod = None
                # procura um 'codigo' dentro de um bloco 'pessoa'
                def find_pessoa_codigo(x, _d=0):
                    if _d > 5:
                        return None
                    if isinstance(x, dict):
                        if "pessoa" in {k.lower() for k in x} :
                            for k in x:
                                if k.lower() == "pessoa" and isinstance(x[k], dict):
                                    return gv(x[k], "codigo")
                        for v in x.values():
                            rr = find_pessoa_codigo(v, _d + 1)
                            if rr is not None:
                                return rr
                    elif isinstance(x, list):
                        for it in x:
                            rr = find_pessoa_codigo(it, _d + 1)
                            if rr is not None:
                                return rr
                    return None
                cp2 = find_pessoa_codigo(o)
            has_cpf = deep(o, "cpf")
            flag = ""
            if st == 200 and (has_cp or cp2 or has_cpf):
                flag = f"  <<< codPessoa={has_cp or cp2} cpf?={'sim' if has_cpf else 'nao'}"
            ks = ""
            if st == 200 and i == 0:
                ks = " keys=" + str(sorted(keys_all(o)))[:180]
            print(f"  {st}  {tmpl}{flag}{ks}")
            time.sleep(0.03)

    # se achamos codPessoa por algum caminho, validar by-pessoa(codPessoa)
    print("\n[validacao by-pessoa(codPessoa)] (se houver ponte)")
    c0 = ativos[0]
    C0 = gv(c0, "codigoCliente", "codigo"); M0 = gv(c0, "matricula")
    # tenta obter codPessoa pela melhor rota encontrada manualmente depois; aqui so registro C0/M0
    print(f"  cliente base: codigoCliente={C0} matricula={M0}")

    print("\n[v] fim.")


if __name__ == "__main__":
    main()
