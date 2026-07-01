#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
716N — validacao de TENURE (histórico de contrato / 1o acesso) + MATRIZ DE FREQUENCIA (18m).
PII-safe (contagens, anos, totais mensais). Env: PACTO_KEY_716NORTE, SAMPLE(=30)
"""
import os, sys, re, json, datetime
import urllib.request, urllib.error
from collections import Counter

BASE = "https://apigw.pactosolucoes.com.br"
KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()
SAMPLE = int(os.environ.get("SAMPLE", "30"))


def http_get(path, timeout=50):
    req = urllib.request.Request(BASE + path, method="GET")
    req.add_header("Authorization", "Bearer " + KEY)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode("utf-8", "replace") if e.fp else "")
    except Exception as e:
        return -1, str(e)


def gj(path):
    st, body = http_get(path)
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


def ym(s):
    m = re.search(r"(\d{4})-(\d{2})", s or "") if isinstance(s, str) else None
    return f"{m.group(1)}-{m.group(2)}" if m else None


def main():
    if not KEY:
        print("[t] sem chave 716N"); sys.exit(1)
    # roster -> ativos
    ativos = []
    for pg in range(120):
        rows = content(gj(f"/clientes/simples?page={pg}&size=200"))
        if not rows:
            break
        ativos += [r for r in rows if isinstance(r, dict) and (r.get("situacao") or "").upper() == "ATIVO"]
        if len(rows) < 200:
            break
    print(f"[716N] ativos={len(ativos)} | amostrando {min(SAMPLE,len(ativos))}")

    contratos_len = Counter()
    anos_contrato = Counter()
    ano_1acesso = Counter()
    com_acesso = 0
    mensal = Counter()
    hoje = datetime.date(2026, 6, 1)
    janela = set()
    for i in range(18):
        y = hoje.year; m = hoje.month - i
        while m <= 0:
            m += 12; y -= 1
        janela.add(f"{y}-{m:02d}")

    for r in ativos[:SAMPLE]:
        cc = r.get("codigoCliente"); mat = r.get("matricula")
        # contrato: quantos + anos citados
        if mat:
            ct = content(gj(f"/v1/contrato/matricula/{mat}"))
            contratos_len[len(ct)] += 1
            for c in ct:
                if isinstance(c, dict):
                    for yy in re.findall(r"(\d{4})", str(c.get("descricao") or "")):
                        if 1985 <= int(yy) <= 2027:
                            anos_contrato[int(yy)] += 1
        # acessos: 1o acesso (ano) + matriz mensal (18m)
        if cc:
            acc = content(gj(f"/acessos-cliente/by-pessoa/{cc}?page=0&size=200"))
            # paginar ate acabar (historico completo p/ 1o acesso)
            pg = 1
            allacc = list(acc)
            while len(acc) == 200 and pg < 40:
                acc = content(gj(f"/acessos-cliente/by-pessoa/{cc}?page={pg}&size=200"))
                allacc += acc; pg += 1
            meses = [ym(a.get("dtHrEntrada")) for a in allacc if isinstance(a, dict)]
            meses = [x for x in meses if x]
            if meses:
                com_acesso += 1
                ano_1acesso[min(meses)[:4]] += 1
                for mm in meses:
                    if mm in janela:
                        mensal[mm] += 1

    print(f"[contrato] itens por aluno (len): {dict(contratos_len)}")
    print(f"[contrato] anos citados nas descricoes (top): {sorted(anos_contrato.items())}")
    print(f"[tenure] 1o acesso por ANO (amostra): {dict(sorted(ano_1acesso.items()))}")
    print(f"[freq] com >=1 acesso: {com_acesso}/{min(SAMPLE,len(ativos))}")
    print(f"[freq] MATRIZ mensal 18m (soma amostra):")
    for mm in sorted(janela):
        print(f"    {mm}: {mensal.get(mm,0)}")
    print("\n[t] fim.")


if __name__ == "__main__":
    main()
