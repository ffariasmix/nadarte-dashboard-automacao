#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""716N — cobertura REAL de frequencia: roster ATIVO x acessos (by-pessoa) cruzado por CPF.
PII-safe: nunca imprime CPF/nome; so contagens, chaves, datas e meios de identificacao."""
import os, sys, json, time
from datetime import datetime, timezone, timedelta
import urllib.request, urllib.error

BASE = "https://apigw.pactosolucoes.com.br"
KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()

NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)
D90 = NOW - timedelta(days=90)


def http_get(path, headers=None, timeout=45):
    req = urllib.request.Request(BASE + path, method="GET")
    req.add_header("Authorization", "Bearer " + KEY)
    req.add_header("Accept", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, str(v))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode("utf-8", "replace") if e.fp else "")
    except Exception as e:
        return -1, str(e)


def gj(path, headers=None):
    st, b = http_get(path, headers)
    try:
        return st, json.loads(b)
    except Exception:
        return st, b


def lst(o):
    """extrai lista de varios formatos, inclusive content.lista (aninhado)."""
    if isinstance(o, list):
        return o
    if isinstance(o, dict):
        for k in ("content", "data", "result", "results", "rows", "list", "items", "alunos", "acessos", "clientes"):
            v = o.get(k)
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                for k2 in ("lista", "content", "items", "rows"):
                    if isinstance(v.get(k2), list):
                        return v[k2]
    return []


def find(d, names):
    """acha 1o valor cujo nome de chave bate (case-insensitive, em qualquer nivel raso)."""
    if not isinstance(d, dict):
        return None
    low = {k.lower(): k for k in d.keys()}
    for n in names:
        if n.lower() in low:
            return d[low[n.lower()]]
    # 1 nivel de aninhamento
    for k, v in d.items():
        if isinstance(v, dict):
            r = find(v, names)
            if r is not None:
                return r
    return None


def to_dt(v):
    if v is None:
        return None
    try:
        if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()):
            n = int(v)
            if n > 10_000_000_000:  # ms
                n //= 1000
            return datetime.fromtimestamp(n, tz=timezone.utc)
        s = str(v)[:19].replace("T", " ")
        for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
            try:
                return datetime.strptime(s, f).replace(tzinfo=timezone.utc)
            except Exception:
                pass
    except Exception:
        return None
    return None


def mask(s):
    s = str(s or "")
    return (s[:1] + "***" + s[-1:]) if len(s) > 2 else "**"


def main():
    if not KEY:
        print("[v] sem chave"); sys.exit(1)

    # ---- 1) SHAPE do roster e da pessoa (PII-safe) ----
    st, o = gj("/clientes/simples?page=0&size=5")
    rows = lst(o)
    print(f"[shape clientes/simples] HTTP {st} | itens_pg={len(rows)}")
    if rows and isinstance(rows[0], dict):
        print("  chaves:", sorted(rows[0].keys()))

    st, o = gj("/v1/pessoa?page=0&size=3")
    prows = lst(o)
    print(f"[shape v1/pessoa] HTTP {st} | itens_pg={len(prows)}")
    if prows and isinstance(prows[0], dict):
        print("  chaves:", sorted(prows[0].keys()))

    # ---- 2) Roster completo (paginado) + distribuicao de situacao ----
    todos = []
    for pg in range(0, 60):
        st, o = gj(f"/clientes/simples?page={pg}&size=200")
        r = lst(o)
        if not r:
            break
        todos.extend([c for c in r if isinstance(c, dict)])
        if len(r) < 200:
            break
    dist = {}
    for c in todos:
        s = str(find(c, ["situacao", "situacaoCliente", "status"]) or "?").upper()
        dist[s] = dist.get(s, 0) + 1
    print(f"\n[roster] total clientes = {len(todos)}")
    print(f"  situacao: {dict(sorted(dist.items(), key=lambda x:-x[1]))}")

    ativos = [c for c in todos if str(find(c, ["situacao", "situacaoCliente", "status"]) or "").upper() == "ATIVO"]
    print(f"  ATIVO exato = {len(ativos)}")

    # ---- 3) Amostra ESPALHADA de ativos: cobertura via by-pessoa(codigoCliente) ----
    N = 90
    step = max(1, len(ativos) // N)
    sample = ativos[::step][:N]
    com_acesso = com_2026 = com_90d = sem_id = erros = 0
    meios = {}
    meios26 = {}
    dmin = dmax = None
    total_acessos = 0
    dump_keys = True
    for c in sample:
        cc = find(c, ["codigoCliente", "codCliente", "codigo"])
        if cc is None:
            sem_id += 1
            continue
        st, o = gj(f"/acessos-cliente/by-pessoa/{cc}?page=0&size=300")
        if st != 200:
            erros += 1
            continue
        acc = lst(o)
        if acc:
            if dump_keys and isinstance(acc[0], dict):
                print(f"\n[acesso] chaves: {sorted(acc[0].keys())}")
                dump_keys = False
            com_acesso += 1
            total_acessos += len(acc)
            has26 = has90 = False
            for a in acc:
                dt = to_dt(find(a, ["dtHrEntrada", "dataHoraEntrada", "dataEntrada", "dataAcesso", "data", "dtAcesso"]))
                m = str(find(a, ["descMeioIdentificacao", "meioIdentificacaoEntrada", "meioIdentificacao", "meio", "tipoAcesso", "formaAcesso"]) or "?")
                meios[m] = meios.get(m, 0) + 1
                if dt:
                    dmin = dt if (dmin is None or dt < dmin) else dmin
                    dmax = dt if (dmax is None or dt > dmax) else dmax
                    if dt.year == 2026:
                        has26 = True
                        meios26[m] = meios26.get(m, 0) + 1
                    if dt >= D90:
                        has90 = True
            com_2026 += 1 if has26 else 0
            com_90d += 1 if has90 else 0
        time.sleep(0.04)

    n = len(sample)
    print(f"\n[cobertura by-pessoa(codigoCliente)] amostra={n} de {len(ativos)} ATIVOS (espalhada)")
    print(f"  sem_id={sem_id} | erros_http={erros}")
    print(f"  com >=1 acesso (qualquer data): {com_acesso}  ({100*com_acesso/max(1,n):.0f}%)")
    print(f"  com acesso em 2026:            {com_2026}  ({100*com_2026/max(1,n):.0f}%)")
    print(f"  com acesso nos ultimos 90d:    {com_90d}  ({100*com_90d/max(1,n):.0f}%)")
    print(f"  total registros amostrados: {total_acessos}")
    if dmin and dmax:
        print(f"  intervalo: {dmin.date()} -> {dmax.date()}")
    print(f"  meios (todos): { {k: meios[k] for k in sorted(meios, key=lambda x:-meios[x])[:10]} }")
    print(f"  meios (so 2026): { {k: meios26[k] for k in sorted(meios26, key=lambda x:-meios26[x])[:10]} }")

    print("\n[v] fim.")


if __name__ == "__main__":
    main()
