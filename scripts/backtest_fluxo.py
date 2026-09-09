"""
Valida o motor de fluxo do scalp sobre os negócios reais publicados pela Bybit.

    python scripts/backtest_fluxo.py                      # últimos 3 dias disponíveis
    python scripts/backtest_fluxo.py --dias 7
    python scripts/backtest_fluxo.py --inicio 2026-09-01 --fim 2026-09-05
    python scripts/backtest_fluxo.py --comparar           # roda também o motor por candle de 1m, mesma janela

O contexto (15m/1h) vem de candles públicos e a função de leitura só enxerga os fechados até o instante
simulado. Os negócios ficam em cache em dados/trades_bybit (~20 MB por dia).
"""
import argparse
import datetime as dt
import json
import logging
import os
import sys
from datetime import date, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.backtest_fluxo import BacktestFluxo, bot_fluxo  # noqa: E402
from core.bybit_trades_fetcher import baixar_dia, dias, fluxo  # noqa: E402
from core.conexoes.conexao_bybit import BybitConnector  # noqa: E402


# aquecimento do contexto: o grau macro precisa de 300 candles de 1h (12,5 dias) antes do primeiro negocio
DIAS_AQUECIMENTO = 15


def candles(con, par, tf, inicio: date, fim: date):
    """
    Candles do contexto cobrindo o periodo mais o aquecimento.

    Buscar so os ultimos 1000 candles limitava o teste a uns 7 dias: 1000 candles de 15m sao 10 dias, e 300
    deles vao embora so no aquecimento do proprio indicador. Paginando, o periodo deixa de ter teto.
    """
    return con.obter_ohlcv_historico(par, tf, ms(inicio - timedelta(days=DIAS_AQUECIMENTO)),
                                     ms(fim + timedelta(days=1)))


def ms(d: date) -> int:
    return int(dt.datetime.combine(d, dt.time()).timestamp() * 1000)


def imprimir(r: dict, titulo: str):
    print(f"\n=== {titulo} ===")
    for k in ("trades", "ganhos", "perdas", "taxa_acerto", "pnl_total", "retorno_pct", "fator_lucro",
              "r_medio", "duracao_media_s", "drawdown_max_pct", "taxas_totais", "banca_final"):
        if k in r:
            print(f"  {k:<18} {r[k]}")
    for k in ("barras", "regua", "decisoes", "gatilhos", "saidas"):
        if k in r:
            print(f"  {k:<18} {r[k]}")
    if r.get("motivos_de_espera"):
        print("  o que segurou o robô:")
        for motivo, n in r["motivos_de_espera"].items():
            print(f"     {n:>6}x  {motivo}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--par", default="BTCUSDT")
    ap.add_argument("--dias", type=int, default=3)
    ap.add_argument("--inicio")
    ap.add_argument("--fim")
    ap.add_argument("--banca", type=float, default=10000.0)
    ap.add_argument("--risco", type=float, default=0.005)
    ap.add_argument("--segundos-alvo", type=float, default=30.0)
    ap.add_argument("--slippage", type=float, default=0.0002)
    ap.add_argument("--perfil", default="conservador")
    ap.add_argument("--risco-minimo-pct", type=float, default=0.0,
                    help="piso do stop, em fração do preço (0 = padrão do motor). Stop mais largo dilui o "
                         "custo fixo da taxa, ao preço de o trade demorar mais")
    ap.add_argument("--alvo-maximo-r", type=float, default=0.0, help="teto do alvo em múltiplos do risco")
    ap.add_argument("--comparar", action="store_true", help="roda também o motor atual, por candle de 1m")
    ap.add_argument("--salvar", help="grava o relatório em JSON")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if a.inicio and a.fim:
        inicio, fim = date.fromisoformat(a.inicio), date.fromisoformat(a.fim)
    else:
        # o arquivo do dia corrente só fica pronto depois que o dia fecha: começa a procurar de ontem para trás
        fim = date.today() - timedelta(days=1)
        while baixar_dia(a.par, fim) is None and (date.today() - fim).days < 7:
            fim -= timedelta(days=1)
        inicio = fim - timedelta(days=max(a.dias - 1, 0))
    print(f"período: {inicio} a {fim} ({len(dias(inicio, fim))} dias)")

    con = BybitConnector("simulador")
    series = {"15m": candles(con, a.par, "15m", inicio, fim), "1h": candles(con, a.par, "1h", inicio, fim)}
    print(f"contexto: {len(series['15m'])} candles de 15m, {len(series['1h'])} de 1h")

    bot = bot_fluxo(ativo=a.par, banca=a.banca, risco_pct=a.risco, barra_segundos_alvo=a.segundos_alvo,
                    confluencia_tipo=a.perfil, slippage_pct=a.slippage,
                    risco_minimo_pct=a.risco_minimo_pct, alvo_maximo_r=a.alvo_maximo_r)
    bt = BacktestFluxo(bot, series_contexto=series, verbose=a.verbose)
    r = bt.executar(fluxo(a.par, inicio, fim))
    imprimir(r, f"MOTOR DE FLUXO — {a.par} {inicio}..{fim}")

    saida = {"periodo": [inicio.isoformat(), fim.isoformat()], "fluxo": r}
    if a.comparar:
        from core.backtest_engine import BacktestEngine, bot_padrao
        c1m = con.obter_ohlcv_historico(a.par, "1m", ms(inicio - timedelta(days=1)), ms(fim + timedelta(days=1)))
        if len(c1m) < 400:
            print("\n(comparação pulada: candles de 1m insuficientes para a janela pedida)")
        else:
            atual = bot_padrao(estilo_trade="scalping", timeframe="1m", ativo=a.par, banca=a.banca,
                               risco_pct=a.risco, confluencia_tipo=a.perfil, slippage_pct=a.slippage,
                               usar_trailing_stop=True, max_trades_dia=30)
            rc = BacktestEngine(c1m, atual, timeframe="1m").executar()
            imprimir(rc, f"MOTOR ATUAL (candle de 1m) — mesma janela, {len(c1m)} candles")
            saida["candle_1m"] = rc

    if a.salvar:
        with open(a.salvar, "w", encoding="utf-8") as f:
            json.dump(saida, f, default=str, ensure_ascii=False, indent=2)
        print(f"\nrelatório em {a.salvar}")


if __name__ == "__main__":
    main()
