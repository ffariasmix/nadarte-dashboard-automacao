#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pacto_probe_contrato.py (v5) — Confirmar se o PRECO do plano existe no detalhe do plano,
e listar TODOS os planos da unidade (nome do plano NAO e' PII) para montar a tabela plano->preco.
Descobertas ate aqui:
  - /v1/contrato = 500 (todas as variacoes).
  - /v1/plano (lista) = 200, mas SEM campo de valor (so codigo/descricao/empresa/vigencias).
  - demais endpoints financeiros = 404.
v5: /v1/plano?size=200 -> lista completa (cod + descricao + qualquer campo de valor no topo);
    e /v1/plano/{codigo} (detalhe) + variacoes -> procura o preco.
    PII-safe (nome de plano e' produto, nao pessoa).

Roda so na 716 Norte. Uso: PACTO_KEY_716NORTE=... python scripts/pacto_probe_contrato.py
"""
import os, sys, json, urllib.request, urllib.error
from pacto_fetch import gj, lst, gv

KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()
if not KEY:
    print("[probe] sem PACTO_KEY_716NORTE", file=sys.stderr); sys.exit(0)

BASE = "https://apigw.pactosolucoes.com.br"
VAL_HINT = ("valor","price","preco","mensal","parcela","total","desconto",
            "liquid","bruto","vlr","receita","ticket","adesao","anuidade","vencimento","tabela")

def raw_get(path, headers=None):
    req = urllib.request.Request(BASE + path, method="GET")
    req.add_header("Authorization", "Bearer " + KEY)
    req.add_header("Accept", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode("utf-8", "replace") if e.fp else "")
    except Exception as e:
        return -1, str(e)

def walk_vals(tag, o, depth=0, maxdepth=5):
    ind = "  " * depth
    if isinstance(o, dict):
        print(f"{ind}[{tag}] keys={sorted(o.keys())}", file=sys.stderr)
        for k, v in o.items():
            if isinstance(v, (dict, list)):
                if depth < maxdepth and v:
                    walk_vals(k, v, depth + 1, maxdepth)
            elif any(h in k.lower() for h in VAL_HINT):
                print(f"{ind}  {k} = {v!r}", file=sys.stderr)
    elif isinstance(o, list):
        print(f"{ind}[{tag}] list n={len(o)}", file=sys.stderr)
        if o and depth < maxdepth:
            walk_vals(tag + "[0]", o[0], depth + 1, maxdepth)

def probe(path):
    st, body = raw_get(path)
    if st == 200:
        try:
            obj = json.loads(body)
        except Exception:
            print(f"[det] {path} -> 200 (nao-JSON)", file=sys.stderr); return
        print(f"[det] {path} -> 200", file=sys.stderr)
        walk_vals(path, obj.get("content", obj) if isinstance(obj, dict) else obj, depth=1)
    else:
        print(f"[det] {path} -> {st} | {body[:120].replace(chr(10),' ')}", file=sys.stderr)

# 1) LISTA COMPLETA de planos (nome do plano = produto, nao PII) + campos de valor no topo
st, o = gj(KEY, "/v1/plano?page=0&size=200")
plans = lst(o)
print(f"[planos] total_na_pagina={len(plans)}", file=sys.stderr)
for p in plans:
    if not isinstance(p, dict): continue
    cod = gv(p, "codigo"); desc = gv(p, "descricao")
    vals = {k: v for k, v in p.items()
            if any(h in k.lower() for h in VAL_HINT) and not isinstance(v, (dict, list))}
    print(f"[plano] cod={cod} desc={desc!r} vals={vals}", file=sys.stderr)

# 2) DETALHE do 1o plano (onde o preco costuma ficar) + variacoes
if plans:
    cod0 = gv(plans[0], "codigo")
    for path in (f"/v1/plano/{cod0}", f"/v1/plano/{cod0}/valor",
                 f"/v1/plano/{cod0}/valores", f"/v1/plano/{cod0}/tabela",
                 f"/v1/tabelaPreco?codigoPlano={cod0}", "/v1/tabelaPreco?page=0&size=5"):
        probe(path)

print("[probe v5] fim (PII-safe)", file=sys.stderr)
