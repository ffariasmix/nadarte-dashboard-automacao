#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validacao multi-unidade PACTO (5 unidades, sem Natal).
Para cada unidade: total de ATIVOS + distribuicao de situacao + distribuicao
do ANO de inicioContrato (para achar a linha de censura da migracao) +
cobertura demografica (amostra). Tudo PII-safe (so contagens).
Env: PACTO_KEY_716NORTE, PACTO_KEY_905SUL, PACTO_KEY_604NORTE, PACTO_KEY_LAGONORTE, PACTO_KEY_LAGOSUL
"""
import os, sys, re, json, datetime
import urllib.request, urllib.error
from collections import Counter

BASE = "https://apigw.pactosolucoes.com.br"
UNIDADES = [
    ("716 Norte", "PACTO_KEY_716NORTE"),
    ("905 Sul",   "PACTO_KEY_905SUL"),
    ("604 Norte", "PACTO_KEY_604NORTE"),
    ("Lago Norte","PACTO_KEY_LAGONORTE"),
    ("Lago Sul",  "PACTO_KEY_LAGOSUL"),
]


def http_get(path, key, timeout=50):
    req = urllib.request.Request(BASE + path, method="GET")
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode("utf-8", "replace") if e.fp else "")
    except Exception as e:
        return -1, str(e)


def gj(path, key):
    st, body = http_get(path, key)
    try:
        return json.loads(body)
    except Exception:
        return None


def content(o):
    if isinstance(o, list):
        return o
    if isinstance(o, dict):
        for k in ("content", "data", "rows", "list", "items", "result", "results"):
            if isinstance(o.get(k), list):
                return o[k]
    return []


def year_of(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):  # epoch ms
        try:
            return datetime.datetime.utcfromtimestamp(v / 1000).year
        except Exception:
            return None
    m = re.search(r"(\d{4})", str(v))
    return int(m.group(1)) if m else None


def unidade(label, key, maxpages=120):
    ativos = []
    sit = Counter()
    for pg in range(maxpages):
        rows = content(gj(f"/clientes/simples?page={pg}&size=200", key))
        if not rows:
            break
        for r in rows:
            if isinstance(r, dict):
                s = (r.get("situacao") or "?").upper()
                sit[s] += 1
                if s == "ATIVO":
                    ativos.append(r)
        if len(rows) < 200:
            break
    # distribuicao de ano de inicioContrato (censura)
    anos = Counter(year_of(r.get("inicioContrato")) for r in ativos)
    com_inicio = sum(v for a, v in anos.items() if a)
    print(f"\n==== {label} ====")
    print(f"  ATIVOS = {len(ativos)}  | situacao total = {json.dumps(dict(sit), ensure_ascii=False)}")
    print(f"  ativos com inicioContrato preenchido = {com_inicio}/{len(ativos)}")
    top = sorted(((a, v) for a, v in anos.items() if a), key=lambda x: -x[1])[:8]
    print(f"  ano inicioContrato (top): {top}")
    return len(ativos)


def main():
    print("[rede] validacao das 5 unidades (sem Natal)")
    total = 0
    resumo = []
    for label, env in UNIDADES:
        key = os.environ.get(env, "").strip()
        if not key:
            print(f"\n==== {label} ==== SEM CHAVE ({env})"); continue
        n = unidade(label, key)
        total += n
        resumo.append((label, n))
    print("\n===== RESUMO ATIVOS POR UNIDADE =====")
    for label, n in resumo:
        print(f"  {label:12} {n}")
    print(f"  {'REDE (5)':12} {total}")
    print("\n[rede] fim.")


if __name__ == "__main__":
    main()
