#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pacto_probe_contrato.py (v9) — Existe QUALQUER dado financeiro acessivel por esta chave?
v8: /v1/bi/contas-receber = "Dados nao encontrados" (empresaId=1, Jun/Mai).
v9: testa os endpoints AGREGADOS do BI (resumo, receita-forma-pgto, saldos, velocimetro)
    com empresaId 1..6, num mes fechado. Sao agregados (sem PII) -> mostra os valores.
    Se algum trouxer numero, o financeiro existe; se todos "nao encontrado", a chave nao expoe.

Roda so na 716 Norte. Uso: PACTO_KEY_716NORTE=... python scripts/pacto_probe_contrato.py
"""
import os, sys, json, urllib.request, urllib.error, datetime, calendar

KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()
if not KEY:
    print("[probe] sem PACTO_KEY_716NORTE", file=sys.stderr); sys.exit(0)

BASE = "https://apigw.pactosolucoes.com.br"
VAL_HINT = ("valor","receb","receita","faturamento","total","saldo","despesa","competencia",
            "entrada","saida","quitacao","atingido","final","inicial")

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
            if isinstance(v, (dict, list)):
                if depth < maxdepth and v:
                    walk(k, v, depth + 1, maxdepth)
            elif any(h in k.lower() for h in VAL_HINT):
                print(f"{ind}  {k} = {v!r}", file=sys.stderr)
    elif isinstance(o, list):
        print(f"{ind}[{tag}] list n={len(o)}", file=sys.stderr)
        if o and depth < maxdepth:
            walk(tag + "[0]", o[0], depth + 1, maxdepth)

t = datetime.date.today()
y, m = (t.year - 1, 12) if t.month == 1 else (t.year, t.month - 1)   # ult. mes fechado
last = calendar.monthrange(y, m)[1]
mes = f"{y}-{m:02d}"
ym1, mm1 = (y, m - 1) if m > 1 else (y - 1, 12)
mesIni = f"{ym1}-{mm1:02d}"

testes = [
    ("receita-forma-pgto", f"/v1/bi/receita-tipo-forma-pagamento?mes={mes}"),
    ("resumo",             f"/v1/bi/resumo?mesInicial={mesIni}&mesFinal={mes}"),
    ("saldos",             f"/v1/bi/saldos?data={y}-{m:02d}-{last:02d}"),
    ("velocimetro-fatur",  f"/v1/bi/velocimetro?mes={mes}&tipoConsulta=2"),
]

for eid in ("1", "2", "3", "4", "5", "6"):
    print(f"\n########## empresaId={eid} ##########", file=sys.stderr)
    achou_algo = False
    for nome, path in testes:
        st, body = raw_get(path, {"empresaId": eid})
        try:
            obj = json.loads(body)
        except Exception:
            print(f"[{nome}] status={st} corpo-nao-JSON", file=sys.stderr); continue
        meta = obj.get("meta") if isinstance(obj, dict) else None
        if isinstance(meta, dict) and meta.get("error"):
            print(f"[{nome}] status={st} META={meta.get('message')!r}", file=sys.stderr)
            continue
        print(f"[{nome}] status={st} OK -> tem dado:", file=sys.stderr)
        walk(nome, obj.get("content", obj) if isinstance(obj, dict) else obj, depth=1)
        achou_algo = True
    if achou_algo:
        print(f"[!] empresaId={eid} TEM dado financeiro — parar aqui", file=sys.stderr)
        break

print("[probe v9] fim", file=sys.stderr)
