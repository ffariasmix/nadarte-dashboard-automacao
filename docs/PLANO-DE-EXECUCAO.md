# Plano de Execução — Inteligência de Retenção Nad'Arte

> **Painel executivo (tabela viva).** Atualizado a cada entrega.
> Última leva: **mês parcial** (fim do falso saldo) + **régua ×12 honesta** (comprometido em contrato) + **entradas em 2 vias** (Nova × Recorrente, KPI e gráfico) + **Natal (RN)** pronta/desligada — deploys #104–#109. Renovação↔retorno **parkeado** (API não expõe histórico de contratos).

**Independente?** = dá pra avançar **agora**, sem esperar o run atual (#83) nem terceiros:
🟢 Sim · 🟡 Construo agora, confirmo num run · 🔴 Bloqueado (dado/integração/ação sua)

---

## ✅ Concluído

| Ação | Impacto no dashboard / operação | Avanço |
|---|---|---|
| Corrigir o mês em curso | Números de julho **confiáveis pra decidir dentro do mês** | ✅ no ar |
| Recência + semana + vencimento | Base pra **agir cedo** (dias sem vir, contrato vencendo) | ✅ no ar |
| Score + fila priorizada | **Quem contatar primeiro, e por quê** | ✅ no ar |
| Score único (painel = Agenda) | Mesmo número no painel e na Agenda, com **prioridade + SLA** | ✅ no ar |
| Calibração por capacidade | Fila do **tamanho que a equipe liga** (~40/unidade) | ✅ no ar (confirmado: P0=5%/unid, 195 na rede) |
| Histórico de score | Começa a **guardar dado pra medir o acerto do modelo** | ✅ no ar (acumulando) |
| Bimestre no seletor | Olhar o desempenho **por bimestre** | ✅ pronto p/ deploy |
| Novo vs Retorno perpétuo (ledger persistente) | Aquisição × reconquista **precisa de verdade** (histórico entre runs) | ✅ pronto p/ deploy |
| Backtest mensal | **Prova** se o sinal (parada/queda) antecipa o churn — precisão/recall/antecedência | ✅ pronto p/ deploy |
| Cohorts por tempo de casa | **Onde o risco se concentra** por fase (novo × veterano) → direciona abordagem | ✅ pronto p/ deploy |
| Tela de Efetividade (Camada 5) | **Recuperação + receita preservada** dos contatos — ciclo fechado | ✅ pronto (enche com o dado real) |
| Read-back das execuções (Agenda→dashboard) | Traz o **resultado do contato** de volta pro modelo (efetividade + backtest) | ✅ pronto (valida no run com D1) |
| Ficha 360 do aluno (sinais-chave) | Recência + vencimento + coorte no drawer — **histórico do aluno num lugar** | ✅ pronto p/ deploy |
| Propensão à renovação (v1) | Separa **"faltou"** de **"não vai renovar"** (contratos vencendo × desengajados) | ✅ pronto p/ deploy |
| Curva de sobrevivência | Retenção por coorte de entrada — **estende sozinha** a cada mês | ✅ pronto p/ deploy |
| Visão Executiva consolidada | **Uma tela de decisão do gestor** — KPIs da Rede + comparação entre unidades | ✅ pronto p/ deploy (fecha as 5 camadas de UX) |
| Ticket real por aluno | Probe rodado (v3): a API **não expõe** valor/mensalidade (contrato só tem código+descrição). **Parkeado** — mantido o ticket médio da unidade (proxy). Religa em 1 linha se surgir o endpoint. | ⏸️ bloqueado pela API |
| **Overhaul de UX (U1–U8)** | Nav responsiva, alertas recolhíveis, títulos fortes padronizados (Big Numbers/Visão gráfica/Resumo Executivo/abas), grupo "Análise em risco", Critérios só admin/dev | ✅ no ar (#93–#95) |
| **Auditoria da aba Perdas (14 pontos)** | 8200% corrigido, escopo/dedup dos alertas, sobrevivência sem Janeiro, "Perfil de quem sai" sempre populado, Lago Norte parcial no ranking/financeiro, checkpoints +1/+3/+6 explicados | ✅ no ar (#96–#97) |
| **Lago Norte — churn completo** | Água/Luta "cego de catraca" entram no **churn por contrato** (saem só da frequência). Era 0% por bug; agora ~5%/mês. Diagnóstico via SITPROBE + lago_debug (confirmado Fev→Jul 5,5/6,0/5,9/4,2/5,0%) | ✅ no ar (#99–#101) |
| **Fix "Perfil de quem sai"** | Categoria/faixa/sexo de quem sai vinham vazios (profile buscava atributo no mês errado por causa da carência) → attrs_flat | ✅ no ar (#103) |

---

## ✅ Concluído nesta leva (deploys #104–#115)

| Ação | Entrega | Status |
|---|---|---|
| **Movimentação — mês parcial** | Entradas reais do mês em curso (filtro cirúrgico por início de contrato) + barra parcial clareada. Matou o falso saldo (Jun→Jul −230 → −9) | ✅ no ar |
| **Prazo de contrato + fim do ×12** | Deriva plano (mensal/bi/tri/sem/anual) por `ini`/`fim`; receita em risco vira **"comprometido em contrato"** (ticket × prazo), líder = /mês | ✅ no ar |
| **Entradas em 2 vias** | 🆕 Nova matrícula × ↩ Recorrente (KPI **e** gráfico empilhado). Honesto | ✅ no ar |
| **Tempo de permanência (item 6)** | Tenure de quem saiu (faixas + tempo médio até sair) + tempo médio de casa da base ativa | ✅ no ar (#112) |
| **Perdas por motivo de saída (item 5)** | Painel novo com `situacaoContrato` real do cadastro (Desistência 69%, Cancelamento…) — sem endpoint extra. Substitui o "Outros" travado | ✅ no ar (#114) |
| **Legendas financeiras respeitam prazo (item 3)** | "Projeção × 12" → **"Comprometido em contrato"** (ticket × prazo real do plano dos que entram/saem); nota de rodapé atualizada | ✅ no ar (#115) |
| **Natal (RN) — Opção A** | Código pronto e **desligado por flag**. Churn desde mar/26, frequência gated (cego de catraca) até `PACTO_NATAL_FREQ`. Liga em ago/26 | 🟡 pronto (você liga em ago) |

### ⏸️ Itens 1, 2, 4 — Nova × Renovação × Retomada (bloqueado na Pacto)
Separar renovação (retenção) de retomada (reconquista) exige o endpoint `/movimentacao-contrato`, que precisa do **código numérico de empresa**. Probe #59 confirmou: `/v1/empresa/resumo` retorna **500** (a chave não tem o escopo `adm:cadastros:outros-cadastros:empresa:consultar`). **Código pronto esperando o ID.** Destrava só via **ticket à Pacto** pedindo o escopo. Sem isso, entradas seguem em 🆕 Nova × ↩ Recorrente (honesto).

---

## 🔜 A fazer (ordenado por prioridade)

| # | Ação | Entrega | Independente? | Depende de |
|---|---|---|---|---|
| 4 | **App Treino → diagnóstico de churn** | (a) perfil de uso do app de quem sai → (b) diagnóstico → (c) **alimenta o risco**, só após **validar no backtest** | 🔴 | massa: churn × uso do app acumulados |
| 5 | **Análise de causa** | **Por que** saem (por unidade/modalidade) | 🔴 | ~1 mês de execuções acumuladas |
| 6 | **Recalibração automática** | Modelo se reajusta com os desfechos | 🔴 | histórico de score+resultado (já acumulando) |
| 7 | **Next Best Action + A/B** | Recomendar e testar abordagem por perfil | 🔴 | histórico do #4/#5 |
| — | **Renovação × Retorno** (dentro de "recorrente") | Separar renovação (retenção) de retorno (reconquista) | ⏸️ | **parkeado — API não expõe histórico de contratos** (probe #54: 1 contrato, só codigo+descricao). Só via ledger de presença acumulado (set/out) |
| — | **Ticket real/aluno · Financeiro · CRM/WhatsApp/NPS** | Integrações que dão mais sinal ao score | 🔴 | API não expõe / não existe |
| — | **Fotos aluno/professor · Hipóteses de IA** | — | ⏸️ | parkeado (decisão sua) |

---

## 🟢 Sequência de execução

Próximo com valor: **#5 Análise de causa** e **#6 Recalibração** — destravam com ~1 mês de execuções acumuladas.

**Como leio esta tabela pra você:** a cada entrega, movo a linha pra "Concluído", atualizo a última leva e reordeno o "a fazer". Você sempre vê **o próximo passo e o quanto já andamos**.
