# Spike de Integração — API Pacto, Painel de Metas e Catraca/App Treino

**Objetivo:** validar de fato os endpoints e definir como cada automação autentica.
**Contexto:** este repositório (`nadarte-dashboard-automacao`) já roda o **Dashboard de Frequência & Retenção** 100% via API Pacto (o Drive foi desligado), publicado no Cloudflare Pages pelo GitHub Actions. Este doc reaproveita o que já funciona e orienta o que falta validar.

---

## 0. Regra de ouro sobre credenciais

Ninguém cola a chave em chat, e-mail ou commit. As chaves vivem **só** em dois lugares:

1. **GitHub Secrets** do repositório (para o pipeline em produção) — já é assim hoje (`PACTO_KEY_716NORTE`, `PACTO_KEY_905SUL`, etc.).
2. **Variável de ambiente local** (para rodar o script de sondagem na sua máquina) — a chave nunca entra no código nem no relatório.

Quem roda o spike executa o script abaixo, e devolve **só o relatório** (status HTTP, formato das respostas, campos encontrados) — sem a chave.

---

## 1. Como a API Pacto funciona (o que já sabemos)

| Item | Valor |
|---|---|
| Gateway | `https://apigw.pactosolucoes.com.br` |
| Autenticação | Header `Authorization: Bearer {ApiKey}` |
| Granularidade da chave | **1 chave por unidade** (cada academia tem a sua) |
| Datas | epoch em **milissegundos** |
| Envelope de resposta | sucesso → `{ "content": ... }` · erro → `{ "meta": { "error": true, "message": "..." } }` |

### Endpoints já validados em produção

| Endpoint | Para quê | Observações |
|---|---|---|
| `GET /clientes/simples?page=0&size=200` | Roster de alunos (cadastro, situação ATIVO/INATIVO) | Paginação instável — iterar com cuidado |
| `GET /clientes/{matricula}/dados-pessoais` | Obter `codPessoa` a partir da matrícula | Ponte para os acessos |
| `GET /acessos-cliente/by-pessoa/{codPessoa}?page=0&size=200` | **Catraca / acessos** do aluno | O acesso carrega `cliente.codigo` e `cliente.matricula` — permite atribuir corretamente por aluno (resolve irmãos em CPF compartilhado) |
| `GET /v1/plano` | Planos e `empresa.codigo` (empresaId) | Não expõe preço |
| `GET /v1/bi/resumo?mesInicial={ms}&mesFinal={ms}` | **Faturamento** por mês (`totalFaturamento`) | Precisa do header `empresaId` (vem do `/v1/plano`). Base do ticket médio dinâmico |

### Endpoints que NÃO serviram (documentar para não repetir)

- `GET /v1/contrato` → **500** (não expõe valor do contrato)
- `GET /v1/bi/contas-receber` → "Dados não encontrados"
- `acesso.matricula` (nível topo) → vem **em branco**; usar `cliente.codigo` do acesso

> Conclusão prática já adotada: como a API não expõe valor por contrato, o **ticket médio** é calculado como `totalFaturamento (mês com folga) ÷ alunos ativos` da unidade.

---

## 2. Script de sondagem (spike) — lê a chave de variável de ambiente

Salvar como `scripts/spike_probe.py`. Ele **não imprime a chave**; imprime só o diagnóstico de cada endpoint.

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spike_probe.py — valida endpoints da Pacto sem expor a chave.
Uso:
  export PACTO_KEY_716NORTE="...."          # a chave fica só no ambiente
  python scripts/spike_probe.py 716NORTE
Devolve um relatório com status HTTP, formato do envelope e campos-chave.
"""
import os, sys, json, time, urllib.request, urllib.error

GATEWAY = "https://apigw.pactosolucoes.com.br"
unit = (sys.argv[1] if len(sys.argv) > 1 else "716NORTE").upper()
KEY = os.environ.get(f"PACTO_KEY_{unit}", "").strip()
if not KEY:
    print(f"[erro] variavel PACTO_KEY_{unit} nao definida no ambiente."); sys.exit(1)

def call(path, headers=None):
    url = GATEWAY + path
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {KEY}", **(headers or {})})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            body = r.read().decode("utf-8", "replace")
            ok, code = True, r.status
    except urllib.error.HTTPError as e:
        body, ok, code = e.read().decode("utf-8", "replace"), False, e.code
    except Exception as e:
        return {"path": path, "status": "EXC", "erro": str(e)[:120]}
    dt = round((time.time() - t0) * 1000)
    # diagnostico sem vazar dados sensiveis: so o formato
    try:
        j = json.loads(body)
        if isinstance(j, dict) and "content" in j:
            c = j["content"]; shape = f"content: {type(c).__name__}"
            if isinstance(c, list): shape += f" (len={len(c)})"
            elif isinstance(c, dict): shape += f" keys={sorted(list(c.keys()))[:12]}"
        elif isinstance(j, dict) and "meta" in j:
            shape = f"meta.error={j['meta'].get('error')} msg={j['meta'].get('message')}"
        elif isinstance(j, list):
            shape = f"list (len={len(j)})"
        else:
            shape = f"{type(j).__name__} keys={sorted(list(j.keys()))[:12] if isinstance(j,dict) else ''}"
    except Exception:
        shape = f"nao-JSON ({len(body)} bytes) inicio={body[:60]!r}"
    return {"path": path, "status": code, "ms": dt, "formato": shape}

# monta datas em epoch-ms (mes retrasado, com folga de fechamento)
import datetime as _dt
now = _dt.date.today().replace(day=1)
mes_ini = (now - _dt.timedelta(days=60)).replace(day=1)
to_ms = lambda d: int(_dt.datetime(d.year, d.month, d.day).timestamp() * 1000)

PROBES = [
    ("/clientes/simples?page=0&size=5", None),
    ("/v1/plano", None),
    (f"/v1/bi/resumo?mesInicial={to_ms(mes_ini)}&mesFinal={to_ms(now)}", {"empresaId": "DESCOBRIR_VIA_/v1/plano"}),
    ("/v1/bi/velocimetro", None),
    ("/v1/contrato", None),
    ("/v1/bi/contas-receber", None),
]

print(f"=== SPIKE Pacto — unidade {unit} ===")
for path, hdr in PROBES:
    print(json.dumps(call(path, hdr), ensure_ascii=False))
print("=== fim (nenhuma credencial impressa) ===")
```

**Como o Claude Cowork usa isto:** ele te pede para exportar a variável e rodar o comando; você cola de volta **só a saída** (as linhas JSON de diagnóstico). Alternativa sem script: usar o **Sandbox da documentação Pacto** e colar as respostas (removendo qualquer dado pessoal).

> Já existem no repo `scripts/pacto_fetch.py`, `pacto_faturamento.py` e `pacto_probe_contrato.py` com os helpers (`gj`, `lst`, `gv`, `unwrap`) — o spike pode reaproveitá-los em vez de reescrever HTTP.

---

## 3. Painel de Metas atrás do Cloudflare Access (`/api/data`)

O painel de faturamento/metas (`nadarte-metas-faturamento.pages.dev`) está protegido por **Cloudflare Access**. Um job de automação **não** consegue passar por login humano/SSO. O caminho correto:

### Opção recomendada — Cloudflare Access **Service Token**

1. No Cloudflare Zero Trust → **Access → Service Auth → Create Service Token**. Gera um par:
   `CF-Access-Client-Id` e `CF-Access-Client-Secret`.
2. Na **Application** que protege o painel, criar uma **policy do tipo *Service Auth*** que inclua esse token (senão o token não é aceito).
3. Guardar o par como **GitHub Secrets** (`CF_ACCESS_CLIENT_ID`, `CF_ACCESS_CLIENT_SECRET`).
4. O job chama `/api/data` mandando os dois headers:

```bash
curl -s https://nadarte-metas-faturamento.pages.dev/api/data \
  -H "CF-Access-Client-Id: $CF_ACCESS_CLIENT_ID" \
  -H "CF-Access-Client-Secret: $CF_ACCESS_CLIENT_SECRET"
```

**Decisões que você precisa tomar aqui:**
- (a) `/api/data` devolve a meta já calculada? Qual o formato (JSON com `{unidade, meta, realizado}`?) → validar com o service token.
- (b) Se o painel de metas e o de frequência forem alimentados pela **mesma fonte** (API Pacto), talvez nem precise ler `/api/data` — dá para calcular a meta direto da Pacto e eliminar a dependência do Cloudflare Access. Vale comparar as duas fontes no spike.

> Segurança: quem cria o Service Token é você (ação de admin no Cloudflare). Eu não crio credenciais nem mexo em permissões — só te digo onde clicar e como o job consome.

---

## 4. Catraca e App Treino — via Pacto ou API própria?

### Catraca → **já está via Pacto** ✅

O dashboard de Frequência usa `GET /acessos-cliente/by-pessoa/{codPessoa}` para os acessos de catraca. Funciona e atribui corretamente por aluno. **Recomendação: manter na Pacto**, sem API separada.

### App Treino → **decidir no spike**

Perguntas que definem o caminho:

| Pergunta | Se SIM → | Se NÃO → |
|---|---|---|
| A Pacto expõe os dados de treino (fichas/execuções) num endpoint acessível com a mesma chave? | Usar Pacto (uma credencial só, mesmo pipeline) | Ir para API própria do App Treino |
| Os dados de treino que você quer no dashboard existem na Pacto com granularidade suficiente? | Pacto | API própria |

**Se for API própria**, preciso de você:
- URL base + documentação (ou coleção Postman);
- Modelo de autenticação (API key? OAuth? token por unidade?);
- Como as credenciais serão guardadas (mesmo padrão: GitHub Secrets);
- Mapa de campos: o que do App Treino entra no dashboard e com que chave casa com o aluno (matrícula? codPessoa?).

**Teste de sondagem sugerido:** no `spike_probe.py`, adicionar 1–2 caminhos candidatos de treino da Pacto (ex.: `/treino/...`, `/v1/treino/...`) e ver se voltam `content` ou `meta.error`. Isso responde "tem na Pacto?" em minutos.

---

## 5. Checklist do spike (o que devolver ao final)

- [ ] Relatório do `spike_probe.py` por unidade (status + formato de cada endpoint) — **sem a chave**.
- [ ] `/v1/bi/resumo` confirmado com o `empresaId` real (tirado do `/v1/plano`).
- [ ] Decisão: meta lida via `/api/data` (com Service Token) **ou** calculada direto da Pacto.
- [ ] Service Token do Cloudflare criado e testado (2 headers) — se optar por `/api/data`.
- [ ] Decisão catraca: **manter Pacto** (confirmado).
- [ ] Decisão App Treino: Pacto **ou** API própria (+ docs/credenciais se própria).
- [ ] Lista de novos GitHub Secrets necessários (`CF_ACCESS_CLIENT_ID`, `CF_ACCESS_CLIENT_SECRET`, chaves do App Treino se aplicável).

---

## 6. Divisão de responsabilidades

| Ação | Quem faz |
|---|---|
| Criar/rotacionar chaves Pacto, Service Token Cloudflare, cadastrar GitHub Secrets | **Você (admin)** — envolve credenciais/permissões |
| Rodar `spike_probe.py` localmente com a chave em variável de ambiente | **Você** (ou eu te guio passo a passo) |
| Ler o relatório, mapear campos, escrever o coletor, ligar no pipeline | **Claude Cowork** |
| Revisar formato das respostas e decidir fonte da meta | **Você + Claude** |

> Eu (Claude) não manuseio, peço em texto, nem armazeno credenciais. Sempre que a etapa exigir uma chave, o desenho acima mantém o segredo só no seu ambiente / nos Secrets.
