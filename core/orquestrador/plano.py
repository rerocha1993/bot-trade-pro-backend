# core/orquestrador/plano.py
"""
O PLANO DE MERCADO do par: a saída do orquestrador (camada 2).

Um plano POR PAR, com direção por grau. Todos os bots do par leem daqui; cada estilo obedece ao grau dele mais o
VETO do superciclo. É função pura: recebe dados prontos e devolve o plano, sem tocar em rede nem em banco
(services/plano_service.py busca os dados e chama isto).

    montar_plano(par, preco, trader, ohlcv_por_tf, ...) -> Dict

Ordem de leitura (a de um trader humano):
    1. superciclo em escala log  -> em que ponto do ciclo estamos (veto de todos)
    2. ciclo semanal manda no primário diário (contagens maduras do TraderService)
    3. indicadores independentes (core/leituras.py) -> níveis e vieses, sem saber uns dos outros
    4. confluência dos níveis -> barreira acima, suporte abaixo, zonas de compra e de venda
    5. exaustão (euforia, preço esticado, fluxo travando) -> permite ou não montar hedge
    -> modo, direção por grau, risco permitido e as zonas onde agir

O plano NÃO decide entrada: diz a direção do grau maior, onde comprar, onde vender e quanto risco é permitido.
O timing continua no motor tático de cada bot (core/strategy_engine.py).
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional, Sequence

from core.hedge_dial import barreiras, exaustao
from core.leituras import (
    Leitura, leitura_elliott, leitura_fibonacci, leitura_order_block, leitura_order_flow, leitura_regime,
    leitura_sentimento, leitura_tpo, leitura_volume_profile, leitura_vwap, niveis_de,
)

# modo -> o que os bots do par podem fazer
MODOS = {
    "acumular": "fundo ou retomada de ciclo: comprar escalonado, não vender, hedge zero",
    "deixar_andar": "impulso de alta imaturo: segurar comprado, não perseguir topo, hedge zero",
    "nao_perseguir": "impulso maduro: comprar só recuo com tamanho reduzido; hedge liberado com exaustão",
    "reduzir": "impulso maduro com contagens virando: reduzir exposição, hedge liberado",
    "hedge": "correção de ciclo confirmada: vender/hedge até o teto, comprar só no alvo",
    "aguardar": "estrutura em dúvida: não abrir posição nova",
}

# estado do superciclo -> (modo base, direção do grau maior, risco permitido)
POR_ESTADO = {
    "fundo_terminal":   ("acumular", "buy", 1.0),
    "novo_impulso":     ("acumular", "buy", 1.0),
    "zona_onda_2":      ("acumular", "buy", 1.0),
    "impulso_alta":     ("deixar_andar", "buy", 1.0),
    "impulso_maduro":   ("nao_perseguir", "hold", 0.5),
    "correcao_inicial": ("hedge", "sell", 1.0),
    "correcao_em_curso": ("hedge", "sell", 0.8),
    "recuo_profundo":   ("aguardar", "hold", 0.5),
}

TETO_HEDGE_POR_MODO = {"acumular": 0.0, "deixar_andar": 0.0, "nao_perseguir": 0.5, "reduzir": 1.0, "hedge": 1.0, "aguardar": 0.0}


def _rsi(closes: Sequence[float], n: int = 14) -> Optional[float]:
    c = [float(x) for x in closes[-(n * 5):]]
    if len(c) < n + 1:
        return None
    ganhos, perdas = [], []
    for i in range(1, len(c)):
        d = c[i] - c[i - 1]
        ganhos.append(max(d, 0.0))
        perdas.append(max(-d, 0.0))
    au = sum(ganhos[:n]) / n
    ad = sum(perdas[:n]) / n
    for i in range(n, len(ganhos)):
        au = (au * (n - 1) + ganhos[i]) / n
        ad = (ad * (n - 1) + perdas[i]) / n
    if ad == 0:
        return 100.0
    return 100 - 100 / (1 + au / ad)


def _zonas(niveis: List[Dict], preco: float, sentido: str, min_fontes: int = 2, n: int = 3) -> List[Dict]:
    """Clusters de confluência de um lado do preço, do mais próximo para o mais distante."""
    lado = [x for x in niveis if (x["preco"] < preco if sentido == "abaixo" else x["preco"] > preco)]
    lado.sort(key=lambda x: abs(x["preco"] - preco))
    clusters: List[Dict] = []
    for x in lado:
        alvo = next((c for c in clusters if abs(c["preco"] - x["preco"]) <= c["preco"] * 0.015), None)
        if alvo:
            k = len(alvo["fontes"])
            alvo["preco"] = (alvo["preco"] * k + x["preco"]) / (k + 1)
            alvo["peso"] += x.get("peso", 1.0)
            alvo["fontes"].append(x["fonte"])
        else:
            clusters.append({"preco": x["preco"], "peso": x.get("peso", 1.0), "fontes": [x["fonte"]]})
    fortes = [c for c in clusters if len(c["fontes"]) >= min_fontes]
    fortes.sort(key=lambda c: abs(c["preco"] - preco))
    return [{"preco": round(c["preco"], 2), "peso": round(c["peso"], 2), "fontes": sorted(set(c["fontes"])),
             "distancia_pct": round((c["preco"] / preco - 1) * 100, 2)} for c in fortes[:n]]


def montar_plano(par: str, preco: float, trader: Optional[Dict], ohlcv_por_tf: Dict[str, Sequence],
                 elliott_por_grau: Optional[Dict[str, Dict]] = None, sentimento: Optional[Dict] = None,
                 order_book: Optional[Dict] = None, trades: Optional[List[Dict]] = None,
                 ohlcv_composto: Optional[Sequence] = None) -> Dict:
    """
    par: 'BTCUSDT'. preco: preço atual. trader: saída de TraderService.leitura (superciclo + contagens maduras).
    ohlcv_por_tf: {'1d': candles, '4h': candles, ...} - o diário sustenta os níveis estruturais.
    elliott_por_grau: {'ciclo': analise, 'primario': analise, 'intermediario': analise} (contagem mestre), opcional.
    """
    ts = int(time.time())
    d1 = list(ohlcv_por_tf.get("1d") or [])
    base = list(ohlcv_composto or d1 or next(iter(ohlcv_por_tf.values()), []))
    if not base:
        return {"par": par, "ts": ts, "preco": preco, "erro": "sem candles para montar o plano", "modo": "aguardar",
                "direcao_grau_maior": "hold", "risco_permitido": 0.0}

    # ---------------------------------------------------------------- 3. indicadores independentes
    leituras: List[Leitura] = [
        leitura_tpo(base[-300:], preco),
        leitura_volume_profile(base[-300:], preco),
        leitura_vwap(base[-200:], preco),
        leitura_order_block(base[-300:], preco),
        leitura_regime(base[-200:]),
    ]
    if order_book or trades:
        leituras.append(leitura_order_flow(order_book or {}, trades or [], base[-200:], "1d"))
    if sentimento:
        leituras.append(leitura_sentimento(sentimento))
    for grau, analise in (elliott_por_grau or {}).items():
        leituras.append(leitura_elliott(analise, preco, nome=f"elliott_{grau}"))
        fase = (analise or {}).get("fase")
        vies = ((analise or {}).get("primario") or {}).get("vies")
        if fase and vies:
            fib = leitura_fibonacci(base[-300:], fase, "buy" if vies == "bull" else "sell")
            fib.fonte = f"fibonacci_{grau}"          # um Fibonacci por grau, sem nomes colididos
            for n in fib.niveis:
                n.fonte = f"{n.fonte}_{grau}"
            leituras.append(fib)

    # ---------------------------------------------------------------- 1 e 2. superciclo e contagens
    sc = (trader or {}).get("superciclo") or {}
    estado = sc.get("estado", "indefinido")
    modo, direcao, risco = POR_ESTADO.get(estado, ("aguardar", "hold", 0.5))
    sub = (trader or {}).get("subordinado") or {}
    prob_bear = float(sub.get("prob_bear") or (trader or {}).get("prob_bear") or 0.0)
    prob_bull = float(sub.get("prob_bull") or (trader or {}).get("prob_bull") or 0.0)

    # ---------------------------------------------------------------- 4. confluência dos níveis
    niveis = niveis_de(leituras)
    # a invalidação e os alvos das hipóteses vivas do trader também são níveis
    for h in ((trader or {}).get("vivas") or [])[:4]:
        if h.get("invalidacao"):
            niveis.append({"preco": float(h["invalidacao"]), "fonte": "trader_invalidacao", "peso": 2.0,
                           "tipo": "resistencia" if h["invalidacao"] > preco else "suporte", "rotulo": "invalidação"})
        for a in (h.get("alvos") or [])[:2]:
            niveis.append({"preco": float(a), "fonte": "trader_alvo", "peso": 1.5,
                           "tipo": "resistencia" if a > preco else "suporte", "rotulo": "alvo"})
    b = barreiras(preco, niveis)
    zonas_compra = _zonas(niveis, preco, "abaixo")
    zonas_venda = _zonas(niveis, preco, "acima")

    # ---------------------------------------------------------------- 5. exaustão
    tpo_dados = next((l.dados for l in leituras if l.fonte == "tpo" and not l.erro), {})
    vwap_dados = next((l.dados for l in leituras if l.fonte == "vwap" and not l.erro), {})
    of_dados = next((l.dados for l in leituras if l.fonte == "order_flow" and not l.erro), {})
    sinais = {
        "fear_greed": (sentimento or {}).get("fear_greed", {}).get("valor") if isinstance((sentimento or {}).get("fear_greed"), dict) else None,
        "vwap_z": vwap_dados.get("z"),
        "acima_vah": (preco > tpo_dados["VAH"]) if tpo_dados.get("VAH") else None,
        "prob_bear": prob_bear,
        "delta_of": of_dados.get("razao_delta"),
        "rsi": _rsi([c[4] for c in base]),
    }
    ex = exaustao(sinais)
    exausto = ex["score"] >= 0.35 and ex.get("confluencias", 0) >= 2

    # ---------------------------------------------------------------- decisão do orquestrador
    motivos = [f"superciclo {estado}: {sc.get('leitura', '')}"]
    # 'nao_perseguir' cobre DOIS casos opostos, e so o primeiro admite compra:
    #   - perna madura com contagens ainda bull -> comprar so recuo, com metade do tamanho
    #   - perna madura com contagens VIRADAS bear, sem exaustao confirmada -> aguardar a barreira
    # Como `pode_comprar` era decidido so pelo nome do modo, o segundo herdava a compra do primeiro. Medido ao
    # vivo: contagens 82% bear, o trader mandando vender, e o plano liberando compra e proibindo venda. Num dia
    # de queda de 2,7% o scalp so podia comprar, comprou cinco recuos e fechou em -70,79; 495 vendas barradas.
    aguardando_barreira = False
    if estado == "impulso_maduro":
        if max(prob_bear, 0.0) >= 0.5 and exausto:
            modo, direcao, risco = "reduzir", "sell", 0.5
            motivos.append(f"contagens viraram (bear {prob_bear:.0%}) com exaustão {ex['score']:.2f}: reduzir e liberar hedge")
        elif max(prob_bear, 0.0) >= 0.5:
            modo, direcao = "nao_perseguir", "hold"
            aguardando_barreira = True
            motivos.append(f"contagens bear {prob_bear:.0%} sem exaustão confirmada: não perseguir, aguardar a "
                           f"barreira — nenhum lado abre posição nova até a exaustão confirmar")
        else:
            motivos.append(f"perna madura mas contagens ainda bull ({prob_bull:.0%}): segurar, comprar só recuo com metade do tamanho")
    elif modo == "acumular":
        motivos.append("fundo ou retomada de ciclo: nenhum bot do par pode vender, nem no perfil turbo")
    elif modo == "hedge":
        motivos.append(f"correção de ciclo: hedge até o teto, comprar só no alvo (bear {prob_bear:.0%})")

    barreira = b.get("resistencia")
    suporte = b.get("suporte")
    if barreira:
        motivos.append(f"barreira {barreira['preco']:,.0f} com {len(barreira['fontes'])} fontes")
    if suporte:
        motivos.append(f"suporte {suporte['preco']:,.0f} com {len(suporte['fontes'])} fontes")

    graus = {}
    for nome, analise in (elliott_por_grau or {}).items():
        a = analise or {}
        pb, pr = float(a.get("prob_bull") or 0), float(a.get("prob_bear") or 0)
        graus[nome] = {"fase": a.get("fase"), "prob_bull": pb, "prob_bear": pr,
                       "vies": "bull" if pb >= 0.6 else "bear" if pr >= 0.6 else "neutro",
                       "primario": (a.get("primario") or {}).get("nome"),
                       "invalidacao": (a.get("primario") or {}).get("invalidacao"),
                       "alvos": (a.get("primario") or {}).get("alvos") or []}
    # os números do TRADER (memória de contagens maduras) ficam ao lado dos da contagem mestre, nunca por cima:
    # são duas leituras diferentes do mesmo grau e o painel deve poder mostrar as duas.
    if trader:
        c = trader.get("ciclo") or {}
        graus.setdefault("ciclo", {})["trader"] = {
            "prob_bull": c.get("prob_bull", 0), "prob_bear": c.get("prob_bear", 0), "primaria": c.get("primaria"),
            "vies": "bull" if c.get("prob_bull", 0) >= 0.6 else "bear" if c.get("prob_bear", 0) >= 0.6 else "neutro",
            "exaurido": c.get("exaurido"),
        }
        graus.setdefault("primario", {})["trader"] = {
            "prob_bull": prob_bull, "prob_bear": prob_bear,
            "vies": "bull" if prob_bull >= 0.6 else "bear" if prob_bear >= 0.6 else "neutro",
            "primaria": ((trader.get("primaria") or {}) or {}).get("nome"),
        }

    return {
        "par": par, "ts": ts, "preco": preco, "estado": estado, "modo": modo, "modo_descricao": MODOS.get(modo, ""),
        "direcao_grau_maior": direcao, "risco_permitido": round(risco, 2),
        "teto_hedge": TETO_HEDGE_POR_MODO.get(modo, 0.0),
        "pode_vender": modo in ("reduzir", "hedge") or estado in ("correcao_inicial", "correcao_em_curso"),
        "pode_comprar": modo in ("acumular", "deixar_andar", "nao_perseguir") and not aguardando_barreira,
        "aguardando_barreira": aguardando_barreira,
        "graus": graus,
        "barreira": barreira, "suporte": suporte,
        "zonas_compra": zonas_compra, "zonas_venda": zonas_venda,
        "exaustao": {"score": ex["score"], "confluencias": ex.get("confluencias", 0), "componentes": ex.get("componentes", {}), "confirmada": exausto},
        "superciclo": sc,
        "leituras": [l.dict() for l in leituras],
        "niveis": sorted(niveis, key=lambda x: -x["preco"]),
        "motivo": " | ".join(m for m in motivos if m),
    }
