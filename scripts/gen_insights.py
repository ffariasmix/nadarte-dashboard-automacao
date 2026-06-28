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


def extract_json(text):
    text = text.strip()
    # remove cercas de codigo se houver
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M)
    a = text.find("{")
    b = text.rfind("}")
    if a == -1 or b == -1 or b <= a:
        raise ValueError("sem objeto JSON na resposta")
    return json.loads(text[a:b + 1])


def main():
    data = load()
    if not KEY:
        finish(data, [], "ANTHROPIC_API_KEY ausente — passo de IA pulado (kill-switch).")

    try:
        import anthropic
    except Exception as e:
        finish(data, [], f"pacote anthropic indisponivel ({e}).")

    metrics = build_metrics(data)
    prompt = (
        "Voce e analista senior de retencao de uma rede de academias (Nad'Arte, Brasilia/DF).\n"
        "Com base nos NUMEROS INTERNOS abaixo, gere de 3 a 5 INSIGHTS ESTRATEGICOS para a gestao.\n"
        "Regras:\n"
        "1. Cada insight e uma HIPOTESE ACIONAVEL — nao um resumo do dado. Conecte o numero interno a uma possivel causa.\n"
        "2. Traga CONTEXTO DE MERCADO atual: tendencias do setor fitness brasileiro, sazonalidade (estamos em meados de 2026), concorrencia, comportamento do consumidor.\n"
        "3. Use a BUSCA NA WEB para embasar o contexto e CITE FONTES REAIS e verificaveis (titulo + URL). Nao invente fontes.\n"
        "4. Inclua uma ACAO sugerida, concreta, por insight.\n"
        "5. Portugues do Brasil, tom executivo e direto.\n"
        "Responda APENAS com JSON valido, sem texto fora do JSON, no formato:\n"
        '{"insights":[{"titulo":"...","hipotese":"...","contexto":"...","acao":"...",'
        '"fontes":[{"titulo":"...","url":"https://..."}]}]}\n\n'
        "NUMEROS INTERNOS:\n" + json.dumps(metrics, ensure_ascii=False, indent=2)
    )

    try:
        client = anthropic.Anthropic(api_key=KEY)
        resp = client.messages.create(
            model=MODEL,
            max_tokens=4000,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}],
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text")
        parsed = extract_json(text)
        insights = parsed.get("insights", [])
        # saneamento basico: manter apenas campos esperados e URLs http(s)
        clean = []
        for x in insights[:6]:
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
