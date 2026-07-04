#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pacto_probe_contrato.py (v6) — Confirmar /v1/bi/contas-receber como fonte do VALOR por aluno.
Doc: "Consultar contas a receber por periodo, incluindo valores, datas de vencimento e
pessoas relacionadas". Params: empresaId (header) + dataInicial + dataFinal.
v6 chama num mes fechado e faz WALK PII-safe: mostra as CHAVES e SO valores de campos de
valor/vencimento + pessoa.codigo (codPessoa). NUNCA loga nome/CPF/email.

Roda so na 716 Norte. Uso: PACTO_KEY_716NORTE=... python scripts/pacto_probe_contrato.py
"""
import os, sys, json, urllib.request, urllib.error, datetime, calendar

KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()
if not KEY:
    print("[probe] sem PACTO_KEY_716NORTE", file=sys.stderr); sys.exit(0)

BASE = "https://apigw.pactosolucoes.com.br"
VAL_HINT = ("valor","vencimento","receb","quitacao","saldo","parcela","desconto",
            "juros","multa","total","liquid","bruto","pago","aberto","competencia")
PII = ("nome","name","cpf","email","telefone","fone","rg","endereco","nascimento",
       "datanasc","logradouro","bairro","cidade","cep","apelido","foto")

def raw_get(path, headers=None):
    req = urllib.request.Request(BASE + path, method="GET")
    req.add_header("Authorization", "Bearer " + KEY)
    req.add_header("Accept", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode("utf-8", "replace") if e.fp else "")
    except Exception as e:
        return -1, str(e)

def walk(tag, o, depth=0, maxdepth=6):
    ind = "  " * depth
    if isinstance(o, dict):
        print(f"{ind}[{tag}] keys={sorted(o.keys())}", file=sys.stderr)
        for k, v in o.items():
            kl = k.lower()
            if any(p in kl for p in PII):
                continue
            if isinstance(v, (dict, list)):
                if depth < maxdepth and v:
                    walk(k, v, depth + 1, maxdepth)
            elif kl == "codigo" or any(h in kl for h in VAL_HINT):
                print(f"{ind}  {k} = {v!r}", file=sys.stderr)
    elif isinstance(o, list):
        print(f"{ind}[{tag}] list n={len(o)}", file=sys.stderr)
        if o and depth < maxdepth:
            walk(tag + "[0]", o[0], depth + 1, maxdepth)

# mes fechado mais recente
t = datetime.date.today()
y, m = (t.year - 1, 12) if t.month == 1 else (t.year, t.month - 1)
di = f"{y}-{m:02d}-01"
df = f"{y}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"
path = f"/v1/bi/contas-receber?dataInicial={di}&dataFinal={df}"
print(f"[req] {path} (empresaId=1)", file=sys.stderr)

st, body = raw_get(path, {"empresaId": "1"})
print(f"[/v1/bi/contas-receber] status={st}", file=sys.stderr)
if st != 200:
    print(f"[erro] corpo: {body[:200].replace(chr(10),' ')}", file=sys.stderr)
else:
    try:
        obj = json.loads(body)
    except Exception:
        obj = None
        print(f"[aviso] corpo nao-JSON: {body[:160]!r}", file=sys.stderr)
    if obj is not None:
        items = obj.get("content", obj) if isinstance(obj, dict) else obj
        if isinstance(items, list):
            print(f"[contas-receber] itens={len(items)}", file=sys.stderr)
            # soma dos valores (se acharmos o campo) e distintos por pessoa.codigo
            if items:
                print("--- ESTRUTURA DO 1o ITEM (PII-safe) ---", file=sys.stderr)
                walk("item", items[0])
        else:
            print("[aviso] content nao e' lista; estrutura:", file=sys.stderr)
            walk("content", items)

print("[probe v6] fim (PII-safe)", file=sys.stderr)
