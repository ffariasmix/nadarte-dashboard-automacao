#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pacto_probe_contrato.py (v4) — Caca ao CAMPO DE VALOR do contrato/plano na API PACTO.
Descobertas ate aqui:
  - /v1/contrato = 500 (sem params).
  - /clientes/{mat}/contrato* = 404.
  - /v1/cliente/{codigo} = 200, mas NAO tem valor: 'vinculos' sao colaboradores;
    'clienteSintetico.situacaocontrato' e' so status (codigo/descricao).
v4: varredura ampla e RAPIDA (amostra da 1a pagina) de endpoints candidatos de
    contrato/plano/financeiro, incluindo /v1/contrato com params e header empresaId.
    Para 200: WALK PII-safe (chaves + campos que parecem valor). Para erro: 1a linha do corpo.
    NUNCA loga nome/CPF/contato.

Roda so na 716 Norte. Uso: PACTO_KEY_716NORTE=... python scripts/pacto_probe_contrato.py
"""
import os, sys, json, urllib.request, urllib.error
from pacto_fetch import gj, lst, gv

KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()
if not KEY:
    print("[probe] sem PACTO_KEY_716NORTE", file=sys.stderr); sys.exit(0)

BASE = "https://apigw.pactosolucoes.com.br"
VAL_HINT = ("valor","price","preco","mensal","parcela","plano","total","desconto",
            "liquid","bruto","vlr","receita","ticket","adesao","anuidade","vencimento")
PII = ("nome","name","cpf","email","telefone","fone","rg","endereco","nascimento",
       "datanasc","logradouro","numero","bairro","cidade","cep","apelido","foto")

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

def walk(tag, o, depth=0, maxdepth=5):
    ind = "  " * depth
    if isinstance(o, dict):
        print(f"{ind}[{tag}] keys={sorted(o.keys())}", file=sys.stderr)
        for k, v in o.items():
            if any(p in k.lower() for p in PII):
                continue
            if isinstance(v, (dict, list)):
                if depth < maxdepth and v:
                    walk(k, v, depth + 1, maxdepth)
            elif any(h in k.lower() for h in VAL_HINT):
                print(f"{ind}  {k} = {v!r}", file=sys.stderr)
    elif isinstance(o, list):
        print(f"{ind}[{tag}] list n={len(o)}", file=sys.stderr)
        if o and depth < maxdepth:
            walk(tag + "[0]", o[0], depth + 1, maxdepth)

def probe(path, headers=None):
    st, body = raw_get(path, headers)
    hdr = " +hdr" if headers else ""
    if st == 200:
        try:
            obj = json.loads(body)
        except Exception:
            print(f"[try{hdr}] {path} -> 200 (corpo nao-JSON: {body[:120]!r})", file=sys.stderr); return
        print(f"[try{hdr}] {path} -> 200", file=sys.stderr)
        walk(path, obj.get("content", obj) if isinstance(obj, dict) else obj, depth=1)
    else:
        print(f"[try{hdr}] {path} -> {st} | {body[:140].replace(chr(10),' ')}", file=sys.stderr)

# amostra: 1 cliente ATIVO da 1a pagina (codigo/matricula sao IDs internos, nao PII sensivel)
st0, o0 = gj(KEY, "/clientes/simples?page=0&size=200")
page = lst(o0)
ativos = [c for c in page if str(gv(c, "situacao") or "").upper() == "ATIVO"]
c = ativos[0] if ativos else (page[0] if page else {})
M = gv(c, "matricula"); cc = gv(c, "codigoCliente", "codigo")
print(f"[amostra] cod={cc} (pagina0={len(page)} ativos={len(ativos)})", file=sys.stderr)

candidatos = [
    "/v1/contrato?page=0&size=5",
    "/v1/contrato?page=0&size=5&empresaId=1",
    f"/v1/contrato?codigoCliente={cc}",
    f"/v1/contrato?codigoCliente={cc}&page=0&size=5",
    f"/v1/contrato/cliente/{cc}",
    f"/v1/cliente/{cc}/contrato",
    f"/v1/cliente/{cc}/contratos",
    f"/v1/cliente/{cc}/financeiro",
    f"/clientes/{M}/financeiro",
    f"/clientes/{M}/parcelas",
    f"/clientes/{M}/contrato-atual",
    f"/clientes/{M}/plano",
    "/v1/plano?page=0&size=5",
    "/v1/planos?page=0&size=5",
    "/planos?page=0&size=5",
    "/v1/parcela?page=0&size=5",
    "/v1/mensalidade?page=0&size=5",
    "/financeiro/parcelas?page=0&size=5",
]
for p in candidatos:
    probe(p)
# variante com header empresaId (como o feed ao vivo usa)
probe("/v1/contrato?page=0&size=5", {"empresaId": "1"})

print("[probe v4] fim (PII-safe)", file=sys.stderr)
