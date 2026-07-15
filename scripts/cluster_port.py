#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cluster_port.py — porta fiel da função `cluster()` do template do dashboard de
Frequência (template/template.html). Reproduz EXATAMENTE a categoria de
comportamento que o dash mostra, para uso no exportador da Lista de Alunos Ativos.

Janela padrão do dash: state.from=1, state.to=len(meses)  (range completo).
Rótulos: Novo · Sem acesso · Em evasão · Em declínio · Esporádico · Retorno ·
         Regular · Em ascensão · Fiel   (idênticos ao dashboard).

NÃO alterar sem reconferir contra template/template.html (função `cluster`).
"""

def _mean(a):
    return sum(a) / len(a) if a else 0


def cluster(ac, frm, to, fs, novo_cad):
    """ac: lista de acessos/mês; frm/to: janela (1-based, inclusive to);
    fs: índice 'first seen' (ou None); novo_cad: matriculado no mês-ref."""
    if novo_cad:
        return "Novo"
    rng = ac[frm - 1:to]
    n = len(rng)
    ai = [i for i in range(n) if rng[i] > 0]
    if not ai:
        return "Sem acesso"
    first = ai[0]; last = ai[-1]; inativo = (n - 1) - last
    seg = rng[first:]; span = len(seg)
    if span >= 2:
        h = max(1, span // 2)
        early = _mean(seg[:h]); late = _mean(seg[h:])
    else:
        early = late = seg[0]
    change = (late - early) / early if early > 0 else (1 if late > 0 else -1)
    presence = len(ai) / span
    favg = _mean(seg)
    if inativo >= 2:
        return "Em evasão"
    if inativo == 1:
        return "Em declínio" if early >= 4 else "Esporádico"
    if span == 1 and first == n - 1:
        abs_idx = frm - 1 + last
        any_before = any(ac[z] > 0 for z in range(abs_idx))
        prev_acc = abs_idx > 0 and ac[abs_idx - 1] > 0
        ledger_old = (fs is not None and 0 <= fs < abs_idx)
        if not any_before and not ledger_old:
            return "Esporádico"
        if prev_acc:
            return "Regular"
        return "Retorno"
    if change <= -0.40:
        return "Em declínio"
    if presence < 0.60:
        return "Esporádico"
    if change >= 0.40:
        return "Em ascensão"
    if favg >= 10 and presence >= 0.85:
        return "Fiel"
    return "Regular"


def categoria_aluno(student, n_meses):
    """Recebe um registro de `students` do freq_multi.json + total de meses,
    devolve a categoria (janela completa = igual ao dash)."""
    ac = student.get("ac") or []
    fs = student.get("fs")
    novo = bool(student.get("novoCad"))
    return cluster(ac, 1, n_meses, fs, novo)


if __name__ == "__main__":
    N = 6
    def c(ac, fs=None, novo=False):
        return cluster(ac, 1, N, fs, novo)
    casos = [
        ("Novo",        c([0,0,0,0,0,1], novo=True)),
        ("Sem acesso",  c([0,0,0,0,0,0])),
        ("Em evasão",   c([5,5,0,0,0,0])),
        ("Em declínio (inativo=1, early>=4)", c([5,5,5,5,5,0])),
        ("Esporádico (inativo=1, early<4)",   c([1,1,1,1,1,0])),
        ("Fiel",        c([10,11,12,10,11,12])),
        ("Em ascensão", c([2,2,3,8,9,10])),
        ("Em declínio (change)", c([10,10,10,2,2,2])),
        ("Esporádico (presence<0.6)", c([5,0,0,5,0,5])),
        ("Regular",     c([3,3,3,3,3,3])),
        ("Retorno (single last, tinha histórico)", c([0,0,0,0,0,5], fs=2)),
        ("Esporádico (single last, sem histórico)", c([0,0,0,0,0,5], fs=None)),
    ]
    esperado = ["Novo","Sem acesso","Em evasão","Em declínio","Esporádico","Fiel",
                "Em ascensão","Em declínio","Esporádico","Regular","Retorno","Esporádico"]
    ok = True
    for (nome, got), exp in zip(casos, esperado):
        flag = "OK " if got == exp else "XX "
        if got != exp: ok = False
        print(f"{flag}{nome:42s} -> {got}  (esperado {exp})")
    print("\nRESULTADO:", "TODOS OK" if ok else "FALHOU")
    import sys; sys.exit(0 if ok else 1)
