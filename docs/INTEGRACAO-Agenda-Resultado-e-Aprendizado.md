# Onda 2b — Resultado de volta & aprendizado (contrato de integração)

> Fecha o ciclo: **alerta → contato → resultado → aprendizado**. Este doc define o **contrato** entre o pipeline do dashboard (`ffariasmix/nadarte-dashboard-automacao`) e o **app da Agenda Tática** (`nadarte-agenda…workers.dev`, repo separado + D1), para implementação rápida quando o repo da Agenda for conectado.

## 1. Fluxo completo

```
build (score fonte única)
  → sync_agenda.mjs grava iniciativas no D1 (com id, matricula, semana_ref, score, prioridade, SLA)
    → app da Agenda: consultora vê a fila, contata, e REGISTRA o resultado
      → D1 guarda resultado + data_contato
        → export/endpoint expõe os resultados (read-only, sem PII sensível)
          → pipeline lê de volta e casa por (matricula, semana_ref)
            → mede efetividade (recuperação/renovação/receita preservada)
            → rotula o backtest (quem foi alertado e voltou/renovou vs perdeu)
              → calibra pesos/cortes do score (Onda 3)
```

## 2. Schema — o que o app da Agenda precisa registrar (D1)

A tabela `iniciativas` já existe (id, unidade_id, categoria_id, titulo, descricao, tipo, prioridade, aluno_nome, matricula, semana_ref, prazo, origem, status, venc, valor_mensal, foto). **Acrescentar** (migração no repo da Agenda):

```sql
ALTER TABLE iniciativas ADD COLUMN resultado       TEXT;    -- enum abaixo
ALTER TABLE iniciativas ADD COLUMN data_contato     TEXT;    -- ISO date do 1º contato
ALTER TABLE iniciativas ADD COLUMN resultado_obs    TEXT;    -- observação livre (motivo/relato)
ALTER TABLE iniciativas ADD COLUMN responsavel      TEXT;    -- quem atuou (consultora/gerente)
ALTER TABLE iniciativas ADD COLUMN data_resultado   TEXT;    -- ISO date do desfecho
ALTER TABLE iniciativas ADD COLUMN score_no_alerta  INTEGER; -- score no momento do alerta (rótulo p/ backtest)
```

`status` (já existe) evolui: `pendente → em_contato → concluida` (ou `expirada`).

### Enum `resultado`

| valor | significado | conta como |
|---|---|---|
| `voltou` | retomou frequência após o contato | recuperação ✅ |
| `renovou` | renovou/antecipou contrato | retenção ✅ |
| `sem_resposta` | não atendeu / não retornou | neutro |
| `recusou` | contatado, sem intenção de voltar | perda provável |
| `perdeu` | cancelou / não renovou | churn confirmado ❌ |
| `justificado` | férias/atestado/viagem — não era risco | excluir do score |
| `contato_feito` | falou, desfecho ainda aberto | em acompanhamento |

## 3. O que o pipeline precisa ler de volta

Um **feed read-only** exposto pela Agenda (endpoint autenticado **ou** export para um JSON no repo da Agenda), **sem PII sensível** — matrícula hasheada (mesmo hash do `presenca.json`) + campos de resultado:

```json
{
  "gerado_em": "2026-07-20T10:00:00Z",
  "resultados": [
    { "mat_hash": "…", "semana_ref": "2026-W29", "status": "concluida",
      "resultado": "voltou", "data_contato": "2026-07-15",
      "data_resultado": "2026-07-19", "responsavel": "consultora-716",
      "score_no_alerta": 78 }
  ]
}
```

Chave de junção: **`mat_hash` + `semana_ref`** (idempotente; casa com a iniciativa gerada).

## 4. O que o dashboard passa a mostrar (tela de Efetividade)

Camada 5 do redesenho (nova aba ou seção), alimentada pelo feed:

- **Contatos feitos / concluídos** (taxa de execução da fila).
- **Recuperação (voltou)** e **Renovação (renovou)** pós-ação — nº e %.
- **Receita preservada** = Σ ticket dos que voltaram/renovaram após alerta.
- **Tempo médio de atuação** (alerta → contato) e **backlog vencido** (SLA estourado).
- **Efetividade por perfil** (unidade, motivo, faixa de score) → quais playbooks funcionam.

## 5. Como isso calibra o score (Onda 3)

Com `resultado` + `score_no_alerta` acumulados:

- **Rótulo de churn:** `perdeu`/`recusou` = positivo real; `voltou`/`renovou` = recuperado.
- **Precisão / recall / lead-time:** o score alto **antecipou** o churn? Com quanta antecedência?
- **Ajuste:** sobe o peso dos fatores que mais separam quem perdeu de quem ficou; recalibra os cortes de P0.
- **Falsos positivos** (score alto que `justificado`/`voltou sem ação`) → criar/afinar atenuações.

## 6. Dependências / ações

| # | Ação | Onde | Responsável |
|---|---|---|---|
| 1 | Conectar o repo do app da Agenda ao ambiente | — | **você** |
| 2 | Migração `ALTER TABLE` (colunas de resultado) | repo Agenda | dev Agenda |
| 3 | UI: consultora registra `resultado`/`data_contato` | repo Agenda | dev Agenda |
| 4 | Endpoint/export do feed read-only (mat hasheada) | repo Agenda | dev Agenda |
| 5 | Pipeline lê o feed + tela de Efetividade | este repo | **eu** |
| 6 | Backtest rotulado + recalibração | este repo | **eu** |

> Enquanto (1)–(4) não existem, os itens (5)–(6) ficam prontos "para plugar": assim que o feed existir no formato acima, ligo em uma passada.
