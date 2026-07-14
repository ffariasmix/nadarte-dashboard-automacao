#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_ticket.py — DESCOBRE o campo de VALOR do contrato na API Pacto, sem expor a chave
nem PII. Hoje o "ticket" é o médio da unidade (Faturamento ÷ alunos). Este probe procura,
no contrato de uma amostra de alunos, o campo que traz o VALOR REAL da mensalidade/contrato
(ex.: valor, valorMensal, mensalidade, preco, valorContrato...).

Uso (a chave fica SÓ no ambiente, nunca é impressa):
  export PACTO_KEY_716NORTE="...."
  python scripts/probe_ticket.py 716NORTE

Saída (PII-safe): para uma amostra, imprime SÓ as chaves do contrato e os campos
numéricos candidatos a "valor". Nenhum nome/CPF/matrícula é impresso.
"""
import os, sys, json, time, urllib.request, urllib.error

GATEWAY = "https://apigw.pactosolucoes.com.br"
unit = (sys.argv[1] if len(sys.argv) > 1 else "716NORTE").upper()
KEY = os.environ.get(f"PACTO_KEY_{unit}", "").strip()
if not KEY:
    print(f"[erro] variavel PACTO_KEY_{unit} nao definida no ambiente."); sys.exit(1)

PII = ("nome", "name", "cpf", "email", "telefone", "fone", "rg", "endereco", "foto", "matricula")
VAL_HINT = ("valor", "mensal", "preco", "preço", "price", "amount", "parcela", "mensalidade", "total", "ticket")

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

def unwrap(j):
    return j["content"] if isinstance(j, dict) and "content" in j else j

def scan(obj, path=""):
    """Anda no JSON e coleta campos NUMERICOS cujo nome sugere valor. PII-safe."""
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if isinstance(v, (dict, list)):
                hits += scan(v, f"{path}.{k}")
            elif any(h in kl for h in VAL_HINT) and isinstance(v, (int, float)) and not any(p in kl for p in PII):
                hits.append((f"{path}.{k}".lstrip("."), v))
    elif isinstance(obj, list) and obj:
        hits += scan(obj[0], f"{path}[0]")
    return hits

print(f"=== PROBE TICKET — unidade {unit} ===")
st, body = raw("/clientes/simples?page=0&size=30")
roster = unwrap(as_json(body) or {})
sample = [c for c in (roster if isinstance(roster, list) else [])][:8]
print(f"amostra: {len(sample)} clientes\n")

campos = {}
for c in sample:
    M = c.get("matricula") or c.get("codigo")
    if not M: continue
    st2, b2 = raw(f"/v1/contrato/matricula/{M}")
    j = unwrap(as_json(b2) or {})
    items = j if isinstance(j, list) else [j]
    for it in items:
        if not isinstance(it, dict): continue
        # imprime as chaves do contrato (sem valores) so 1x
        if not campos:
            print("chaves do contrato:", sorted(it.keys())[:20], "\n")
        for nome, val in scan(it):
            campos.setdefault(nome, []).append(val)

if campos:
    print("CANDIDATOS A VALOR REAL DO CONTRATO (campo -> exemplos de valores):")
    for nome, vals in sorted(campos.items()):
        ex = ", ".join(str(v) for v in vals[:5])
        print(f"  {nome} = {ex}")
    print("\n-> me diz qual desses campos e' a mensalidade/ticket real que eu ligo no build.")
else:
    print("Nenhum campo numerico de valor encontrado no contrato desta amostra.")
    print("Pode ser que o valor venha de /v1/plano ou de outro endpoint — me avisa que sondo esses.")
print("=== fim (nenhuma credencial/PII impressa) ===")
