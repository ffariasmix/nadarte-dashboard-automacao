#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_ticket.py v3 — DESCOBRE onde esta o VALOR real da mensalidade na API Pacto.
PII-safe: imprime so ESTRUTURA DE CHAVES + campos numericos candidatos a valor.
Nao imprime nome/CPF/email/chave.

Estrategia: filtra clientes ATIVOS (como o build), tenta varios, e dumpa a arvore de
chaves de /v1/contrato e /v1/plano; alem disso tenta endpoints de financeiro/mensalidade.

  export PACTO_KEY_716NORTE="...."
  python scripts/probe_ticket.py 716NORTE
"""
import os, sys, json, urllib.request, urllib.error

GATEWAY = "https://apigw.pactosolucoes.com.br"
unit = (sys.argv[1] if len(sys.argv) > 1 else "716NORTE").upper()
KEY = os.environ.get(f"PACTO_KEY_{unit}", "").strip()
if not KEY:
    print(f"[erro] variavel PACTO_KEY_{unit} nao definida."); sys.exit(1)

PII = ("nome", "name", "cpf", "email", "telefone", "fone", "rg", "endereco", "foto", "cliente")
VAL_HINT = ("valor", "mensal", "preco", "preço", "price", "amount", "parcela", "mensalidade", "ticket", "cobranca")

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
    if isinstance(o, list): return o
    if isinstance(o, dict):
        for k in ("content", "data", "result", "results", "rows", "list", "items", "lista"):
            v = o.get(k)
            if isinstance(v, list): return v
            if isinstance(v, dict):
                for k2 in ("lista", "content", "items", "rows"):
                    if isinstance(v.get(k2), list): return v[k2]
    return []

def key_tree(d, depth=0, maxd=3):
    """Arvore de chaves (PII-safe). Mostra tipo; numericos com hint de valor mostram o numero."""
    out = []
    pad = "  " * depth
    if isinstance(d, dict):
        for k, v in d.items():
            kl = str(k).lower()
            if isinstance(v, dict):
                out.append(f"{pad}{k}: {{}}");
                if depth < maxd: out += key_tree(v, depth+1, maxd)
            elif isinstance(v, list):
                out.append(f"{pad}{k}: [len={len(v)}]")
                if v and isinstance(v[0], (dict, list)) and depth < maxd: out += key_tree(v[0], depth+1, maxd)
            else:
                show = v if (isinstance(v, (int, float)) and any(h in kl for h in VAL_HINT) and not any(p in kl for p in PII)) else ("<num>" if isinstance(v,(int,float)) else "<str>")
                out.append(f"{pad}{k}: {show}")
    return out

def scan_val(d, path=""):
    hits = []
    if isinstance(d, dict):
        for k, v in d.items():
            kl = str(k).lower()
            if isinstance(v, (dict, list)): hits += scan_val(v, f"{path}.{k}")
            elif isinstance(v, (int, float)) and any(h in kl for h in VAL_HINT) and not any(p in kl for p in PII):
                hits.append((f"{path}.{k}".lstrip("."), v))
    elif isinstance(d, list) and d:
        hits += scan_val(d[0], f"{path}[0]")
    return hits

print(f"=== PROBE TICKET v3 — unidade {unit} ===")
st, body = raw("/clientes/simples?page=0&size=100")
roster = lst(as_json(body))
ativos = [c for c in roster if str(c.get("situacao","")).strip().upper() == "ATIVO"] or roster
print(f"roster={len(roster)} · ativos={len(ativos)}\n")

cand = {}
dumped_ct = dumped_fin = False
for c in ativos[:15]:
    M = c.get("matricula") or c.get("codigo") or c.get("codigoCliente")
    if not M: continue
    st2, b2 = raw(f"/v1/contrato/matricula/{M}")
    j = as_json(b2); its = lst(j)
    if its and not dumped_ct:
        dumped_ct = True
        print(f"[/v1/contrato] itens={len(its)} · ARVORE DE CHAVES do 1o item:")
        for line in key_tree(its[0])[:40]: print("   " + line)
        print()
    for it in its:
        for nome, val in scan_val(it): cand.setdefault("contrato."+nome, []).append(val)
    # financeiro por matricula (candidatos comuns)
    for fp in (f"/v1/financeiro/matricula/{M}", f"/clientes/{M}/financeiro", f"/v1/contas-receber/matricula/{M}"):
        stf, bf = raw(fp); jf = as_json(bf); itf = lst(jf)
        if itf and not dumped_fin:
            dumped_fin = True
            print(f"[{fp}] itens={len(itf)} · ARVORE DE CHAVES do 1o item:")
            for line in key_tree(itf[0])[:40]: print("   " + line)
            print()
        for it in itf:
            for nome, val in scan_val(it): cand.setdefault("financeiro."+nome, []).append(val)

# planos (catalogo)
pln = lst(as_json(raw("/v1/plano")[1]))
if pln:
    print(f"[/v1/plano] itens={len(pln)} · ARVORE DE CHAVES do 1o plano:")
    for line in key_tree(pln[0])[:40]: print("   " + line)
    print()
    for p in pln[:40]:
        for nome, val in scan_val(p): cand.setdefault("plano."+nome, []).append(val)

print("="*50)
if cand:
    print("CANDIDATOS A VALOR (campo -> exemplos):")
    for nome, vals in sorted(cand.items()):
        print(f"  {nome} = " + ", ".join(str(v) for v in vals[:6]))
    print("\n-> me diz qual campo e' a mensalidade real.")
else:
    print("Sem valor nos endpoints testados. Me manda as ARVORES DE CHAVES acima")
    print("(contrato/financeiro/plano) que eu identifico o campo ou o endpoint certo.")
print("=== fim (nenhuma credencial/PII impressa) ===")
