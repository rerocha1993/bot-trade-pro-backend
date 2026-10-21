# conselho/fluxo.py
"""
Leituras de fluxo sobre os negócios gravados (conselho/coletor_negocios.py) e o livro (conselho/livro_historico.py).

1. ``barras``: velas de N minutos com o footprint somado (compra e venda a mercado por faixa de US$ 20).

2. ``presos``: a leitura de footprint do Tradeiros (live xc2nq9ti8Ns, docs/tradeiros/presos_footprint.md).
   Compradores presos numa vela = um NÓ de compra a mercado (volume comprador da faixa >= ``FATOR_NO`` × a mediana
   das faixas da vela e >= ``BTC_MIN_NO``) no terço de cima da vela, e a vela fecha abaixo do nó (o nó foi absorvido).
   A marca fica "confirmada" quando as ``N_ABANDONO`` velas seguintes fecham pelo menos ``ABANDONO_PCT`` abaixo do
   nó (o preço abandonou quem comprou ali). Vendedores presos é o espelho.

3. ``absorcao``: a "distorção" que o usuário descreveu (20/10/2026): muita gente comprando a mercado e alavancada
   contra uma parede grande de venda no livro, e o preço sem atravessar. Numa vela de 5 min, as quatro juntas:
      a) parede de venda no livro com intensidade >= ``FATOR_PAREDE`` × o normal (mapa de calor), cujo início está
         a no máximo ``ENCOSTOU_PCT`` acima da máxima da vela (o preço foi até ela);
      b) delta comprador da vela >= ``Z_DELTA`` × o desvio típico do delta nas últimas 24 h (agressão fora do normal);
      c) open interest da Bybit subindo nos últimos 15 min (alavancagem entrando);
      d) a vela fecha abaixo da parede (não atravessou).
   O espelho (parede de compra, delta vendedor, OI subindo, fecha acima) é a absorção no fundo.

Nada disso foi medido contra sorteio ainda (o histórico de livro começou em 20/10/2026): é leitura para o olho, sem %.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional

import numpy as np

from conselho import livro_historico as lh
from conselho.coletor_negocios import PASTA_NEGOCIOS

FATOR_NO = 3.0
BTC_MIN_NO = 5.0
N_ABANDONO = 2
ABANDONO_PCT = 0.003
FATOR_PAREDE = 4.0
ENCOSTOU_PCT = 0.0015
Z_DELTA = 2.0
JANELA_DELTA_S = 24 * 3600


def carregar_minutos(exchanges: Iterable[str], ts_inicio: float, ts_fim: float, raiz: str = PASTA_NEGOCIOS) -> Dict[str, List[Dict]]:
    return {ex: lh.carregar_periodo(ex, ts_inicio, ts_fim, raiz) for ex in exchanges}


def barras(minutos_por_ex: Dict[str, List[Dict]], passo_s: int = 300, preco_de: Optional[str] = None) -> List[Dict]:
    """
    Junta os minutos em velas de ``passo_s`` segundos, somando compra, venda e o footprint de todas as exchanges.
    O OHLC vem de ``preco_de`` (padrão: a primeira exchange da lista que tiver o minuto), para não misturar USD e USDT.
    """
    exs = list(minutos_por_ex)
    ref = preco_de or (exs[0] if exs else None)
    out: Dict[int, Dict] = {}
    for ex, regs in minutos_por_ex.items():
        for r in regs:
            k = (int(r["ts"]) // passo_s) * passo_s
            b = out.setdefault(k, {"ts": k, "compra": 0.0, "venda": 0.0, "niveis": {}, "_ohlc": []})
            b["compra"] += float(r["compra"])
            b["venda"] += float(r["venda"])
            for f, c, v in r["niveis"]:
                nv = b["niveis"].setdefault(float(f), [0.0, 0.0])
                nv[0] += float(c)
                nv[1] += float(v)
            if ex == ref:
                b["_ohlc"].append((int(r["ts"]), float(r["abertura"]), float(r["maxima"]), float(r["minima"]), float(r["fechamento"])))
    saida = []
    for k in sorted(out):
        b = out.pop(k)
        o = sorted(b.pop("_ohlc"))
        if not o:
            continue
        b.update(abertura=o[0][1], maxima=max(x[2] for x in o), minima=min(x[3] for x in o), fechamento=o[-1][4])
        b["delta"] = b["compra"] - b["venda"]
        saida.append(b)
    return saida


def presos(velas: List[Dict], fator: float = FATOR_NO, btc_min: float = BTC_MIN_NO, n_abandono: int = N_ABANDONO,
           abandono_pct: float = ABANDONO_PCT, passo_s: Optional[int] = None) -> List[Dict]:
    """
    Velas com compradores ou vendedores presos (ver o topo do módulo). ``confirmado`` None = é uma das últimas velas e
    as seguintes ainda não fecharam. Se faltam dados logo depois da vela (buraco na coleta), a marca não sai.
    """
    if passo_s is None:
        passo_s = (velas[1]["ts"] - velas[0]["ts"]) if len(velas) > 1 else 300
    por_ts = {b["ts"]: b for b in velas}
    ultimo_ts = velas[-1]["ts"] if velas else 0
    eventos = []
    for i, b in enumerate(velas):
        niveis = b["niveis"]
        if not niveis:
            continue
        hi, lo, fe = b["maxima"], b["minima"], b["fechamento"]
        amp = hi - lo
        if amp <= 0:
            continue
        compras = np.array([v[0] for v in niveis.values()])
        vendas = np.array([v[1] for v in niveis.values()])
        med_c = float(np.median(compras[compras > 0])) if (compras > 0).any() else 0.0
        med_v = float(np.median(vendas[vendas > 0])) if (vendas > 0).any() else 0.0
        candidatos = []
        for f, (c, v) in niveis.items():
            passo = 20.0
            centro = f + passo / 2
            if med_c > 0 and c >= fator * med_c and c >= btc_min and centro >= hi - amp / 3 and fe < f:
                candidatos.append(("compradores", centro, c, c / med_c))
            if med_v > 0 and v >= fator * med_v and v >= btc_min and centro <= lo + amp / 3 and fe > f + passo:
                candidatos.append(("vendedores", centro, v, v / med_v))
        for lado in ("compradores", "vendedores"):
            do_lado = [c for c in candidatos if c[0] == lado]
            if not do_lado:
                continue
            _, preco, btc, vezes = max(do_lado, key=lambda c: c[2])
            esperadas = [b["ts"] + passo_s * k for k in range(1, n_abandono + 1)]
            seguintes = [por_ts[t] for t in esperadas if t in por_ts]
            if len(seguintes) < n_abandono:
                if esperadas[-1] <= ultimo_ts:
                    continue                    # buraco na coleta logo depois: sem como saber
                confirmado = None
            elif lado == "compradores":
                confirmado = all(s["fechamento"] <= preco * (1 - abandono_pct) for s in seguintes)
            else:
                confirmado = all(s["fechamento"] >= preco * (1 + abandono_pct) for s in seguintes)
            eventos.append({"ts": b["ts"], "lado": lado, "preco": round(preco, 2), "btc": round(btc, 3),
                            "vezes": round(vezes, 1), "confirmado": confirmado})
    return eventos


def _subindo(oi: List[list], ts_s: int, janela_s: int = 900) -> Optional[float]:
    """Variação % do open interest nos ``janela_s`` segundos até o fim da vela; None sem dado."""
    if not oi:
        return None
    ts = np.array([p[0] / 1000.0 for p in oi])
    v = np.array([p[1] for p in oi])
    fim = np.searchsorted(ts, ts_s, side="right") - 1
    ini = np.searchsorted(ts, ts_s - janela_s, side="right") - 1
    if fim < 0 or ini < 0 or v[ini] <= 0:
        return None
    return float(v[fim] / v[ini] - 1) * 100


def absorcao(velas: List[Dict], calor: Dict, oi: List[list], passo_s: int = 300, fator_parede: float = FATOR_PAREDE,
             encostou_pct: float = ENCOSTOU_PCT, z_delta: float = Z_DELTA) -> List[Dict]:
    """
    Velas com absorção (ver o topo do módulo). ``calor`` é a saída de ``livro_historico.mapa_calor`` no mesmo passo;
    ``oi`` é [[ts_ms, oi], ...] de ``conselho.mercado.open_interest``. Cada evento diz até quando a parede ficou de pé
    (``ate_ts``: última coluna seguida em que ainda havia célula no mesmo preço).
    """
    colunas = {c["ts"]: c for c in calor.get("colunas", [])}
    if not velas or not colunas:
        return []
    deltas = np.array([b["delta"] for b in velas])
    tss = np.array([b["ts"] for b in velas])
    eventos = []
    for i, b in enumerate(velas):
        col = colunas.get(b["ts"])
        if not col:
            continue
        janela = deltas[(tss < b["ts"]) & (tss >= b["ts"] - JANELA_DELTA_S)]
        if len(janela) < 24:
            continue
        escala = float(np.median(np.abs(janela - np.median(janela)))) * 1.4826
        if escala <= 0:
            continue
        z = (b["delta"] - float(np.median(janela))) / escala
        var_oi = _subindo(oi, b["ts"] + passo_s)
        if var_oi is None or var_oi <= 0:
            continue
        hi, lo, fe = b["maxima"], b["minima"], b["fechamento"]
        for lo_c, hi_c, lado, btc, inten in col["celulas"]:
            if inten < fator_parede:
                continue
            if lado == 1 and z >= z_delta and hi >= lo_c * (1 - encostou_pct) and fe < lo_c:
                tipo = "venda"          # parede de venda segurou compradores agressivos: compradores presos no topo
            elif lado == 0 and z <= -z_delta and lo <= hi_c * (1 + encostou_pct) and fe > hi_c:
                tipo = "compra"         # parede de compra segurou vendedores agressivos: vendedores presos no fundo
            else:
                continue
            ate = b["ts"]
            for j in range(i + 1, len(velas)):
                prox = colunas.get(velas[j]["ts"])
                if not prox or not any(c[2] == lado and c[0] == lo_c for c in prox["celulas"]):
                    break
                ate = velas[j]["ts"]
            eventos.append({"ts": b["ts"], "ate_ts": ate + passo_s, "tipo": tipo, "baixo": lo_c, "alto": hi_c,
                            "intensidade": inten, "parede_btc": btc, "delta_btc": round(b["delta"], 2),
                            "delta_z": round(z, 1), "oi_var_pct": round(var_oi, 2), "fechamento": fe})
    return eventos


def leitura_recente(agora_s: float, horas: float = 6.0) -> Dict:
    """
    Presos (30 min, Bybit) e absorções (5 min, três corretoras) das últimas ``horas``, com o livro e o open interest
    público da Bybit. Usada pelo serviço de avisos e pelos robôs (uma leitura só, o mesmo resultado).
    """
    from conselho import mercado

    ini = agora_s - horas * 3600
    v30 = barras(carregar_minutos(("bybit",), ini, agora_s), 1800, preco_de="bybit")
    presos_30 = presos(v30, abandono_pct=0.005, passo_s=1800)
    v5 = barras(carregar_minutos(("bybit", "binance", "coinbase"), ini - JANELA_DELTA_S, agora_s), 300, preco_de="bybit")
    calor = lh.mapa_calor(ini, agora_s, passo_s=300)
    oi = mercado.open_interest("BTCUSDT", int((ini - 3600) * 1000), int(agora_s * 1000))
    return {"presos": presos_30, "absorcoes": absorcao(v5, calor, oi, 300), "calor": calor, "oi": oi}
