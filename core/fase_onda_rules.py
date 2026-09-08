# core/fase_onda_rules.py
"""
Regras institucionais por fase da onda de Elliott.

Para cada fase:
    indicadores              -> validadores permitidos (só votam os que o bot habilitou E a fase permite)
    tp_sl                    -> fonte prioritária para TP/SL ('elliott', 'fibonacci', 'tpo', 'vwap', 'orderblock')
    bloquear_zona_institucional -> se True, NÃO entra quando o preço está colado em um ponto
                                   institucional relevante CONTRA a direção do trade
    tolerancia_preco         -> raio (fração do preço) considerado "colado" em um ponto institucional
    direcao                  -> 'tendencia' (a favor do impulso), 'contra' (a favor da correção) ou None (não opera)
    perfis                   -> perfis de confluência que podem operar nesta fase
"""
from __future__ import annotations

from typing import Dict, List, Optional

FASE_ONDA_RULES: Dict[str, Dict] = {
    "inicio_onda_3": {
        "indicadores": ["TPO", "VWAP", "OrderFlow", "VolumeProfile", "OrderBlock"],
        "tp_sl": "elliott",
        "bloquear_zona_institucional": True,
        "tolerancia_preco": 0.004,
        "direcao": "tendencia",
        "perfis": ["conservador", "turbo"],
    },
    "meio_onda_3": {
        "indicadores": ["VWAP", "OrderFlow", "TPO", "VolumeProfile"],
        "tp_sl": "elliott",
        "bloquear_zona_institucional": True,
        "tolerancia_preco": 0.003,
        "direcao": "tendencia",
        "perfis": ["conservador", "turbo"],
    },
    "final_onda_3": {
        "indicadores": ["Fibonacci", "OrderBlock", "VWAP"],
        "tp_sl": "fibonacci",
        "bloquear_zona_institucional": True,
        "tolerancia_preco": 0.003,
        "direcao": "tendencia",
        "perfis": ["turbo"],
    },
    "onda_1": {
        "indicadores": ["OrderFlow", "VWAP", "OrderBlock", "VolumeProfile"],
        "tp_sl": "elliott",
        "bloquear_zona_institucional": True,
        "tolerancia_preco": 0.004,
        "direcao": "tendencia",
        "perfis": ["turbo"],
    },
    "onda_2": {
        "indicadores": ["VWAP", "VolumeProfile"],
        "tp_sl": "fibonacci",
        "bloquear_zona_institucional": True,
        "tolerancia_preco": 0.003,
        "direcao": None,
        "perfis": [],
    },
    "onda_4": {
        "indicadores": ["VWAP", "VolumeProfile"],
        "tp_sl": "vwap",
        "bloquear_zona_institucional": True,
        "tolerancia_preco": 0.004,
        "direcao": None,
        "perfis": [],
    },
    "onda_5": {
        "indicadores": ["Fibonacci", "VWAP", "OrderBlock", "OrderFlow"],
        "tp_sl": "elliott",
        "bloquear_zona_institucional": True,
        "tolerancia_preco": 0.003,
        "direcao": "tendencia",
        "perfis": ["conservador", "turbo"],
    },
    "correcao_a": {
        "indicadores": ["VWAP", "VolumeProfile", "OrderFlow"],
        "tp_sl": "elliott",
        "bloquear_zona_institucional": True,
        "tolerancia_preco": 0.004,
        "direcao": "contra",
        "perfis": ["turbo"],
    },
    "correcao_b": {
        "indicadores": ["VWAP"],
        "tp_sl": "vwap",
        "bloquear_zona_institucional": True,
        "tolerancia_preco": 0.003,
        "direcao": None,
        "perfis": [],
    },
    "correcao_c": {
        "indicadores": ["Fibonacci", "VWAP", "OrderFlow"],
        "tp_sl": "elliott",
        "bloquear_zona_institucional": True,
        "tolerancia_preco": 0.003,
        "direcao": "contra",
        "perfis": ["conservador", "turbo"],
    },
    "triangulo": {
        "indicadores": ["VWAP", "TPO", "OrderFlow"],
        "tp_sl": "elliott",
        "bloquear_zona_institucional": True,
        "tolerancia_preco": 0.003,
        "direcao": None,
        "perfis": [],
    },
    "consolidacao": {
        "indicadores": ["VWAP", "TPO"],
        "tp_sl": "vwap",
        "bloquear_zona_institucional": False,
        "tolerancia_preco": 0.002,
        "direcao": None,
        "perfis": [],
    },
    "indefinido": {
        "indicadores": [],
        "tp_sl": None,
        "bloquear_zona_institucional": True,
        "tolerancia_preco": None,
        "direcao": None,
        "perfis": [],
    },
}

TODOS_INDICADORES = ["VWAP", "TPO", "OrderFlow", "VolumeProfile", "OrderBlock", "Fibonacci"]
INDICADORES_VOTANTES = ["VWAP", "TPO", "OrderFlow", "VolumeProfile", "OrderBlock"]  # Fibonacci só dá níveis


def get_regras_fase_onda(fase_onda: Optional[str]) -> Dict:
    return FASE_ONDA_RULES.get(fase_onda or "indefinido", FASE_ONDA_RULES["indefinido"])


def indicadores_para_fase(fase_onda: Optional[str], indicadores_habilitados: List[str]) -> List[str]:
    """Interseção entre o que a fase permite e o que o bot habilitou."""
    permitidos = get_regras_fase_onda(fase_onda)["indicadores"]
    return [i for i in indicadores_habilitados if i in permitidos]


def get_tp_sl_prioritario(fase_onda: Optional[str]) -> Optional[str]:
    return get_regras_fase_onda(fase_onda)["tp_sl"]


def get_tolerancia_preco(fase_onda: Optional[str]) -> Optional[float]:
    return get_regras_fase_onda(fase_onda)["tolerancia_preco"]


def bloquear_zona_institucional(fase_onda: Optional[str]) -> bool:
    return bool(get_regras_fase_onda(fase_onda)["bloquear_zona_institucional"])


def direcao_permitida(fase_onda: Optional[str], perfil: str) -> Optional[str]:
    """'tendencia' | 'contra' | None conforme a fase e o perfil (conservador/turbo)."""
    regras = get_regras_fase_onda(fase_onda)
    if (perfil or "conservador").lower() not in regras["perfis"]:
        return None
    return regras["direcao"]
