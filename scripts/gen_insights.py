#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Caminho B: gera insights estrategicos (hipoteses + contexto de mercado + fontes reais)
via API da Anthropic com busca na web, e grava em data/freq_multi.json sob a chave "insights".

- Kill-switch: se ANTHROPIC_API_KEY estiver ausente, pula sem falhar (insights=[]).
- Tolerante a falha: qualquer erro -> insights=[] e exit 0 (o dashboard publica normal).
- Sem PII: envia apenas metricas agregadas (churn/fluxos por unidade), nunca dados de aluno.

Uso: python3 gen_insights.py [data/freq_multi.json]
"""
import os, sys, json, re

DATA_PATH = sys.argv[1] if len(sys.argv) > 1 else "data/freq_multi.json"
KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
MODEL = os.environ.get("INSIGHTS_MODEL", "claude-sonnet-4-6").strip()


def load():
    return json.load(open(DATA_PATH, encoding="utf-8"))


def save(data):
    json.dump(data, open(DATA_PATH, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


def finish(data, insights, msg=None):
    data["insights"] = insights
    save(data)
    if msg:
        print("[insights] " + msg, file=sys.stderr)
    sys.exit(0)


def build_metrics(data):
    meses = data.get("meses", [])
    partial = meses[-1] if meses else ""
    churn = data.get("churn", {})
    unidades = data.get("unidades", [])

    def summ(u):
        tr = [t for t in churn.get(u, {}).get("trans", []) if t.get("para") != partial and t.get("base")]
        if not tr:
            return None
        rates = [t["perdas"] / t["base"] for t in tr]
        lastr = rates[-1]
        trend = None
        if len(rates) >= 2:
            d = rates[-1] - rates[-2]
            trend = "piorando" if d > 0.003 else "melhorando" if d < -0.003 else "estavel"
        return {
            "churn_semestre_pct": round(sum(rates) / len(rates) * 100, 1),
            "churn_ultimo_mes_pct": round(lastr * 100, 1),
            "tendencia": trend,
            "base_alunos": tr[-1]["base"],
        }

    por_unidade = {}
    for u in unidades:
        k = u.get("key")
        if k == "REDE":
            continue
        s = summ(k)
        if s:
            por_unidade[u.get("label", k)] = s

    rede = summ("REDE")
    flow = (data.get("flow", {}) or {}).get("REDE", [])
    fluxo_recente = flow[-1] if flow else None

    return {
        "rede": "Nad'Arte (academias, Brasilia/DF)",
        "dados_referencia": data.get("baseUpdated", ""),
        "periodo": (meses[0] + " a " + meses[-1]) if meses else "",
        "mes_parcial_excluido": partial,
        "metas_churn_mensal": {"ouro": "<=2.5%", "prata": "<=3.5%", "bronze": "<=4.0%", "basico": "<=4.5%"},
        "churn_rede": rede,
        "churn_por_unidade": por_unidade,
        "fluxo_recente_rede": fluxo_recente,
    }


OUTPUT_TOOL = {
    "name": "registrar_insights",
    "description": "Registra os insights estrategicos finais em formato estruturado.",
    "input_schema": {
        "type": "object",
        "properties": {
            "insights": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "titulo": {"type": "string"},
                        "hipotese": {"type": "string"},
                        "contexto": {"type": "string"},
                        "acao": {"type": "string"},
                        "fontes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "titulo": {"type": "string"},
                                    "url": {"type": "string"},
                                },
                                "required": ["titulo", "url"],
                            },
                        },
                    },
                    "required": ["titulo", "hipotese", "contexto", "acao", "fontes"],
                },
            },
            "hooks": {
                "type": "array",
                "description": "Ganchos de mercado por grupo de modalidade, para usar no contato com o aluno.",
                "items": {
                    "type": "object",
                    "properties": {
                        "grupo": {"type": "string", "description": "Um de: Fitness, Água, Ambos, Lutas e Outros"},
                        "gancho": {"type": "string", "description": "Frase/argumento de mercado para usar na abordagem desse grupo"},
                        "fonte": {
                            "type": "object",
                            "properties": {"titulo": {"type": "string"}, "url": {"type": "string"}},
                            "required": ["titulo", "url"],
                        },
                    },
                    "required": ["grupo", "gancho"],
                },
            },
        },
        "required": ["insights"],
    },
}


def extract_json(text):
    """Fallback: extrai o primeiro objeto JSON via brace-matching string-aware."""
    text = re.sub(r"```(?:json)?", "", text or "")
    a = text.find("{")
    if a == -1:
        raise ValueError("sem objeto JSON na resposta")
    depth = 0; in_str = False; esc = False
    for i in range(a, len(text)):
        c = text[i]
        if in_str:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == '"': in_str = False
        else:
            if c == '"': in_str = True
            elif c == "{": depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[a:i + 1])
    raise ValueError("objeto JSON nao fechado")


def main():
    data = load()
    if not KEY:
        finish(data, [], "ANTHROPIC_API_KEY ausente — passo de IA pulado (kill-switch).")

    try:
        import anthropic
    except Exception as e:
        finish(data, [], f"pacote anthropic indisponivel ({e}).")

    metrics = build_metrics(data)
    metrics_str = json.dumps(metrics, ensure_ascii=False, indent=2)
    regras = (
        "Voce e analista senior de retencao de uma rede de academias (Nad'Arte, Brasilia/DF).\n"
        "Regras dos insights:\n"
        "1. Cada insight e uma HIPOTESE ACIONAVEL — nao um resumo do dado. Conecte o numero a uma possivel causa.\n"
        "2. Traga CONTEXTO DE MERCADO: setor fitness brasileiro, sazonalidade (meados de 2026), concorrencia, consumidor.\n"
        "3. Cite FONTES REAIS e verificaveis (titulo + URL). Nao invente fontes.\n"
        "4. Inclua uma ACAO concreta por insight.\n"
        "5. Portugues do Brasil, tom executivo e direto.\n"
    )

    def call(client, messages, tools, max_tokens, tool_choice=None):
        kwargs = dict(model=MODEL, max_tokens=max_tokens, tools=tools, messages=list(messages))
        if tool_choice:
            kwargs["tool_choice"] = tool_choice
        last = None
        for _ in range(8):  # continuacao para pause_turn (busca web longa)
            last = client.messages.create(**kwargs)
            if getattr(last, "stop_reason", None) == "pause_turn":
                kwargs["messages"] = kwargs["messages"] + [{"role": "assistant", "content": last.content}]
                continue
            break
        return last

    try:
        client = anthropic.Anthropic(api_key=KEY)

        # Etapa 1 — pesquisa de mercado com busca na web
        prompt_pesq = (
            regras +
            "\nPesquise na web e escreva um BRIEFING curto (com URLs das fontes) sobre o cenario do setor fitness "
            "brasileiro relevante para os numeros abaixo (retencao, sazonalidade, concorrencia em Brasilia/DF).\n\n"
            "NUMEROS INTERNOS:\n" + metrics_str
        )
        r1 = call(client, [{"role": "user", "content": prompt_pesq}],
                  [{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}], 5000)
        briefing = "".join(getattr(b, "text", "") for b in r1.content if getattr(b, "type", None) == "text")
        print(f"[insights] etapa1 stop={getattr(r1,'stop_reason',None)} brief_len={len(briefing)}", file=sys.stderr)

        # Etapa 2 — estruturacao com tool_choice forcado (garante saida valida)
        prompt_estr = (
            regras +
            "\nUse o BRIEFING e os NUMEROS para chamar a ferramenta registrar_insights com:\n"
            "(a) de 3 a 5 INSIGHTS estrategicos da rede; e\n"
            "(b) HOOKS de mercado por grupo de modalidade (Fitness, Agua, Ambos, Lutas e Outros): para cada grupo, uma frase/argumento "
            "que o atendente possa usar na ligacao com um aluno daquele grupo (ex.: tendencia, beneficio, sazonalidade), com 1 fonte real.\n"
            "Cite as URLs do briefing nas fontes.\n\n"
            "NUMEROS INTERNOS:\n" + metrics_str +
            "\n\nBRIEFING DE MERCADO:\n" + (briefing or "(sem briefing — use conhecimento do setor e cite fontes conhecidas)")
        )
        r2 = call(client, [{"role": "user", "content": prompt_estr}],
                  [OUTPUT_TOOL], 5000, tool_choice={"type": "tool", "name": "registrar_insights"})
        tool_input = None
        for b in r2.content:
            if getattr(b, "type", None) == "tool_use" and getattr(b, "name", "") == "registrar_insights":
                tool_input = getattr(b, "input", {}) or {}
                break
        if tool_input is None:
            text = "".join(getattr(b, "text", "") for b in r2.content if getattr(b, "type", None) == "text")
            try:
                tool_input = extract_json(text)
            except Exception:
                tool_input = {}
        insights = tool_input.get("insights", []) or []
        # hooks de mercado por grupo -> {grupo: {gancho, fonte}}
        GRUPOS = {"fitness": "Fitness", "agua": "Água", "água": "Água", "ambos": "Ambos",
                  "lutas e outros": "Lutas e Outros", "lutas": "Lutas e Outros"}
        hooks_map = {}
        for h in (tool_input.get("hooks", []) or [])[:8]:
            if not isinstance(h, dict):
                continue
            g = GRUPOS.get(str(h.get("grupo", "")).strip().lower())
            if not g or not h.get("gancho"):
                continue
            fonte = None
            f = h.get("fonte") or {}
            if isinstance(f, dict) and re.match(r"^https?://", str(f.get("url", ""))):
                fonte = {"titulo": str(f.get("titulo", f.get("url")))[:160], "url": str(f.get("url"))}
            hooks_map[g] = {"gancho": str(h.get("gancho", ""))[:500], "fonte": fonte}
        data["hooks"] = hooks_map
        print(f"[insights] etapa2 stop={getattr(r2,'stop_reason',None)} n_raw={len(insights or [])} hooks={len(hooks_map)}", file=sys.stderr)

        # saneamento basico: manter apenas campos esperados e URLs http(s)
        clean = []
        for x in (insights or [])[:6]:
            if not isinstance(x, dict):
                continue
            fontes = []
            for f in (x.get("fontes") or [])[:5]:
                u = str(f.get("url", "")) if isinstance(f, dict) else ""
                if re.match(r"^https?://", u):
                    fontes.append({"titulo": str(f.get("titulo", u))[:160], "url": u})
            clean.append({
                "titulo": str(x.get("titulo", ""))[:160],
                "hipotese": str(x.get("hipotese", ""))[:800],
                "contexto": str(x.get("contexto", ""))[:1000],
                "acao": str(x.get("acao", ""))[:600],
                "fontes": fontes,
            })
        if not clean:
            finish(data, [], "resposta sem insights validos.")
        finish(data, clean, f"{len(clean)} insights gerados (modelo {MODEL}).")
    except Exception as e:
        finish(data, [], f"falha na geracao de insights: {e}")


if __name__ == "__main__":
    main()
