"""
Escolhe (ou reprova) o scalp por indicadores em 5m.

    python scripts/backtest_scalp.py                                   # jan a set de 2026, 1/3 final de validação
    python scripts/backtest_scalp.py --inicio 2026-03-01 --fim 2026-09-10
    python scripts/backtest_scalp.py --fluxo                           # variação com order flow (30 dias com negócios)

Cada setup roda sozinho, para o resultado ser atribuível. O período é dividido em TREINO (onde se escolhe) e
VALIDAÇÃO (o último terço, que a escolha não vê). Aprovado é quem passa no critério nos dois — o critério está
em core/backtest_scalp.py e foi escrito antes de qualquer resultado.
"""
import argparse
import datetime as dt
import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.backtest_scalp import CRITERIO, BacktestScalp, avaliar_criterio  # noqa: E402
from core.scalp_indicadores import SETUPS, com_fluxo, montar_contextos  # noqa: E402

PASTA = os.path.join("dados", "candles")


def ms(d: dt.date) -> int:
    return int(dt.datetime.combine(d, dt.time(), tzinfo=dt.timezone.utc).timestamp() * 1000)


def carregar_5m(par: str, inicio: dt.date, fim: dt.date):
    caminho = os.path.join(PASTA, f"{par}_5m_{inicio.isoformat()}_{fim.isoformat()}.json")
    if os.path.exists(caminho):
        with open(caminho) as f:
            return json.load(f)
    from core.conexoes.conexao_bybit import BybitConnector
    os.makedirs(PASTA, exist_ok=True)
    velas = BybitConnector("simulador").obter_ohlcv_historico(par, "5m", ms(inicio), ms(fim), pausa=0.5)
    with open(caminho, "w") as f:
        json.dump(velas, f)
    return velas


def deltas_5m(par: str, inicio: dt.date, fim: dt.date):
    """Agressão líquida por candle de 5m, a partir dos negócios públicos da Bybit (só onde houver arquivo)."""
    from core.bybit_trades_fetcher import fluxo
    out = {}
    for t in fluxo(par, inicio, fim):
        chave = t["timestamp"] - t["timestamp"] % 300_000
        out[chave] = out.get(chave, 0.0) + (t["qty"] if t["side"] == "buy" else -t["qty"])
    return out


def linha(nome, r):
    if not r["trades"]:
        return f"  {nome:<26} sem trades"
    return (f"  {nome:<26} {r['trades']:>4} trades  acerto {r['acerto']:>5.0%}  bruto {r['bruto_pct_medio']:+.4%}  "
            f"custo {r['custo_pct_medio']:.4%}  bruto/custo {r['razao_bruto_custo'] if r['razao_bruto_custo'] is not None else '-':>6}  "
            f"liquido {r['pnl_liquido']:+9.2f}  FL {r['fator_lucro'] if r['fator_lucro'] is not None else '-':>5}  DD {r['dd_max_pct']:>5.2f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--par", default="BTCUSDT")
    ap.add_argument("--inicio", default="2026-01-01")
    ap.add_argument("--fim", default="2026-09-10")
    ap.add_argument("--validacao", type=float, default=1 / 3, help="fração final do período reservada para validação")
    ap.add_argument("--aquecimento-dias", type=int, default=3)
    ap.add_argument("--fluxo", action="store_true", help="testa a variação com order flow onde houver negócios")
    ap.add_argument("--salvar")
    a = ap.parse_args()

    inicio, fim = dt.date.fromisoformat(a.inicio), dt.date.fromisoformat(a.fim)
    velas = carregar_5m(a.par, inicio, fim)
    deltas = None
    if a.fluxo:
        ini_f, fim_f = dt.date(2026, 8, 10), dt.date(2026, 9, 8)
        print(f"lendo negócios de {ini_f} a {fim_f} para o order flow...")
        deltas = deltas_5m(a.par, ini_f, fim_f)
        velas = [v for v in velas if ms(ini_f) - a.aquecimento_dias * 86_400_000 <= v[0] < ms(fim_f + dt.timedelta(days=1))]
    print(f"{len(velas)} candles de 5m, montando contexto (VWAP, value area, order blocks, regime)...")
    ctxs = montar_contextos(velas, deltas=deltas)

    t_ini = ctxs[0].ts + a.aquecimento_dias * 86_400_000
    t_fim = ctxs[-1].ts + 300_000
    corte = int(t_ini + (t_fim - t_ini) * (1 - a.validacao))
    fmt = lambda t: dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).strftime("%Y-%m-%d")
    print(f"treino {fmt(t_ini)} a {fmt(corte)} | validação {fmt(corte)} a {fmt(t_fim)}")
    print(f"critério (fixado antes): {CRITERIO}\n")

    setups = {k: com_fluxo(f) for k, f in SETUPS.items()} if a.fluxo else dict(SETUPS)
    relatorio = {"periodo": [fmt(t_ini), fmt(corte), fmt(t_fim)], "criterio": CRITERIO, "setups": {}}
    aprovados = []
    for nome, f in setups.items():
        tr = BacktestScalp(ctxs, {nome: f}).executar(t_ini, corte)
        va = BacktestScalp(ctxs, {nome: f}).executar(corte, t_fim)
        ok, falhas = avaliar_criterio(tr, va)
        print(f"{nome}{' (com fluxo)' if a.fluxo else ''}")
        print(linha("treino", tr))
        print(linha("validação", va))
        print(f"  -> {'APROVADO' if ok else 'reprovado: ' + '; '.join(falhas)}\n")
        relatorio["setups"][nome] = {"treino": {k: v for k, v in tr.items() if k != "lista"},
                                     "validacao": {k: v for k, v in va.items() if k != "lista"},
                                     "aprovado": ok, "falhas": falhas}
        if ok:
            aprovados.append(nome)
    print(f"APROVADOS: {aprovados or 'nenhum'}")
    if a.salvar:
        with open(a.salvar, "w", encoding="utf-8") as f:
            json.dump(relatorio, f, ensure_ascii=False, indent=2, default=str)
        print(f"relatório em {a.salvar}")


if __name__ == "__main__":
    main()
