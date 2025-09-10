# core/detector_institucional.py

import logging
from sqlalchemy.orm import sessionmaker
from api.database import engine
from services.detector_ponto_institucional_service import DetectorPontoInstitucionalService
from core.tpo import TPOProfile
from core.vwap import VWAPCalculator
from core.order_flow import OrderFlowAnalyzerPro
from core.volume_profile_pro import VolumeProfilePRO
from core.order_block import OrderBlockDetector
from models.pair_institucional import PairInstitucional
from models.exchange_institucional import ExchangeInstitucional
from core.exchange_factory import get_exchange_connector

def detectar_para_par_e_timeframe(db, con, par, tf_name, exchange_name, tf_minutes):

    logging.info(f"Iniciando detecção para {par} no timeframe {tf_name}")

    # 1. Busca candles OHLCV
    ohlcv = con.obter_ohlcv(par, tf_name, 500)
    closes = [c[4] for c in ohlcv]

    # ============ TPO ============
    try:
        tpo = TPOProfile(closes)
        resultado = tpo.analisar()
        for tipo, preco in [
            (f"TPO_POC_{tf_name}", resultado['POC']),
            (f"TPO_VAL_{tf_name}", resultado['VAL']),
            (f"TPO_VAH_{tf_name}", resultado['VAH'])
        ]:
            DetectorPontoInstitucionalService.registrar_ponto(
                db=db,
                preco=float(preco),
                tipo=tipo,
                motivo=f"{tipo} institucional",
                par=par,
                exchange=con.exchange_name if hasattr(con, "exchange_name") else "",
                relevancia=2.0,
                extra={"fonte": "TPO", "timeframe": tf_name}
            )
        for hvn in resultado.get('HVN', []):
            DetectorPontoInstitucionalService.registrar_ponto(
                db=db,
                preco=float(hvn),
                tipo=f"TPO_HVN_{tf_name}",
                motivo="HVN institucional",
                par=par,
                exchange=con.exchange_name if hasattr(con, "exchange_name") else "",
                relevancia=1.5,
                extra={"fonte": "TPO", "timeframe": tf_name}
            )
        for lvn in resultado.get('LVN', []):
            DetectorPontoInstitucionalService.registrar_ponto(
                db=db,
                preco=float(lvn),
                tipo=f"TPO_LVN_{tf_name}",
                motivo="LVN institucional",
                par=par,
                exchange=con.exchange_name if hasattr(con, "exchange_name") else "",
                relevancia=1.0,
                extra={"fonte": "TPO", "timeframe": tf_name}
            )
    except Exception as e:
        import traceback
        traceback.print_exc()  # <-- ISSO É IMPORTANTE
        logging.error(f"Erro TPO {par} {tf_name}: {e}")

    # ============ VWAP ============
    try:
        vwap_calc = VWAPCalculator(ohlcv)
        vwap = vwap_calc.vwap()
        DetectorPontoInstitucionalService.registrar_ponto(
            db=db,
            preco=float(vwap),
            tipo=f"VWAP_{tf_name}",
            motivo=f"VWAP institucional",
            par=par,
            exchange=con.exchange_name if hasattr(con, "exchange_name") else "",
            relevancia=1.8,
            extra={"fonte": "VWAP", "timeframe": tf_name}
        )
        bandas = vwap_calc.vwap_bandas()
        for nome, preco in bandas["bandas"].items():
            DetectorPontoInstitucionalService.registrar_ponto(
                db=db,
                preco=float(preco),
                tipo=f"VWAP_BANDA_{nome}_{tf_name}",
                motivo=f"VWAP Banda {nome} institucional",
                par=par,
                exchange=con.exchange_name if hasattr(con, "exchange_name") else "",
                relevancia=1.2,
                extra={"fonte": "VWAP", "timeframe": tf_name, "banda": nome}
            )
    except Exception as e:
        import traceback
        traceback.print_exc()  # <-- ISSO É IMPORTANTE
        logging.error(f"Erro VWAP {par} {tf_name}: {e}")

    # ============ VOLUME PROFILE ============
    try:
        vp = VolumeProfilePRO(ohlcv)
        nodes = vp.hvn_lvn()
        for preco in nodes['HVN']:
            DetectorPontoInstitucionalService.registrar_ponto(
                db=db,
                preco=float(preco),
                tipo=f"VP_HVN_{tf_name}",
                motivo=f"Volume Profile HVN institucional",
                par=par,
                exchange=con.exchange_name if hasattr(con, "exchange_name") else "",
                relevancia=1.7,
                extra={"fonte": "VOLUME_PROFILE", "timeframe": tf_name}
            )
        for preco in nodes['LVN']:
            DetectorPontoInstitucionalService.registrar_ponto(
                db=db,
                preco=float(preco),
                tipo=f"VP_LVN_{tf_name}",
                motivo=f"Volume Profile LVN institucional",
                par=par,
                exchange=con.exchange_name if hasattr(con, "exchange_name") else "",
                relevancia=1.1,
                extra={"fonte": "VOLUME_PROFILE", "timeframe": tf_name}
            )
    except Exception as e:
        import traceback
        traceback.print_exc()  # <-- ISSO É IMPORTANTE
        logging.error(f"Erro VL PROFILE {par} {tf_name}: {e}")

    # ============ ORDER FLOW ============
    try:
        order_book = con.obter_order_book(par)
        trades = con.obter_trades(par)
        ofa = OrderFlowAnalyzerPro(order_book, trades, ohlcv)
        clusters = ofa.clusterizar_volume()
        for preco, volume in clusters:
            DetectorPontoInstitucionalService.registrar_ponto(
                db=db,
                preco=float(preco),
                tipo=f"OF_CLUSTER_{tf_name}",
                motivo=f"Order Flow Cluster institucional ({volume})",
                par=par,
                exchange=con.exchange_name if hasattr(con, "exchange_name") else "",
                relevancia=1.4,
                extra={"fonte": "ORDER_FLOW", "timeframe": tf_name, "volume": volume}
            )
    except Exception as e:
        import traceback
        traceback.print_exc()  # <-- ISSO É IMPORTANTE
        logging.error(f"Erro Order Flow {par} {tf_name}: {e}")

    # ============ ORDER BLOCK ============
    try:
        obd = OrderBlockDetector(ohlcv)
        for block in obd.identificar_blocks(tipo='bullish'):
            DetectorPontoInstitucionalService.registrar_ponto(
                db=db,
                preco=float(block['zona'][0]),
                tipo=f"OB_BULLISH_{tf_name}",
                motivo="Order Block institucional (bullish)",
                par=par,
                exchange=con.exchange_name if hasattr(con, "exchange_name") else "",
                relevancia=2.2,
                extra={"fonte": "ORDER_BLOCK", "timeframe": tf_name, "tipo": "bullish"}
            )
        for block in obd.identificar_blocks(tipo='bearish'):
            DetectorPontoInstitucionalService.registrar_ponto(
                db=db,
                preco=float(block['zona'][0]),
                tipo=f"OB_BEARISH_{tf_name}",
                motivo="Order Block institucional (bearish)",
                par=par,
                exchange=con.exchange_name if hasattr(con, "exchange_name") else "",
                relevancia=2.2,
                extra={"fonte": "ORDER_BLOCK", "timeframe": tf_name, "tipo": "bearish"}
            )
    except Exception as e:
        import traceback
        traceback.print_exc()  # <-- ISSO É IMPORTANTE
        logging.error(f"Erro Order Book {par} {tf_name}: {e}")

def run_detector():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')
    Session = sessionmaker(bind=engine)
    db = Session()

    query = db.query(PairInstitucional, ExchangeInstitucional).join(
        ExchangeInstitucional, PairInstitucional.exchange_id == ExchangeInstitucional.id
    ).filter(
        PairInstitucional.ativo == True,
        ExchangeInstitucional.ativa == True
    ).all()

    for pair, exchange in query:
        par = pair.par
        tf_name = pair.timeframe
        exchange_name = exchange.nome
        connector = get_exchange_connector(exchange_name)
        # Se o seu conector tem .exchange_name, garanta que está populado corretamente!
        if not hasattr(connector, "exchange_name"):
            connector.exchange_name = exchange_name
        try:
            detectar_para_par_e_timeframe(db, connector, par, tf_name, exchange_name, None)
        except Exception as e:
            import traceback
            traceback.print_exc()  # <-- ISSO É IMPORTANTE
            logging.error(f"Erro Geral em {par} {tf_name}: {e}")
    db.close()

if __name__ == "__main__":
    run_detector()
