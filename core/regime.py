# core/regime.py
"""
Filtro de regime de mercado (complementa Elliott, não o substitui).

Mede se o mercado tem "energia" para completar a estrutura que Elliott identificou:
    eficiencia  = |deslocamento líquido| / soma dos deslocamentos (Kaufman): 1 = tendência limpa, 0 = serrilhado
    vol_rel     = ATR curto / ATR longo: < 0,7 = volatilidade comprimida (fase de acumulação/triângulo)
    largura     = (máx - mín) da janela em ATRs: < 4 ATR = faixa estreita
Regimes:
    tendencia    -> eficiência alta: entradas a favor liberadas
    expansao     -> volatilidade acima do normal com eficiência média: entradas ok com SL maior (ATR já cobre)
    compressao   -> volatilidade comprimida e faixa estreita: só entra em ROMPIMENTO (thrust de triângulo, onda 3
                    com fechamento fora da faixa); demais entradas bloqueadas
    serrilhado   -> eficiência muito baixa sem compressão: bloqueia (mercado sem direção)
"""
from __future__ import annotations

from typing import Dict, Sequence

import numpy as np

from core.utils_indicadores import atr


def analisar_regime(ohlcv: Sequence, janela: int = 40) -> Dict:
    dados = list(ohlcv)
    if len(dados) < 30:
        return {"regime": "indefinido", "eficiencia": 0.0, "vol_rel": 1.0, "largura_atr": 0.0, "permite_entrada": True, "motivo": "poucos candles"}
    win = dados[-janela:]
    closes = np.array([c[4] for c in win], dtype=float)
    liquido = abs(closes[-1] - closes[0])
    caminho = float(np.sum(np.abs(np.diff(closes)))) or 1e-9
    eficiencia = liquido / caminho
    a_curto = atr(dados[-20:], 14) or 1e-9
    a_longo = atr(dados[-150:], 100) or a_curto
    vol_rel = a_curto / a_longo
    largura = (max(c[2] for c in win) - min(c[3] for c in win)) / a_longo
    fechou_fora = closes[-1] > max(c[2] for c in win[:-1]) or closes[-1] < min(c[3] for c in win[:-1])

    if vol_rel < 0.7 and largura < 5:
        regime = "compressao"
        permite = fechou_fora
        motivo = f"volatilidade comprimida (ATR {vol_rel:.2f}x, faixa {largura:.1f} ATR): só rompimento" + (" (rompeu)" if fechou_fora else "")
    elif eficiencia < 0.15:
        regime = "serrilhado"
        permite = False
        motivo = f"eficiência {eficiencia:.2f}: sem direção"
    elif eficiencia >= 0.35:
        regime = "tendencia"
        permite = True
        motivo = f"tendência limpa (eficiência {eficiencia:.2f})"
    else:
        regime = "expansao" if vol_rel > 1.2 else "neutro"
        permite = True
        motivo = f"eficiência {eficiencia:.2f}, ATR {vol_rel:.2f}x"
    return {"regime": regime, "eficiencia": round(float(eficiencia), 3), "vol_rel": round(float(vol_rel), 3),
            "largura_atr": round(float(largura), 2), "permite_entrada": bool(permite), "rompimento": bool(fechou_fora), "motivo": motivo}
