#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pacto_probe_contrato.py — Probe PII-safe para descobrir o CAMPO DE VALOR do contrato
na API PACTO (para ticket real / perda real por aluno). Nao loga nome/CPF: apenas
nomes de campos, valores numericos de plano e contagens.

Reaproveita helpers testados do pacto_fetch.py. Roda so na 716 Norte (canario).
Uso (GitHub Actions, com Secret): PACTO_KEY_716NORTE=... python scripts/pacto_probe_contrato.py
"""
import os, sys
from pacto_fetch import gj, lst, gv, unwrap, roster_full

KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()
if not KEY:
    print("[probe] sem PACTO_KEY_716NORTE", file=sys.stderr); sys.exit(0)

VAL_HINT = ("valor", "price", "preco", "mensal", "parcela", "plano", "total",
            "desconto", "liquid", "bruto", "vlr", "receita", "ticket")

def show_obj(tag, o):
    if isinstance(o, dict):
        print(f"[{tag}] keys={sorted(o.keys())}", file=sys.stderr)
        for k, v in o.items():
            kl = k.lower()
            if any(h in kl for h in VAL_HINT) and not isinstance(v, (dict, list)):
                print(f"[{tag}] {k} = {v!r}", file=sys.stderr)
            if isinstance(v, dict):
                for k2, v2 in v.items():
                    if any(h in k2.lower() for h in VAL_HINT):
                        print(f"[{tag}] {k}.{k2} = {v2!r}", file=sys.stderr)
    else:
        print(f"[{tag}] tipo={type(o).__name__} amostra={str(o)[:120]!r}", file=sys.stderr)

# 1) Endpoint documentado: /v1/contrato?page&size
st, o = gj(KEY, "/v1/contrato?page=0&size=5")
items = lst(o)
print(f"[/v1/contrato] status={st} itens_na_pagina={len(items)}", file=sys.stderr)
if items:
    show_obj("/v1/contrato[0]", items[0])

# 2) Contrato por cliente: 3 matriculas ATIVAS, testando caminhos candidatos
full = roster_full(KEY)
ativos = [c for c in full if str(gv(c, "situacao") or "").upper() == "ATIVO"]
print(f"[roster] total={len(full)} ativos={len(ativos)}", file=sys.stderr)
for c in ativos[:3]:
    M = gv(c, "matricula"); cc = gv(c, "codigoCliente", "codigo")
    for path in (f"/clientes/{M}/contratos", f"/clientes/{M}/contrato",
                 f"/v1/cliente/{cc}/contrato", f"/v1/cliente/{cc}"):
        st2, o2 = gj(KEY, path)
        n = len(lst(o2)) if isinstance(o2, (list, dict)) else 0
        print(f"[cliente-path] {path} -> status={st2} lista={n}", file=sys.stderr)
        if st2 == 200:
            sample = (lst(o2)[0] if n else (unwrap(o2) if isinstance(o2, dict) else o2))
            show_obj(path, sample)
    print("---", file=sys.stderr)

print("[probe] fim (PII-safe: so campos/valores de plano, sem nome/CPF)", file=sys.stderr)
