#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROBE PACTO — confirma o JOIN cliente<->pessoa para ligar demograficos.
NAO imprime dados pessoais. Uso: python scripts/pacto_fetch.py --probe
"""
import os, sys, re, json
import urllib.request, urllib.error

BASE = "https://apigw.pactosolucoes.com.br"
SENS = re.compile(r"cpf|nasc|sexo|nome|telefone|email|rg", re.I)


def http_get(path, key, timeout=45):
    req = urllib.request.Request(BASE + path, method="GET")
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.headers.get("Content-Type", "") if e.headers else ""), (e.read().decode("utf-8", "replace") if e.fp else "")
    except Exception as e:
        return -1, "", "EXC: " + str(e)


def gj(path, key):
    st, ct, body = http_get(path, key)
    if st == 200 and "json" in ct.lower():
        try:
            return st, json.loads(body)
        except Exception:
            return st, None
    return st, body


def rows(o):
    if isinstance(o, list):
        return o
    if isinstance(o, dict):
        for k in ("content", "data", "rows", "list", "items", "registros", "dados", "result", "results"):
            if isinstance(o.get(k), list):
                return o[k]
    return []


def fields(o):
    r = (o[0] if isinstance(o, list) and o else (rows(o)[0] if rows(o) else (o if isinstance(o, dict) else None)))
    return sorted(r.keys()) if isinstance(r, dict) else None


def probe():
    key = os.environ.get("PACTO_API_KEY", "").strip()
    if not key:
        print("[probe] ERRO: sem PACTO_API_KEY"); sys.exit(1)
    print(f"[probe] unidade={os.environ.get('PACTO_UNIT','?')} (len={len(key)})")

    # roster
    st, obj = gj("/clientes/simples?page=0&size=10", key)
    rs = rows(obj)
    print(f"[clientes_simples] HTTP {st} | linhas {len(rs)} | campos {fields(obj)}")
    cc = next((r.get("codigoCliente") for r in rs if isinstance(r, dict) and r.get("codigoCliente")), None)
    print(f"[clientes_simples] codigoCliente exemplo capturado: {'sim' if cc else 'nao'}")

    # /v1/pessoa lista + paginacao
    st, pj = gj("/v1/pessoa?page=0&size=3", key)
    print(f"[v1_pessoa_lista] HTTP {st} | campos {fields(pj)} | tipo_topo {type(pj).__name__}")
    if isinstance(pj, dict):
        print(f"[v1_pessoa_lista] chaves_topo {sorted(pj.keys())}")

    pp = None
    if cc:
        st, ac = gj(f"/acessos-cliente/by-pessoa/{cc}?page=0&size=1", key)
        arow = rows(ac)
        cl = arow[0].get("cliente") if arow and isinstance(arow[0], dict) else None
        if isinstance(cl, dict):
            print(f"[acesso.cliente] chaves {sorted(cl.keys())}")
            pp = cl.get("pessoa")
        print(f"[join] cliente.pessoa capturado: {'sim' if pp else 'nao'}")

        # Testa /v1/pessoa/{id} com codPessoa e com codigoCliente, p/ saber qual e a chave
        for nome, val in [("codPessoa", pp), ("codigoCliente", cc)]:
            if val is None:
                continue
            st, d = gj(f"/v1/pessoa/{val}", key)
            f = fields(d)
            tem = [k for k in (f or []) if SENS.search(k)]
            print(f"[v1_pessoa/{nome}] HTTP {st} | campos {f} | sensiveis {tem}")
            st2, d2 = gj(f"/pessoas/{val}", key)
            f2 = fields(d2)
            tem2 = [k for k in (f2 or []) if SENS.search(k)]
            print(f"[pessoas/{nome}] HTTP {st2} | campos {f2} | sensiveis {tem2}")
    print("\n[probe] fim.")


if __name__ == "__main__":
    probe() if "--probe" in sys.argv else print("Use --probe.")
