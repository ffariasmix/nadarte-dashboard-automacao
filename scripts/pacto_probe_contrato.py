#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pacto_probe_contrato.py (v10) — Ler /v1/bi/resumo e /v1/bi/receita-tipo-forma-pagamento
(que ja funcionam) para travar o campo de FATURAMENTO/RECEITA por unidade/mes.
Objetivo: ticket dinamico por unidade = faturamento real / alunos ativos.
v9 provou que ha dado financeiro (velocimetro faturamento = R$187k na 716). Aqui mostramos
o conteudo completo do resumo (agregado, sem PII).

Roda so na 716 Norte. Uso: PACTO_KEY_716NORTE=... python scripts/pacto_probe_contrato.py
"""
import os, sys, json, urllib.request, urllib.error, datetime, calendar

KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()
if not KEY:
    print("[probe] sem PACTO_KEY_716NORTE", file=sys.stderr); sys.exit(0)

BASE = "https://apigw.pactosolucoes.com.br"

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

def show(nome, obj):
    """imprime META (mensagem) e o CONTENT completo (agregado, sem PII)."""
    meta = obj.get("meta") if isinstance(obj, dict) else None
    if isinstance(meta, dict):
        print(f"[{nome}] meta.message={meta.get('message')!r}", file=sys.stderr)
    content = obj.get("content", obj) if isinstance(obj, dict) else obj
    print(f"[{nome}] content=" + json.dumps(content, ensure_ascii=False)[:1500], file=sys.stderr)

t = datetime.date.today()
y, m = (t.year - 1, 12) if t.month == 1 else (t.year, t.month - 1)   # ult. mes fechado
mes = f"{y}-{m:02d}"
ym1, mm1 = (y, m - 1) if m > 1 else (y - 1, 12)
mesIni = f"{ym1}-{mm1:02d}"
last = calendar.monthrange(y, m)[1]

print(f"[periodo] mesIni={mesIni} mes={mes}", file=sys.stderr)

for nome, path in [
    ("resumo", f"/v1/bi/resumo?mesInicial={mesIni}&mesFinal={mes}"),
    ("receita-forma-pgto", f"/v1/bi/receita-tipo-forma-pagamento?mes={mes}"),
    ("velocimetro-receita(1)", f"/v1/bi/velocimetro?mes={mes}&tipoConsulta=1"),
    ("velocimetro-faturamento(2)", f"/v1/bi/velocimetro?mes={mes}&tipoConsulta=2"),
]:
    st, body = raw_get(path, {"empresaId": "1"})
    try:
        obj = json.loads(body)
    except Exception:
        print(f"[{nome}] status={st} corpo-nao-JSON: {body[:120]!r}", file=sys.stderr); continue
    print(f"--- {nome} (status={st}) ---", file=sys.stderr)
    show(nome, obj)

print("[probe v10] fim", file=sys.stderr)
