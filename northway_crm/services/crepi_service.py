"""Regras de classificação da Matriz CREPI (Causa, Risco, Efeito, Probabilidade, Impacto).

Fonte única da regra de nível. O front-end (client_details.html) replica a mesma lógica
em `crepiNivel()`; ao alterar aqui, alterar lá também.

Regra:
- Score = Probabilidade x Impacto (0 a 100).
- Impacto catastrófico (I >= 9):
    - P >= 3 -> crítico (ação imediata);
    - P <= 2 -> médio, com plano de contingência obrigatório.
- Demais casos: score > 40 crítico; 16 a 40 médio; até 15 baixo.
- P ou I igual a 0 -> não avaliado.
"""

IMPACTO_CATASTROFICO = 9
PROB_MIN_CRITICO_CATASTROFICO = 3
LIMITE_CRITICO = 40
LIMITE_MEDIO = 15

STATUS_VALIDOS = ('aberta', 'em_tratamento', 'mitigada', 'confirmada', 'ocorreu')


def _to_int(value, default=0, lo=0, hi=10):
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def calcular_nivel(probabilidade, impacto):
    """Retorna (nivel, score, contingencia_obrigatoria).

    nivel: 'critico' | 'medio' | 'baixo' | 'nao_avaliado'
    """
    p = _to_int(probabilidade)
    i = _to_int(impacto)
    score = p * i
    if p == 0 or i == 0:
        return 'nao_avaliado', score, False
    if i >= IMPACTO_CATASTROFICO:
        if p >= PROB_MIN_CRITICO_CATASTROFICO:
            return 'critico', score, False
        return 'medio', score, True
    if score > LIMITE_CRITICO:
        return 'critico', score, False
    if score > LIMITE_MEDIO:
        return 'medio', score, False
    return 'baixo', score, False


def normalizar_status(status):
    return status if status in STATUS_VALIDOS else 'aberta'
