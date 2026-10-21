# api/routes/nuvens_routes.py
"""
As "nuvens" do TRDR no painel (conselho/coletor_livro.py grava, conselho/livro_historico.py agrega).

    GET /api/nuvens/overlay?inicio&fim&exchanges&passo   Order Book Depth Overlay: por passo de tempo, BTC por
                                                        categoria de distância (0–1%, 1–2,5%, 2,5–5%, 5–10%,
                                                        10–25%) somando as exchanges, razão bids/asks e o lado
                                                        com vantagem; `inicio`/`fim` em segundos (epoch, UTC)
    GET /api/nuvens/calor?inicio&fim&exchanges&fator   heatmap de liquidez: só as faixas de preço com ordens
                                                        acima do normal; a intensidade é a cor
    GET /api/nuvens/top?ts&exchanges                    Order Book Top Levels: os 10 maiores níveis por lado,
                                                        somados entre exchanges no mesmo preço (grade de 0,05%)
    GET /api/nuvens/perp?inicio&passo                  livro dos perpétuos (Binance, Bybit, OKX) até 0,1% do preço,
                                                        por vela: o mais fundo que as três APIs públicas alcançam

Só lê os arquivos de dados/livro/; nada aqui toca a internet nem envia ordem. Registros gravados antes das
categorias (20/10/2026) entram aproximados pelas faixas de 0,1% e vêm marcados com `aproximado`.
"""
import time
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from conselho import livro_historico as lh
from conselho.coletor_livro import EXCHANGES
from conselho.coletor_livro_perp import BUSCADORES as PERPS, FAIXA_PCT as FAIXA_PERP, PASTA_LIVRO_PERP

router = APIRouter()

PERIODO_MAXIMO_S = 7 * 86400

# o que cada exchange NÃO alcança: medido em 20/10/2026 e explicado no topo de conselho/coletor_livro.py
LIMITACOES = {
    "coinbase": "level 2 devolve o livro inteiro: alcança as cinco categorias (até 25%) e além.",
    "binance": "depth 5000 (máximo da API pública) pára a ~1% do melhor preço: só a categoria 0–1% é completa; "
               "o websocket @depth manda diferenças sobre esse mesmo snapshot, não o livro inteiro.",
    "bybit": "orderbook 500 (máximo da API v5, REST e websocket) pára a ~0,1%: nenhuma categoria é completa; "
             "serve para o topo do livro, não para paredes distantes.",
}


def _exchanges(texto: str) -> List[str]:
    pedidas = [e.strip().lower() for e in (texto or "").split(",") if e.strip()]
    desconhecidas = [e for e in pedidas if e not in EXCHANGES]
    if desconhecidas:
        raise HTTPException(status_code=400, detail=f"exchanges desconhecidas: {desconhecidas}; válidas: {list(EXCHANGES)}")
    return pedidas or list(EXCHANGES)


@router.get("/overlay")
def overlay(inicio: Optional[int] = Query(None, description="epoch em segundos (UTC); padrão: fim - 24 h"),
            fim: Optional[int] = Query(None, description="epoch em segundos (UTC); padrão: agora"),
            exchanges: str = Query("coinbase,binance,bybit"),
            passo: int = Query(lh.PASSO_OVERLAY_S, ge=30, le=3600, description="segundos por ponto (300 = candle de 5 min)")) -> Dict:
    exs = _exchanges(exchanges)
    fim_s = int(fim) if fim is not None else int(time.time())
    inicio_s = int(inicio) if inicio is not None else fim_s - 86400
    if inicio_s > fim_s:
        raise HTTPException(status_code=400, detail="inicio depois do fim")
    if fim_s - inicio_s > PERIODO_MAXIMO_S:
        raise HTTPException(status_code=400, detail=f"período máximo de {PERIODO_MAXIMO_S // 86400} dias")
    serie = lh.serie_overlay(inicio_s, fim_s, exs, passo_s=passo)
    return {
        "inicio": inicio_s, "fim": fim_s, "exchanges": exs,
        **serie,
        "ultimo_ts": lh.ultimo_ts(exs),
        "limitacoes": {ex: LIMITACOES[ex] for ex in exs},
    }


@router.get("/top")
def top(ts: Optional[int] = Query(None, description="epoch em segundos (UTC); padrão: o último snapshot gravado"),
        exchanges: str = Query("coinbase,binance,bybit")) -> Dict:
    exs = _exchanges(exchanges)
    return {**lh.top_agregado(ts, exs), "exchanges_pedidas": exs}


@router.get("/calor")
def calor(inicio: Optional[int] = Query(None, description="epoch em segundos (UTC); padrão: fim - 24 h"),
          fim: Optional[int] = Query(None, description="epoch em segundos (UTC); padrão: agora"),
          exchanges: str = Query("coinbase,binance,bybit"),
          passo: int = Query(lh.PASSO_OVERLAY_S, ge=30, le=3600, description="segundos por coluna (300 = candle de 5 min)"),
          fator: float = Query(lh.FATOR_MIN_CALOR, ge=1.0, le=20.0, description="só acende com N vezes o normal da distância"),
          btc: float = Query(lh.BTC_MIN_CALOR, ge=0.0, le=1000.0, description="quantidade mínima na célula")) -> Dict:
    """Heatmap de liquidez: células de preço com ordens acima do normal (mediana 24 h na mesma distância do mid)."""
    exs = _exchanges(exchanges)
    fim_s = int(fim) if fim is not None else int(time.time())
    inicio_s = int(inicio) if inicio is not None else fim_s - 86400
    if inicio_s > fim_s:
        raise HTTPException(status_code=400, detail="inicio depois do fim")
    if fim_s - inicio_s > PERIODO_MAXIMO_S:
        raise HTTPException(status_code=400, detail=f"período máximo de {PERIODO_MAXIMO_S // 86400} dias")
    mapa = lh.mapa_calor(inicio_s, fim_s, exs, passo_s=passo, fator_min=fator, btc_min=btc)
    return {"inicio": inicio_s, "fim": fim_s, **mapa, "limitacoes": {ex: LIMITACOES[ex] for ex in exs}}


@router.get("/perp")
def perp(inicio: Optional[int] = Query(None, description="epoch em segundos (UTC); padrão: agora - 24 h"),
         passo: int = Query(lh.PASSO_OVERLAY_S, ge=60, le=14400, description="segundos por vela")) -> Dict:
    """Por vela: média de cada corretora no período da vela, somada entre as corretoras presentes."""
    fim_s = int(time.time())
    inicio_s = int(inicio) if inicio is not None else fim_s - 86400
    if fim_s - inicio_s > PERIODO_MAXIMO_S:
        raise HTTPException(status_code=400, detail=f"período máximo de {PERIODO_MAXIMO_S // 86400} dias")
    por_vela: Dict[int, Dict[str, List[Dict]]] = {}
    for ex in PERPS:
        for r in lh.carregar_periodo(ex, inicio_s, fim_s, PASTA_LIVRO_PERP):
            por_vela.setdefault(int(r["ts"]) // passo * passo, {}).setdefault(ex, []).append(r)
    velas = []
    for t in sorted(por_vela):
        exs = por_vela[t]
        velas.append({"ts": t, "exchanges": sorted(exs),
                      "bids": round(sum(sum(r["bids"] for r in rs) / len(rs) for rs in exs.values()), 3),
                      "asks": round(sum(sum(r["asks"] for r in rs) / len(rs) for rs in exs.values()), 3)})
    return {"inicio": inicio_s, "fim": fim_s, "passo_s": passo, "faixa_pct": FAIXA_PERP, "exchanges": list(PERPS), "velas": velas}
