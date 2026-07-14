#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_ticket.py — DESCOBRE onde está o VALOR real do contrato/plano na API Pacto,
sem expor a chave nem PII. Hoje o "ticket" e' o medio da unidade (Faturamento / alunos).

v2: extrai os itens de forma robusta (como o build), imprime as CHAVES REAIS dos itens
de /v1/contrato E de /v1/plano, e destaca campos numericos candidatos a valor.

Uso (a chave fica SO no ambiente, nunca e' impressa):
  export PACTO_KEY_716NORTE="...."
  python scripts/probe_ticket.py 716NORTE
"""
import os, sys, json, urllib.request, urllib.error

GATEWAY = "https://apigw.pactosolucoes.com.br"
unit = (sys.argv[1] if len(sys.argv) > 1 else "716NORTE").upper()
KEY = os.environ.get(f"PACTO_KEY_{unit}", "").strip()
if not KEY:
    print(f"[erro] variavel PACTO_KEY_{unit} nao definida."); sys.exit(1)

PII = ("nome", "name", "cpf", "email", "telefone", "fone", "rg", "endereco", "foto")
VAL_HINT = ("valor", "mensal", "preco", "preço", "price", "amount", "parcela", "mensalidade", "ticket")

def raw(path):
    req = urllib.request.Request(GATEWAY + path,
        headers={"Authorization": f"Bearer {KEY}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return "EXC", str(e)[:140]

def as_json(b):
    try: return json.loads(b)
    except Exception: return None

def lst(o):
    """Extrai a LISTA de itens de varios formatos de envelope (igual ao build)."""
    if isinstance(o, list): return o
    if isinstance(o, dict):
        for k in ("content", "data", "result", "results", "rows", "list", "items"):
            v = o.get(k)
            if isinstance(v, list): return v
            if isinstance(v, dict):
                for k2 in ("lista", "content", "items", "rows"):
                    if isinstance(v.get(k2), list): return v[k2]
                return [v]
    return []

def all_num_val(d, path=""):
    hits = []
    if isinstance(d, dict):
        for k, v in d.items():
            kl = str(k).lower()
            if isinstance(v, (dict, list)):
                hits += all_num_val(v, f"{path}.{k}")
            elif isinstance(v, (int, float)) and any(h in kl for h in VAL_HINT) and not any(p in kl for p in PII):
                hits.append((f"{path}.{k}".lstrip("."), v))
    elif isinstance(d, list) and d:
        hits += all_num_val(d[0], f"{path}[0]")
    return hits

def keys_of(d):
    return sorted(str(k) for k in d.keys()) if isinstance(d, dict) else f"(nao-dict: {type(d).__name__})"

print(f"=== PROBE TICKET v2 — unidade {unit} ===")
st, body = raw("/clientes/simples?page=0&size=30")
roster = as_json(body)
sample = lst(roster)[:6]
print(f"amostra: {len(sample)} clientes\n")

cand = {}
# ---- /v1/contrato ----
for i, c in enumerate(sample):
    M = c.get("matricula") or c.get("codigo") or c.get("codigoCliente")
    if not M: continue
    st2, b2 = raw(f"/v1/contrato/matricula/{M}")
    j = as_json(b2)
    its = lst(j)
    if i == 0:
        print(f"[/v1/contrato] status={st2} envelope_keys={keys_of(j)}")
        print(f"[/v1/contrato] itens={len(its)} · chaves do 1o item={keys_of(its[0]) if its else '(vazio)'}\n")
    for it in its:
        for nome, val in all_num_val(it):
            cand.setdefault("contrato."+nome, []).append(val)

# ---- /v1/plano ----
stp, bp = raw("/v1/plano")
planos = lst(as_json(bp))
print(f"[/v1/plano] itens={len(planos)} · chaves do 1o plano={keys_of(planos[0]) if planos else '(vazio)'}")
for p in planos[:30]:
    for nome, val in all_num_val(p):
        cand.setdefault("plano."+nome, []).append(val)

print("\n" + "="*50)
if cand:
    print("CANDIDATOS A VALOR (campo -> exemplos):")
    for nome, vals in sorted(cand.items()):
        print(f"  {nome} = " + ", ".join(str(v) for v in vals[:6]))
    print("\n-> me diz qual campo e' a mensalidade/ticket real que eu ligo no build.")
else:
    print("Ainda sem campo numerico de valor. Me manda as 'chaves do 1o item' acima")
    print("(contrato e plano) que eu vejo onde procurar / ajusto o endpoint.")
print("=== fim (nenhuma credencial/PII impressa) ===")
