#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pacto_probe_contrato.py (v8) — Achar o empresaId certo e ler /v1/bi/contas-receber.
v7: chamada valida (200) mas "Dados nao encontrados" com empresaId=1 -> empresaId errado.
v8: descobre o empresaId via /v1/plano (campo empresa.codigo) e tenta o contas-receber
    com esse id (header), em Mai e Jun. Ao dar certo, WALK PII-safe (valor/vencimento +
    pessoa.codigo). Nunca loga nome/CPF.

Roda so na 716 Norte. Uso: PACTO_KEY_716NORTE=... python scripts/pacto_probe_contrato.py
"""
import os, sys, json, urllib.request, urllib.error, datetime, calendar
from pacto_fetch import gj, lst, gv

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

# 1) descobrir empresaId(s) via /v1/plano -> empresa.codigo
st, o = gj(KEY, "/v1/plano?page=0&size=20")
plans = lst(o)
emp_ids = []
for p in plans:
    if isinstance(p, dict):
        e = p.get("empresa")
        ec = gv(e, "codigo") if isinstance(e, dict) else None
        if ec is not None and ec not in emp_ids:
            emp_ids.append(ec)
print(f"[empresaId] candidatos via /v1/plano: {emp_ids}", file=sys.stderr)
candidatos = [str(x) for x in emp_ids] or []
for fb in ("1", "2"):
    if fb not in candidatos:
        candidatos.append(fb)

# 2) contas-receber com cada empresaId, em Jun e Mai
t = datetime.date.today()
def periodo(back):
    y, mm = t.year, t.month - 1 - back
    while mm < 1:
        mm += 12; y -= 1
    last = calendar.monthrange(y, mm)[1]
    return f"{y}-{mm:02d}-01", f"{y}-{mm:02d}-{last:02d}"

achou = False
for eid in candidatos:
    if achou: break
    for back in (0, 1):  # ultimo mes fechado e o anterior
        d1, d2 = periodo(back)
        path = f"/v1/bi/contas-receber?dataInicial={d1}&dataFinal={d2}"
        st, body = raw_get(path, {"empresaId": eid})
        try:
            obj = json.loads(body)
        except Exception:
            print(f"[empresaId={eid} {d1}] status={st} corpo-nao-JSON", file=sys.stderr); continue
        meta = obj.get("meta") if isinstance(obj, dict) else None
        if isinstance(meta, dict) and meta.get("error"):
            print(f"[empresaId={eid} {d1}..{d2}] status={st} META={meta.get('message')!r}", file=sys.stderr)
            continue
        items = obj.get("content", obj) if isinstance(obj, dict) else obj
        n = len(items) if isinstance(items, list) else "n/a"
        print(f"[empresaId={eid} {d1}..{d2}] status={st} OK itens={n}", file=sys.stderr)
        if isinstance(items, list) and items:
            print("--- ESTRUTURA 1o ITEM (PII-safe) ---", file=sys.stderr)
            walk("item", items[0], depth=1)
            achou = True; break

print("[probe v8] fim (PII-safe)", file=sys.stderr)
