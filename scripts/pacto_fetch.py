#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROBE PACTO — endpoint de CADASTRO COMPLETO (grupo Pessoa).
NAO imprime dados pessoais (so nomes de campos). Uso: python scripts/pacto_fetch.py --probe
Env: PACTO_API_KEY (Bearer), PACTO_UNIT
"""
import os, sys, re, json
import urllib.request, urllib.error

BASE = "https://apigw.pactosolucoes.com.br"
SENSIVEL = re.compile(r"cpf|nasc|sexo|genero|telefone|email|nome|rg|endereco|logradouro|bairro|cep", re.I)


def http_get(path, key, timeout=45):
    req = urllib.request.Request(BASE + path, method="GET")
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace") if e.fp else ""
        return e.code, (e.headers.get("Content-Type", "") if e.headers else ""), body
    except Exception as e:
        return -1, "", "EXC: " + str(e)


def get_json(path, key):
    st, ct, body = http_get(path, key)
    return st, ct, (json.loads(body) if st == 200 and "json" in ct.lower() else body)


def first_row(obj):
    if isinstance(obj, list):
        return obj[0] if obj else None
    if isinstance(obj, dict):
        for k in ("content", "data", "rows", "list", "items", "registros", "dados", "result", "results"):
            if isinstance(obj.get(k), list) and obj[k]:
                return obj[k][0]
        return obj
    return None


def show_fields(label, obj):
    row = first_row(obj)
    if not isinstance(row, dict):
        print(f"    ({label}) sem objeto/linha"); return
    ks = sorted(row.keys())
    print(f"    campos ({len(ks)}): {ks}")
    # destaca campos sensiveis presentes (so o NOME do campo, nunca o valor)
    hits = [k for k in ks if SENSIVEL.search(k)]
    print(f"    >> tem cadastro? campos sensiveis presentes: {hits}")
    # tipos dos campos aninhados (dict) — so chaves
    for k, v in row.items():
        if isinstance(v, dict):
            print(f"    .{k} (dict) chaves: {sorted(v.keys())}")


def try_ep(label, path, key):
    print(f"\n=== {label}  GET {path} ===")
    st, ct, obj = get_json(path, key)
    print(f"  HTTP {st} {str(ct).split(';')[0]}")
    if st == 200 and not isinstance(obj, str):
        show_fields(label, obj)
    else:
        print(f"  corpo(140c): {str(obj)[:140]}")


def probe():
    key = os.environ.get("PACTO_API_KEY", "").strip()
    if not key:
        print("[probe] ERRO: PACTO_API_KEY ausente."); sys.exit(1)
    print(f"[probe] unidade={os.environ.get('PACTO_UNIT','?')} (ApiKey len={len(key)})")

    # 1) codigoCliente do roster
    st, ct, obj = get_json("/clientes/simples?page=0&size=5", key)
    cod = None
    row = first_row(obj) if st == 200 else None
    if isinstance(obj, list):
        for r in obj:
            if isinstance(r, dict) and r.get("codigoCliente"):
                cod = r["codigoCliente"]; break
    print(f"[probe] codigoCliente: {'ok' if cod else 'nao'}")

    # 2) codPessoa a partir de um registro de acesso (cliente.pessoa)
    codpessoa = None
    if cod:
        st, ct, ac = get_json(f"/acessos-cliente/by-pessoa/{cod}?page=0&size=1", key)
        arow = first_row(ac) if st == 200 else None
        if isinstance(arow, dict):
            cl = arow.get("cliente")
            if isinstance(cl, dict):
                codpessoa = cl.get("pessoa") or cl.get("codigo")
                print(f"    cliente.chaves: {sorted(cl.keys())}")
    print(f"[probe] codPessoa: {'ok' if codpessoa else 'nao'} (valor oculto)")

    # 3) Endpoints de cadastro (grupo Pessoa)
    if codpessoa:
        cp = str(codpessoa)
        try_ep("pessoas_detalhe",   f"/pessoas/{cp}", key)
        try_ep("v1_pessoa_id",      f"/v1/pessoa/{cp}", key)
        try_ep("venda_avulsa_pessoa", f"/venda-avulsa/pessoa/{cp}", key)
    # 4) Lista de pessoas (bulk) e /clientes/simplificado (por cpf — so testa forma)
    try_ep("v1_pessoa_lista", "/v1/pessoa?page=0&size=3", key)
    print("\n[probe] fim.")


if __name__ == "__main__":
    if "--probe" in sys.argv:
        probe()
    else:
        print("Use --probe.")
