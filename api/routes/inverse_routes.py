# api/routes/inverse_routes.py
"""
Modo inverse (short-only em range, acumulação de BTC).

    GET  /inverse/{bot_id}/estado                 range atual, alocação, posição, leitura da contagem mestre
    GET  /inverse/{bot_id}/range/proposta         proposta automática (pivôs primários no diário + regime + Elliott)
    POST /inverse/{bot_id}/range/aprovar?low&high aprova (manual ou a proposta), status 'aprovado'; recusa com os
                                                  motivos quando algo não fecha, a menos que venha forcar=true
    POST /inverse/{bot_id}/range/cancelar         volta a 'sem range' (recusa com short aberto, salvo forcar=true)
    POST /inverse/backtest?desde=2017-01-01       backtest em BTC no histórico 4h da Bitstamp
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.database import get_db
from models.bot import Bot
from services.bot_manager import get_manager

router = APIRouter()


def _bot(db, bot_id):
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(404, "Bot não encontrado")
    return bot


@router.get("/{bot_id}/estado")
def estado(bot_id: int, db: Session = Depends(get_db)):
    bot = _bot(db, bot_id)
    st = get_manager().status_bot(bot_id) or {}
    return {"bot": bot.as_dict(), "range": {"low": bot.range_low, "high": bot.range_high, "status": bot.range_status, "motivo": bot.range_motivo},
            "escada": json.loads(bot.escada_json) if bot.escada_json else None, "estado": st.get("inverse"), "ultima_decisao": st.get("ultima_decisao"),
            "grade": json.loads(bot.grade_json) if bot.grade_json else None}


@router.get("/{bot_id}/range/proposta")
def proposta(bot_id: int, db: Session = Depends(get_db)):
    from core.inverse_range import propor_range
    from services.elliott_mestre_service import ElliottMestreService
    bot = _bot(db, bot_id)
    con = get_manager().servicos["connectors"]["simulador"]
    m = ElliottMestreService(db, con).calcular(bot.ativo)
    prim = m["graus"].get("primario") or {}
    preco = con.obter_preco_atual(bot.ativo)
    prop = propor_range(prim.get("pivots", []), preco, prim.get("regime"), prim.get("primario"))
    return {"preco": preco, "proposta": prop, "elliott_primario": prim.get("primario"), "trava": m.get("trava")}


def _contratos_abertos(bot) -> float:
    """Short ainda aberto na grade salva (fatias + short de reteste)."""
    try:
        g = json.loads(bot.grade_json) if bot.grade_json else {}
    except Exception:
        return 0.0
    total = sum(float(f.get("contratos") or 0) for f in (g.get("fatias") or []))
    reteste = (g.get("rompimento") or {}).get("reteste") or {}
    return total + float(reteste.get("contratos") or 0)


@router.post("/{bot_id}/range/aprovar")
def aprovar(bot_id: int, low: Optional[float] = None, high: Optional[float] = None, folga_stop: float = 0.01,
            short_base_max: float = 0.5, escada: Optional[str] = Query(None, description='JSON {"0.236":0.1,...}'),
            forcar: bool = Query(False, description="aprova mesmo com avisos (sem proposta válida, preço fora do range)"),
            db: Session = Depends(get_db)):
    """
    Antes esta rota aceitava tudo calada — inclusive a proposta que o próprio robô marcava como inválida. Agora
    confere antes: range impossível e grade com short aberto BLOQUEIAM; o resto vira aviso e só passa com forcar.
    """
    from core.inverse_rompimento import validar_aprovacao
    bot = _bot(db, bot_id)
    low = low or bot.range_low
    high = high or bot.range_high
    try:
        preco = get_manager().servicos["connectors"]["simulador"].obter_preco_atual(bot.ativo)
    except Exception:
        preco = None
    bloqueios, avisos = validar_aprovacao(low, high, preco, bot.range_status, _contratos_abertos(bot))
    if bloqueios:
        raise HTTPException(400, {"motivo": "aprovação impossível", "bloqueios": bloqueios, "avisos": avisos})
    if avisos and not forcar:
        raise HTTPException(400, {"motivo": "aprovação recusada", "avisos": avisos,
                                  "como_forcar": "repita com forcar=true se tiver certeza"})
    bot.range_low, bot.range_high, bot.range_status = float(low), float(high), "aprovado"
    bot.folga_stop, bot.short_base_max = folga_stop, short_base_max
    if escada:
        try:
            bot.escada_json = json.dumps(json.loads(escada))
        except Exception:
            raise HTTPException(400, "escada deve ser JSON")
    # a grade é remontada do zero no próximo ciclo, com o preço daquele momento
    bot.grade_json = None
    bot.range_motivo = ((bot.range_motivo or "") + " | aprovado pelo usuário"
                        + (f" (forçado: {'; '.join(avisos)})" if avisos else ""))[:255]
    db.commit()
    return {"ok": True, "range": [bot.range_low, bot.range_high], "status": bot.range_status, "preco": preco,
            "avisos": avisos, "forcado": bool(avisos)}


@router.post("/{bot_id}/range/cancelar")
def cancelar(bot_id: int, forcar: bool = Query(False, description="cancela mesmo com short aberto"),
             db: Session = Depends(get_db)):
    """Cancelar com short aberto deixa essa posição na corretora sem ninguém cuidando dela."""
    bot = _bot(db, bot_id)
    abertos = _contratos_abertos(bot)
    if abertos > 0 and not forcar:
        raise HTTPException(400, {"motivo": "cancelamento recusado",
                                  "avisos": [f"a grade tem short aberto ({abertos:,.0f} contratos): cancelar agora deixa "
                                             f"essa posição na corretora sem gestão"],
                                  "como_forcar": "repita com forcar=true se tiver certeza"})
    bot.range_status, bot.range_motivo = None, "cancelado pelo usuário"
    db.commit()
    return {"ok": True, "short_abandonado": abertos if abertos > 0 else 0}


@router.get("/dial")
def dial(par: str = "BTCUSDT"):
    """Leitura do dial de hedge agora: barreira (confluência acima), suporte, exaustão (F&G, VWAP z, RSI, VAH, prob. bear), Elliott e recomendação."""
    from core.backtest_hedge import leitura_dial_ao_vivo
    m = get_manager()
    con = m.servicos["connectors"]["simulador"]
    # histórico diário completo (desde 2011 para BTC): o contexto de superciclo precisa de todos os ciclos
    try:
        from services.trader_service import TraderService
        d1 = TraderService(con)._diario(par)
    except Exception:
        d1 = []
    if len(d1) < 800:
        d1 = con.obter_ohlcv(par, "1d", 800, somente_fechados=True)
    fg = None
    try:
        fg = (m.servicos["sentimento"].fear_greed() or {}).get("valor")
    except Exception:
        pass
    return leitura_dial_ao_vivo(d1, fg)


@router.post("/backtest")
def backtest(desde: str = "2022-01-01", exigir_corretivo: bool = True, bloquear_ciclo_bull: bool = True, saida_estrutural: bool = False,
             subfatias: int = 3):
    """Backtest da grade inversa (sem stop) em BTC, no histórico 4h da Bitstamp."""
    import os
    from datetime import datetime, timezone
    import pandas as pd
    from core.backtest_grade import BacktestGrade
    caminho = os.path.join("data", "historico", "BTCUSD_bitstamp_4h.csv")
    if not os.path.exists(caminho):
        raise HTTPException(400, "histórico 4h ausente: rode scripts/baixar_historico.py --tf 4h")
    df = pd.read_csv(caminho).sort_values("timestamp")
    h4 = df[["timestamp", "open", "high", "low", "close", "volume"]].values.tolist()
    desde_ms = int(datetime.fromisoformat(desde).replace(tzinfo=timezone.utc).timestamp() * 1000)
    bt = BacktestGrade(h4, desde_ms=desde_ms, exigir_corretivo=exigir_corretivo, bloquear_ciclo_bull=bloquear_ciclo_bull,
                       saida_estrutural=saida_estrutural, subfatias=subfatias)
    r = bt.executar()
    r["eventos"] = [e for e in r["eventos"] if e.get("evento")][-50:]
    r["por_ano"] = bt.por_ano().reset_index().to_dict("records")
    return r
