# api/routes/fluxo_routes.py
"""
Leituras de fluxo para o gráfico (conselho/fluxo.py):

    GET /api/fluxo/presos?inicio&passo&exchanges     velas com compradores ou vendedores presos no footprint
    GET /api/fluxo/absorcao?inicio                   a "distorção": parede no livro + agressão alavancada contra ela
                                                     + preço travado; é a nuvem que aparece no gráfico

`inicio` e os `ts` da resposta em segundos (UTC). Só lê dados/negocios e dados/livro, mais o open interest público
da Bybit; nada envia ordem.
"""
import time
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from conselho import fluxo, livro_historico as lh, mercado

router = APIRouter()

PERIODO_MAXIMO_S = 7 * 86400
EXCHANGES_NEGOCIOS = ("bybit", "binance", "coinbase")


def _periodo(inicio: Optional[int], fim: Optional[int]):
    fim_s = int(fim) if fim is not None else int(time.time())
    inicio_s = int(inicio) if inicio is not None else fim_s - 86400
    if inicio_s > fim_s or fim_s - inicio_s > PERIODO_MAXIMO_S:
        raise HTTPException(status_code=400, detail="período inválido (máximo de 7 dias)")
    return inicio_s, fim_s


@router.get("/presos")
def presos(inicio: Optional[int] = Query(None), fim: Optional[int] = Query(None),
           passo: int = Query(300, description="segundos por vela: 300 (5 min) ou 1800 (30 min)"),
           exchanges: str = Query("bybit", description="de onde vem o footprint (o print do Tradeiros é o da Bybit)")) -> Dict:
    if passo not in (300, 900, 1800):
        raise HTTPException(status_code=400, detail="passo: 300, 900 ou 1800")
    exs = [e.strip() for e in exchanges.split(",") if e.strip() in EXCHANGES_NEGOCIOS] or ["bybit"]
    inicio_s, fim_s = _periodo(inicio, fim)
    velas = fluxo.barras(fluxo.carregar_minutos(exs, inicio_s, fim_s), passo, preco_de=exs[0])
    abandono = 0.002 if passo <= 300 else 0.004 if passo <= 900 else 0.005
    eventos = fluxo.presos(velas, abandono_pct=abandono, passo_s=passo)
    return {"inicio": inicio_s, "fim": fim_s, "passo_s": passo, "exchanges": exs, "abandono_pct": abandono,
            "velas_com_footprint": len(velas), "primeira_vela": velas[0]["ts"] if velas else None, "eventos": eventos}


@router.get("/absorcao")
def absorcao(inicio: Optional[int] = Query(None), fim: Optional[int] = Query(None)) -> Dict:
    inicio_s, fim_s = _periodo(inicio, fim)
    passo = 300
    # o delta "normal" olha 24 h para trás: carrega um dia a mais de negócios
    velas = fluxo.barras(fluxo.carregar_minutos(EXCHANGES_NEGOCIOS, inicio_s - fluxo.JANELA_DELTA_S, fim_s), passo, preco_de="bybit")
    calor = lh.mapa_calor(inicio_s, fim_s, passo_s=passo)
    try:
        oi = mercado.open_interest("BTCUSDT", (inicio_s - 3600) * 1000, fim_s * 1000)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"open interest da Bybit indisponível: {e}")
    eventos = [e for e in fluxo.absorcao(velas, calor, oi, passo) if e["ts"] >= inicio_s]
    cobertura = sorted({b["ts"] for b in velas if b["ts"] >= inicio_s} & {c["ts"] for c in calor.get("colunas", [])})
    return {"inicio": inicio_s, "fim": fim_s, "passo_s": passo, "eventos": eventos,
            "velas_com_livro_e_negocios": len(cobertura), "desde": cobertura[0] if cobertura else None,
            "criterio": {"parede_vezes": fluxo.FATOR_PAREDE, "delta_z": fluxo.Z_DELTA, "encostou_pct": fluxo.ENCOSTOU_PCT * 100,
                         "oi": "subindo nos 15 min até o fim da vela"}}
