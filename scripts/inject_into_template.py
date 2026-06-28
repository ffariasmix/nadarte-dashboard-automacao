#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Injeta freq_multi.json no template congelado (secao 10/10.1 do runbook).
Substitui APENAS: o objeto `const DATA=...;`, o selo de versao (verbadge) e o carimbo (footMeta).
Nada mais do HTML e tocado.

Uso: python3 inject_into_template.py <model.html> <freq_multi.json> <out.html> <new_version> <badge_date DD/MM> [foot_day DD/MM]
"""
import sys, re, json, datetime

model_path, json_path, out_path, new_ver, badge_date = sys.argv[1:6]
foot_day = sys.argv[6] if len(sys.argv) > 6 else None  # ex "16/06" para "dados até"

html = open(model_path, "r", encoding="utf-8").read()
new_json = open(json_path, "r", encoding="utf-8").read().strip()
# garante que e JSON valido e minificado de uma linha
obj = json.loads(new_json)
new_json = json.dumps(obj, ensure_ascii=False, separators=(", ", ": "))

# ---- 1. localizar e substituir o bloco const DATA=...; via brace-matching (string-aware) ----
anchor = "const DATA="
start = html.index(anchor)
i = start + len(anchor)
assert html[i] == "{", "esperado '{' apos const DATA="
depth = 0; in_str = False; esc = False; end = None
while i < len(html):
    ch = html[i]
    if in_str:
        if esc: esc = False
        elif ch == "\\": esc = True
        elif ch == '"': in_str = False
    else:
        if ch == '"': in_str = True
        elif ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i; break
    i += 1
assert end is not None, "nao fechou o objeto DATA"
assert html[end+1] == ";", f"esperado ';' apos o objeto DATA, achei {html[end+1]!r}"
old_ver_m = re.search(r'verbadge">v([0-9.]+)', html)
old_ver = "v"+old_ver_m.group(1) if old_ver_m else None

new_html = html[:start] + "const DATA=" + new_json + ";" + html[end+2:]

# ---- 2. selo de versao (verbadge) ----
new_html, n1 = re.subn(r'(verbadge">)[^<]*(<)',
                       lambda m: m.group(1) + new_ver + " · " + badge_date + m.group(2),
                       new_html, count=1)
assert n1 == 1, "verbadge nao encontrado/substituido"

# ---- 3. carimbo do rodape (footMeta) — versao e, opcionalmente, 'dados até DD/MM' ----
if old_ver:
    # troca a versao APENAS no carimbo (verbadge ja foi tratado e nao casa mais com old_ver)
    new_html, n2 = re.subn(re.escape(old_ver) + r"\b", new_ver, new_html)
else:
    n2 = 0
if foot_day:
    new_html = re.sub(r'(dados até )\d{1,2}/\d{1,2}', r'\g<1>' + foot_day, new_html)

open(out_path, "w", encoding="utf-8").write(new_html)

# ---- relatorio ----
delta = len(new_html) - len(html)
print(f"[ok] gerado: {out_path}")
print(f"[info] versao {old_ver} -> {new_ver} (substituicoes no rodape: {n2}); selo='{new_ver} · {badge_date}'")
print(f"[info] tamanho model={len(html)} -> novo={len(new_html)} (delta {delta:+d})")
print(f"[info] DATA substituido entre offsets {start}..{end+1}")
