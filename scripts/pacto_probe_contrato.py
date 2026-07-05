#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pacto_probe_contrato.py (v12) — Qual campo do ACESSO (by-pessoa) identifica o aluno?
v11: acesso.matricula vem SEMPRE em branco. A base de conhecimento diz que o acesso tem
'cliente.codigo' (= codigoCliente, que mapeia 1:1 com a matricula). v12 abre a estrutura de
um acesso e confere: as chaves do acesso, o cliente.codigo, e se varia entre acessos do mesmo
codPessoa (indicando CPF compartilhado / irmaos). PII-safe: so chaves e codigos, sem nome/CPF.

Roda so na 716 Norte. Uso: PACTO_KEY_716NORTE=... python scripts/pacto_probe_contrato.py
"""
import os, sys
from pacto_fetch import gj, lst, gv, unwrap

KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()
if not KEY:
    print("[probe] sem PACTO_KEY_716NORTE", file=sys.stderr); sys.exit(0)

PII = ("nome","name","cpf","email","telefone","fone","rg","apresentar","descricao")

def show(tag, o, depth=0, maxd=3):
    ind = "  " * depth
    if isinstance(o, dict):
        print(f"{ind}[{tag}] keys={sorted(o.keys())}", file=sys.stderr)
        for k, v in o.items():
            kl = k.lower()
            if any(p in kl for p in PII):
                continue
            if isinstance(v, dict) and depth < maxd and v:
                show(k, v, depth + 1, maxd)
            elif not isinstance(v, (dict, list)):
                if kl in ("codigo","matricula","codigocliente","codpessoa","codigopessoa","sentido","meioidentificacaoentrada"):
                    print(f"{ind}  {k} = {v!r}", file=sys.stderr)

st, o = gj(KEY, "/clientes/simples?page=0&size=200")
ativos = [c for c in lst(o) if str(gv(c, "situacao") or "").upper() == "ATIVO"]
print(f"[amostra] ativos_na_pagina={len(ativos)}", file=sys.stderr)

for c in ativos[:3]:
    M = str(gv(c, "matricula") or ""); cc = gv(c, "codigoCliente", "codigo")
    st1, o1 = gj(KEY, f"/clientes/{M}/dados-pessoais")
    cp = gv(unwrap(o1) if isinstance(o1, dict) else {}, "codigoPessoa", "codPessoa")
    if not cp:
        continue
    st2, o2 = gj(KEY, f"/acessos-cliente/by-pessoa/{cp}?page=0&size=200")
    accs = lst(o2) if st2 == 200 else []
    print(f"\n=== cliente matricula={M} codigoCliente={cc} codPessoa={cp} acessos={len(accs)} ===", file=sys.stderr)
    if accs:
        print("--- ESTRUTURA DO 1o ACESSO ---", file=sys.stderr)
        show("acesso", accs[0])
    # cliente.codigo distintos entre os acessos (revela irmaos no mesmo codPessoa)
    cods = {}
    for a in accs:
        cl = gv(a, "cliente")
        cd = gv(cl, "codigo") if isinstance(cl, dict) else None
        cods[str(cd)] = cods.get(str(cd), 0) + 1
    print(f"  cliente.codigo distintos nos acessos: {cods}  (== codigoCliente {cc}? multiplos = CPF compartilhado)", file=sys.stderr)

print("[probe v12] fim (PII-safe)", file=sys.stderr)
