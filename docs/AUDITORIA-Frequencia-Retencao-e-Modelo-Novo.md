# Auditoria & Evolução — Frequência & Retenção Nad'Arte

> **Sistema de Inteligência de Retenção** — auditoria crítica do dashboard atual + modelo novo.
> **Data de corte da análise:** 12/07/2026 (julho parcial, ~11–12 dias operacionais decorridos).
> **Método:** auditoria do **código-fonte real** do pipeline (`template/template.html`, `scripts/build_freq_multi.py`, `scripts/pacto_fetch.py`, `scripts/sync_agenda.mjs`) — a fonte da verdade, mais precisa que inspeção visual do site (que está atrás de Cloudflare Access e é client-rendered). Nada aqui foi inventado: cada falha aponta a linha/função de origem.
> **Repositório:** `ffariasmix/nadarte-dashboard-automacao` · **Versão auditada:** v9.4.

---

## 1. Resumo executivo

O dashboard hoje é um **bom painel analítico de frequência**, mas **ainda não é um sistema de inteligência de retenção**. Ele descreve o passado bem; falha em três eixos que definem "inteligência de retenção":

1. **Cálculo do mês corrente está tecnicamente quebrado.** A lógica de mês parcial foi feita com **índices fixos** (`m<5`, `i===5`, arrays de 6 posições) e um **cutoff estático de 16 dias** — nunca derivado da data real. Com julho já publicado (7 meses na série), isso produz agora: **junho (mês fechado) prorrateado a 16 dias** → % de meta de junho **inflada**; **julho (parcial, ~12 dias) prorrateado a 16 dias** → % de julho **subestimada**; e o **gráfico de evolução não plota julho**. É exatamente o erro que o mês parcial deveria evitar — comparar/normalizar errado. *(evidência: `computeDias` L513, `evolChart` L578–585, `state.cutoff:16` L507).* **Severidade: Crítica.**

2. **Não há recência nem visão semanal — só contagem mensal.** O modelo de dados guarda **acessos por mês** (`ac[m]` = contagem), não **acessos datados**. Logo, "dias desde a última visita", "semana comparável", "velocidade de queda" — o coração da leitura decisória de mês aberto — **não são calculáveis hoje**, embora os dados datados **sejam baixados** e depois descartados no build. *(evidência: `ac` em `build_freq_multi.py` L324; datas em `fetch_client_full` L305–317 agregadas e perdidas).* **Severidade: Alta.**

3. **Risco não é explicável, priorizado por valor, nem fecha o ciclo da ação.** O "risco" (Alto/Médio/Baixo) sai da clusterização por contagem mensal, sem score numérico auditável, sem confiança, e a priorização = risco (não risco × valor × urgência × recuperabilidade). A ponte para a Agenda Tática **já existe** (`sync_agenda.mjs` → Cloudflare D1) mas envia listas fixas por tipo, **sem score, sem confiança, sem SLA, sem resultado de volta** (não há aprendizado). **Severidade: Alta.**

**A boa notícia:** a fundação é sólida e rara — pipeline diário automático, ledger perpétuo (Novo × Retorno já correto), churn com carência, risco só de contrato ativo, e **integração viva com a Agenda Tática**. Não é preciso reconstruir; é preciso **corrigir o mês aberto (Onda 0)**, **enriquecer o modelo de dados com recência/semana (Onda 1)** e **fechar o ciclo ação→resultado→aprendizado (Ondas 2–3)**.

**Prioridade imediata (P0):** corrigir a normalização do mês corrente. Enquanto isso não é feito, os números de julho e junho na aba Visão Geral/Meta **não são confiáveis para decisão**.

---

## 2. Diagnóstico do dashboard atual

### 2.1 O que existe (8 abas)

| Aba | Pergunta que responde | Veredito |
|---|---|---|
| **Visão Geral** | Como está a base? Estamos evoluindo? | Manter + **corrigir mês aberto** |
| **Comportamento** | Como se distribuem os perfis (Fiel, Regular, Evasão…)? | Manter |
| **Modalidades** | Frequência/risco por categoria (7 cats) | Manter |
| **Risco & Evasão** | Quem está em risco? | **Evoluir** (score explicável + fila) |
| **Meta Atingida** | Quem bate a meta de frequência? | Manter + corrigir mês aberto |
| **Engajados** | Quem é núcleo fiel? | **Fundir** com Comportamento |
| **Perdas** | Churn, entradas (Novo×Retorno), saldo R$ | Manter (recém-revisada) |
| **Aniversariantes** | Oportunidade de relacionamento | Manter (já alimenta Agenda) |

### 2.2 Modelo de dados real (o que cada aluno carrega)

Do build (`students.append`, L327–333), cada aluno tem:
`u` (unidade), `mat`, `nome`, `grupo` (7 categorias), `mod` (texto do plano), `sexo`, `band` (faixa etária), `dps` (dias/semana de funcionamento da unidade), `bm/bd/by` (aniversário), **`ac[]` (contagem de acessos por mês)**, **`active[]` (flag de contrato ativo por mês)**, `fs` (índice da 1ª aparição — ledger perpétuo), `fa` (data do 1º acesso), `dm` (dataMatrícula), `foto`, `prof`, `profRole`.

### 2.3 Fluxo do pipeline

`pacto_fetch.py` (coleta API Pacto) → `build_freq_multi.py` (gera `freq_multi.json`) → `sync_agenda.mjs` (grava alertas no D1 da Agenda Tática) → `inject_into_template.py` → `validate_render.js` (jsdom) → publica (Cloudflare Pages). **Snapshot diário 04:00 BRT**, mês corrente com D-1.

---

## 3. Falhas e divergências identificadas (mapa de furos)

| ID | Tela/Componente | Problema | Evidência (código) | Impacto no negócio | Severidade | Correção recomendada |
|---|---|---|---|---|---|---|
| F01 | Núcleo de cálculo (mês parcial) | Cutoff **estático 16 dias**, nunca derivado da data real (D-1). | `state.cutoff:16` (L507, L1265) | % de meta do mês corrente sistematicamente errada. | **Crítica** | Derivar cutoff de `DATA.junMax` (dia real). Ver §4. |
| F02 | `computeDias` | Índice fixo `m<5`: só Jan–Mai contam mês inteiro; **junho (fechado) é prorrateado a 16 dias**. | `const tot=(m<5)?diasNoMes(m):state.cutoff` (L513) | Meta de **junho inflada** (denominador pequeno). Comparação MoM jun×mai distorcida. | **Crítica** | Prorratear **apenas** o mês parcial (índice dinâmico `PIDX`), demais meses inteiros. |
| F03 | `evolChart` | Arrays fixos de **6 posições** e `i===5`: com 7 meses, **julho não é plotado** e junho vira "projetado". | `avgReal=[...,null]`, `avgProj`, `i===5` (L580–585) | Gráfico "Estamos evoluindo?" mostra o mês errado como parcial. | **Crítica** | Reescrever com `PIDX` dinâmico. |
| F04 | `diasNoMes` / `domingos` | Array de **6 meses** `[31,28,31,30,31,30]` e ano **fixo 2026**. Julho→`undefined`; quebra em 2027. | L510–511 | Bug latente ao crescer a série / virar o ano. | Alta | Calcular por `Date`/ano real. |
| F05 | `cumpr` | Cumprimento **capado em 1**: quem vai 6× (meta 3×) = quem vai 3× (ambos "100%"). | `Math.min(1,ac/expected)` (L516) | Perde sinal de super-frequência (protetores de churn). | Média | Guardar cumprimento sem cap para tendência; capar só na exibição de "meta". |
| F06 | `cluster` | Ausência no **mês parcial** vira "Em declínio/Esporádico"; queda de contagem parcial vira tendência negativa. | `inativo===1`→declínio (L531); early×late (L526–527) | **Falso positivo**: aluno normal que ainda não veio nos 12 primeiros dias de julho é marcado risco. | Alta | Não contar o mês parcial como "mês sem acesso"; usar aderência parcial normalizada. |
| F07 | Recência | Não existe "dias desde a última visita" por aluno. | `ac` = contagem mensal (L324); datas descartadas (L316) | Sem o sinal #1 de churn precoce. | Alta | Reter `ultimaVisita` e semana por aluno no build. |
| F08 | Visão semanal | Inexistente. Só granularidade mensal. | — | Não dá para agir dentro do mês. | Alta | Reter acessos por semana ISO (§11). |
| F09 | Projeção | Projeta `avg×30/cutoff` — mês fixo de 30 dias, cutoff errado, sem intervalo/confiança. | `projJun=avg[-1]*(30/cut)` (L579) | Projeção enganosa apresentada quase como fato. | Alta | Projeção por oportunidades restantes + banda + rótulo "projeção". |
| F10 | Vencimento/renovação | `sync_agenda` usa `s.venc`, mas o build **não** propaga `fim` do contrato ao aluno. | `students.append` sem `fim`/`venc` (L327–333); `fim` existe no fetch (L302) | "Dias para renovação" (sinal forte) fica vazio. | Alta | Propagar `fim`/`venc` ao registro do aluno. |
| F11 | Score de risco | Não há número (0–100) nem fatores; risco = rótulo do cluster. | `cluster()` retorna `risco` categórico (L529) | Não é auditável nem priorizável. | Alta | Score explicável aditivo (§15–16). |
| F12 | Confiança | Nenhuma métrica de confiança do diagnóstico. | — | Trata coorte e histórico longo com a mesma certeza. | Alta | Nível de confiança por volume de observação (§8, §16). |
| F13 | Ticket em risco | Ticket é **médio da unidade** (Faturamento÷alunos), rotulado como "por aluno". | `ticketU` (L576); nota já no card | "Valor em risco" impreciso no nível do aluno. | Média | Manter como proxy, rotular claramente; buscar ticket real (§18). |
| F14 | Financeiro/experiência | Inadimplência, NPS, App Treino, CRM/WhatsApp **não existem** na base. | Ausentes em `pacto_fetch` | Score cego a causas não-comportamentais. | Média | Integração futura (§18); **não inventar** enquanto não houver. |
| F15 | Priorização Agenda | Alertas por **caps fixos** (em_risco:40, sumiu:20…), sem risco×valor×urgência×recuperabilidade. | `CAP` (sync L20) | Fila não reflete prioridade real. | Alta | Priorização tática (§24). |
| F16 | Ciclo de aprendizado | Agenda recebe alertas, mas **resultado não volta** ao modelo. | sync unidirecional (INSERT no D1) | Sem backtesting nem calibração. | Alta | Retorno de resultado (§17, §23). |
| F17 | Duplicidade Meta×Engajados | Duas abas com leitura sobreposta (bate meta / é fiel). | Abas `meta` e `eng` | Excesso sem hierarquia de decisão. | Baixa | Fundir. |
| F18 | Mês aberto vs fechado (rótulo × conta) | Rótulos já dizem "Jul.26 em curso" (v9.4), mas a **conta** ainda trata junho como parcial. | `PARTIAL/PIDX` só nos textos; `computeDias` fixo | **Divergência** entre o que o texto diz e o que o número faz. | **Crítica** | Ligar `PIDX` também no núcleo de cálculo (§4). |

---

## 4. Revisão completa do cálculo para mês aberto (correção P0)

### 4.1 O problema, com números (12/07/2026)

Hoje `expected(m,g,dps) = vezMeta[g] × semanas(m)`, e `semanas(m) = diasOperacionais(m)/dps`. Para o mês parcial, `diasOperacionais = state.cutoff = 16` (fixo).

**Aluno Fitness (meta 3×/sem), unidade 7 dias/sem, em 12/07:**

- **Como está hoje (errado):** `semanas(jul) = 16/7 = 2,29` → `esperado = 3 × 2,29 = 6,9 visitas`. Se o aluno foi 3× até 12/07, cumprimento = `3/6,9 = 43%` → parece "abaixo da meta". Mas **só ~11–12 dias operacionais ocorreram**, não 16. O denominador está inflado → aluno **normal parece em queda**.
- **Junho (fechado) hoje (errado):** como `m≥5`, junho também usa 16 → `esperado(jun)=6,9` em vez de `3×(30/7)=12,9`. Um aluno que foi 12× em junho: hoje mostra `min(1, 12/6,9)=100%`; correto seria `12/12,9=93%`. **Junho inflado.**

### 4.2 Princípio correto

> Em mês aberto, **não** compare visitas brutas com mês fechado. Compare o **realizado até a data** com as **oportunidades que já deveriam ter ocorrido** até a data.

### 4.3 Índice de Oportunidades Decorridas (a chave)

```text
IOD = Oportunidades esperadas até D-1 / Oportunidades esperadas no mês completo
```

Com base em dias operacionais reais (não `dia/total`):

```text
diasOperacionaisDecorridos(mês parcial) = dias de funcionamento da unidade entre 1º e D-1,
                                          menos feriados/fechamentos conhecidos
IOD = diasOperacionaisDecorridos / diasOperacionaisNoMêsCompleto
```

**Exemplo 12/07 (unidade 7 dias/sem, sem feriado):** decorridos = 11 (01→11/07), mês = 31 → **IOD = 11/31 = 35,5%**. (Se unidade 6 dias/sem: descontar domingos de ambos.)

### 4.4 Hierarquia de cálculo do "esperado até hoje" (do melhor ao pior dado)

| Nível | Quando | Fórmula | Disponível hoje? |
|---|---|---|---|
| **N1 — Agenda contratada** | Há frequência/dias contratados por aluno | `Esperado = Σ oportunidades da rotina do aluno até D-1` | **Não** (só meta por categoria) |
| **N2 — Baseline individual** | Há histórico do aluno (60–90d) | `FreqSemanalEsperada = mediana das semanas comparáveis; Esperado = FreqSem × semanasOperacionaisDecorridas` | **Parcial** (só contagem mensal; precisa de semana — Onda 1) |
| **N3 — Coorte comparável** | Aluno novo/sem histórico | mediana de pares (unidade, modalidade, plano, tenure, faixa) | Sim (marcar **confiança baixa**) |

**Enquanto N2 semanal não existe:** usar a **meta por categoria × IOD** como esperado parcial (melhor que o cutoff fixo). Ver aderência parcial abaixo.

### 4.5 Aderência parcial (substitui o `cumpr` no mês aberto)

```text
Esperado_até_hoje = metaMensalEsperada(categoria, unidade) × IOD
AderênciaParcial  = Visitas_realizadas_até_hoje / Esperado_até_hoje
```

**Exemplo (Fitness 3×/sem, 7d, 12/07, foi 3×):** `metaMês = 3×(31/7)=13,3`; `Esperado_hoje = 13,3 × 0,355 = 4,7`; `Aderência = 3/4,7 = 64%` → **"dentro do padrão inicial"**, não "43% em queda". A diferença entre 43% (hoje) e 64% (correto) é a distorção que hoje gera falso alerta.

### 4.6 Correções mínimas no código (P0, Onda 0)

1. `state.cutoff` **dinâmico** = dia de `DATA.junMax` (D-1 real), quando `PARTIAL`. Fim do "16".
2. `computeDias`: prorratear **apenas** `PIDX` (mês parcial). Todos os outros meses = mês inteiro real (inclusive junho).
3. `diasNoMes`/`domingos`: calcular por `Date` e **ano real** (fim do array de 6 e do `2026` fixo).
4. `evolChart`: arrays por `MES.length` e `PIDX` (fim do `i===5` e das 6 posições).
5. Introduzir **IOD** e **AderênciaParcial**; no mês parcial, `metaInfo` usa aderência parcial, não `cumpr` bruto.
6. **Rotular sempre**: "realizado até D-1", "esperado até D-1", "IOD %", "projeção (não é fato)".

### 4.7 Projeção de fechamento (separada do realizado)

```text
Projeção = Realizado_até_hoje + (Esperado_restante × FatorTendência)
Esperado_restante = metaMês × (1 − IOD)
FatorTendência = clamp( média_2sem_recentes / média_6sem_anteriores , 0.5 , 1.5 )
```

Exibir: realizado até hoje · esperado até hoje · projeção · **banda provável** · **confiança (baixa/média/alta)** · frase explicativa. Nunca a projeção como número consumado.

---

## 5. Modelo recomendado de risco de churn (explicável)

### 5.1 Dicionário — não misturar conceitos

| Conceito | Definição operacional | Fonte hoje |
|---|---|---|
| Ausência pontual | 1 lapso isolado dentro do padrão | `ac` |
| Queda de frequência | Aderência < baseline individual, persistente | precisa semana (Onda 1) |
| Desengajamento | Queda + recência alta + quebra de padrão | Onda 1 |
| **Risco de churn** | Probabilidade de sair **enquanto ainda ativo** | score (novo) |
| Churn confirmado | Saiu da base ativa por 2+ meses (carência) | `active`/churn |
| Cancelamento / Não renovação | Contrato encerrado / não renovado | `active`; `fim` (propagar) |
| Suspensão / Trancamento | Pausa administrativa válida | **falta** (marcar como exceção) |
| Inadimplência | Pendência financeira | **falta** |
| Reativação / Retorno | Voltou após ausência (já tinha histórico) | ledger `fs` (já ok) |

> **Regra de ouro:** risco de churn (previsto, acionável) **nunca** é somado a churn confirmado (perda realizada). Já corrigido em parte (risco só de contrato ativo); manter separado nas telas.

### 5.2 Score explicável (0–100), aditivo e auditável

Score = soma ponderada de fatores **disponíveis hoje**, com espaço reservado para fatores futuros (peso 0 até existir dado). Cada fator contribui pontos e **aparece na explicação**.

| Bloco | Fator | Disponível hoje? | Peso inicial sugerido |
|---|---|---|---|
| **Recência** | Dias desde última visita (vs baseline) | Onda 1 (reter data) | 25 |
| **Frequência** | Aderência parcial vs baseline individual | Onda 1 | 25 |
| **Tendência** | Velocidade de queda (2sem vs 6sem) | Onda 1 | 15 |
| **Contrato** | Dias p/ vencimento + histórico de renovação | `fim` (propagar, F10) | 15 |
| **Constância** | Semanas com presença / com oportunidade | Onda 1 | 10 |
| **Tenure/coorte** | Coorte de permanência (0–30…365+) | `dm`/`fs` (hoje) | 10 |
| Financeiro | Inadimplência/cobrança | **futuro** | 0 → 10 |
| Experiência | NPS/reclamações | **futuro** | 0 → 10 |
| App Treino | Login/treino/avaliação | **futuro** | 0 → 5 |
| Relacionamento | WhatsApp/CRM | **futuro** | 0 → 5 |

**Regras de atenuação (não gerar alerta):** contrato < 15 dias; suspensão/férias registrada; contrato já cancelado; unidade fechada/sem oportunidade (ex.: Lago Norte água — já tratado no `sync`); aluno já contatado (cooldown); ação aberta no prazo; dados insuficientes → status **"Dados insuficientes"**, não "Baixo".

### 5.3 Formato do score por aluno (auditável)

```text
Risco: 78/100 — Elevado   |   Confiança: Alta
Principais fatores:
 1. Frequência 52% abaixo do baseline individual (+22)
 2. 11 dias sem visita (+18)
 3. Queda de ritmo: 2 últimas semanas −40% vs 6 anteriores (+14)
 4. Contrato vence em 18 dias (+12)
 5. Coorte 91–180d (janela de risco) (+8)
Atenuante: viagem informada até 15/07 (−12)
Ação: contato acolhedor do professor responsável em até 24h
```

### 5.4 Status operacional (mês aberto) — substitui Alto/Médio/Baixo seco

Dentro do padrão · Atenção inicial · Queda relevante · Risco elevado · Ação imediata · Em acompanhamento · Justificado/não acionar · Dados insuficientes. Cada um com **regra objetiva, motivo, confiança, ação, prazo, responsável** (§13/§25).

### 5.5 Calibração (backtesting) — obrigatório antes de confiar no score

Pegar alunos que já saíram (churn confirmado), voltar 7/15/30/45/60 dias, medir se o score teria alertado. Métricas: precisão, recall, falsos+/−, **antecedência média do alerta**, retenção pós-ação. Meta: **não** maximizar quantidade de alertas — um modelo que sinaliza todos não prioriza ninguém.

---

## 6. Fontes de dados e APIs (real vs. desejado — sem inventar)

### 6.1 Já coletado (Pacto), confirmado no código

`/clientes/simples` (roster), `/clientes/{mat}/dados-pessoais` (codPessoa, CPF, dataMatrícula, sexo, nascimento), `/v1/contrato/matricula/{mat}` (modalidade/plano, início/fim), `/acessos-cliente/by-pessoa/{codPessoa}` (histórico de acessos datados — **hoje agregado em contagem mensal**), `/v1/cliente/{cc}` (foto/professor, desligado).

### 6.2 Disponível mas **descartado/não propagado** (ganhos rápidos)

- **Acessos datados** → hoje viram `ac[m]` (contagem). Reter **última visita** e **semana ISO** habilita recência + visão semanal (F07/F08).
- **`fim` do contrato** → fetch tem, build não propaga. Habilita "dias p/ vencimento" (F10).

### 6.3 **Inexistente hoje** (não criar indicador sem dado)

Financeiro/inadimplência; NPS/pesquisas; App Treino (login/treino/avaliação/evolução); CRM/RD/WhatsApp; aulas agendadas/reservas/presenças por aula (só catraca); calendário de feriados/fechamentos/manutenção; motivo de cancelamento; agenda/rotina contratada individual. **Score deve rodar sem esses e abrir espaço quando existirem.**

### 6.4 Mapa por sistema (para roadmap de integração)

| Sistema | Traz | Status | Onda |
|---|---|---|---|
| Pacto | frequência, contrato, modalidade, tenure | **ativo** | 0–1 |
| Pacto (fim contrato) | vencimento/renovação | propagar | 1 |
| Financeiro (Pacto/gateway) | inadimplência, cobrança | avaliar endpoint | 2 |
| App Treino | treino, avaliação, evolução | integrar | 3 |
| CRM/RD/WhatsApp | mensagens, resposta, campanha, resultado | integrar | 2–3 |
| NPS/Pesquisa | satisfação | integrar | 3 |
| **Agenda Tática (D1)** | ação, responsável, prazo, resultado | **ativo** (evoluir p/ retorno) | 1–2 |

---

## 7. Merge e separação de dados (identidade única)

**Separar sempre:** Pessoa · Responsável financeiro · Dependente · Matrícula · Contrato · Plano · Modalidade · Unidade · Aula · Professor · Ação de relacionamento.

- **Chave mestra hoje:** `(unidade, matrícula)`; fallback CPF/nome (já implementado como `key`/`skey`). O **ledger perpétuo** (`fs`) já resolve "1ª vez na rede" corretamente (Novo × Retorno).
- **Regra:** nunca fazer merge só por nome/telefone/e-mail sem validação (CPF ou matrícula). Uma **pessoa** pode ter várias **matrículas** (dependentes, planos conjuntos) → contar pessoa e matrícula separadamente para não duplicar base nem risco.
- **Granularidades incompatíveis:** acesso (evento) × contrato (período) × pessoa (perpétuo) — manter em camadas, não achatar.
- **Fora do score (viés/qualidade):** faixa etária e sexo → só para coorte/segmentação, **nunca** como fator de risco individual.

---

## 8. Nova arquitetura de informação e telas (5 camadas)

Cada componente responde a **uma decisão**. Drill-down sob demanda; nada de card+gráfico repetindo o mesmo número.

**Camada 1 — Visão Executiva** (o que decidir hoje): base ativa · em risco (acionável) · ação imediata · R$/mês e /ano em risco · contratos vencendo · taxa de recuperação · churn (tendência) · **confiança + data D-1**. *Estado vazio:* "sem alertas acionáveis hoje".

**Camada 2 — Diagnóstico de Risco:** distribuição por faixa · principais motivos · evolução **semanal** · risco por unidade/modalidade/plano/coorte · sazonalidade. (Professor/carteira: só com contexto, sem julgamento.)

**Camada 3 — Fila Priorizada** (o coração operacional): aluno · unidade · modalidade · professor · **risco + confiança + motivo** · última visita · dias p/ renovação · R$ em risco · **ação recomendada + prazo + status**. Ordenada por **Prioridade** (§24), não por risco. Botão "enviar p/ Agenda Tática".

**Camada 4 — 360 do Aluno:** linha do tempo (frequência/contrato/financeiro/treino/contatos/satisfação) · ações realizadas · resultado. Hoje: frequência mensal→semanal, contrato, tenure; demais quando integrados.

**Camada 5 — Efetividade das Ações:** contatos feitos/bem-sucedidos · recuperados · renovações pós-ação · tempo médio de atuação · ação mais efetiva por perfil · **receita preservada** · backlog vencido.

**Fusões/remoções:** fundir **Engajados→Comportamento** (F17); **separar** sempre realizado × projeção e risco previsto × perda confirmada.

---

## 9. Integração com a Agenda Tática (evoluir o que já existe)

Já existe `sync_agenda.mjs` → grava no **D1** (`unidade_id, categoria_id, titulo, descricao, tipo, prioridade, aluno_nome, matricula, semana_ref, prazo, origem, status, venc, valor_mensal, foto`). É a base — falta fechar o ciclo.

**Fluxo-alvo:** Dado → Sinal → Score+Confiança → **Priorização** → Ação → Responsável → Prazo → Contato → **Resultado** → Nova ação/encerramento → **Aprendizado**.

**Campos a acrescentar no alerta:** `id_pessoa`, `id_contrato`, `score`, `confianca`, `motivo_principal`, `fatores[]`, `valor_risco`, `dias_renovacao`, `canal_recomendado`, `responsavel`, `sla`, `status`, `resultado`, `motivo_encerramento`.

**Só enviar alertas acionáveis** (aplicar as atenuações §5.2) para não gerar ruído. **Retorno obrigatório:** a Agenda devolve `status/resultado` → alimenta backtesting (§17) e a efetividade (Camada 5).

---

## 10. Playbooks de retenção (alinhados ao DNA: acolhimento, empatia, cuidado, família)

| Motivo (score) | Responsável | Canal | Abordagem | Objetivo | Prazo |
|---|---|---|---|---|---|
| Queda de frequência | Professor | WhatsApp/presencial | Acolher + ajustar rotina | Retomar constância | 24–48h |
| Vencimento próximo | Comercial/Recepção | WhatsApp/ligação | Antecipar renovação | Renovar | 7d antes |
| Sumiço (2+ meses) | Professor + Comercial | Ligação | Resgate consultivo | Reativar | 24h |
| Treino desatualizado | Professor/Coord. | App/contato | Atualizar treino/meta | Reengajar | 72h |
| Reclamação | Gestão | Ligação | Escuta + resolução | Recuperar confiança | 24h |
| Inadimplência | Financeiro/Recepção | Canal adequado | Regularização respeitosa | Preservar contrato | 48h |
| Férias/viagem | Recepção/Professor | Registro + lembrete | **Não pressionar** | Retorno programado | no retorno |
| Troca de professor | Coordenação | Pessoal | Recriar vínculo | Evitar ruptura | 72h |

---

## 11. Backlog priorizado

**Épico A — Confiança do mês aberto (P0).**
- História: *"Como gestor, quero ver a aderência parcial do aluno com base nas oportunidades já transcorridas, para não classificar errado no início do mês."*
  - Regra: cutoff = dia de `junMax`; prorratear só `PIDX`; IOD e aderência parcial.
  - Aceite: em 12/07, aluno Fitness com 3 visitas mostra ~64% ("dentro do padrão"), **não** 43%; junho mostra mês inteiro (não 16 dias); evolução plota julho.
  - Fonte: `ac`, `junMax`, `dps`. Dependência: nenhuma. Risco: baixo. Validação: jsdom + casos numéricos.

**Épico B — Recência e visão semanal (P1).**
- História: *"…quero ver dias desde a última visita e a frequência por semana comparável, para agir dentro do mês."*
  - Regra: reter `ultimaVisita` e acessos por semana ISO no build.
  - Aceite: "dias sem visita" e "semana 2 jul × semana 2 dos últimos meses" disponíveis por aluno.
  - Fonte: acessos datados (já baixados). Dependência: mudança no build. Risco: médio (peso do build — respeitar limite do runner). Validação: consistência + tempo de run.

**Épico C — Score explicável + fila priorizada (P1).**
- Aceite: cada aluno com score 0–100, confiança, top-5 fatores, atenuantes, ação/prazo; fila ordenada por prioridade.

**Épico D — Vencimento/renovação (P1).** Propagar `fim`→`venc` (F10); "dias p/ renovação" no score e na fila.

**Épico E — Ciclo fechado com a Agenda (P2).** Campos novos no alerta; retorno de resultado; Camada 5 (efetividade).

**Épico F — Backtesting & calibração (P2/P3).** Métricas de precisão/recall/antecedência; calibrar pesos e faixas de peso do mês corrente.

**Épico G — Integrações externas (P3).** Financeiro, App Treino, CRM/NPS — cada uma habilita seus fatores (peso 0→ativo).

---

## 12. Plano de implantação por ondas

| Onda | Objetivo | Entregas | Dependências | Riscos | Critério de sucesso |
|---|---|---|---|---|---|
| **0 — Confiança** | Consertar mês aberto | Cutoff dinâmico; prorratear só o parcial; IOD/aderência; evolChart dinâmico; rótulos realizado/esperado/projeção | nenhuma | baixo | Números de jun/jul batem com a operação; jsdom 0 erros |
| **1 — Diagnóstico acionável** | Recência+semana+score+fila | última visita, semana ISO, score explicável, fila priorizada, `venc` | Onda 0; build mais pesado (cuidar do runner) | médio | Fila prioriza por valor×urgência; score auditável |
| **2 — Efetividade** | Fechar o ciclo | ação↔resultado na Agenda, SLAs, receita preservada, playbooks | Onda 1; D1 | médio | Resultado das ações medido; ruído baixo |
| **3 — Inteligência** | Aprender e antecipar | backtesting, propensão, next best action, integrações externas | Ondas 1–2; APIs externas | alto | Antecedência média do alerta ↑; falsos+ ↓ |

---

## 13. Riscos, premissas e limitações

- **Snapshot diário, não tempo real** (correto p/ o caso; agir em D-1).
- **Peso do build/runner:** o #72 caiu por CPU/memória ao inchar o `win`. Reter dados semanais/datados aumenta o build — implementar incremental e vigiar o runner (lição aprendida).
- **Ticket é médio da unidade**, não por aluno — "R$ em risco" é proxy.
- **Sem financeiro/NPS/App/CRM hoje** — o score roda cego a causas não-comportamentais; **não** simular esses dados.
- **Só catraca (musculação):** categorias sem catraca (água/luta puros em unidades específicas, ex.: Lago Norte) não têm sinal de frequência — já tratado; manter a exclusão para não gerar falso "sumiu".
- **Faixa etária/sexo:** segmentação, nunca fator de risco individual (viés/LGPD).

---

## 14. Perguntas que precisam de validação humana

1. Existe **frequência/rotina contratada por aluno** (dias/horários) na Pacto ou em outro sistema? Habilitaria o N1 (melhor cálculo).
2. Há endpoint de **financeiro/inadimplência** acessível com o escopo atual da chave?
3. **App Treino** tem API? Quais campos (login, treino, avaliação, evolução)?
4. **CRM/RD/WhatsApp**: como retornar resultado de contato para fechar o ciclo?
5. Calendário de **feriados/fechamentos/manutenção** por unidade — existe fonte estruturada?
6. Pesos do score e **faixas de peso do mês corrente** (§ tabela) — calibrar com quais meses de histórico?
7. **SLAs e responsáveis** por tipo de alerta e por unidade — confirmar com a operação.
8. Política de **cooldown** (quantos dias sem recontatar o mesmo aluno)?

---

## 15. Anexo — Dicionário de métricas e fórmulas

```text
IOD (Índice de Oportunidades Decorridas)
  = diasOperacionaisDecorridos(mêsParcial até D-1) / diasOperacionaisNoMêsCompleto

Esperado_até_hoje = metaMensal(categoria,unidade) × IOD
AderênciaParcial  = VisitasRealizadasAtéHoje / Esperado_até_hoje

Desvio de Frequência = (Realizado − Esperado) / Esperado
Queda Relativa       = (Esperado − Realizado) / Esperado
Índice de Constância = SemanasComPresença / SemanasComOportunidade
Dias sem Visita      = D-1 − DataÚltimaVisitaVálida
Velocidade de Queda  = média(2 últimas semanas) − média(6 semanas anteriores)

Projeção         = Realizado + (Esperado_restante × FatorTendência)
Esperado_restante= metaMensal × (1 − IOD)
FatorTendência   = clamp(média_2sem/média_6sem, 0.5, 1.5)

Peso do mês corrente por IOD (calibrar com histórico):
  0–20% → 20% | 21–40% → 35% | 41–60% → 55% | 61–80% → 75% | 81–100% → 90–100%

Risco Atual = (RiscoHistórico × PesoHist)
            + (RiscoParcialMês × PesoPeríodoDecorrido)
            + Agravantes − Atenuantes

Score de Churn (0–100) = Σ fatores disponíveis (recência, frequência, tendência,
  contrato, constância, coorte) ponderados; fatores futuros com peso 0 até haver dado.

Prioridade de Ação = Risco × ValorContrato × UrgênciaTemporal
                    × ProbabilidadeRecuperação × AusênciaDeAçãoRecente

Confiança = f(volume de observação): Alta (histórico individual robusto),
  Média (histórico curto), Baixa (coorte/aluno novo/dados insuficientes)

Churn confirmado (carência) = saiu da base ativa por 2+ meses (1 lapso perdoado)  [já implementado]
Novo × Retorno = 1ª aparição no ledger perpétuo vs. reaparição  [já implementado]
Risco em R$ = nº (Alto+Médio, contrato ativo) × ticket médio da unidade  [proxy]
```

---

### Fecho

O caminho não é "mais um dashboard": é uma **Onda 0 curta e cirúrgica** que devolve confiança ao mês corrente (a base de qualquer decisão), seguida da camada de **recência + semana + score explicável** que transforma o painel em **fila de ação priorizada**, e do **ciclo fechado com a Agenda Tática** que faz o sistema **aprender**. Tudo isso sobre a fundação que já existe — sem reinventar, e sem inventar dados que a operação ainda não tem.
