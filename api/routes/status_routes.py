# api/routes/status_routes.py
"""
Estado ao vivo do sistema (para o painel): bots rodando, posições, decisões, análise de Elliott
multi-cenário, sentimento, dados de mercado compostos e diagnóstico da Bybit.
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.database import get_db
from models.bot import Bot
from models.decisao_bot import DecisaoBot
from models.posicao_bot import PosicaoBot
from services.bot_manager import get_manager

router = APIRouter()


@router.get("/")
def status_geral():
    m = get_manager()
    return {"bots": m.status(), "servicos": {"market_data": m.servicos["market_data"].status(),
                                              "telegram": m.servicos["telegram"].ativo}}


@router.get("/bots/{bot_id}")
def status_bot(bot_id: int, db: Session = Depends(get_db)):
    m = get_manager()
    st = m.status_bot(bot_id)
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(404, "Bot não encontrado")
    posicao = db.query(PosicaoBot).filter_by(bot_id=bot_id, status="aberta").order_by(PosicaoBot.id.desc()).first()
    ultima = db.query(DecisaoBot).filter_by(bot_id=bot_id).order_by(DecisaoBot.id.desc()).first()
    return {"bot": bot.as_dict(), "rodando": bool(st and st.get("thread_viva")), "estado": st,
            "posicao": posicao.as_dict() if posicao else None,
            "ultima_decisao": ultima.as_dict() if ultima else None}


@router.get("/bots/{bot_id}/decisoes")
def decisoes(bot_id: int, limite: int = Query(50, le=500), detalhes: bool = False, db: Session = Depends(get_db)):
    rows = db.query(DecisaoBot).filter_by(bot_id=bot_id).order_by(DecisaoBot.id.desc()).limit(limite).all()
    out = []
    for r in rows:
        d = r.as_dict()
        if detalhes and d.get("detalhes"):
            try:
                d["detalhes"] = json.loads(d["detalhes"])
            except Exception:
                pass
        elif not detalhes:
            d.pop("detalhes", None)
        out.append(d)
    return out


@router.get("/bots/{bot_id}/posicoes")
def posicoes(bot_id: int, status: Optional[str] = None, limite: int = Query(100, le=1000), db: Session = Depends(get_db)):
    q = db.query(PosicaoBot).filter_by(bot_id=bot_id)
    if status:
        q = q.filter_by(status=status)
    rows = q.order_by(PosicaoBot.id.desc()).limit(limite).all()
    fechadas = [r for r in rows if r.status == "fechada" and r.pnl is not None]
    ganhos = [r.pnl for r in fechadas if r.pnl > 0]
    perdas = [r.pnl for r in fechadas if r.pnl <= 0]
    resumo = {"total": len(fechadas), "ganhos": len(ganhos), "perdas": len(perdas),
              "taxa_acerto": round(len(ganhos) / len(fechadas), 3) if fechadas else None,
              "pnl_total": round(sum(r.pnl for r in fechadas), 2) if fechadas else 0.0,
              "fator_lucro": round(sum(ganhos) / abs(sum(perdas)), 2) if perdas and sum(perdas) else None}
    return {"resumo": resumo, "posicoes": [r.as_dict() for r in rows]}


@router.get("/elliott")
def analise_elliott(par: str = "BTCUSDT", timeframe: str = "15m", estilo: str = "daytrade", perfil: str = "conservador",
                    multigrau: bool = True):
    from services.elliott_service import ElliottService
    svc = ElliottService(connector=get_manager().servicos["connectors"]["simulador"])
    if multigrau:
        return svc.analisar_multi_grau(par, estilo, timeframe, perfil)
    return svc.analisar(par, timeframe)


@router.get("/elliott/mestre")
def contagem_mestre(par: str = "BTCUSDT", db: Session = Depends(get_db)):
    from services.elliott_mestre_service import ElliottMestreService
    return ElliottMestreService(db, get_manager().servicos["connectors"]["simulador"]).calcular(par)


@router.get("/sentimento")
def sentimento(par: str = "BTCUSDT"):
    return get_manager().servicos["sentimento"].score(par)


@router.get("/mercado/candles")
def candles(par: str = "BTCUSDT", timeframe: str = "15m", limite: int = Query(300, le=1000), composto: bool = False):
    m = get_manager()
    if composto:
        velas = m.servicos["market_data"].ohlcv_composto(par, timeframe, limite)
        return {"fonte": "composto", "cesta": m.servicos["market_data"].status(), "candles": velas}
    return {"fonte": "bybit", "candles": m.servicos["connectors"]["simulador"].obter_ohlcv(par, timeframe, limite)}


@router.get("/mercado/niveis")
def niveis(par: str = "BTCUSDT", timeframe: str = "15m", limite: int = Query(300, le=1000)):
    """TPO, Volume Profile, VWAP e order blocks calculados agora (para desenhar no gráfico)."""
    from core.tpo import TPOProfile
    from core.volume_profile_pro import VolumeProfilePRO
    from core.vwap import VWAPCalculator
    from core.order_block import OrderBlockDetector
    m = get_manager()
    con = m.servicos["connectors"]["simulador"]
    ohlcv = con.obter_ohlcv(par, timeframe, limite, somente_fechados=True)
    try:
        comp = m.servicos["market_data"].ohlcv_composto(par, timeframe, limite)
    except Exception:
        comp = ohlcv
    preco = con.obter_preco_atual(par)
    tp = TPOProfile(comp, bins=30)
    tpo = tp.analisar()
    tpo.pop("freq", None)
    try:
        cont, edges = tp.contagem, tp.edges
        mx = float(max(cont)) or 1.0
        tpo["perfil"] = [{"lo": float(edges[i]), "hi": float(edges[i + 1]), "valor": round(float(cont[i]) / mx, 4)} for i in range(len(cont))]
    except Exception:
        tpo["perfil"] = []
    vp = VolumeProfilePRO(comp)
    vpr = vp.analisar()
    try:
        labels, hist = vp.export_heatmap()
        bw = float(vp.bin_width)
        mx = float(max(hist)) or 1.0
        vpr["perfil"] = [{"lo": float(l) - bw / 2, "hi": float(l) + bw / 2, "valor": round(float(h) / mx, 4)} for l, h in zip(labels, hist)]
    except Exception:
        vpr["perfil"] = []
    vw = VWAPCalculator(ohlcv).vwap_bandas()
    if vw:
        vw["banda_sup"] = vw["bandas"].get("+1σ")
        vw["banda_inf"] = vw["bandas"].get("-1σ")
    out = {"preco": preco, "tpo": tpo, "volume_profile": vpr, "vwap": vw}
    try:
        obd = OrderBlockDetector(ohlcv)
        out["order_blocks"] = {"bullish": obd.identificar_blocks("bullish"), "bearish": obd.identificar_blocks("bearish")}
    except Exception as e:
        out["order_blocks"] = {"erro": str(e)}
    return out


@router.get("/mercado/historico")
def historico(par: str = "BTCUSDT", timeframe: str = "1w", limite: int = Query(6000, le=20000)):
    """Histórico longo (BTC: Bitstamp desde 2011 + Bybit recente) reamostrado em 1d/1w, para a mesa do trader."""
    from core.market_data import reamostrar
    from services.trader_service import TraderService
    m = get_manager()
    d1 = TraderService(m.servicos["connectors"]["simulador"])._diario(par)
    serie = reamostrar(d1, "1d", timeframe) if timeframe != "1d" else d1
    return {"fonte": "bitstamp+bybit" if par.replace("/", "").upper() == "BTCUSDT" else "bybit", "timeframe": timeframe, "candles": serie[-limite:]}


@router.get("/subcontas")
def subcontas(modo: str = "demo", verificar_uid: bool = False, db: Session = Depends(get_db)):
    """
    Quais subcontas os robôs usam e quais já têm chave no ambiente. Nunca devolve o valor da chave.
    Com `verificar_uid=true`, pergunta à Bybit de quem é cada chave e usa o UID real para apontar conflitos.
    """
    from core.conexoes.conexao_bybit import credenciais, nomes_variaveis, subcontas_configuradas
    configuradas = {c["subconta"]: c for c in subcontas_configuradas(modo)}
    linhas = []
    for bot in db.query(Bot).order_by(Bot.id).all():
        sub = (bot.subconta or "principal").lower()
        k, sec = nomes_variaveis(sub, modo)
        linhas.append({"bot_id": bot.id, "bot": bot.nome, "par": bot.ativo, "modo_execucao": bot.modo_execucao,
                       "subconta": sub, "configurada": bool(configuradas.get(sub, {}).get("configurada") or all(credenciais(sub, modo))),
                       "variaveis": [k, sec]})
    # prova de verdade: pergunta à Bybit de quem é cada chave. Dois robôs com o mesmo UID disputam a mesma posição.
    if verificar_uid:
        from core.conexoes.conexao_bybit import BybitConnector
        cache: Dict[str, Dict] = {}
        for l in linhas:
            sub = l["subconta"]
            if sub not in cache:
                try:
                    cache[sub] = BybitConnector(modo, "linear", subconta=sub).info_chave()
                except Exception as e:
                    cache[sub] = {"erro": str(e)[:140]}
            l["chave"] = cache[sub]
            l["uid"] = cache[sub].get("uid")

    # só conta como conflito quem realmente manda ordem: bots em simulador nunca tocam a exchange
    conflitos = {}
    for l in linhas:
        if l["modo_execucao"] == "simulador":
            continue
        chave = (l["par"], l.get("uid") or l["subconta"])
        conflitos.setdefault(chave, []).append(l["bot"])
    return {"modo": modo, "subcontas_no_ambiente": subcontas_configuradas(modo), "bots": linhas,
            "conflitos": [{"par": p, "conta": s, "bots": b} for (p, s), b in conflitos.items() if len(b) > 1],
            "nota": ("conflito = mais de um robô que ENVIA ORDEM no mesmo par e na mesma conta. Na Bybit cada símbolo "
                     "tem uma posição por conta, então eles fechariam a posição um do outro. Bots em simulador "
                     "não contam: nunca tocam a exchange.")}


@router.get("/bybit")
def diagnostico_bybit(modo: str = "simulador"):
    from core.conexoes.conexao_bybit import BybitConnector
    try:
        return BybitConnector(modo).testar_conexao()
    except Exception as e:
        raise HTTPException(400, str(e))
