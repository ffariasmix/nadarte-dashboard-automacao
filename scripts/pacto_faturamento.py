#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pacto_faturamento.py — Faturamento real por unidade (MES FECHADO COM FOLGA = 2 meses atras,
pois o mes recem-fechado ainda tem faturamento a lancar) via /v1/bi/resumo
da API PACTO. Escreve data/faturamento.json = {"mes": "AAAA-MM", "faturamento": {unit: valor}}.
Usado pelo build para o TICKET dinamico (faturamento / alunos ativos por unidade).
Robusto: descobre o empresaId de cada unidade via /v1/plano; falha silenciosa por unidade
(o build tem fallback pros valores fixos). Sem PII.

Uso: PACTO_KEY_*=... python scripts/pacto_faturamento.py [data_dir]
"""
import os, sys, json, time, urllib.request, urllib.error, datetime

BASE = "https://apigw.pactosolucoes.com.br"
UNITS = [("716Norte","PACTO_KEY_716NORTE"), ("905Sul","PACTO_KEY_905SUL"),
         ("604Norte","PACTO_KEY_604NORTE"), ("LagoNorte","PACTO_KEY_LAGONORTE"),
         ("LagoSul","PACTO_KEY_LAGOSUL")]
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else "data"

def get(key, path, headers=None, tries=4):
    for i in range(tries):
        req = urllib.request.Request(BASE + path, method="GET")
        req.add_header("Authorization", "Bearer " + key)
        req.add_header("Accept", "application/json")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                time.sleep(1.5 * (i + 1)); continue
            return e.code, (e.read().decode("utf-8", "replace") if e.fp else "")
        except Exception as e:
            if i < tries - 1:
                time.sleep(1.5 * (i + 1)); continue
            return -1, str(e)
    return -1, ""

def empresa_id(key):
    """codigo da empresa da unidade (via /v1/plano.empresa.codigo). Fallback '1'."""
    st, body = get(key, "/v1/plano?page=0&size=1")
    try:
        obj = json.loads(body)
        c = obj.get("content", obj) if isinstance(obj, dict) else obj
        if isinstance(c, list) and c and isinstance(c[0], dict):
            e = c[0].get("empresa") or {}
            if isinstance(e, dict) and e.get("codigo") is not None:
                return str(e["codigo"])
    except Exception:
        pass
    return "1"

def month_back(n):
    """(ano, mes) de n meses atras a partir de hoje."""
    t = datetime.date.today()
    y, m = t.year, t.month - n
    while m < 1:
        m += 12; y -= 1
    return (y, m)

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    # mes com FOLGA: pula o mes recem-fechado (faturamento ainda em lancamento) e usa o anterior.
    y, m = month_back(2)
    mes = f"{y}-{m:02d}"
    fat = {}
    for unit, secret in UNITS:
        key = os.environ.get(secret, "").strip()
        if not key:
            print(f"[fat] {unit}: sem secret {secret}", file=sys.stderr); continue
        eid = empresa_id(key)
        st, body = get(key, f"/v1/bi/resumo?mesInicial={mes}&mesFinal={mes}", {"empresaId": eid})
        try:
            obj = json.loads(body)
            content = obj.get("content", obj) if isinstance(obj, dict) else obj
        except Exception:
            print(f"[fat] {unit}: resposta invalida (st={st})", file=sys.stderr); continue
        val = None
        if isinstance(content, list):
            for row in content:
                if isinstance(row, dict) and str(row.get("mes", "")) == mes:
                    val = row.get("totalFaturamento"); break
            if val is None and content and isinstance(content[0], dict):
                val = content[0].get("totalFaturamento")
        if val is None:
            print(f"[fat] {unit}: sem totalFaturamento (empresaId={eid}, st={st})", file=sys.stderr); continue
        fat[unit] = round(float(val), 2)
        print(f"[fat] {unit}: {mes} empresaId={eid} totalFaturamento={fat[unit]}", file=sys.stderr)

    if fat:
        with open(os.path.join(DATA_DIR, "faturamento.json"), "w") as f:
            json.dump({"mes": mes, "faturamento": fat}, f, ensure_ascii=False)
        print(f"[fat] escrito faturamento.json ({mes}): {fat}", file=sys.stderr)
    else:
        print("[fat] nada coletado; build usara os valores fixos (fallback)", file=sys.stderr)

if __name__ == "__main__":
    main()
