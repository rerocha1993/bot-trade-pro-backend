# core/elliott_pro/multidegree.py
"""
Análise multi-grau (fractal): o grau OPERACIONAL do bot (scalp / daytrade / swing) precisa estar
alinhado ao grau de CONTEXTO e é informado pelo grau MACRO.

Exemplo: o swing enxerga uma onda 3 maior de alta (4h). Dentro dela o daytrade vê um 1-2-3-4-5
menor (15m/30m) e o scalp vê as subondas de 1m/5m. Todos operam na mesma direção, mas cada um
entra e sai nas suas próprias ondas.

Regras de alinhamento:
    - conservador: direção operacional == consenso do contexto (ou contexto neutro sem fase proibida)
    - turbo: aceita contexto neutro/contrário, mas marca `contra_tendencia` (o executor reduz o tamanho)
    - macro contrário + contexto contrário = bloqueio em qualquer perfil
Sinal de saída:
    - o grau operacional completa o impulso (fase correcao_a) ou inverte o consenso (≥ 60% contra)
    - para swing, a saída considera também o grau de contexto
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence

from core.utils_indicadores import atr, normalizar_timeframe, timeframe_ms
from .pivots import zigzag_atr
from .scenarios import ScenarioEngine

# perfil -> (timeframe operacional padrão, contexto, macro, fator ATR do zigzag)
PERFIS: Dict[str, Dict] = {
    "scalping": {"op": "1m", "contexto": "15m", "macro": "1h", "fator_atr": 1.8, "candles": 300},
    "daytrade": {"op": "15m", "contexto": "4h", "macro": "1d", "fator_atr": 2.0, "candles": 300},
    "swing": {"op": "4h", "contexto": "1d", "macro": "1w", "fator_atr": 2.2, "candles": 300},
}
_ESCADA = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "1w"]
FASES_PROIBEM_ENTRADA_CONTEXTO = {"onda_5": None, "correcao_a": None}  # tratadas na lógica abaixo


def normalizar_perfil(estilo: Optional[str]) -> str:
    e = (estilo or "daytrade").lower()
    if "scalp" in e:
        return "scalping"
    if "swing" in e:
        return "swing"
    return "daytrade"


def timeframes_do_perfil(estilo: Optional[str], timeframe_bot: Optional[str]) -> Dict[str, str]:
    """Garante contexto > operacional e macro > contexto."""
    perfil = normalizar_perfil(estilo)
    cfg = PERFIS[perfil]
    op = normalizar_timeframe(timeframe_bot or cfg["op"])
    ctx, macro = cfg["contexto"], cfg["macro"]

    def acima(tf: str) -> str:
        i = _ESCADA.index(tf) if tf in _ESCADA else 0
        return _ESCADA[min(i + 2, len(_ESCADA) - 1)]

    if timeframe_ms(ctx) <= timeframe_ms(op):
        ctx = acima(op)
    if timeframe_ms(macro) <= timeframe_ms(ctx):
        macro = acima(ctx)
    return {"perfil": perfil, "operacional": op, "contexto": ctx, "macro": macro, "fator_atr": cfg["fator_atr"],
            "candles": cfg["candles"]}


_CALIBRADOR = None
_CALIBRADORES_PAR: Dict[str, object] = {}


def calibrador_padrao(par: Optional[str] = None):
    """Modelo por moeda (data/calibracao_elliott_<PAR>.json) se existir; senão o padrão (BTC, 2011-2026)."""
    global _CALIBRADOR
    import os
    from .calibracao import ARQUIVO_PADRAO, Calibrador
    if par:
        chave = par.replace("/", "").upper()
        if chave not in _CALIBRADORES_PAR:
            caminho = ARQUIVO_PADRAO.replace(".json", f"_{chave}.json")
            _CALIBRADORES_PAR[chave] = Calibrador(caminho) if os.path.exists(caminho) else None
        if _CALIBRADORES_PAR[chave] is not None:
            return _CALIBRADORES_PAR[chave]
    if _CALIBRADOR is None:
        _CALIBRADOR = Calibrador()
    return _CALIBRADOR


def analisar_serie(ohlcv: Sequence, fator_atr: float = 2.0, timeframe: str = "15m", calibrar: bool = True,
                   par: Optional[str] = None) -> Dict:
    """Roda ZigZag + cenários numa série de candles; aplica a calibração histórica se houver modelo."""
    if not ohlcv or len(ohlcv) < 30:
        return {"fase": "indefinido", "direcao": "hold", "consenso": "hold", "prob_bull": 0.0, "prob_bear": 0.0,
                "primario": None, "alternativos": [], "cenarios": [], "erro": "candles insuficientes"}
    piv, limiar = zigzag_atr(ohlcv, fator_atr=fator_atr)
    a = atr(ohlcv, 14) or 0.0
    eng = ScenarioEngine(piv, float(ohlcv[-1][4]), limiar, a)
    res = eng.analisar()
    res["atr"] = a
    res["fator_atr"] = fator_atr
    from core.regime import analisar_regime
    res["regime"] = analisar_regime(ohlcv)
    if calibrar:
        cal = calibrador_padrao(par)
        if cal.ativo:
            res = cal.aplicar(res, float(ohlcv[-1][4]), a, timeframe, res["regime"])
    return res


class AnaliseMultiGrau:
    def __init__(self, fetch_ohlcv: Callable[[str, int], Sequence], par: str, estilo_trade: str,
                 timeframe_bot: str, perfil_confluencia: str = "conservador", trava: Optional[Dict] = None,
                 trader: Optional[Dict] = None):
        """
        fetch_ohlcv(timeframe, limite) -> candles. Pode ser o conector Bybit, o agregador ou dados de backtest.
        trava: cenário mestre travado pelo usuário ({'vies', 'fase', 'invalidacao', 'status'}) ou None.
        trader: leitura do TraderService ({'direcao', 'superciclo': {'estado', ...}}) ou None.
        """
        self.fetch = fetch_ohlcv
        self.trava = trava if (trava and trava.get("status", "ativa") == "ativa") else None
        self.trader = trader if (trader and not trader.get("erro")) else None
        self.par = par
        self.cfg = timeframes_do_perfil(estilo_trade, timeframe_bot)
        self.perfil_conf = (perfil_confluencia or "conservador").lower()
        self.resultado: Dict = {}

    def analisar(self, ohlcv_operacional: Optional[Sequence] = None) -> Dict:
        cfg = self.cfg
        graus = {}
        for grau in ("operacional", "contexto", "macro"):
            tf = cfg[grau]
            try:
                dados = ohlcv_operacional if (grau == "operacional" and ohlcv_operacional) else self.fetch(tf, cfg["candles"])
                graus[grau] = analisar_serie(dados, cfg["fator_atr"], timeframe=tf, par=self.par)
                graus[grau]["timeframe"] = tf
            except Exception as e:
                graus[grau] = {"fase": "indefinido", "direcao": "hold", "consenso": "hold", "prob_bull": 0.0,
                               "prob_bear": 0.0, "primario": None, "alternativos": [], "cenarios": [],
                               "timeframe": tf, "erro": str(e)[:120]}
        alinhamento = self._alinhar(graus)
        self.resultado = {"perfil": cfg["perfil"], "timeframes": {k: cfg[k] for k in ("operacional", "contexto", "macro")},
                          "graus": graus, "alinhamento": alinhamento}
        return self.resultado

    # ------------------------------------------------------------ alinhamento
    def _alinhar(self, graus: Dict) -> Dict:
        op, ctx, macro = graus["operacional"], graus["contexto"], graus["macro"]
        direcao = op.get("direcao") or "hold"
        fase_op = op.get("fase", "indefinido")
        prim = op.get("primario") or {}
        motivo = [f"operacional {op.get('timeframe')}: {fase_op} ({prim.get('nome', '')}) p={prim.get('probabilidade', 0):.0%}"]

        def vies(g: Dict) -> str:
            pb, pr = g.get("prob_bull", 0), g.get("prob_bear", 0)
            if pb >= 0.6:
                return "buy"
            if pr >= 0.6:
                return "sell"
            return "neutro"

        v_ctx, v_macro = vies(ctx), vies(macro)
        motivo.append(f"contexto {ctx.get('timeframe')}: {ctx.get('fase')} viés {v_ctx} (bull {ctx.get('prob_bull', 0):.0%})")
        motivo.append(f"macro {macro.get('timeframe')}: {macro.get('fase')} viés {v_macro}")
        v_mestre = None
        if self.trava:
            v_mestre = "buy" if self.trava.get("vies") == "bull" else "sell"
            motivo.append(f"mestre travado ({self.trava.get('grau', '?')}): {self.trava.get('fase')} viés {v_mestre}")
        v_trader, est_trader = None, None
        if self.trader:
            est_trader = (self.trader.get("superciclo") or {}).get("estado")
            v_trader = self.trader.get("direcao") if self.trader.get("direcao") in ("buy", "sell") else "neutro"
            motivo.append(f"trader: superciclo {est_trader} viés {v_trader}")

        alinhado, contra, bloqueado = True, False, False
        fator_tamanho = 1.0
        if direcao in ("buy", "sell"):
            oposto = "sell" if direcao == "buy" else "buy"
            # o trader humano manda antes de tudo: nunca vender fundo de ciclo, nunca comprar correção recém-iniciada,
            # não perseguir impulso maduro
            if direcao == "sell" and est_trader in ("fundo_terminal", "novo_impulso", "zona_onda_2"):
                if self.perfil_conf == "conservador":
                    bloqueado = True
                    motivo.append(f"trader: {est_trader} (fundo/retomada de ciclo), venda bloqueada")
                else:
                    contra, alinhado, fator_tamanho = True, False, 0.5
                    motivo.append(f"turbo: vendendo contra o superciclo ({est_trader}), tamanho reduzido")
            elif direcao == "buy" and est_trader == "correcao_inicial":
                if self.perfil_conf == "conservador":
                    bloqueado = True
                    motivo.append("trader: correção de ciclo recém-iniciada, compra bloqueada")
                else:
                    contra, alinhado, fator_tamanho = True, False, 0.5
                    motivo.append("turbo: comprando em correção inicial de ciclo, tamanho reduzido")
            elif direcao == "buy" and est_trader == "impulso_maduro":
                fator_tamanho = 0.5
                motivo.append("trader: impulso de ciclo maduro, não perseguir (tamanho reduzido)")
            if v_mestre == oposto and not bloqueado:
                if self.perfil_conf == "conservador":
                    bloqueado = True
                    motivo.append("contra a contagem mestre travada: bloqueado (conservador)")
                else:
                    contra = True
                    alinhado = False
                    motivo.append("turbo: contra a contagem mestre (tamanho reduzido)")
            # conservador: macro contrário bloqueia, a não ser que o contexto esteja fortemente a favor (>= 70%)
            if v_macro == oposto and self.perfil_conf == "conservador":
                forte_ctx = ctx.get("prob_bull" if direcao == "buy" else "prob_bear", 0) >= 0.7
                if not forte_ctx:
                    bloqueado = True
                    motivo.append("macro contrário à direção operacional (conservador): bloqueado")
            if bloqueado:
                pass
            elif v_ctx == oposto:
                if v_macro == oposto or self.perfil_conf == "conservador":
                    bloqueado = True
                    motivo.append("contexto contrário à direção operacional: bloqueado")
                else:
                    contra = True
                    alinhado = False
                    motivo.append("turbo: operando contra o contexto (tamanho reduzido)")
            elif v_ctx == "neutro":
                # contexto sem consenso: conservador exige que a fase do contexto não seja terminal
                fase_ctx = ctx.get("fase", "indefinido")
                if self.perfil_conf == "conservador" and fase_ctx in ("onda_5", "correcao_a", "indefinido") and (ctx.get("primario") or {}).get("vies") == ("bear" if direcao == "buy" else "bull"):
                    bloqueado = True
                    motivo.append(f"contexto em {fase_ctx} contra a direção: bloqueado (conservador)")
                else:
                    alinhado = v_ctx != "neutro"
        if bloqueado:
            direcao_final = "hold"
        else:
            direcao_final = direcao
        return {
            "direcao": direcao_final,
            "direcao_operacional": direcao,
            "fase": fase_op,
            "alinhado": alinhado and not bloqueado,
            "contra_tendencia": contra,
            "bloqueado": bloqueado,
            "vies_contexto": v_ctx,
            "vies_macro": v_macro,
            "vies_mestre": v_mestre,
            "vies_trader": v_trader,
            "estado_superciclo": est_trader,
            "fator_tamanho": fator_tamanho,
            "tendencia_macro": macro.get("tendencia", "lateral"),
            "motivo": " | ".join(motivo),
        }

    # ------------------------------------------------------------ saída
    LIMIAR_SAIDA = 0.7

    def sinal_saida(self, direcao_posicao: str) -> Dict:
        """
        Deve fechar a posição? Usa o grau operacional (e o contexto para swing).
            - os cenários contrários somam ≥ 70% E o primário é contrário
            - o primário virou correcao_a (impulso completo) contra a posição
        """
        if not self.resultado:
            return {"sair": False, "motivo": "sem análise"}
        graus = self.resultado["graus"]
        alvo = graus["contexto"] if self.cfg["perfil"] == "swing" else graus["operacional"]
        contra = "bear" if direcao_posicao == "buy" else "bull"
        prob_contra = alvo.get("prob_bear" if contra == "bear" else "prob_bull", 0)
        prim = alvo.get("primario") or {}
        if prob_contra >= self.LIMIAR_SAIDA and prim.get("vies") == contra:
            return {"sair": True, "motivo": f"Cenários {contra} somam {prob_contra:.0%} no grau {alvo.get('timeframe')} ({prim.get('nome')})"}
        if prim.get("fase") == "correcao_a" and prim.get("vies") == contra:
            return {"sair": True, "motivo": f"Impulso concluído ({prim.get('nome')}); correção iniciando"}
        return {"sair": False, "motivo": f"Cenário primário {prim.get('fase')} ainda a favor"}
