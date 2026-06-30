#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coletor da API PACTO -> Dashboard Frequencia & Retencao (Nad'Arte).

MODO PROBE (descoberta segura de schema): NAO imprime dados pessoais.
Para cada endpoint imprime apenas: status HTTP, formato, contagem,
NOMES de campos, tipos e intervalos de datas (datas nao sao PII).
Encadeia: /clientes/simples -> pega 1 codigoCliente/matricula (valores
mascarados) -> testa endpoints de ACESSO por pessoa e variacoes do bulk.

Uso:  python scripts/pacto_fetch.py --probe
Env:  PACTO_API_KEY (Bearer, vem de GitHub Secret), PACTO_UNIT (rotulo)
"""
import os, sys, re, json, datetime
import urllib.request, urllib.error, urllib.parse

BASE = "https://apigw.pactosolucoes.com.br"
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}")
DATE_HINT = ("data", "date", "dt", "nasc", "matric", "acesso", "checkin", "cadastro", "venc", "hora")


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
    if isinstance(obj, list):
        return obj, None
    if isinstance(obj, dict):
        page = {k: obj[k] for k in ("totalElements", "totalPages", "number", "size",
                                    "total", "totalItens", "pagina", "last", "first") if k in obj}
        for k in ("content", "data", "rows", "list", "items", "registros", "dados", "result", "results"):
            if isinstance(obj.get(k), list):
                return obj[k], page
        return None, page
    return None, None


def describe(obj):
    rows, page = unwrap_list(obj)
    if page:
        print(f"    paginacao: {json.dumps(page, ensure_ascii=False)}")
    if rows is None:
        if isinstance(obj, dict):
            print(f"    objeto chaves: {sorted(obj.keys())}")
        else:
            print(f"    tipo: {type(obj).__name__}")
        return rows
    print(f"    itens: {len(rows)}")
    if rows and isinstance(rows[0], dict):
        first = rows[0]
        print(f"    campos ({len(first)}): {sorted(first.keys())}")
        print(f"    tipos: {json.dumps({k: type(v).__name__ for k, v in first.items()}, ensure_ascii=False)}")
        df = {}
        for k in first:
            if any(h in k.lower() for h in DATE_HINT) or (isinstance(first.get(k), str) and DATE_RE.search(first[k] or "")):
                ds = [parse_date(r.get(k)) for r in rows if isinstance(r, dict)]
                ds = [d for d in ds if d]
                if ds:
                    df[k] = f"{min(ds).isoformat()}..{max(ds).isoformat()} (n={len(ds)})"
        if df:
            print(f"    datas (intervalo na amostra): {json.dumps(df, ensure_ascii=False)}")
    return rows


def try_json(label, path, key):
    print(f"\n=== {label}  GET {path} ===")
    status, ctype, body = http_get(path, key)
    print(f"  HTTP {status} {ctype}")
    if status == 200 and "json" in ctype.lower():
        try:
            return describe(json.loads(body))
        except Exception as e:
            print(f"    (JSON invalido: {e})")
    else:
        print(f"    corpo(160c): {body[:160].replace(chr(10),' ')}")
    return None


def probe():
    key = os.environ.get("PACTO_API_KEY", "").strip()
    unit = os.environ.get("PACTO_UNIT", "?")
    if not key:
        print("[probe] ERRO: PACTO_API_KEY ausente."); sys.exit(1)
    print(f"[probe] unidade={unit} base={BASE} (ApiKey len={len(key)}, valor NAO impresso)")

    # 1) Roster de clientes (paginado)
    rows = try_json("clientes_simples", "/clientes/simples?page=0&size=5", key)

    # 2) Captura um id/matricula (mascarados) para testar acessos por pessoa
    cod, mat = None, None
    if rows:
        for r in rows:
            if isinstance(r, dict):
                cod = cod or r.get("codigoCliente")
                mat = mat or r.get("matricula")
                if cod and mat:
                    break
    print(f"\n[probe] codigoCliente capturado: {'sim' if cod else 'nao'} | matricula capturada: {'sim' if mat else 'nao'} (valores ocultos)")

    # 3) Endpoints de ACESSO por pessoa (substituindo ids reais)
    if cod is not None:
        c = urllib.parse.quote(str(cod))
        try_json("acessos_by_pessoa",   f"/acessos-cliente/by-pessoa/{c}", key)
        try_json("acessos_ultimosmeses", f"/acessos-cliente/{c}/ultimos-meses", key)
        try_json("acessos_info",         f"/acessos-cliente/{c}/info-acessos", key)
        try_json("periodo_acesso",       f"/clientes/{c}/periodo-acesso", key)
    if mat is not None:
        m = urllib.parse.quote(str(mat))
        try_json("registro_acesso_matricula", f"/clientes/listar-registro-de-acesso/{m}", key)

    # 4) Bulk de acessos — tenta variacoes de parametros de data (descoberta)
    di, dfim = "2026-06-01", "2026-06-30"
    variants = [
        f"?dataInicial={di}&dataFinal={dfim}",
        f"?dataInicio={di}&dataFim={dfim}",
        f"?inicio={di}&fim={dfim}",
        f"?dataInicial={urllib.parse.quote('01/06/2026')}&dataFinal={urllib.parse.quote('30/06/2026')}",
        "?filters=" + urllib.parse.quote(json.dumps({"dataInicial": di, "dataFinal": dfim})),
    ]
    print("\n=== bulk lista-rapida-acessos (variacoes de data) ===")
    for qs in variants:
        status, ctype, body = http_get("/psec/alunos/lista-rapida-acessos" + qs, key)
        print(f"  {qs[:70]} -> HTTP {status} {ctype.split(';')[0]}")
        if status == 200 and "json" in ctype.lower():
            try:
                describe(json.loads(body)); print("   >> OK nesta variacao."); break
            except Exception as e:
                print(f"   (JSON invalido: {e})")

    print("\n[probe] fim.")


if __name__ == "__main__":
    if "--probe" in sys.argv:
        probe()
    else:
        print("Use --probe (a coleta real sera implementada apos travar o schema).")
