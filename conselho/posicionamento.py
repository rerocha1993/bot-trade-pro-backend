# conselho/posicionamento.py
"""
CVD, open interest e a "distorção de posicionamento" do BTC, por vela, para os painéis da tela Gráfico.

1. CVD (delta acumulado): em cada vela, compra − venda a mercado (quem agrediu), somado vela a vela.
      alavancado   perpétuo BTCUSDT da Binance: as velas da API já trazem o volume do comprador agressor
                   (campo 9 do kline), então o histórico é tão longo quanto o gráfico; + Bybit do nosso coletor
      à vista      BTCUSDT da Binance (mesmo campo) + BTC-USD da Coinbase do nosso coletor (desde 20/10/2026)

2. Open interest: contratos abertos em BTC, somando Binance (openInterestHist, só os últimos 30 dias), Bybit e OKX.
   OI subindo = gente NOVA abrindo posição; caindo = gente fechando (ou sendo liquidada).

   Em velas (como o MMT do Maroja, live de 04/11/2026), separado em LINEAR (perpétuo em USDT, margem em dólar) e
   INVERSE (perpétuo em USD margeado em BTC, onde o Tradeiros diz que entra o dinheiro grande), Binance + Bybit.
   O inverse vem em dólares (contratos de US$ 1 na Bybit, US$ 100 na Binance): a tela converte ao preço de agora,
   para a forma da curva ser a dos contratos e não andar só porque o preço andou.

   Net Positioning (o "NS/NL" do MMT): em cada vela, o OI que entrou ou saiu vai para os longs ou para os shorts
   conforme o lado que agrediu a mercado:
      OI subiu e compraram   -> longs abrindo        OI subiu e venderam -> shorts abrindo
      OI caiu e compraram    -> shorts fechando      OI caiu e venderam  -> longs fechando
   É estimativa (a corretora não diz quem abriu), a mesma conta das plataformas.
   A leitura do Maroja: no fundo, CVD caindo com OI subindo = shorts novos presos ("volume reativo"); na máxima,
   delta positivo com OI saindo = stop, liquidação ou realização, não long novo.

3. Distorção (o que o usuário pediu em 03/11/2026: "o mercado subindo e muita gente shortando"). Olha as últimas
   ``JANELA`` velas:
      de alta    o preço subiu, o perpétuo VENDEU a mercado no saldo (delta / volume <= −``R_MIN``) e o OI subiu:
                 gente abrindo short contra a alta. Se a alta continuar, eles viram combustível (short squeeze).
      de baixa   o espelho: o preço caiu, o perpétuo COMPROU no saldo e o OI subiu: gente abrindo long contra a queda.
   O preço só conta se andou pelo menos o movimento típico da janela (a mediana de |variação| no período pedido),
   para não acender em vela parada. "Spot confirma" = o à vista agrediu a favor do preço (o à vista empurrando e o
   alavancado apostando contra é a leitura clássica do Tradeiros).

Leitura para o olho, sem % de acerto: nada disto foi medido contra sorteio (ver a memória "motor de fluxo sem
vantagem"); os robôs não usam.
"""
from __future__ import annotations

import logging
from bisect import bisect_right
from statistics import median
from typing import Dict, Iterable, List, Optional, Tuple

import requests

from conselho import livro_historico as lh
from conselho.coletor_negocios import PASTA_NEGOCIOS

logger = logging.getLogger(__name__)

TIMEOUT_S = 10.0
CABECALHOS = {"User-Agent": "bot-trade-pro/1.0 (conselho)"}
JANELA = 6                  # velas que a distorção olha para trás
PERCENTIL = 50.0            # "contra o preço" forte = acima da mediana das janelas em que ele foi contra (no período)
OI_MIN_PCT = 0.0            # OI precisa ter subido (qualquer alta) na janela

# tempo do gráfico (s) → nome do intervalo em cada API; o OI não tem 1 min: usa o de 5 min (fica em degrau)
KLINE = {60: "1m", 300: "5m", 900: "15m", 1800: "30m", 3600: "1h", 14400: "4h"}
OI_BINANCE = {60: "5m", 300: "5m", 900: "15m", 1800: "30m", 3600: "1h", 14400: "4h"}
OI_BYBIT = {60: "5min", 300: "5min", 900: "15min", 1800: "30min", 3600: "1h", 14400: "4h"}
OI_OKX = {60: "5m", 300: "5m", 900: "15m", 1800: "30m", 3600: "1H", 14400: "4H"}
PASSOS = tuple(KLINE)

# velas da Binance com o volume do agressor: mercado -> (url, símbolo, campo do volume em BTC, campo da compra em BTC)
# (no COIN-M os campos 5 e 9 são contratos de US$ 100; os 7 e 10 já vêm em BTC)
KLINES = {"perp": ("https://fapi.binance.com/fapi/v1/klines", "BTCUSDT", 5, 9),
          "spot": ("https://api.binance.com/api/v3/klines", "BTCUSDT", 5, 9),
          "inv": ("https://dapi.binance.com/dapi/v1/klines", "BTCUSD_PERP", 7, 10)}

# OI em velas: de quanto em quanto tempo (s) vêm os pontos para cada tempo do gráfico, para a vela ter máxima e mínima
OI_PONTO = {60: 300, 300: 300, 900: 300, 1800: 300, 3600: 900, 14400: 3600}
PERIODO_BINANCE = {300: "5m", 900: "15m", 3600: "1h"}
PERIODO_BYBIT = {300: "5min", 900: "15min", 3600: "1h"}
USD_POR_CONTRATO_COINM = 100.0


def _json(url: str, params: dict):
    r = requests.get(url, params=params, headers=CABECALHOS, timeout=TIMEOUT_S)
    r.raise_for_status()
    return r.json()


# ------------------------------------------------------------------------------------------------ busca
def velas_agressao(mercado: str, passo: int, inicio_s: int, fim_s: int) -> Dict[int, Dict]:
    """Velas da Binance (``mercado`` em KLINES) com o volume do comprador agressor: {ts_s: {fechamento, volume, compra}},
    volume e compra em BTC."""
    url, simbolo, i_vol, i_compra = KLINES[mercado]
    saida: Dict[int, Dict] = {}
    desde = inicio_s
    while desde <= fim_s:
        lote = _json(url, {"symbol": simbolo, "interval": KLINE[passo], "startTime": desde * 1000,
                           "endTime": fim_s * 1000, "limit": 1000})
        for c in lote:
            saida[int(c[0]) // 1000] = {"fechamento": float(c[4]), "volume": float(c[i_vol]),
                                        "compra": float(c[i_compra])}
        if len(lote) < 1000:
            break
        desde = int(lote[-1][0]) // 1000 + passo
    return saida


def _binance_hist(caminho: str, periodo: str, inicio_s: int, fim_s: int, campo: str,
                  base: str = "https://fapi.binance.com", filtro: Optional[dict] = None) -> Dict[int, float]:
    """Séries /futures/data da Binance (só 30 dias): a API devolve as 500 MAIS NOVAS do trecho, então pagina para trás."""
    saida: Dict[int, float] = {}
    fim = fim_s * 1000
    while fim >= inicio_s * 1000:
        lote = _json(base + "/futures/data/" + caminho,
                     {**(filtro or {"symbol": "BTCUSDT"}), "period": periodo, "startTime": inicio_s * 1000,
                      "endTime": fim, "limit": 500})
        for p in lote:
            saida[int(p["timestamp"]) // 1000] = float(p[campo])
        if len(lote) < 500:
            break
        fim = min(int(p["timestamp"]) for p in lote) - 1
    return saida


def oi_binance(passo: int, inicio_s: int, fim_s: int) -> Dict[int, float]:
    """Open interest do perpétuo BTCUSDT da Binance em BTC."""
    return _binance_hist("openInterestHist", OI_BINANCE[passo], inicio_s, fim_s, "sumOpenInterest")


def contas_binance(passo: int, inicio_s: int, fim_s: int) -> Dict[int, float]:
    """Fração das contas do perpétuo da Binance que estão COMPRADAS (0 a 1); o resto está vendido."""
    return _binance_hist("globalLongShortAccountRatio", OI_BINANCE[passo], inicio_s, fim_s, "longAccount")


def oi_bybit(passo: int, inicio_s: int, fim_s: int, inverse: bool = False,
             intervalo: Optional[str] = None) -> Dict[int, float]:
    """Open interest do perpétuo da Bybit (a API pagina do mais novo para o mais velho): BTCUSDT em BTC, ou o inverse
    BTCUSD em dólares (contratos de US$ 1)."""
    saida: Dict[int, float] = {}
    fim = fim_s * 1000
    while fim >= inicio_s * 1000:
        res = _json("https://api.bybit.com/v5/market/open-interest",
                    {"category": "inverse" if inverse else "linear", "symbol": "BTCUSD" if inverse else "BTCUSDT",
                     "intervalTime": intervalo or OI_BYBIT[passo],
                     "startTime": inicio_s * 1000, "endTime": fim, "limit": 200})
        lista = (res.get("result") or {}).get("list") or []
        for p in lista:
            saida[int(p["timestamp"]) // 1000] = float(p["openInterest"])
        if len(lista) < 200:
            break
        fim = min(int(p["timestamp"]) for p in lista) - 1
    return saida


def oi_okx(passo: int, inicio_s: int, fim_s: int) -> Dict[int, float]:
    """Open interest do BTC-USDT-SWAP da OKX em BTC (100 por chamada; a API devolve zeros em alguns horários)."""
    saida: Dict[int, float] = {}
    fim = fim_s * 1000
    while fim >= inicio_s * 1000:
        res = _json("https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-history",
                    {"instId": "BTC-USDT-SWAP", "period": OI_OKX[passo], "begin": inicio_s * 1000, "end": fim,
                     "limit": 100})
        lista = res.get("data") or []
        for ts, _contratos, em_btc, _usd in lista:
            if float(em_btc) > 0:
                saida[int(ts) // 1000] = float(em_btc)
        if len(lista) < 100:
            break
        fim = min(int(x[0]) for x in lista) - 1
    return saida


def oi_pontos(inverse: bool, ponto: int, inicio_s: int, fim_s: int) -> Dict[int, float]:
    """OI de Binance + Bybit somado a cada ``ponto`` segundos: linear em BTC, inverse em dólares."""
    if inverse:
        bin_ = _binance_hist("openInterestHist", PERIODO_BINANCE[ponto], inicio_s, fim_s, "sumOpenInterest",
                             base="https://dapi.binance.com", filtro={"pair": "BTCUSD", "contractType": "PERPETUAL"})
        bin_ = {t: v * USD_POR_CONTRATO_COINM for t, v in bin_.items()}
    else:
        bin_ = _binance_hist("openInterestHist", PERIODO_BINANCE[ponto], inicio_s, fim_s, "sumOpenInterest")
    byb = oi_bybit(0, inicio_s, fim_s, inverse=inverse, intervalo=PERIODO_BYBIT[ponto])
    return somar_na_grade([bin_, byb], ponto, inicio_s, fim_s)


def somar_na_grade(series: List[Dict[int, float]], ponto: int, inicio_s: int, fim_s: int) -> Dict[int, float]:
    """A soma das séries em cada ponto da grade de ``ponto`` segundos: o último valor de cada uma até ali (no máximo
    2 pontos de atraso). O ponto só existe quando TODAS têm valor, para a soma não pular de nível."""
    chaves = [sorted(s) for s in series]
    saida: Dict[int, float] = {}
    for p in range(-(-inicio_s // ponto) * ponto, fim_s + 1, ponto):
        total = 0.0
        for s, ks in zip(series, chaves):
            k = bisect_right(ks, p) - 1
            if k < 0 or p - ks[k] > 2 * ponto:
                break
            total += s[ks[k]]
        else:
            saida[p] = total
    return saida


def velas_oi(pontos: Dict[int, float], passo: int, tempos: Iterable[int]) -> Dict[int, Optional[List[float]]]:
    """[abertura, máxima, mínima, fechamento] do OI em cada vela: abre no último ponto até o começo dela e fecha no
    último até o fim (o fechamento de uma é a abertura da seguinte); a máxima e a mínima vêm dos pontos de dentro.
    Sem ponto até 2 velas antes do começo, abre no primeiro de dentro."""
    ks = sorted(pontos)
    saida: Dict[int, Optional[List[float]]] = {}
    for t in tempos:
        i0, i1 = bisect_right(ks, t) - 1, bisect_right(ks, t + passo) - 1
        primeiro = i0 if i0 >= 0 and t - ks[i0] <= 2 * passo else i0 + 1
        vals = [pontos[ks[k]] for k in range(primeiro, i1 + 1)]
        saida[t] = [round(vals[0], 1), round(max(vals), 1), round(min(vals), 1), round(vals[-1], 1)] if vals else None
    return saida


def posicionamento_liquido(d_oi: float, delta: float) -> Tuple[float, float]:
    """(longs, shorts) que entraram (+) ou saíram (-) na vela, pelo OI e pelo lado que agrediu (ver o topo do arquivo)."""
    if d_oi == 0 or delta == 0:
        return 0.0, 0.0
    return (d_oi, 0.0) if (d_oi > 0) == (delta > 0) else (0.0, d_oi)


def _delta_coletor(exchange: str, passo: int, inicio_s: int, fim_s: int) -> Dict[int, Dict]:
    """Compra e venda a mercado por vela, dos minutos gravados pelo nosso coletor de negócios, e o fechamento (o
    último preço do último minuto com negócio)."""
    saida: Dict[int, Dict] = {}
    for r in sorted(lh.carregar_periodo(exchange, inicio_s, fim_s, PASTA_NEGOCIOS), key=lambda r: r["ts"]):
        t = int(r["ts"]) // passo * passo
        v = saida.setdefault(t, {"compra": 0.0, "venda": 0.0, "fechamento": None})
        v["compra"] += float(r["compra"])
        v["venda"] += float(r["venda"])
        if r.get("fechamento"):
            v["fechamento"] = float(r["fechamento"])
    return saida


def _degrau(serie: Dict[int, float], tempos: Iterable[int]) -> Dict[int, Optional[float]]:
    """O último valor conhecido até cada tempo (o OI de 5 min nas velas de 1 min), sem passar de 2 h de atraso."""
    chaves = sorted(serie)
    saida, k = {}, -1
    for t in sorted(tempos):
        while k + 1 < len(chaves) and chaves[k + 1] <= t:
            k += 1
        saida[t] = serie[chaves[k]] if k >= 0 and t - chaves[k] <= 7200 else None
    return saida


def trecho(passo: int, inicio_s: int, fim_s: int) -> List[Dict]:
    """
    Uma linha por vela de [inicio_s, fim_s]: fechamento (perpétuo da Binance), compra/venda do perpétuo e do à vista
    por fonte e o OI de cada corretora. Uma fonte fora do ar vira None naquela coluna, sem derrubar o resto.
    """
    if passo not in KLINE:
        raise ValueError(f"passo: {list(KLINE)}")
    perp = velas_agressao("perp", passo, inicio_s, fim_s)
    tempos = sorted(perp)
    ponto = OI_PONTO[passo]
    extras = {"spot": lambda: velas_agressao("spot", passo, inicio_s, fim_s),
              "inv": lambda: velas_agressao("inv", passo, inicio_s, fim_s),
              "bybit": lambda: _delta_coletor("bybit", passo, inicio_s, fim_s),
              "bybit_inv": lambda: _delta_coletor("bybit_inv", passo, inicio_s, fim_s),
              "oi_lin": lambda: velas_oi(oi_pontos(False, ponto, inicio_s - 2 * ponto, fim_s + passo), passo, tempos),
              "oi_inv": lambda: velas_oi(oi_pontos(True, ponto, inicio_s - 2 * ponto, fim_s + passo), passo, tempos),
              "coinbase": lambda: _delta_coletor("coinbase", passo, inicio_s, fim_s),
              "oi_binance": lambda: _degrau(oi_binance(passo, inicio_s - 3600, fim_s), tempos),
              "oi_bybit": lambda: _degrau(oi_bybit(passo, inicio_s - 3600, fim_s), tempos),
              "oi_okx": lambda: _degrau(oi_okx(passo, inicio_s - 3600, fim_s), tempos),
              "contas": lambda: _degrau(contas_binance(passo, inicio_s - 3600, fim_s), tempos)}
    dados = {}
    for nome, f in extras.items():
        try:
            dados[nome] = f()
        except Exception as e:      # uma corretora fora do ar não derruba o painel
            logger.warning("posicionamento: %s indisponível: %s", nome, e)
            dados[nome] = {}
    linhas = []
    for t in tempos:
        p, s = perp[t], dados["spot"].get(t)
        by, cb = dados["bybit"].get(t), dados["coinbase"].get(t)
        iv, byi = dados["inv"].get(t), dados["bybit_inv"].get(t)
        oi_lin, oi_inv = dados["oi_lin"].get(t), dados["oi_inv"].get(t)
        # Net Positioning de cada grupo: o OI da vela (o inverse em BTC ao preço dela) e o saldo a mercado das fontes
        np_ = {}
        for grupo, oi_v, partes in (
                ("lin", oi_lin, [(p["compra"], p["volume"] - p["compra"]), by and (by["compra"], by["venda"])]),
                ("inv", oi_inv, [iv and (iv["compra"], iv["volume"] - iv["compra"]), byi and (byi["compra"], byi["venda"])])):
            partes = [x for x in partes if x]
            if oi_v and partes:
                d_oi = (oi_v[3] - oi_v[0]) / (p["fechamento"] if grupo == "inv" else 1.0)
                np_[grupo] = [round(x, 2) for x in posicionamento_liquido(d_oi, sum(c - v for c, v in partes))]
        linhas.append({
            "ts": t, "fechamento": p["fechamento"],
            "perp_binance": [round(p["compra"], 3), round(p["volume"] - p["compra"], 3)],
            "perp_bybit": [round(by["compra"], 3), round(by["venda"], 3)] if by else None,
            "spot_binance": [round(s["compra"], 3), round(s["volume"] - s["compra"], 3)] if s else None,
            "spot_coinbase": [round(cb["compra"], 3), round(cb["venda"], 3)] if cb else None,
            # prêmio da Coinbase (o COINBASE_PREMIUM do aggr.trade): BTC-USD da Coinbase − BTCUSDT à vista da Binance, em
            # dólares; negativo = o americano vendendo mais que o resto (ou a Binance comprando)
            "premio": round(cb["fechamento"] - s["fechamento"], 2) if cb and cb.get("fechamento") and s else None,
            "inv_binance": [round(iv["compra"], 3), round(iv["volume"] - iv["compra"], 3)] if iv else None,
            "inv_bybit": [round(byi["compra"], 3), round(byi["venda"], 3)] if byi else None,
            "oi_lin": oi_lin, "oi_inv": oi_inv, "np": np_ or None,
            "oi": {ex: (round(dados[f"oi_{ex}"].get(t), 1) if dados[f"oi_{ex}"].get(t) is not None else None)
                   for ex in ("binance", "bybit", "okx")},
            "contas_long": round(dados["contas"][t], 4) if dados["contas"].get(t) is not None else None,
        })
    return linhas


# ------------------------------------------------------------------------------------------------ leitura
def _soma(linha: Dict, chaves: Iterable[str]):
    """(compra, venda) somados das fontes presentes na vela; None se nenhuma tiver."""
    pares = [linha[k] for k in chaves if linha.get(k)]
    if not pares:
        return None
    return sum(c for c, _ in pares), sum(v for _, v in pares)


def oi_total(linha: Dict) -> Optional[float]:
    """OI somado das corretoras; só quando as três têm valor (senão a soma pularia de nível ao trocar de fonte)."""
    vals = list(linha["oi"].values())
    return round(sum(vals), 1) if vals and all(v is not None for v in vals) else None


def variacao_oi(antes: Dict, depois: Dict) -> Optional[float]:
    """Variação do OI entre duas velas: a média das variações das corretoras que têm as duas pontas, pesada pelo
    tamanho (a OKX só tem 5 dias de 5 min; assim a janela não depende de todas estarem lá)."""
    pares = [(antes["oi"][ex], depois["oi"][ex]) for ex in antes["oi"]
             if antes["oi"].get(ex) and depois["oi"].get(ex)]
    base = sum(a for a, _ in pares)
    return sum(d - a for a, d in pares) / base if base > 0 else None


def _percentil(valores: List[float], q: float) -> Optional[float]:
    v = sorted(valores)
    return v[min(len(v) - 1, int(len(v) * q / 100))] if v else None


def _janela(linhas: List[Dict], i: int, janela: int) -> Dict:
    """Os números de uma janela de ``janela`` velas terminando em i."""
    trecho_ = linhas[i - janela + 1: i + 1]
    p0, p1 = linhas[i - janela]["fechamento"], linhas[i]["fechamento"]
    perp = [x for x in (_soma(l, ("perp_binance", "perp_bybit")) for l in trecho_) if x]
    spot = [x for x in (_soma(l, ("spot_binance", "spot_coinbase")) for l in trecho_) if x]
    vol_p, vol_s = sum(c + v for c, v in perp), sum(c + v for c, v in spot)
    c0, c1 = linhas[i - janela].get("contas_long"), linhas[i].get("contas_long")
    return {"preco": p1 / p0 - 1 if p0 > 0 else 0.0,
            "perp": sum(c - v for c, v in perp) / vol_p if vol_p > 0 else None,
            "spot": sum(c - v for c, v in spot) / vol_s if vol_s > 0 else None,
            "oi": variacao_oi(linhas[i - janela], linhas[i]),
            "contas": c1 - c0 if c0 is not None and c1 is not None else None}


def _contra(js, campo: str) -> List[float]:
    """|valor| das janelas em que ``campo`` foi CONTRA o preço (subiu e venderam, caiu e compraram)."""
    return [abs(j[campo]) for j in (x[1] if isinstance(x, tuple) else x for x in js)
            if j[campo] is not None and j["preco"] != 0 and (j[campo] > 0) != (j["preco"] > 0)]


def distorcao(linhas: List[Dict], janela: int = JANELA, percentil: float = PERCENTIL,
              oi_min_pct: float = OI_MIN_PCT) -> List[Dict]:
    """
    A leitura de cada vela (a partir da ``janela``-ésima): variação do preço, saldo do perpétuo e do à vista sobre o
    volume, variação do OI e das contas compradas, e ``lado`` = "alta" / "baixa" quando a distorção acende.

    Os limites saem do próprio período: o preço precisa ter andado pelo menos a mediana dos movimentos, e o
    perpétuo (ou as contas) precisa ter ido contra o preço mais forte que ``percentil``% das janelas em que foi contra
    (no período pedido). ``por`` diz qual
    das duas acendeu: "agressao" (venderam / compraram a mercado) ou "contas" (mais contas do lado oposto).
    """
    js = [(i, _janela(linhas, i, janela)) for i in range(janela, len(linhas))]
    tipico = median([abs(j["preco"]) for _, j in js]) if js else 0.0
    lim_perp = _percentil(_contra(js, "perp"), percentil)
    lim_contas = _percentil(_contra(js, "contas"), percentil)
    saida = []
    for i, j in js:
        lado, por = None, []
        if j["oi"] is not None and abs(j["preco"]) >= tipico and j["preco"] != 0 and j["oi"] * 100 > oi_min_pct:
            sinal = 1 if j["preco"] > 0 else -1
            if j["perp"] is not None and lim_perp and -sinal * j["perp"] >= lim_perp:
                por.append("agressao")
            if j["contas"] is not None and lim_contas and -sinal * j["contas"] >= lim_contas:
                por.append("contas")
            if por:
                lado = "alta" if sinal > 0 else "baixa"
        saida.append({
            "ts": linhas[i]["ts"], "lado": lado, "por": por,
            "preco_pct": round(j["preco"] * 100, 3),
            "perp_pct": round(j["perp"] * 100, 1) if j["perp"] is not None else None,
            "spot_pct": round(j["spot"] * 100, 1) if j["spot"] is not None else None,
            "oi_pct": round(j["oi"] * 100, 3) if j["oi"] is not None else None,
            "contas_pp": round(j["contas"] * 100, 2) if j["contas"] is not None else None,
            "spot_confirma": bool(lado and j["spot"] is not None and (j["spot"] > 0) == (j["preco"] > 0)),
        })
    return saida


def limites(linhas: List[Dict], janela: int = JANELA, percentil: float = PERCENTIL) -> Dict:
    """Os limites que ``distorcao`` usou no período, para o painel mostrar."""
    js = [_janela(linhas, i, janela) for i in range(janela, len(linhas))]
    def pct(v, q):
        x = _percentil(v, q)
        return round(x * 100, 3) if x is not None else None
    return {"janela_velas": janela, "percentil": percentil,
            "preco_pct": round(median([abs(j["preco"]) for j in js]) * 100, 3) if js else None,
            "perp_pct": pct(_contra(js, "perp"), percentil),
            "contas_pp": pct(_contra(js, "contas"), percentil)}
