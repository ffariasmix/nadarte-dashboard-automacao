# Roadmap — Dashboard Nad'Arte (Frequência & Retenção)

> Consolidação das correções e evoluções acordadas. Escopo atual: **2026-only** (janela enxuta, fácil de reconciliar).
> Atualizado: jul/2026.

---

## Como o dado atualiza (snapshot diário D-1) — não é tempo real

O dashboard é um **HTML estático** (snapshot), não uma tela conectada à API ao vivo. Quem roda ao vivo é o **pipeline**: às **04:00 BRT, todo dia**, o GitHub Actions conecta na API da Pacto, puxa os dados reais e **republica** o dashboard. Ao abrir o link, o usuário vê os números do **último run** (não consulta a API na hora, e não muda ao longo do dia).

- Inclui o **mês corrente parcial**, com dados até **D-1** (ontem).
- Leitura correta: *"atualizado diariamente, sozinho, com dado de D-1"* — não *"streaming ao vivo"*.
- Frequência/retenção mudam devagar → diário é o ponto ótimo (economiza chamadas de API + minutos). Dá pra adicionar mais horários no cron se necessário.

---

## Princípios (o que orienta as decisões)

- **Snapshot, não tempo real.** O dashboard é HTML estático regerado pelo pipeline (GitHub Actions) — não há backend consultando a Pacto ao vivo. "Vivo o suficiente" = run diário + mês corrente com D-1.
- **Fidelidade > sofisticação.** Melhor um número que bate 100% com a operação do que um indicador complexo difícil de confiar.
- **Passado = realizado; corrente = em curso.** Período fechado mostra o que foi; mês corrente é parcial e marcado.
- **Risco = acionável.** "Em risco" só quem dá pra reconquistar (contrato ativo que parou); quem já cancelou é perda realizada.

---

## ✅ Concluído e NO AR (v9.4 — jul/2026)

| Item | O que faz |
|---|---|
| **Carência de 2 meses no churn** | "Perda" só conta após 2 meses de inatividade real (lapso de 1 mês perdoado). Reduz churn técnico. Mantém consistência base+novos−perdas. |
| **Contrato ativo no risco** | "Receita em risco" e KPIs de Risco Alto/Médio contam **só contrato ativo que parou** (quem já cancelou vira perda realizada, não risco). |
| **Métrica "Estamos evoluindo?"** | "% da base que bateu a meta (≥90%)", MoM em pontos percentuais — mostra nº de alunos (ex.: 687 de 4.469). |
| **Card MoM com rótulo de mês** | "Jun.26: 687 · Mai.26: 864 alunos" — cada número identificado, sem ambiguidade. |
| **Novo vs Retorno (aba Perdas)** | Split das entradas: 🆕 novo (1ª vez na rede, via ledger) × ↩ retorno (já existiu antes). Reconcilia com o total. |
| **Mês corrente parcial (D-1)** | Mês em curso incluído, marcado "em curso / parcial (até DD/MM)". Fetch leve: `win` só de meses fechados (não incha a base) → sem timeout. |
| **Datas em formato BR** | "Dados Ref." e afins em DD/MM/AAAA (ex.: 12/07/2026). |
| **Run diário automático** | Cron 04:00 BRT, nos servidores do GitHub. Zero envolvimento, sem computador ligado. |
| **Comparativos por granularidade** | Mês→MoM, Trim→QoQ, Semestre→SoS, Ano→YoY. |
| **Score anual, passado realizado, base com crescimento, limpeza de UI** | — |

---

## 🧭 Proposto — a decidir / fase seguinte

| Item | Nota do especialista |
|---|---|
| **Bimestre no seletor** | Granularidade de 2 meses (comparativo bimestre vs bimestre). Fácil de adicionar ao seletor. Recomendado. |
| **Faturamento real por aluno** | Hoje o ticket é médio da unidade (Faturamento ÷ nº alunos). Ticket real por aluno depende de endpoint/escopo de contrato da Pacto — sondar antes. |
| **Fotos (aluno + professor)** | Prontas no código, desligadas. Exigem Cloudflare Access (PII) + escopo. Reativar quando quiser. |
| **Hipóteses de IA (contexto de mercado)** | Depende do secret `ANTHROPIC_API_KEY`. Painel foi removido por ora; volta quando o secret existir. |
| **Frequência do cron** | Diário é o ponto ótimo. Só aumentar se houver necessidade real (custo de minutos + rate-limit). |

---

## Como cada número é calculado (referência rápida)

- **Novos/Entradas:** hoje = quem entrou na **base ativa** no mês (ativos_b − ativos_a). *Vai passar a separar Novo × Retorno.*
- **Perdas:** saiu da base ativa. *Com carência: só após 2 meses de inatividade.*
- **Saldo líquido /mês (R$):** (novos − perdas) × **ticket médio da unidade** = variação da **receita mensal recorrente**. Ex.: +533 alunos líquidos × ticket ≈ +R$165k/mês.
- **Projeção /ano (R$):** saldo/mês × 12 = impacto anualizado **se o quadro se mantiver** (não é previsão).
- **Receita em risco:** nº de Alto+Médio **com contrato ativo** × ticket = exposição recorrente do público acionável.
- **Score da unidade:** 35% frequência + 25% engajados + 10% (1−risco alto) + 30% retenção. Anual (meses fechados do ano).

---

## Dependências / decisões suas

- **Novo vs Retorno:** confirmado — implementar (via matrícula + ledger).
- **Mês corrente D-1:** confirmado — implementar.
- **Bimestre:** a confirmar (recomendo sim).
- **Secret `ANTHROPIC_API_KEY`** (se quiser as hipóteses de IA de volta): ação sua.
- **Cloudflare Access + `PACTO_FOTOS=1`** (se quiser fotos): ação sua.

---

*Ordem sugerida: fechar o "próximo pacote" (itens 1–3) num deploy único, validar com você, depois Bimestre e o resto.*
