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


@router.get("/footprint")
def footprint(passo: int = Query(1800, description="segundos por vela: 300, 900 ou 1800"),
              linha: float = Query(50.0, ge=10.0, le=500.0, description="altura da linha de preço em US$"),
              n: int = Query(24, ge=1, le=96, description="quantas velas, das mais recentes"),
              exchanges: str = Query("bybit")) -> Dict:
    """
    Footprint das últimas `n` velas: em cada linha de `linha` US$, o volume agredido de venda e de compra,
    o delta e o POC da vela, mais as marcas de presos (mesma regra de /presos).
    """
    if passo not in (300, 900, 1800):
        raise HTTPException(status_code=400, detail="passo: 300, 900 ou 1800")
    exs = [e.strip() for e in exchanges.split(",") if e.strip() in EXCHANGES_NEGOCIOS] or ["bybit"]
    fim_s = int(time.time())
    inicio_s = fim_s - passo * (n + 4)                   # +4 velas para a confirmação dos presos no começo
    velas = fluxo.barras(fluxo.carregar_minutos(exs, inicio_s, fim_s), passo, preco_de=exs[0])
    abandono = 0.002 if passo <= 300 else 0.004 if passo <= 900 else 0.005
    marcas = {(e["ts"], e["lado"]): e for e in fluxo.presos(velas, abandono_pct=abandono, passo_s=passo)}
    saida = []
    for b in velas[-n:]:
        linhas: Dict[float, list] = {}
        for f, (c, v) in b["niveis"].items():
            k = (f // linha) * linha
            acc = linhas.setdefault(k, [0.0, 0.0])
            acc[0] += c
            acc[1] += v
        ordenadas = sorted(linhas.items())
        poc = max(ordenadas, key=lambda kv: kv[1][0] + kv[1][1])[0] if ordenadas else None
        saida.append({
            "ts": b["ts"], "abertura": b["abertura"], "maxima": b["maxima"], "minima": b["minima"], "fechamento": b["fechamento"],
            "compra": round(b["compra"], 3), "venda": round(b["venda"], 3), "delta": round(b["delta"], 3), "poc": poc,
            "linhas": [[p, round(c, 3), round(v, 3)] for p, (c, v) in ordenadas],
            "presos": [marcas[(b["ts"], lado)] for lado in ("compradores", "vendedores") if (b["ts"], lado) in marcas],
        })
    return {"passo_s": passo, "linha_usd": linha, "exchanges": exs, "velas": saida}
