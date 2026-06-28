# Nad'Arte — Automação do Dashboard de Frequência & Retenção

Pipeline **sem Claude**: o GitHub Actions baixa as bases do Google Drive, gera o
dashboard e publica num **link fixo** no Cloudflare Pages. Toda quinta-feira
(após a equipe atualizar as planilhas na quarta) — ou no botão manual.

```
Google Drive (xlsx)  ──►  GitHub Actions  ──►  Cloudflare Pages (link fixo)
  Alunos Ativos            build_freq_multi.py     nadarte-frequencia.pages.dev
  Acessos Catraca          inject_into_template.py
                           validate_render.js
```

## Estrutura

```
.
├── .github/workflows/build-deploy.yml   # agendador + pipeline
├── scripts/
│   ├── drive_download.py                # baixa as 11 planilhas (service account)
│   ├── build_freq_multi.py              # xlsx -> data/freq_multi.json
│   ├── inject_into_template.py          # template + json -> public/index.html
│   └── validate_render.js               # validação headless (jsdom)
├── template/template.html               # << VOCÊ adiciona (HTML congelado)
├── version.txt                          # versão atual (vX.Y), o bot incrementa
├── requirements.txt                     # openpyxl, google-api-python-client, google-auth
└── package.json                         # jsdom
```

## O que é regra de ouro

- O **template é congelado**: o pipeline só troca `const DATA`, o selo de versão e o carimbo de data.
- Chave de junção é **(unidade + matrícula)** — nunca CPF.
- **Base** = mês de maior prefixo em *Alunos Ativos*.
- Se a checagem de consistência de churn falhar (`[WARN]`), o pipeline **aborta sem publicar**.

---

## Setup (uma vez só)

### 1) Service Account do Google (acesso ao Drive)

1. Acesse https://console.cloud.google.com/ → crie um projeto (ex.: `nadarte-dashboard`).
2. **APIs & Services → Library →** ative a **Google Drive API**.
3. **APIs & Services → Credentials → Create credentials → Service account**. Nome: `nadarte-dashboard-bot`.
4. Abra a service account → aba **Keys → Add key → Create new key → JSON**. Baixe o arquivo `.json`.
5. Anote o **e-mail** da service account (algo como `nadarte-dashboard-bot@SEU-PROJETO.iam.gserviceaccount.com`).

### 2) Compartilhar as pastas do Drive com a service account

Com a conta dona das planilhas (**contatoconnectindigital@gmail.com**), compartilhe
as **duas pastas** com o e-mail da service account, papel **Leitor (Viewer)**:

- **Alunos Ativos** — ID `1U5prMp9ImJ3mR1flWanictD4rb4u0GRc`
- **Acessos Catraca** — ID `1-vdLb3wO_wfT_trX9Bl0p83SYxGzCA9_`

> Compartilhar a pasta já cobre todos os arquivos dentro dela.

### 3) Cloudflare Pages (link fixo)

1. Crie conta em https://dash.cloudflare.com/ (plano grátis serve).
2. Copie o **Account ID** (Workers & Pages → Overview, coluna direita).
3. **My Profile → API Tokens → Create Token →** template **"Edit Cloudflare Workers"**
   (ou um custom com permissão **Account → Cloudflare Pages → Edit**). Copie o token.
4. Crie o projeto Pages uma vez (escolha o nome, ex.: `nadarte-frequencia`):
   - Pela interface: **Workers & Pages → Create → Pages → Direct Upload**, nome `nadarte-frequencia`; **ou**
   - Pelo terminal: `npx wrangler@3 pages project create nadarte-frequencia --production-branch main`
5. O link fixo será **`https://nadarte-frequencia.pages.dev`**.

### 4) Secrets e variáveis no GitHub

No repositório: **Settings → Secrets and variables → Actions**.

**Secrets:**
| Nome | Valor |
|---|---|
| `GOOGLE_SA_KEY` | conteúdo **inteiro** do JSON da service account |
| `CLOUDFLARE_API_TOKEN` | token criado no passo 3.3 |
| `CLOUDFLARE_ACCOUNT_ID` | Account ID do passo 3.2 |

**Variável (opcional):** `CF_PAGES_PROJECT` = `nadarte-frequencia` (se usar outro nome de projeto).

### 5) Template e versão

- Coloque o HTML congelado em **`template/template.html`** (veja `template/README.md`).
- `version.txt` já vem com `v5.9`; o bot incrementa +0.1 a cada rodada bem-sucedida.

### 6) Subir e rodar

```bash
git init && git add . && git commit -m "pipeline inicial"
git branch -M main
git remote add origin git@github.com:SEU-USUARIO/nadarte-dashboard-automacao.git
git push -u origin main
```

Depois: **aba Actions → "Build & Deploy Dashboard Nad'Arte" → Run workflow** para testar na hora.

---

## Agendamento

`cron: '0 11 * * 4'` = **quinta-feira 08:00 (America/Sao_Paulo)**.
Para mudar o horário/dia, edite o `cron` em `.github/workflows/build-deploy.yml`
(lembre que o GitHub usa **UTC**; BRT = UTC−3).

## Rodar localmente (opcional, para depurar)

```bash
pip install -r requirements.txt && npm install
export GOOGLE_SA_KEY_FILE=./sa_key.json     # chave da service account
python scripts/drive_download.py data
python scripts/build_freq_multi.py data
python scripts/inject_into_template.py template/template.html data/freq_multi.json public/index.html v6.0 $(TZ=America/Sao_Paulo date +%d/%m) 25/06
node scripts/validate_render.js public/index.html $(python -c "import json;print(len(json.load(open('data/freq_multi.json'))['students']))")
```

## Solução de problemas

- **"template/template.html ausente"** → adicione o HTML congelado em `template/`.
- **"faltam arquivos de Alunos Ativos ou Acessos Catraca"** → as pastas não foram compartilhadas com a service account (passo 2).
- **`[WARN]` de consistência** → divergência nas bases; o pipeline não publica. Verifique as planilhas do mês.
- **Falha no deploy Cloudflare** → confira `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` e se o projeto Pages existe (passo 3.4).
