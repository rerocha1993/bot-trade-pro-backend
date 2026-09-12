# api/routes/posicoes_routes.py
"""
MESA DE POSIÇÕES: tudo que está aberto agora, em todos os robôs, e a intervenção do usuário.

    GET  /posicoes/abertas                    posições abertas com P&L ao vivo, R corrido, escada e stop
    POST /posicoes/{bot_id}/fechar            fecha a mercado (e cancela a escada que sobrou)
    POST /posicoes/{bot_id}/parcial?fracao    realiza uma fração da mão (padrão metade)
    POST /posicoes/{bot_id}/zero-a-zero       leva o stop para o preço de entrada
    POST /posicoes/{bot_id}/stop-alvo?sl&tp   stop e/ou alvo novos, escolhidos pelo usuário
    POST /posicoes/{bot_id}/cancelar-escada   cancela só as ordens de ENTRADA ainda no livro

Quem manda a ordem é sempre a thread do robô: o painel deixa o pedido e acorda o robô (a sessão do banco é dela).
Por isso a intervenção exige o robô rodando — sem isso, a posição ficaria fechada na corretora e aberta no banco.
"""
import time
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.database import get_db
from models.bot import Bot
from models.posicao_bot import PosicaoBot
from services.bot_manager import get_manager

router = APIRouter()

ESPERA_S = 8.0          # quanto o painel espera o robô executar antes de devolver "pendente"


def _preco(par: str) -> Optional[float]:
    try:
        return float(get_manager().servicos["connectors"]["simulador"].obter_preco_atual(par))
    except Exception:
        return None


def _executor(bot_id: int):
    ex = get_manager().executores.get(bot_id)
    if ex is None or not ex.status().get("rodando"):
        raise HTTPException(409, "O robô não está rodando: sem ele, a ordem sairia na corretora e o registro ficaria aberto no banco")
    return ex


def _escada(st: Dict) -> Optional[Dict]:
    """Fatias ainda no livro (robôs 9 e 10) e a ordem limitada pendente do fluxo antigo."""
    for chave in ("fatias", "range"):
        d = (st or {}).get(chave)
        if isinstance(d, dict) and d.get("fatias_pendentes"):
            return {"pendentes": d["fatias_pendentes"], "executadas": d.get("fatias_executadas"), "de": d.get("de"),
                    "precos": d.get("precos_pendentes") or []}
    ped = (st or {}).get("ordem_pendente")
    if ped:
        return {"pendentes": 1, "executadas": 0, "de": 1, "preco": ped.get("preco")}
    return None


@router.get("/abertas")
def abertas(db: Session = Depends(get_db)) -> List[Dict]:
    m = get_manager()
    bots = {b.id: b for b in db.query(Bot).all()}
    linhas = []
    precos: Dict[str, Optional[float]] = {}
    for pos in db.query(PosicaoBot).filter_by(status="aberta").order_by(PosicaoBot.aberto_em.desc()).all():
        bot = bots.get(pos.bot_id)
        st = m.status_bot(pos.bot_id) or {}
        if pos.par not in precos:
            precos[pos.par] = _preco(pos.par)
        preco = precos[pos.par]
        sinal = 1 if pos.direcao == "buy" else -1
        qtd, entrada = float(pos.quantidade or 0), float(pos.preco_entrada or 0)
        parcial = float(pos.pnl_parcial or 0)
        aberto = (preco - entrada) * qtd * sinal if preco else None
        risco = abs(entrada - float(pos.sl_inicial)) if pos.sl_inicial else None
        linhas.append({
            "bot_id": pos.bot_id, "bot": bot.nome if bot else f"#{pos.bot_id}", "estrategia": bot.estrategia if bot else None,
            "modo": pos.modo_execucao, "par": pos.par, "timeframe": bot.timeframe if bot else None,
            "direcao": pos.direcao, "quantidade": qtd, "quantidade_inicial": float(pos.quantidade_inicial or qtd),
            "preco_entrada": entrada, "preco": preco, "sl": pos.sl, "sl_inicial": pos.sl_inicial, "tp": pos.tp,
            "pnl_aberto": round(aberto, 4) if aberto is not None else None, "pnl_parcial": round(parcial, 4),
            "pnl_total": round(aberto + parcial, 4) if aberto is not None else None,
            "r_corrido": round((preco - entrada) * sinal / risco, 2) if (preco and risco) else None,
            "zero_a_zero": bool(pos.sl and abs(float(pos.sl) - entrada) <= entrada * 0.0005),
            "aberto_em": pos.aberto_em, "motivo_entrada": pos.motivo_entrada, "cenario": pos.cenario,
            "rodando": bool(st.get("rodando")), "escada": _escada(st), "id": pos.id,
        })
    return linhas


def _pedir(bot_id: int, acao: str, fracao: Optional[float] = None, motivo: Optional[str] = None,
           dados: Optional[Dict] = None) -> Dict:
    ex = _executor(bot_id)
    token = ex.pedir_intervencao(acao, fracao, motivo, dados)
    limite = time.time() + ESPERA_S
    while time.time() < limite:
        r = ex.resultado_intervencao(token) or {}
        if r.get("status") == "feita":
            return r
        if r.get("status") == "erro":
            raise HTTPException(409, r.get("erro") or "a intervenção falhou")
        time.sleep(0.25)
    return {"status": "pendente", "token": token, "acao": acao,
            "aviso": "o robô está no meio de um ciclo; o pedido roda no próximo"}


@router.post("/{bot_id}/fechar")
def fechar(bot_id: int, motivo: str = Query("Fechamento manual")):
    return _pedir(bot_id, "fechar", motivo=motivo)


@router.post("/{bot_id}/parcial")
def parcial(bot_id: int, fracao: float = Query(0.5, gt=0, le=1), motivo: str = Query("Realização manual")):
    return _pedir(bot_id, "parcial", fracao=fracao, motivo=motivo)


@router.post("/{bot_id}/zero-a-zero")
def zero_a_zero(bot_id: int, motivo: str = Query("Zero a zero manual")):
    return _pedir(bot_id, "zero_a_zero", motivo=motivo)


@router.post("/{bot_id}/stop-alvo")
def stop_alvo(bot_id: int, sl: Optional[float] = Query(None, gt=0), tp: Optional[float] = Query(None, gt=0),
              motivo: str = Query("Stop/alvo ajustados no painel")):
    if sl is None and tp is None:
        raise HTTPException(400, "informe pelo menos o stop (sl) ou o alvo (tp)")
    return _pedir(bot_id, "stop_alvo", motivo=motivo, dados={"sl": sl, "tp": tp})


@router.post("/{bot_id}/cancelar-escada")
def cancelar_escada(bot_id: int, motivo: str = Query("Escada cancelada pelo usuário")):
    return _pedir(bot_id, "cancelar_escada", motivo=motivo)
