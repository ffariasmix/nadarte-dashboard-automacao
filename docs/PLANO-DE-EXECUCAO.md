# Plano de Execução — Inteligência de Retenção Nad'Arte

> **Painel executivo (tabela viva).** Atualizado a cada entrega.
> Última leva: **overhaul de UX (U1–U8)** + **auditoria da aba Perdas (14 pontos)** — deploys #93–#97.

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

---

## 🔜 A fazer (ordenado por prioridade)

| # | Ação | Impacto no dashboard / operação | Independente? | Avanço |
|---|---|---|---|---|
| 6 | **Visão Executiva + ficha 360 do aluno** | **Uma tela de decisão** + histórico completo do aluno num lugar | 🟢 Sim | ⏳ |
| 7 | **Propensão à renovação** | Separar **"faltou"** de **"não vai renovar"** | 🟡 v1 agora | ⏳ |
| 8 | **Curva de sobrevivência** | **Quando** o risco de perda é maior (agir antes) | 🟡 Robustece com dados | ⏳ |
| 9 | **Ticket real por aluno** | Valor em risco **real** (hoje é média da unidade) | 🟡 Sondar API antes | ⏳ |
| 10 | **Recalibração automática** | O modelo **se ajusta sozinho** com os resultados | 🔴 Precisa dados acumulados | ⏳ |
| 11 | **Análise de causa** | **Por que** os alunos saem (por unidade/modalidade) | 🔴 Precisa execuções acumuladas | ⏳ |
| 12 | **Next Best Action + testes A/B** | **Recomendar e testar** a melhor abordagem por perfil | 🔴 Precisa histórico | ⏳ |
| 13 | **Integração Financeiro** | Score enxerga **inadimplência/cobrança** | 🔴 API não existe hoje | ⏳ |
| 14 | **Integração App Treino** | Score enxerga **treino/avaliação/evolução** | 🔴 API não existe hoje | ⏳ |
| 15 | **Integração CRM/WhatsApp/NPS** | Score enxerga **relacionamento e satisfação** | 🔴 Integração externa | ⏳ |
| 16 | **Fotos aluno/professor** | Foto no painel (mais humano) | 🔴 Ação sua (Cloudflare + flag) | ⏳ |
| 17 | **Hipóteses de IA (mercado)** | Contexto de mercado automático | 🔴 Ação sua (secret) | ⏳ |

---

## 🟢 Dá pra adiantar já (sem esperar o #83)

**Sequência sugerida:** #5 Fix Novo/Retorno (rápido) → #3 Backtest mensal → #4 Cohorts → #1 Tela de Efetividade → #2/#6.
Tudo isso eu construo e valido agora; só o **read-back (#2)** e a **efetividade real** confirmam no seu run do D1.

**Como leio esta tabela pra você:** a cada entrega, movo a linha pra "Concluído", atualizo a versão no ar e reordeno o "a fazer". Você sempre vê **o próximo passo e o quanto já andamos**.
