"""
O backtest por candle aplica os limites do dia como o robô: sem eles ele contava trades que o robô ao vivo não
faria — e justamente nos dias ruins, quando o limite de perda já teria parado tudo.
"""
import core.backtest_engine as be
from core.backtest_engine import BacktestEngine, bot_padrao

H1 = 3_600_000
T0 = 1_780_000_000_000 - (1_780_000_000_000 % 86_400_000)


class _Engine:
    """StrategyEngine de mentira: compra em todo candle, stop a 1% e alvo a 1%."""
    def __init__(self, janela, bot, db=None, servicos=None):
        self.preco = janela[-1][4]

    def sinal_saida(self, direcao):
        return {"sair": False}

    def decidir(self):
        return {"acao": "buy", "sl": self.preco * 0.99, "tp": self.preco * 1.01, "fase_onda": "teste"}


def _serie(n, passo=-0.012):
    """Queda de 1,2% por hora: todo trade de compra bate o stop no candle seguinte."""
    out, p = [], 100.0
    for i in range(n):
        o, c = p, p * (1 + passo)
        out.append([T0 + i * H1, o, max(o, c), min(o, c), c, 10.0])
        p = c
    return out


def test_limite_de_trades_por_dia(monkeypatch):
    monkeypatch.setattr(be, "StrategyEngine", _Engine)
    bot = bot_padrao(max_trades_dia=2, max_perda_dia_pct=0.99, timeframe="1h")
    # subida de 1,2% por hora: todo trade bate o alvo no candle seguinte e o robô quer entrar de novo
    r = BacktestEngine(_serie(24 + 10, passo=0.012), bot=bot, timeframe="1h", janela=10).executar()
    por_dia = {}
    for t in r["lista_trades"]:
        por_dia[t["ts_entrada"] // 86_400_000] = por_dia.get(t["ts_entrada"] // 86_400_000, 0) + 1
    assert por_dia and max(por_dia.values()) <= 2
    assert r["bloqueios_limite_dia"] > 0


def test_limite_de_perda_do_dia_para_as_entradas(monkeypatch):
    monkeypatch.setattr(be, "StrategyEngine", _Engine)
    bot = bot_padrao(max_trades_dia=100, max_perda_dia_pct=0.02, risco_pct=0.01, timeframe="1h")
    r = BacktestEngine(_serie(20 + 10), bot=bot, timeframe="1h", janela=10).executar()
    # toda entrada do dia aconteceu com a perda acumulada ainda acima do limite; depois dele, nenhuma
    limite = 0.02 * 10000.0
    acumulado = 0.0
    for t in sorted(r["lista_trades"], key=lambda t: t["ts_entrada"]):
        if t["ts_entrada"] // 86_400_000 != T0 // 86_400_000:
            continue
        assert acumulado > -limite, "entrou depois de bater a perda máxima do dia"
        acumulado += t["pnl"]
    assert acumulado <= -limite
    assert r["bloqueios_limite_dia"] > 0


def test_sinal_com_ordem_limitada_pendente_e_ignorado_como_no_robo(monkeypatch):
    monkeypatch.setattr(be, "StrategyEngine", _Engine)

    class _Limite(_Engine):
        def decidir(self):
            d = super().decidir()
            d["preco_limite"] = self.preco * 0.95        # longe: não executa
            return d

    monkeypatch.setattr(be, "StrategyEngine", _Limite)
    bot = bot_padrao(tipo_entrada="limite", limite_candles_espera=3, timeframe="1h")
    r = BacktestEngine(_serie(10 + 9, passo=0.0), bot=bot, timeframe="1h", janela=10).executar()
    assert r["ordens_limite"]["expiradas"] == 2, "uma ordem por vez, cada uma vivendo os 3 candles dela"
