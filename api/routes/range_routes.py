# api/routes/range_routes.py
"""
O JOGO DO RANGE no painel (core/range_tradeiros.py, core/tpo_sessao.py).

    GET /api/range/contexto?par=BTCUSDT   range do merge adaptativo, perfis diários e de sessão, naked POCs,
                                          toques em cada borda, aceitação, long/short de contas e o plano de agora

É a mesma leitura que o robô 10 faz a cada bloco de 30 min fechado — aqui só para ver. Nada envia ordem.
"""
import time
from typing import Dict, List, Optional

from fastapi import APIRouter, Query

from core.contexto_derivativos import LeitorLSR
from core.range_tradeiros import ParametrosRange, leitura_ao_vivo
from core.tpo_sessao import BLOCO_MS, DIA_MS, Perfil, blocos_30m, dias as perfis_por_dia, naked_pocs, sessoes
from services.bot_manager import get_manager

router = APIRouter()

P = ParametrosRange()
DIAS_HISTORICO = 23
VALIDADE_S = 60
_cache: Dict[str, tuple] = {}
_lsr = LeitorLSR()


def _f(x, dec: int = 1) -> Optional[float]:
    """numpy float não serializa em JSON: sai float puro."""
    return None if x is None else round(float(x), dec)


def _bool(x) -> Optional[bool]:
    return None if x is None else bool(x)


def _niveis(p: Perfil) -> Dict:
    val, vah = p.area_valor()
    return {"inicio": p.inicio, "poc": _f(p.poc()), "val": _f(val), "vah": _f(vah),
            "minima": _f(p.minima), "maxima": _f(p.maxima), "blocos": len(p.blocos)}


def _plano(pl) -> Optional[Dict]:
    if pl is None:
        return None
    return {"lado": int(pl.lado), "jogada": pl.jogada, "niveis": [_f(x) for x in pl.niveis], "stop": _f(pl.stop),
            "alvo1": _f(pl.alvo1), "alvo2": _f(pl.alvo2), "rr": _f(pl.rr, 2), "motivo": pl.motivo}


@router.get("/contexto")
def contexto(par: str = Query("BTCUSDT"), dias: int = Query(10, ge=3, le=20)) -> Dict:
    agora = int(time.time() * 1000)
    guardado = _cache.get(par)
    if guardado and time.time() - guardado[0] < VALIDADE_S:
        return guardado[1]
    con = get_manager().servicos["connectors"]["simulador"]
    candles = con.obter_ohlcv_historico(par, "30m", (agora // DIA_MS - DIAS_HISTORICO) * DIA_MS)
    fechados = [c for c in candles if c[0] + BLOCO_MS <= agora]
    blocos = blocos_30m(fechados)
    perfis: List[Perfil] = perfis_por_dia(fechados)
    lsr = _lsr.contexto()
    leitura = leitura_ao_vivo(blocos, "borda", P, lsr.filtro() if lsr else None)
    ctx, pl = leitura["contexto"], leitura["plano"]
    hoje = perfis[-1] if perfis else None
    fluxo = None
    if lsr:
        fluxo = {"atual": _f(lsr.atual(agora), 3), "mediana_30d": _f(lsr.mediana(agora), 3),
                 "presos_no_val": _bool(lsr.presos_contra(agora, 1)), "presos_no_vah": _bool(lsr.presos_contra(agora, -1))}
    resposta = {
        "par": par, "preco": _f(con.obter_preco_atual(par)), "ate_ms": blocos[-1][0] if blocos else None,
        "range": ({**_niveis_do_contexto(ctx), "dias": int(ctx.dias), "valido": bool(ctx.valido)} if ctx else None),
        "perfis": [{**_niveis(p), "sessoes": {n: _niveis(s) for n, s in sessoes(p).items()}} for p in perfis[-dias:]],
        "hoje": ({**_niveis(hoje), "sessoes": {n: _niveis(s) for n, s in sessoes(hoje).items()}} if hoje else None),
        "naked_pocs": [{"preco": _f(x["preco"]), "dia_ms": x["dia_ms"]} for x in naked_pocs(perfis)],
        "toques": {"val": int((leitura.get("toques") or {}).get(1) or 0), "vah": int((leitura.get("toques") or {}).get(-1) or 0)},
        "aceitacao": int(leitura.get("aceitacao") or 0),
        "long_short": fluxo, "plano": _plano(pl), "barrado": _plano(leitura.get("barrado")), "motivo": leitura["motivo"],
    }
    _cache[par] = (time.time(), resposta)
    return resposta


def _niveis_do_contexto(ctx) -> Dict:
    return {"val": _f(ctx.val), "poc": _f(ctx.poc), "vah": _f(ctx.vah), "minima": _f(ctx.minima), "maxima": _f(ctx.maxima),
            "largura_pct": _f(ctx.largura / ctx.poc * 100, 2) if ctx.poc else None,
            "pocs_diarios": [_f(x) for x in ctx.pocs_diarios]}
