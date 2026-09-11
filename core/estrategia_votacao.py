# core/estrategia_votacao.py
"""
ESTRATÉGIA "VOTAÇÃO + FATIAS": o robô que saiu do laboratório (scripts/lab_indicadores.py, 4h, gestão so_fatias).

    entrada   quando pelo menos 2 de 4 indicadores concordam no lado — VWAP da sessão, TPO, Volume Profile e
              Order Block —, fora de mercado serrilhado (filtro de regime)
    fatias    5 entradas iguais: a 1ª no sinal, as outras 4 como ordens limitadas a 20/40/60/80% do caminho até
              o stop (gestão do usuário: preço médio em vez de entrar de uma vez)
    stop      1,5 ATR contra o preço do sinal; alvo 3,0 ATR a favor; saída por tempo depois de 24 candles
    tamanho   o pior caso (todas as fatias executadas e stop) perde `risco_pct` da banca

Resultado no backtest (BTC 4h): +0,215 / +0,208 / +0,165 R por trade em treino (2021–jun/2023), validação
(jul/2023–2024) e holdout (2025–2026), compra e venda positivas. É o vencedor de uma busca de 516 variantes: o
modo demo existe para confirmar daqui para a frente, não para acreditar.

Os sinais saem de `core.sinais_indicadores.sinais_do_candle` e a votação de `core.lab_combinacoes.lado_da_votacao`,
as mesmas funções do backtest.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from core.lab_combinacoes import Variante, lado_da_votacao
from core.sinais_indicadores import JANELA, atr_simples, sinais_do_candle


@dataclass(frozen=True)
class ConfigVotacao:
    indicadores: tuple = ("VWAP_sessao", "TPO", "Volume_Profile", "Order_Block")
    votos_min: int = 2
    usar_regime: bool = True
    usar_elliott: bool = False
    mult_stop: float = 1.5
    mult_alvo: float = 3.0
    horizonte: int = 24
    n_entradas: int = 5
    espacamento: float = 0.2

    @property
    def variante(self) -> Variante:
        return Variante(tuple(self.indicadores), self.votos_min, self.usar_elliott, self.usar_regime)


PADRAO = ConfigVotacao()


def niveis_fatias(lado: int, preco: float, risco: float, cfg: ConfigVotacao = PADRAO) -> List[float]:
    """Preço de cada fatia: a 1ª no sinal, as outras a k x espacamento x risco em direção ao stop."""
    return [preco - lado * k * cfg.espacamento * risco for k in range(cfg.n_entradas)]


def quantidade_total(banca: float, risco_pct: float, lado: int, preco: float, risco: float,
                     cfg: ConfigVotacao = PADRAO) -> float:
    """Tamanho de TODAS as fatias somadas: se todas executarem e o stop bater, perde banca x risco_pct."""
    niveis = niveis_fatias(lado, preco, risco, cfg)
    stop = preco - lado * risco
    medio = sum(niveis) / len(niveis)
    dist = abs(medio - stop)
    return (banca * risco_pct) / dist if dist > 0 else 0.0


def decidir(ohlcv: Sequence[Sequence[float]], cfg: ConfigVotacao = PADRAO) -> Dict:
    """Decisão no fechamento do último candle de `ohlcv` (só candles fechados)."""
    if len(ohlcv) < JANELA:
        return {"acao": "hold", "motivo": f"candles insuficientes ({len(ohlcv)} < {JANELA})"}
    win = [[int(c[0])] + [float(x) for x in c[1:6]] for c in ohlcv[-JANELA:]]
    try:
        sinais = sinais_do_candle(win)
    except Exception as e:
        return {"acao": "hold", "motivo": f"indicador não calculou: {e}"}
    lado = lado_da_votacao(sinais, cfg.variante)
    preco = win[-1][4]
    votos = {i: sinais.get(i, 0) for i in cfg.indicadores}
    texto_votos = ", ".join(f"{i} {'compra' if v == 1 else 'venda' if v == -1 else '—'}" for i, v in votos.items())
    base = {"preco": preco, "sinais": sinais, "votos": votos, "candle_ts": win[-1][0]}
    if lado == 0:
        motivo = "mercado serrilhado (filtro de regime)" if cfg.usar_regime and sinais.get("Regime") == 0 \
            else f"sem {cfg.votos_min} votos do mesmo lado"
        return {**base, "acao": "hold", "motivo": f"{motivo} | {texto_votos}"}
    atr = atr_simples(win)
    risco = cfg.mult_stop * atr
    stop = preco - lado * risco
    alvo = preco + lado * cfg.mult_alvo * risco
    return {**base, "acao": "buy" if lado == 1 else "sell", "lado": lado, "atr": atr, "risco": risco, "sl": stop,
            "tp": alvo, "niveis": niveis_fatias(lado, preco, risco, cfg),
            "motivo": f"votação {sum(1 for v in votos.values() if v == lado)} de {len(votos)} a favor | {texto_votos} | "
                      f"stop {stop:,.0f} (1,5 ATR), alvo {alvo:,.0f} (3 ATR), 5 fatias até {cfg.horizonte} candles"}
