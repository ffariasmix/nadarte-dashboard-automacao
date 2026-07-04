#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pacto_probe_contrato.py (v7) — /v1/bi/contas-receber: descobrir a chamada correta.
v6: status=200 mas corpo = {meta:{error,...}} (erro de validacao) — faltou imprimir a msg.
v7: imprime a MENSAGEM do erro e testa variacoes (data com hora, empresaId em query).
    Ao dar certo, WALK PII-safe (valores/vencimento + pessoa.codigo). Nunca loga nome/CPF.

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

t = datetime.date.today()
y, m = (t.year - 1, 12) if t.month == 1 else (t.year, t.month - 1)
last = calendar.monthrange(y, m)[1]
d1, d2 = f"{y}-{m:02d}-01", f"{y}-{m:02d}-{last:02d}"

variacoes = [
    ("data simples + empresaId header",
     f"/v1/bi/contas-receber?dataInicial={d1}&dataFinal={d2}", {"empresaId": "1"}),
    ("data com hora + empresaId header",
     f"/v1/bi/contas-receber?dataInicial={d1}T00:00:00&dataFinal={d2}T23:59:59", {"empresaId": "1"}),
    ("empresaId em query (sem header)",
     f"/v1/bi/contas-receber?empresaId=1&dataInicial={d1}&dataFinal={d2}", None),
    ("empresaId query + header",
     f"/v1/bi/contas-receber?empresaId=1&dataInicial={d1}&dataFinal={d2}", {"empresaId": "1"}),
]

for nome, path, hdr in variacoes:
    st, body = raw_get(path, hdr)
    print(f"\n=== [{nome}] status={st} ===", file=sys.stderr)
    print(f"    {path}", file=sys.stderr)
    try:
        obj = json.loads(body)
    except Exception:
        print(f"    corpo nao-JSON: {body[:160]!r}", file=sys.stderr); continue
    meta = obj.get("meta") if isinstance(obj, dict) else None
    if isinstance(meta, dict) and meta.get("error"):
        print(f"    META.error={meta.get('error')} | message={meta.get('message')!r} | campo={meta.get('messageValue')!r}", file=sys.stderr)
        continue
    items = obj.get("content", obj) if isinstance(obj, dict) else obj
    if isinstance(items, list):
        print(f"    OK itens={len(items)}", file=sys.stderr)
        if items:
            print("    --- ESTRUTURA 1o ITEM (PII-safe) ---", file=sys.stderr)
            walk("item", items[0], depth=2)
        break  # achou a chamada certa
    else:
        walk("content", items, depth=2)

print("\n[probe v7] fim (PII-safe)", file=sys.stderr)
