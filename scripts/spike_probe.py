#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spike_probe.py — valida endpoints da Pacto e DESCOBRE o campo de modalidade,
sem expor a chave. A chave e lida de variavel de ambiente e nunca e impressa.

Uso:
  export PACTO_KEY_716NORTE="...."          # a chave fica so no ambiente
  python scripts/spike_probe.py 716NORTE

Devolve: (1) relatorio de status/formato dos endpoints e
         (2) DESCOBERTA DE MODALIDADE — as chaves de um cliente do roster,
             do dados-pessoais e uma amostra de /v1/plano (PII-safe: so chaves
             e campos nao sensiveis; nada de nome/CPF).
"""
import os, sys, json, time, datetime as _dt, urllib.request, urllib.error

GATEWAY = "https://apigw.pactosolucoes.com.br"
unit = (sys.argv[1] if len(sys.argv) > 1 else "716NORTE").upper()
KEY = os.environ.get(f"PACTO_KEY_{unit}", "").strip()
if not KEY:
    print(f"[erro] variavel PACTO_KEY_{unit} nao definida no ambiente."); sys.exit(1)

PII = ("nome", "name", "cpf", "email", "telefone", "fone", "rg", "endereco", "foto")

def raw(path, headers=None):
    req = urllib.request.Request(GATEWAY + path,
        headers={"Authorization": f"Bearer {KEY}", "Accept": "application/json", **(headers or {})})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read().decode("utf-8", "replace"), round((time.time()-t0)*1000)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), round((time.time()-t0)*1000)
    except Exception as e:
        return "EXC", str(e)[:140], round((time.time()-t0)*1000)

def as_json(body):
    try: return json.loads(body)
    except Exception: return None

def unwrap(j):
    return j["content"] if isinstance(j, dict) and "content" in j else j

def shape(body):
    j = as_json(body)
    if j is None: return f"nao-JSON inicio={body[:60]!r}"
    c = unwrap(j)
    if isinstance(c, list): return f"list(len={len(c)})" + (f" item0keys={sorted(c[0].keys())[:14]}" if c and isinstance(c[0], dict) else "")
    if isinstance(c, dict):
        if "meta" in j and isinstance(j.get("meta"), dict): return f"meta.error={j['meta'].get('error')} msg={j['meta'].get('message')}"
        return f"dict keys={sorted(c.keys())[:16]}"
    return type(c).__name__

def safe_keys(d, tag):
    """imprime chaves e valores NAO sensiveis (candidatos a modalidade)."""
    if not isinstance(d, dict):
        print(f"  [{tag}] (nao e dict)"); return
    print(f"  [{tag}] keys={sorted(d.keys())}")
    for k, v in d.items():
        kl = k.lower()
        if any(p in kl for p in PII): continue
        if isinstance(v, (dict, list)): continue
        if any(w in kl for w in ("plano", "modalid", "categor", "descri", "produto", "servico", "contrato", "turma")):
            print(f"     {k} = {v!r}")

# ---------- 1) ENDPOINTS ----------
now = _dt.date.today().replace(day=1)
mes_ini = (now - _dt.timedelta(days=60)).replace(day=1)
to_ms = lambda d: int(_dt.datetime(d.year, d.month, d.day).timestamp() * 1000)
print(f"=== SPIKE Pacto — unidade {unit} ===")
for path, hdr in [
    ("/clientes/simples?page=0&size=5", None),
    ("/v1/plano", None),
    (f"/v1/bi/resumo?mesInicial={to_ms(mes_ini)}&mesFinal={to_ms(now)}", None),
    ("/v1/bi/velocimetro", None),
    ("/v1/contrato", None),
    ("/v1/bi/contas-receber", None),
    # candidatos de treino (responde "tem na Pacto?")
    ("/treino", None),
    ("/v1/treino", None),
]:
    st, body, ms = raw(path, hdr)
    print(json.dumps({"path": path, "status": st, "ms": ms, "formato": shape(body)}, ensure_ascii=False))

# ---------- 2) DESCOBERTA DE MODALIDADE ----------
print("\n=== DESCOBERTA DE MODALIDADE (PII-safe) ===")
st, body, _ = raw("/clientes/simples?page=0&size=50")
roster = unwrap(as_json(body) or {})
cliente = roster[0] if isinstance(roster, list) and roster else {}
safe_keys(cliente, "cliente(roster)")

M = cliente.get("matricula") or cliente.get("codigo")
if M:
    st, body, _ = raw(f"/clientes/{M}/dados-pessoais")
    safe_keys(unwrap(as_json(body) or {}), "dados-pessoais")
    # tentativas de endpoints de plano/contrato por matricula (descartar 404 depois)
    for p in (f"/clientes/{M}/plano", f"/clientes/{M}/contrato", f"/clientes/{M}/contratos"):
        st, body, _ = raw(p)
        print(f"  [{p}] status={st} formato={shape(body)}")

st, body, _ = raw("/v1/plano")
planos = unwrap(as_json(body) or {})
if isinstance(planos, list) and planos:
    print(f"  [/v1/plano] amostra de nomes: " +
          ", ".join(str(p.get('descricao') or p.get('nome') or p.get('nomePlano') or '?') for p in planos[:8]))
    print(f"  [/v1/plano] keys do plano: {sorted(planos[0].keys())[:16]}")

# ---------- 3) FOTOS / PROFESSOR (PII-safe: so presenca de campo) ----------
print("\n=== FOTOS/PROFESSOR (PII-safe) ===")
cc = cliente.get("codigoCliente") or cliente.get("codigo")
if cc:
    st, body, _ = raw(f"/v1/cliente/{cc}")
    cli = unwrap(as_json(body) or {})
    if isinstance(cli, dict):
        pes = cli.get("pessoa") or {}
        vinc = cli.get("vinculos")
        vk = sorted(vinc[0].keys()) if isinstance(vinc, list) and vinc and isinstance(vinc[0], dict) else "sem vinculos"
        print(f"  [/v1/cliente/{{cc}}] status={st} pessoa.fotoUrl_presente={bool(pes.get('fotoUrl'))} vinculos_item_keys={vk}")
st, body, _ = raw("/psec/colaboradores/bi-professores-vinculos")
profs = unwrap(as_json(body) or {})
if isinstance(profs, list) and profs and isinstance(profs[0], dict):
    p = profs[0].get("professor") or {}
    print(f"  [bi-professores-vinculos] itens={len(profs)} professor.keys={sorted(p.keys())} imageUri_presente={bool(p.get('imageUri'))}")

print("=== fim (nenhuma credencial impressa) ===")
