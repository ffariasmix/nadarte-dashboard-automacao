#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coletor PACTO -> Dashboard Frequencia & Retencao (Nad'Arte).

Modos:
  --collect  : pagina o roster (/clientes/simples) e agrega acessos por mes
               (/acessos-cliente/by-pessoa) para uma AMOSTRA de clientes, e
               imprime um resumo PII-safe (contagens, situacao, cobertura de meses).
  --probe    : descoberta de schema (sem dados pessoais).

Env:
  PACTO_API_KEY   ApiKey (Bearer) de UMA unidade (GitHub Secret)
  PACTO_UNIT      rotulo (ex.: 716NORTE)
  SAMPLE          qtd de clientes para amostrar acessos (default 25)
  ROSTER_MAXPAGES limite de paginas do roster (default 60)
"""
import os, sys, re, json
import urllib.request, urllib.error
from collections import Counter, defaultdict

BASE = "https://apigw.pactosolucoes.com.br"


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


def get_json(path, key):
    st, ct, body = http_get(path, key)
    if st == 200 and "json" in ct.lower():
        try:
            return json.loads(body)
        except Exception:
            return None
    return None


def rows_of(obj):
    if isinstance(obj, list):
        return obj, {}
    if isinstance(obj, dict):
        page = {k: obj.get(k) for k in ("totalElements", "totalPages", "number", "size", "last") if k in obj}
        for k in ("content", "data", "rows", "list", "items", "registros", "dados", "result", "results"):
            if isinstance(obj.get(k), list):
                return obj[k], page
        return [], page
    return [], {}


def paginate(path_base, key, size=200, max_pages=60):
    """Itera paginas ?page=&size= ate acabar. Retorna (rows, paginas_lidas, total_declarado)."""
    sep = "&" if "?" in path_base else "?"
    all_rows, total = [], None
    for pg in range(max_pages):
        obj = get_json(f"{path_base}{sep}page={pg}&size={size}", key)
        if obj is None:
            break
        rows, page = rows_of(obj)
        if total is None and page.get("totalElements") is not None:
            total = page["totalElements"]
        all_rows.extend(rows)
        if page.get("last") is True or len(rows) < size or not rows:
            return all_rows, pg + 1, total
    return all_rows, max_pages, total


def ym(s):
    if not isinstance(s, str):
        return None
    m = re.search(r"(\d{4})-(\d{2})", s) or re.search(r"(\d{2})/(\d{2})/(\d{4})", s)
    if not m:
        return None
    g = m.groups()
    return f"{g[0]}-{g[1]}" if len(g[0]) == 4 else f"{g[2]}-{g[1]}"


def collect():
    key = os.environ.get("PACTO_API_KEY", "").strip()
    unit = os.environ.get("PACTO_UNIT", "?")
    sample = int(os.environ.get("SAMPLE", "25"))
    roster_max = int(os.environ.get("ROSTER_MAXPAGES", "60"))
    if not key:
        print("[collect] ERRO: PACTO_API_KEY ausente."); sys.exit(1)
    print(f"[collect] unidade={unit} (ApiKey len={len(key)}) sample={sample}")

    # 1) ROSTER completo
    roster, pages, total = paginate("/clientes/simples", key, size=200, max_pages=roster_max)
    print(f"[roster] paginas lidas={pages} | total declarado={total} | linhas obtidas={len(roster)}")
    sit = Counter((r.get("situacao") or "?") for r in roster if isinstance(r, dict))
    print(f"[roster] distribuicao por situacao: {json.dumps(dict(sit), ensure_ascii=False)}")
    cods = [r.get("codigoCliente") for r in roster if isinstance(r, dict) and r.get("codigoCliente")]
    print(f"[roster] clientes com codigoCliente: {len(cods)}")

    # 2) ACESSOS agregados por mes (amostra)
    glob_month = Counter()
    depth_min, depth_max = None, None
    tot_acc = 0
    sampled = 0
    for cod in cods[:sample]:
        rows, pgs, t = paginate(f"/acessos-cliente/by-pessoa/{cod}", key, size=200, max_pages=40)
        sampled += 1
        for a in rows:
            d = ym(a.get("dtHrEntrada")) if isinstance(a, dict) else None
            if d:
                glob_month[d] += 1
                tot_acc += 1
                depth_min = d if depth_min is None or d < depth_min else depth_min
                depth_max = d if depth_max is None or d > depth_max else depth_max
    print(f"[acessos] clientes amostrados={sampled} | acessos somados={tot_acc}")
    print(f"[acessos] cobertura de meses: {depth_min} .. {depth_max}")
    # histograma mensal (amostra) — ultimos 18 meses
    meses = sorted(glob_month.keys())
    tail = meses[-18:] if len(meses) > 18 else meses
    print("[acessos] acessos/mes (amostra, ult. meses):")
    for m in tail:
        print(f"    {m}: {glob_month[m]}")
    print(f"[acessos] meses distintos na amostra: {len(meses)}")
    print("\n[collect] fim.")


def probe():
    key = os.environ.get("PACTO_API_KEY", "").strip()
    print(f"[probe] ApiKey len={len(key)}")
    for label, p in [("clientes_simples", "/clientes/simples?page=0&size=3"),
                     ("ultimos_meses_amostra", None)]:
        if p:
            obj = get_json(p, key)
            rows, page = rows_of(obj or {})
            print(label, "->", len(rows), "linhas;", (sorted(rows[0].keys()) if rows and isinstance(rows[0], dict) else ""))
    print("[probe] fim.")


if __name__ == "__main__":
    if "--collect" in sys.argv:
        collect()
    elif "--probe" in sys.argv:
        probe()
    else:
        print("Use --collect ou --probe.")
