# core/inverse_passo.py
"""
O passo de UM candle do inverse: máquina de rompimento + grade. Uma função só, usada pelo robô ao vivo
(core/inverse_executor.py) e pelo backtest (core/backtest_grade.py).

Antes cada um tinha a sua versão, e o backtest ficou para trás: pesos antigos, grade nascendo com todos os níveis
ativos, sem a regra de rompimento do usuário. Ele validava uma estratégia que não era a que estava rodando.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from core.inverse_grade import GradeInversa
from core.inverse_rompimento import MaquinaRompimento


def passo_inverse(grade: GradeInversa, maquina: MaquinaRompimento, ts: int, high: float, low: float, close: float,
                  banca_btc: float, guia: Optional[Dict] = None) -> Dict:
    """
    Aplica um candle FECHADO. Muda `grade` e `maquina` no lugar e devolve:

        execs         vendas/recompras a executar (as da máquina e as da grade)
        fechar_grade  topo rompido de verdade: todas as fatias foram recompradas no fechamento
        concluido     o ciclo do range terminou (ex.: short de reteste encerrado no alvo ou no stop)
        motivo        o que a máquina leu
    """
    guia = guia or {}
    equity = banca_btc + grade.pnl_nao_realizado(close) + maquina.pnl_nao_realizado(close)
    alvos: Sequence[float] = [a for a in (guia.get("alvos") or []) if a] if guia.get("vies") == "bear" else []
    r = maquina.avaliar(ts, high, low, close, max(equity, 1e-6), grade.low, grade.high, list(alvos),
                        fracao_ja_vendida=grade.fracao_aberta())
    execs: List[Dict] = list(r["execs"])
    # o resultado do short de reteste entra no BTC realizado da grade, para o resultado aparecer inteiro
    grade.btc_realizado += sum(e.get("pnl_btc", 0.0) for e in r["execs"] if e["tipo"] == "recompra")
    if r["fechar_grade"]:
        for f in grade.fatias:
            if f.contratos > 0:
                pnl = f.contratos * (1 / close - 1 / f.preco_venda)
                grade.btc_realizado += pnl
                execs.append({"ts": ts, "tipo": "recompra", "nivel": f.nivel, "preco": close, "contratos": f.contratos,
                              "pnl_btc": pnl})
                f.contratos = 0.0
    else:
        # só dentro do range a grade vende. Rompendo, esperando o reteste ou vendido no reteste, o range acabou ou
        # está em xeque — as recompras continuam, porque recompra é lucro. O estado vale DEPOIS do fechamento:
        # um pavio acima do topo que fecha de volta dentro vende o pavio, que é o que se quer num falso
        execs += grade.processar_candle(ts, high, low, close, max(equity, 1e-6), guia or None, vender=maquina.no_range)
    return {"execs": execs, "fechar_grade": bool(r["fechar_grade"]), "concluido": bool(r["concluido"]),
            "motivo": r.get("motivo") or "", "estado": r.get("estado")}
