# core/detector_institucional.py
"""
Detector de pontos institucionais por par/timeframe (roda periodicamente pelo BotManager ou via script).

Fontes:
    TPO (POC/VAL/VAH/HVN/LVN) e Volume Profile sobre as velas COMPOSTAS (cesta TradingView + Bybit)
    VWAP e bandas (Bybit)
    Clusters de Order Flow (trades recentes compostos)
    Order Blocks do gráfico (deslocamento ≥ 1,5 ATR)
Cada ponto é registrado sem duplicar (tolerância 0,15%) e classificado por tipo/timeframe.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import sessionmaker

from api.database import engine
from core.order_block import OrderBlockDetector
from core.order_flow import OrderFlowAnalyzerPro
from core.tpo import TPOProfile
from core.volume_profile_pro import VolumeProfilePRO
from core.vwap import VWAPCalculator
from models.exchange_institucional import ExchangeInstitucional
from models.pair_institucional import PairInstitucional
from services.detector_ponto_institucional_service import DetectorPontoInstitucionalService
from services.ponto_institucional_service import PontoInstitucionalService

logger = logging.getLogger(__name__)


def detectar_para_par_e_timeframe(db, par: str, tf_name: str, exchange_name: str = "bybit",
                                  market_data=None, connector=None, limite: int = 300) -> int:
    from core.conexoes.conexao_bybit import BybitConnector
    con = connector or BybitConnector("simulador")
    par = par.replace("/", "")
    ohlcv = con.obter_ohlcv(par, tf_name, limite, somente_fechados=True)
    comp = ohlcv
    if market_data is not None:
        try:
            comp = market_data.ohlcv_composto(par, tf_name, limite)
        except Exception as e:
            logger.warning("velas compostas indisponíveis para %s %s: %s", par, tf_name, e)
    preco = float(ohlcv[-1][4])
    n = 0

    def reg(preco_p, tipo, motivo, relev, fonte, **extra):
        nonlocal n
        DetectorPontoInstitucionalService.registrar_ponto(
            db=db, preco=float(preco_p), tipo=tipo, motivo=motivo, par=par, exchange=exchange_name,
            relevancia=relev, extra={"fonte": fonte, "timeframe": tf_name, **extra})
        n += 1

    # TPO
    try:
        res = TPOProfile(comp, bins=30).analisar()
        reg(res["POC"], f"TPO_POC_{tf_name}", "POC do TPO", 2.0, "TPO")
        reg(res["VAL"], f"TPO_VAL_{tf_name}", "VAL do TPO", 1.8, "TPO")
        reg(res["VAH"], f"TPO_VAH_{tf_name}", "VAH do TPO", 1.8, "TPO")
        for h in res["HVN"]:
            reg(h, f"TPO_HVN_{tf_name}", "HVN do TPO", 1.5, "TPO")
        for l in res["LVN"]:
            reg(l, f"TPO_LVN_{tf_name}", "LVN do TPO", 1.0, "TPO")
    except Exception as e:
        logger.error("TPO %s %s: %s", par, tf_name, e)
        db.rollback()
    # Volume Profile
    try:
        vp = VolumeProfilePRO(comp, num_bins=40).analisar()
        reg(vp["POC"], f"VP_POC_{tf_name}", "POC do Volume Profile", 2.0, "VOLUME_PROFILE")
        reg(vp["VAL"], f"VP_VAL_{tf_name}", "VAL do Volume Profile", 1.7, "VOLUME_PROFILE")
        reg(vp["VAH"], f"VP_VAH_{tf_name}", "VAH do Volume Profile", 1.7, "VOLUME_PROFILE")
        for h in vp["HVN"]:
            reg(h, f"VP_HVN_{tf_name}", "HVN do Volume Profile", 1.6, "VOLUME_PROFILE")
        for l in vp["LVN"]:
            reg(l, f"VP_LVN_{tf_name}", "LVN do Volume Profile", 1.1, "VOLUME_PROFILE")
    except Exception as e:
        logger.error("VP %s %s: %s", par, tf_name, e)
        db.rollback()
    # VWAP
    try:
        vb = VWAPCalculator(ohlcv).vwap_bandas()
        if vb:
            reg(vb["vwap"], f"VWAP_{tf_name}", "VWAP", 1.8, "VWAP")
            for nome in ("+2σ", "-2σ"):
                reg(vb["bandas"][nome], f"VWAP_BANDA_{nome}_{tf_name}", f"VWAP banda {nome}", 1.2, "VWAP", banda=nome)
    except Exception as e:
        logger.error("VWAP %s %s: %s", par, tf_name, e)
        db.rollback()
    # Order Flow (clusters de volume negociado)
    try:
        trades = market_data.trades_compostos(par, 500) if market_data is not None else con.obter_trades(par, 500)
        book = con.obter_order_book(par, 50)
        for preco_c, vol in OrderFlowAnalyzerPro(book, trades, ohlcv, timeframe=tf_name).clusterizar_volume(top=5):
            reg(preco_c, f"OF_CLUSTER_{tf_name}", f"Cluster de order flow ({vol:.2f})", 1.4, "ORDER_FLOW", volume=vol)
    except Exception as e:
        logger.error("OrderFlow %s %s: %s", par, tf_name, e)
        db.rollback()
    # Order Blocks
    try:
        obd = OrderBlockDetector(ohlcv)
        for b in obd.identificar_blocks("bullish")[-6:]:
            reg(b["preco"], f"OB_BULLISH_{tf_name}", f"Order block bullish (força {b['forca']} ATR)", 2.2, "ORDER_BLOCK", zona=b["zona"])
        for b in obd.identificar_blocks("bearish")[-6:]:
            reg(b["preco"], f"OB_BEARISH_{tf_name}", f"Order block bearish (força {b['forca']} ATR)", 2.2, "ORDER_BLOCK", zona=b["zona"])
    except Exception as e:
        logger.error("OrderBlock %s %s: %s", par, tf_name, e)
        db.rollback()
    # atualiza testados/rompidos com o preço atual e poda excesso
    try:
        PontoInstitucionalService.atualizar_pontos_testados_ou_rompidos(db, preco, par, exchange_name, preco_fechamento=preco)
        PontoInstitucionalService.limpar_antigos(db, par, exchange_name)
    except Exception as e:
        logger.error("manutenção %s: %s", par, e)
        db.rollback()
    logger.info("detector %s %s: %d pontos registrados/atualizados", par, tf_name, n)
    return n


def run_detector(market_data=None, session=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s:%(message)s")
    db = session or sessionmaker(bind=engine)()
    total = 0
    try:
        pares = db.query(PairInstitucional, ExchangeInstitucional).join(
            ExchangeInstitucional, PairInstitucional.exchange_id == ExchangeInstitucional.id).filter(
            PairInstitucional.ativo == True, ExchangeInstitucional.ativa == True).all()  # noqa: E712
        for pair, exchange in pares:
            if exchange.nome.lower() != "bybit":
                continue  # a execução é na Bybit; as outras exchanges entram pela cesta composta
            try:
                total += detectar_para_par_e_timeframe(db, pair.par, pair.timeframe, "bybit", market_data=market_data)
            except Exception as e:
                logger.error("Erro geral em %s %s: %s", pair.par, pair.timeframe, e)
                db.rollback()
    finally:
        if session is None:
            db.close()
    return total


if __name__ == "__main__":
    from core.market_data import MarketDataAggregator
    print("pontos:", run_detector(market_data=MarketDataAggregator("tradingview")))
