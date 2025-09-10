# Local sugerido: core/fase_onda_rules.py

FASE_ONDA_RULES = {
    "inicio_onda_3": {
        "indicadores": ["TPO", "VWAP", "OrderFlow"],
        "tp_sl": "tpo",    # Prioriza TP/SL sugerido pelo TPO
        "bloquear_zona_institucional": True,
        "tolerancia_preco": 0.03,   # Exemplo: só aceitar níveis até 3% do preço atual
    },
    "meio_onda_3": {
        "indicadores": ["VWAP", "OrderFlow"],
        "tp_sl": "vwap",
        "bloquear_zona_institucional": True,
        "tolerancia_preco": 0.025,
    },
    "final_onda_3": {
        "indicadores": ["Fibonacci", "OrderBlock"],
        "tp_sl": "fibonacci",
        "bloquear_zona_institucional": True,
        "tolerancia_preco": 0.02,
    },
    "onda_4": {
        "indicadores": ["VWAP", "VolumeProfile"],
        "tp_sl": "vwap",
        "bloquear_zona_institucional": True,
        "tolerancia_preco": 0.03,
    },
    "onda_5": {
        "indicadores": ["Fibonacci", "VWAP", "OrderBlock"],
        "tp_sl": "fibonacci",
        "bloquear_zona_institucional": True,
        "tolerancia_preco": 0.025,
    },
    "correcao_a": {
        "indicadores": ["VWAP", "VolumeProfile"],
        "tp_sl": "vwap",
        "bloquear_zona_institucional": True,
        "tolerancia_preco": 0.03,
    },
    "correcao_b": {
        "indicadores": ["VWAP"],
        "tp_sl": "vwap",
        "bloquear_zona_institucional": True,
        "tolerancia_preco": 0.025,
    },
    "correcao_c": {
        "indicadores": ["Fibonacci", "VWAP"],
        "tp_sl": "fibonacci",
        "bloquear_zona_institucional": True,
        "tolerancia_preco": 0.025,
    },
    "consolidacao": {
        "indicadores": ["VWAP"],
        "tp_sl": "vwap",
        "bloquear_zona_institucional": False,
        "tolerancia_preco": 0.01,
    },
    "indefinido": {
        "indicadores": [],
        "tp_sl": None,
        "bloquear_zona_institucional": True,
        "tolerancia_preco": None,
    }
}

def get_regras_fase_onda(fase_onda):
    """
    Retorna o dicionário de regras/contexto para a fase técnica da onda.
    """
    return FASE_ONDA_RULES.get(fase_onda, FASE_ONDA_RULES["indefinido"])


def indicadores_para_fase(fase_onda, indicadores_habilitados):
    """
    Retorna a lista de indicadores ATIVOS para a fase atual da onda,
    cruzando regras institucionais da fase com os indicadores habilitados/configurados no banco.
    - fase_onda: string, ex: 'inicio_onda_3'
    - indicadores_habilitados: lista de strings, ex: ['VWAP', 'Fibonacci', ...]
    """
    regras = get_regras_fase_onda(fase_onda)
    indicadores_contextuais = regras['indicadores']
    # Interseção: só ativa se estiver em AMBOS
    return [i for i in indicadores_habilitados if i in indicadores_contextuais]


def get_tp_sl_prioritario(fase_onda):
    """
    Retorna o nome do indicador a ser priorizado para cálculo de TP/SL, conforme contexto institucional.
    """
    regras = get_regras_fase_onda(fase_onda)
    return regras['tp_sl']


def get_tolerancia_preco(fase_onda):
    """
    Retorna a tolerância de preço recomendada para a fase da onda (ex: 0.03 = 3%)
    """
    regras = get_regras_fase_onda(fase_onda)
    return regras['tolerancia_preco']


def bloquear_zona_institucional(fase_onda):
    """
    Retorna se deve ou não bloquear entrada em zonas institucionais para a fase
    """
    regras = get_regras_fase_onda(fase_onda)
    return regras['bloquear_zona_institucional']
