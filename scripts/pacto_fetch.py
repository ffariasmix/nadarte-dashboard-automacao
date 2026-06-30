#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coletor da API PACTO -> Dashboard Frequencia & Retencao (Nad'Arte).
MODO PROBE: descoberta segura de schema (NAO imprime dados pessoais; so nomes de campos).
Foco desta versao: achar o endpoint de CADASTRO COMPLETO (CPF, nascimento, sexo, modalidade, matricula).
Uso:  python scripts/pacto_fetch.py --probe
Env:  PACTO_API_KEY (Bearer), PACTO_UNIT (rotulo)
"""
import os, sys, re, json, datetime
import urllib.request, urllib.error, urllib.parse

BASE = "https://apigw.pactosolucoes.com.br"


def http_get(path, key, timeout=40):
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


def keys_of(obj):
    rows = obj if isinstance(obj, list) else None
    if isinstance(obj, dict):
        for k in ("content", "data", "rows", "list", "items", "registros", "dados", "result", "results"):
            if isinstance(obj.get(k), list):
                rows = obj[k]; break
        if rows is None:
            return ("dict", sorted(obj.keys()))
    if rows is not None:
        if rows and isinstance(rows[0], dict):
            return ("list[%d]" % len(rows), sorted(rows[0].keys()))
        return ("list[%d]" % len(rows), [])
    return (type(obj).__name__, [])


def try_json(label, path, key, show_nested=()):
    print(f"\n=== {label}  GET {path} ===")
    status, ctype, body = http_get(path, key)
    print(f"  HTTP {status} {ctype.split(';')[0]}")
    if status == 200 and "json" in ctype.lower():
        try:
            obj = json.loads(body)
            kind, ks = keys_of(obj)
            print(f"  {kind} campos: {ks}")
            # inspeciona objetos aninhados (so nomes de chaves, sem valores)
            sample = (obj if isinstance(obj, dict) else (obj[0] if obj else {}))
            rows = None
            if isinstance(obj, dict):
                for k in ("content","data","rows","list","items","registros","dados","result","results"):
                    if isinstance(obj.get(k), list) and obj[k]:
                        sample = obj[k][0]; break
            elif isinstance(obj, list) and obj:
                sample = obj[0]
            for nk in show_nested:
                if isinstance(sample, dict) and isinstance(sample.get(nk), dict):
                    print(f"    .{nk} chaves: {sorted(sample[nk].keys())}")
            return obj
        except Exception as e:
            print(f"  (JSON invalido: {e})")
    else:
        print(f"  corpo(160c): {body[:160].replace(chr(10),' ')}")
    return None


def probe_spec(key):
    print("\n##### OpenAPI spec (mapeia todos os endpoints) #####")
    for spec in ["/v3/api-docs", "/adm-core-ms/v3/api-docs", "/adm-core-ms/api-docs",
                 "/swagger.json", "/openapi.json", "/v2/api-docs", "/api-docs"]:
        status, ctype, body = http_get(spec, key)
        print(f"  {spec} -> HTTP {status} {ctype.split(';')[0]} ({len(body)} bytes)")
        if status == 200 and "json" in ctype.lower():
            try:
                d = json.loads(body)
                paths = d.get("paths", {})
                print(f"  >> SPEC OK: {len(paths)} paths")
                rx = re.compile(r"client|pessoa|perfil|matricula|cadastr|aluno", re.I)
                hits = [p for p in paths if rx.search(p)]
                print(f"  >> paths de cadastro ({len(hits)}):")
                for p in hits[:60]:
                    methods = ",".join(sorted(paths[p].keys()))
                    print(f"     {methods.upper()} {p}")
                return True
            except Exception as e:
                print(f"     (JSON invalido: {e})")
    print("  (spec nao acessivel pelos caminhos testados)")
    return False


def probe():
    key = os.environ.get("PACTO_API_KEY", "").strip()
    unit = os.environ.get("PACTO_UNIT", "?")
    if not key:
        print("[probe] ERRO: PACTO_API_KEY ausente."); sys.exit(1)
    print(f"[probe] unidade={unit} (ApiKey len={len(key)}, valor NAO impresso)")

    rows = try_json("clientes_simples", "/clientes/simples?page=0&size=5", key)
    cod = None
    if isinstance(rows, list):
        for r in rows:
            if isinstance(r, dict) and r.get("codigoCliente"):
                cod = r["codigoCliente"]; break
    elif isinstance(rows, dict):
        for k in ("content","data","rows","list"):
            if isinstance(rows.get(k), list):
                for r in rows[k]:
                    if isinstance(r, dict) and r.get("codigoCliente"):
                        cod = r["codigoCliente"]; break
                break
    print(f"\n[probe] codigoCliente capturado: {'sim' if cod else 'nao'} (valor oculto)")

    # 1) Inspeciona o objeto 'cliente' aninhado num acesso (pode ja conter cadastro)
    if cod is not None:
        c = urllib.parse.quote(str(cod))
        try_json("acesso_nested", f"/acessos-cliente/by-pessoa/{c}?page=0&size=1", key,
                 show_nested=("cliente", "localAcesso", "coletor"))
        # 2) Candidatos de detalhe/cadastro por codigoCliente
        for label, p in [
            ("clientes_detalhe",      f"/clientes/{c}"),
            ("clientes_dados",        f"/clientes/{c}/dados"),
            ("clientes_cadastrais",   f"/clientes/{c}/dados-cadastrais"),
            ("clientes_perfil",       f"/clientes/{c}/perfil"),
            ("perfil_aluno",          f"/perfil-aluno/{c}"),
            ("pessoa_detalhe",        f"/pessoa/{c}"),
            ("clientes_completo",     f"/clientes/{c}/completo"),
        ]:
            try_json(label, p, key)

    # 3) OpenAPI spec (jackpot: lista todos os endpoints de cliente)
    probe_spec(key)
    print("\n[probe] fim.")


if __name__ == "__main__":
    if "--probe" in sys.argv:
        probe()
    else:
        print("Use --probe.")
