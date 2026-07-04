#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pacto_probe_contrato.py (v2) — Descobrir o CAMPO DE VALOR do contrato/plano na API PACTO.
v1 mostrou: /v1/contrato=500; /clientes/{mat}/contrato*=404; MAS /v1/cliente/{codigo}=200
com ramos 'vinculos' e 'clienteSintetico' (o valor deve estar aninhado ai).
v2 faz um WALK recursivo PII-safe: imprime as CHAVES de cada nivel e SO os valores de campos
que parecem valor (valor/mensal/plano/parcela...). NUNCA imprime nome/CPF/contato.

Roda so na 716 Norte (canario). Uso: PACTO_KEY_716NORTE=... python scripts/pacto_probe_contrato.py
"""
import os, sys
from pacto_fetch import gj, lst, gv, roster_full

KEY = os.environ.get("PACTO_KEY_716NORTE", "").strip()
if not KEY:
    print("[probe] sem PACTO_KEY_716NORTE", file=sys.stderr); sys.exit(0)

VAL_HINT = ("valor","price","preco","mensal","parcela","plano","total","desconto",
            "liquid","bruto","vlr","receita","ticket","adesao","anuidade","modalidade")
PII = ("nome","name","cpf","email","telefone","fone","rg","endereco","nascimento",
       "datanasc","logradouro","numero","bairro","cidade","cep","apelido","foto")

def walk(tag, o, depth=0, maxdepth=5):
    ind = "  " * depth
    if isinstance(o, dict):
        print(f"{ind}[{tag}] dict keys={sorted(o.keys())}", file=sys.stderr)
        for k, v in o.items():
            kl = k.lower()
            if any(p in kl for p in PII):
                continue  # nunca loga PII
            if isinstance(v, (dict, list)):
                if depth < maxdepth and v:
                    walk(k, v, depth + 1, maxdepth)
            elif any(h in kl for h in VAL_HINT):
                print(f"{ind}  {k} = {v!r}", file=sys.stderr)
    elif isinstance(o, list):
        print(f"{ind}[{tag}] list n={len(o)}", file=sys.stderr)
        if o and depth < maxdepth:
            walk(tag + "[0]", o[0], depth + 1, maxdepth)

# 1) retry /v1/contrato (pode precisar de filtro; registra o status)
st, o = gj(KEY, "/v1/contrato?page=0&size=5")
print(f"[/v1/contrato] status={st} itens={len(lst(o))}", file=sys.stderr)

# 2) o caminho promissor: /v1/cliente/{codigo} -> vinculos / clienteSintetico
full = roster_full(KEY)
ativos = [c for c in full if str(gv(c, "situacao") or "").upper() == "ATIVO"]
print(f"[roster] total={len(full)} ativos={len(ativos)}", file=sys.stderr)
for c in ativos[:3]:
    cc = gv(c, "codigoCliente", "codigo")
    st2, o2 = gj(KEY, f"/v1/cliente/{cc}")
    print(f"=== /v1/cliente/{cc} status={st2} ===", file=sys.stderr)
    if st2 == 200 and isinstance(o2, dict):
        body = o2.get("content", o2) if isinstance(o2.get("content"), dict) else o2
        walk("cliente", body)
    print("---", file=sys.stderr)

print("[probe v2] fim (PII-safe)", file=sys.stderr)
