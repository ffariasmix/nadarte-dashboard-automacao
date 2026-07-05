#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pacto_probe_contrato.py (v11) — Confirmar se o ACESSO da catraca (by-pessoa) carrega a
MATRICULA de quem entrou, e se em casos de CPF compartilhado (irmaos) os acessos vem com
matriculas DIFERENTES. Se sim, da' pra chavear frequencia por (unidade+matricula) sem fundir
irmaos. PII-safe: loga so matriculas (ID interno) e contagens; nunca nome/CPF.

Roda so na 716 Norte. Uso: PACTO_KEY_716NORTE=... python scripts/pacto_probe_contrato.py
"""
import os, sys
from pacto_fetch import gj, lst, gv, unwrap

KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()
if not KEY:
    print("[probe] sem PACTO_KEY_716NORTE", file=sys.stderr); sys.exit(0)

st, o = gj(KEY, "/clientes/simples?page=0&size=200")
page = lst(o)
ativos = [c for c in page if str(gv(c, "situacao") or "").upper() == "ATIVO"]
print(f"[amostra] pagina0={len(page)} ativos={len(ativos)}", file=sys.stderr)

vistos_multi = 0
sem_matricula_no_acesso = 0
checados = 0
for c in ativos[:50]:
    M = str(gv(c, "matricula") or "")
    st1, o1 = gj(KEY, f"/clientes/{M}/dados-pessoais")
    dp = unwrap(o1) if isinstance(o1, dict) else {}
    cp = gv(dp, "codigoPessoa", "codPessoa")
    if not cp:
        continue
    checados += 1
    st2, o2 = gj(KEY, f"/acessos-cliente/by-pessoa/{cp}?page=0&size=200")
    accs = lst(o2) if st2 == 200 else []
    # conta matriculas presentes nos acessos + quantos acessos sem matricula
    mats = {}
    blanks = 0
    for a in accs:
        am = gv(a, "matricula")
        if am is None or str(am).strip() == "":
            blanks += 1; continue
        k = str(am)
        mats[k] = mats.get(k, 0) + 1
    if blanks:
        sem_matricula_no_acesso += 1
    distintas = list(mats.keys())
    multi = (len(distintas) > 1) or (distintas and distintas[0] != M)
    tag = "  >> MULTI/COMPARTILHADO" if multi else ""
    print(f"[cli mat={M} codPessoa={cp}] acessos={len(accs)} blanks={blanks} matriculas_nos_acessos={mats}{tag}", file=sys.stderr)
    if multi:
        vistos_multi += 1
        if vistos_multi >= 4:  # ja temos exemplos suficientes de CPF compartilhado
            break

print(f"[v11] checados={checados} | casos multi-matricula(CPF compartilhado)={vistos_multi} | clientes c/ acesso sem matricula={sem_matricula_no_acesso}", file=sys.stderr)
print("[probe v11] fim (PII-safe)", file=sys.stderr)
