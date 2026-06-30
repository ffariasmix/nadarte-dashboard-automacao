#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coletor da API PACTO -> Dashboard Frequencia & Retencao (Nad'Arte).

MODO PROBE (descoberta segura de schema): NAO imprime dados pessoais.
Para cada endpoint, imprime apenas: status HTTP, formato (lista/objeto),
contagem de itens, NOMES de campos do 1o item, tipos e intervalos de datas.
Assim mapeamos os campos sem expor PII e sem o usuario rodar nada manualmente.

Uso:
  python scripts/pacto_fetch.py --probe
Env:
  PACTO_API_KEY   ApiKey (Bearer) de UMA unidade (vem de GitHub Secret)
  PACTO_UNIT      rotulo da unidade (ex.: 716NORTE) - so para log
"""
import os, sys, re, json, datetime
import urllib.request, urllib.error

BASE = "https://apigw.pactosolucoes.com.br"

# Endpoints "em massa" (sem path param) que validam conexao e revelam schema.
PROBE_ENDPOINTS = [
    ("clientes_simples",        "GET", "/clientes/simples"),
    ("acessos_lista_rapida",    "GET", "/psec/alunos/lista-rapida-acessos"),
    ("checkins_agregados",      "GET", "/psec/alunos/ultimos-checkins-agregados"),
]
# Variacoes de querystring a tentar caso a chamada simples falhe (paginacao comum).
QS_FALLBACKS = ["", "?page=0&size=1", "?pagina=0&tamanho=1", "?limit=1", "?inicio=0&total=1"]

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}")
DATE_HINT = ("data", "date", "dt", "nasc", "matric", "acesso", "checkin", "cadastro", "venc")


def http_get(path, key, timeout=30):
    req = urllib.request.Request(BASE + path, method="GET")
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
            return r.status, r.headers.get("Content-Type", ""), body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace") if e.fp else ""
        return e.code, e.headers.get("Content-Type", "") if e.headers else "", body
    except Exception as e:
        return -1, "", "EXC: " + str(e)


def parse_date(v):
    if not isinstance(v, str):
        return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", v)
    if m:
        try: return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError: return None
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", v)
    if m:
        try: return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError: return None
    return None


def unwrap_list(obj):
    """Acha a lista de registros (resposta crua OU envelope de paginacao)."""
    if isinstance(obj, list):
        return obj, None
    if isinstance(obj, dict):
        page_keys = {k: obj[k] for k in ("totalElements", "totalPages", "number",
                                         "size", "total", "totalItens", "pagina") if k in obj}
        for k in ("content", "data", "rows", "list", "items", "registros", "dados", "result", "results"):
            if isinstance(obj.get(k), list):
                return obj[k], page_keys
        return None, page_keys
    return None, None


def describe(name, obj):
    rows, page = unwrap_list(obj)
    if page:
        print(f"    paginacao: {json.dumps(page, ensure_ascii=False)}")
    if rows is None:
        if isinstance(obj, dict):
            print(f"    objeto com chaves: {sorted(obj.keys())}")
        else:
            print(f"    tipo inesperado: {type(obj).__name__}")
        return
    print(f"    itens na pagina: {len(rows)}")
    if not rows or not isinstance(rows[0], dict):
        return
    first = rows[0]
    print(f"    campos ({len(first)}): {sorted(first.keys())}")
    # tipos por campo (sem valores) + intervalos de data
    type_map, date_fields = {}, {}
    for k, v in first.items():
        type_map[k] = type(v).__name__
    print(f"    tipos: {json.dumps(type_map, ensure_ascii=False)}")
    for k in first:
        if any(h in k.lower() for h in DATE_HINT) or (isinstance(first.get(k), str) and DATE_RE.search(first[k] or "")):
            ds = [parse_date(r.get(k)) for r in rows if isinstance(r, dict)]
            ds = [d for d in ds if d]
            if ds:
                date_fields[k] = f"{min(ds).isoformat()} .. {max(ds).isoformat()} (n={len(ds)})"
    if date_fields:
        print(f"    campos de data (intervalo na amostra): {json.dumps(date_fields, ensure_ascii=False)}")


def probe():
    key = os.environ.get("PACTO_API_KEY", "").strip()
    unit = os.environ.get("PACTO_UNIT", "?")
    if not key:
        print("[probe] ERRO: PACTO_API_KEY ausente."); sys.exit(1)
    print(f"[probe] unidade={unit} base={BASE}")
    print(f"[probe] ApiKey presente: sim (len={len(key)}) — valor NAO e impresso")
    for label, _m, path in PROBE_ENDPOINTS:
        print(f"\n=== {label}  GET {path} ===")
        ok = False
        for qs in QS_FALLBACKS:
            status, ctype, body = http_get(path + qs, key)
            print(f"  tentativa '{qs or '(sem querystring)'}' -> HTTP {status} {ctype}")
            if status == 200 and "json" in ctype.lower():
                try:
                    describe(label, json.loads(body))
                    ok = True
                    break
                except Exception as e:
                    print(f"    (falha ao parsear JSON: {e})")
            elif status in (400, 422):
                # provavel falta de parametro — tenta proxima variacao
                snippet = body[:200].replace("\n", " ")
                print(f"    corpo(200c): {snippet}")
                continue
            else:
                snippet = body[:200].replace("\n", " ")
                print(f"    corpo(200c): {snippet}")
                break
        if not ok:
            print("  >> endpoint nao retornou lista JSON 200 nas variacoes testadas.")
    print("\n[probe] fim.")


if __name__ == "__main__":
    if "--probe" in sys.argv:
        probe()
    else:
        print("Use --probe (modo coleta real sera implementado apos travar o schema).")
