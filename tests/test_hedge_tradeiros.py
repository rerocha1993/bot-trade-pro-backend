"""Hedge de carteira do Tradeiros no inverse: vende em escada na resistência, recompra no POC/VAL, stop no rompimento."""
from core.hedge_tradeiros import BacktestHedgeTradeiros, ParametrosHedge
from core.tpo_sessao import BLOCO_MS, DIA_MS

T0 = 1_780_000_000_000 - (1_780_000_000_000 % DIA_MS)


def _dia(d, lo, hi, fase=0.0):
    """Dia de range: gira em volta do meio (o POC) e faz excursões rápidas até perto das bordas."""
    meio, meia = (lo + hi) / 2, (hi - lo) / 2
    ciclo = [0, 0.15, -0.15, 0, 0.85, 0.95, 0.85, 0.25, 0, -0.25, -0.85, -0.95]
    k = int(fase * 10) % len(ciclo)
    out = []
    for i in range(48):
        m = meio + meia * ciclo[(i + k) % len(ciclo)]
        out.append((T0 + d * DIA_MS + i * BLOCO_MS, m, m + 50, m - 50, m, 10.0))
    return out


def test_range_lateral_vende_no_topo_recompra_embaixo_e_ganha_btc():
    blocos = [b for d in range(30) for b in _dia(d, 76000, 80000, fase=d * 0.9)]
    r = BacktestHedgeTradeiros(blocos, p=ParametrosHedge(funding=False)).executar()
    assert r["vendas"] > 0 and r["recompras"] > 0 and r["stops"] == 0
    assert r["btc_final"] > 1.0, "vender em cima e recomprar embaixo acumula BTC"


def test_rompimento_para_cima_fecha_o_short_com_prejuizo_pequeno():
    lateral = [b for d in range(10) for b in _dia(d, 76000, 80000, fase=d * 0.9)]
    alta = [(T0 + (10 + d) * DIA_MS + i * BLOCO_MS, p, p + 60, p - 60, p, 10.0)
            for d in range(4) for i, p in enumerate([80500 + 150 * (d * 48 + j) for j in range(48)])]
    r = BacktestHedgeTradeiros(lateral + alta, p=ParametrosHedge(funding=False)).executar()
    assert r["stops"] >= 1
    assert r["btc_final"] > 0.95, "o short é no máximo 35% da carteira e sai no rompimento"


def test_funding_positivo_paga_quem_esta_vendido():
    blocos = [b for d in range(30) for b in _dia(d, 76000, 80000, fase=d * 0.9)]
    fund = {T0 + d * DIA_MS + (i + 1) * BLOCO_MS: 0.0001 for d in range(30) for i in range(48)}
    sem = BacktestHedgeTradeiros(blocos, p=ParametrosHedge(funding=False)).executar()
    com = BacktestHedgeTradeiros(blocos, funding=fund).executar()
    assert com["funding_btc"] > 0 and com["btc_final"] > sem["btc_final"]
