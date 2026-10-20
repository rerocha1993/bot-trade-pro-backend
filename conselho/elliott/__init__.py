"""
Elliott Pro: motor de ondas com múltiplos cenários e múltiplos graus.

    pivots      -> ZigZag por ATR (um ou vários graus)
    patterns    -> catálogo de padrões (impulso, diagonais, zigzag, flats, triângulos, combinações)
    scenarios   -> gera cenários concorrentes (bull/bear) com probabilidade, fase, invalidação e alvos
    multidegree -> alinha o grau operacional (scalp/daytrade/swing) com o grau de contexto e o macro
"""
from .pivots import Pivot, zigzag_atr, zigzag_multi  # noqa: F401
from .patterns import Leg, legs_de_pivots, PatternFit, ajustar_todos, PADROES  # noqa: F401
from .scenarios import Cenario, ScenarioEngine  # noqa: F401
from .multidegree import AnaliseMultiGrau, PERFIS  # noqa: F401
