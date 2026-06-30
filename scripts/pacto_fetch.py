#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROBE PACTO — descoberta de endpoints de cadastro via OpenAPI dos microservicos.
NAO imprime dados pessoais. Uso: python scripts/pacto_fetch.py --probe
Env: PACTO_API_KEY (Bearer), PACTO_UNIT
"""
import os, sys, re, json
import urllib.request, urllib.error

BASE = "https://apigw.pactosolucoes.com.br"
RX = re.compile(r"client|pessoa|perfil|matricula|cadastr|aluno|nasciment|modalidade|sexo|contrato|churn|ltv|renova|inadim|acesso|simplific", re.I)


def http_get(path, key, timeout=50):
    req = urllib.request.Request(BASE + path, method="GET")
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace") if e.fp else ""
        return e.code, (e.headers.get("Content-Type", "") if e.headers else ""), body
    except Exception as e:
        return -1, "", "EXC: " + str(e)


def dump_spec(label, path, key):
    status, ctype, body = http_get(path, key)
    print(f"\n### {label}  {path} -> HTTP {status} {ctype.split(';')[0]} ({len(body)}b)")
    if status != 200 or "json" not in ctype.lower():
        print(f"   {body[:120].replace(chr(10),' ')}")
        return
    try:
        d = json.loads(body)
    except Exception as e:
        print(f"   (JSON invalido: {e})"); return
    paths = d.get("paths", {})
    print(f"   paths totais: {len(paths)}")
    hits = sorted([p for p in paths if RX.search(p)])
    print(f"   paths de interesse ({len(hits)}):")
    for p in hits[:150]:
        methods = ",".join(sorted(paths[p].keys())).upper()
        print(f"     {methods} {p}")


def probe():
    key = os.environ.get("PACTO_API_KEY", "").strip()
    unit = os.environ.get("PACTO_UNIT", "?")
    if not key:
        print("[probe] ERRO: PACTO_API_KEY ausente."); sys.exit(1)
    print(f"[probe] unidade={unit} (ApiKey len={len(key)})")

    # Gateway (lista de servicos) + specs dos microservicos provaveis
    for label, p in [
        ("gateway", "/v3/api-docs"),
        ("adm-core-ms", "/adm-core-ms/v3/api-docs"),
        ("adm-core-ms-v2", "/adm-core-ms/v2/api-docs"),
        ("adm-bff", "/adm-bff/v3/api-docs"),
        ("core-ms", "/core-ms/v3/api-docs"),
        ("crm-ms", "/crm-ms/v3/api-docs"),
        ("treino-ms", "/treino-ms/v3/api-docs"),
        ("financeiro-ms", "/financeiro-ms/v3/api-docs"),
    ]:
        dump_spec(label, p, key)
    print("\n[probe] fim.")


if __name__ == "__main__":
    if "--probe" in sys.argv:
        probe()
    else:
        print("Use --probe.")
