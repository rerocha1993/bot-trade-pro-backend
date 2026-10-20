# core/elliott_pro/superciclo.py
"""
Contexto de SUPERCICLO em escala logarítmica: o que um elliottista humano olha ANTES de contar ondas.

Ideia: em um mercado em superciclo de alta (fundos cada vez mais altos: 2 -> 65 -> 152 -> 3.150 -> 15.476),
cada bear market é uma correção de grau maior, e a leitura correta em escala log é:
    - ciclos delimitados por topos históricos (ATH) seguidos de queda >= 60% (bear de BTC);
    - a correção é medida como retração logarítmica da perna de alta anterior (fundo do ciclo -> topo);
      as correções de BTC retraem ~0,38 a ~0,5 em log (2015: 0,45 | 2018: 0,38 | 2022: 0,50);
    - zona de término da correção (guias de Elliott): retração log >= 0,382, tempo >= 9 meses desde o topo,
      queda linear >= 60% -> pelo menos 2 dos 3;
    - a correção acabou estruturalmente quando, passados >= 6 meses do topo, o preço recupera >= 0,382 (em log) da queda (um 5 ondas de alta
      de grau menor já aconteceu) -> novo impulso; recuos de 0,382..0,786 dessa perna nova = zona de onda 2/4;
    - a perna de alta é MADURA quando sua extensão logarítmica chega a >= 0,618 da perna de alta do ciclo anterior
      (retornos decrescentes: 2013->2017 0,76 | 2018->2021 0,63 | 2022->2025 0,63). Madura não é venda: é
      "não perseguir; vender quando as contagens de grau menor virarem".

Nada aqui olha o futuro: o estado só usa o passado até o candle atual.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

MES_MS = 30.44 * 86_400_000

# multiplicadores aplicados às hipóteses das memórias (continuação = fase impulsiva no mesmo sentido)
MULTIPLICADORES = {
    "fundo_terminal":  {"bear_cont": 0.2, "bull": 2.0},
    "novo_impulso":    {"bear_cont": 0.3, "bull": 1.5},
    "zona_onda_2":     {"bear_cont": 0.4, "bull": 1.4},
    "impulso_alta":    {"bear_cont": 0.5, "bull": 1.2},
    "impulso_maduro":  {"bull_cont": 0.5, "bear": 1.3},
    "correcao_inicial": {"bull_cont": 0.6},
    "correcao_em_curso": {"bull_cont": 0.7},
    "recuo_profundo":  {},
}


class ContextoSuperciclo:
    def __init__(self, queda_ciclo: float = 0.60, retracao_terminal: float = 0.382, meses_terminal: int = 9,
                 queda_terminal: float = 0.60, recuperacao_fim: float = 0.382, extensao_madura: float = 0.618,
                 meses_minimos_correcao: int = 6, meses_ciclo_minimo: int = 9):
        self.queda_ciclo = queda_ciclo
        self.retracao_terminal = retracao_terminal
        self.meses_terminal = meses_terminal
        self.queda_terminal = queda_terminal
        self.recuperacao_fim = recuperacao_fim
        self.extensao_madura = extensao_madura
        self.meses_minimos_correcao = meses_minimos_correcao
        self.meses_ciclo_minimo = meses_ciclo_minimo   # correção mais curta que isso é sub-onda, não fim de ciclo
        self.ciclos: List[Dict] = []          # ciclos fechados (topo confirmado e superado)
        self.ath: Optional[float] = None
        self.ts_ath: int = 0
        self.fundo_ciclo: Optional[float] = None   # fundo da perna de alta atual
        self.ts_fundo: int = 0
        self.topo_conf: Optional[float] = None     # topo confirmado por queda >= 60% e ainda não superado
        self.ts_topo_conf: int = 0
        self.min_desde_topo: Optional[float] = None
        self.ts_min: int = 0
        self.max_desde_min: Optional[float] = None
        self.ts_inicio: int = 0
        self.ts: int = 0
        self.close: float = 0.0

    # ------------------------------------------------------------------ atualização
    def passo(self, ts: int, high: float, low: float, close: float):
        if not self.ts_inicio:
            self.ts_inicio = ts
            self.ath, self.ts_ath = high, ts
            self.fundo_ciclo, self.ts_fundo = low, ts
        self.ts, self.close = ts, close
        if self.topo_conf is not None:
            if low < self.min_desde_topo:
                self.min_desde_topo, self.ts_min = low, ts
                self.max_desde_min = high
            elif high > (self.max_desde_min or 0):
                self.max_desde_min = high
            if high > self.topo_conf:
                # rompeu o topo confirmado: fecha o ciclo e começa perna nova a partir do fundo. Se a correção durou
                # menos que meses_ciclo_minimo (2013: 266 -> 65 em 7 meses) foi sub-onda: a perna continua a mesma.
                if (ts - self.ts_topo_conf) / MES_MS >= self.meses_ciclo_minimo:
                    self.ciclos.append({"topo": self.topo_conf, "ts_topo": self.ts_topo_conf, "fundo": self.min_desde_topo,
                                        "ts_fundo": self.ts_min, "fundo_anterior": self.fundo_ciclo, "ts_fundo_anterior": self.ts_fundo})
                    self.fundo_ciclo, self.ts_fundo = self.min_desde_topo, self.ts_min
                self.topo_conf, self.min_desde_topo, self.max_desde_min = None, None, None
                self.ath, self.ts_ath = high, ts
            return
        if high > self.ath:
            self.ath, self.ts_ath = high, ts
        if 1 - low / self.ath >= self.queda_ciclo:
            self.topo_conf, self.ts_topo_conf = self.ath, self.ts_ath
            self.min_desde_topo, self.ts_min = low, ts
            self.max_desde_min = high

    # ------------------------------------------------------------------ leitura
    def _perna_anterior(self) -> Optional[float]:
        """Extensão log da perna de alta do ciclo anterior (fundo_anterior -> topo)."""
        if not self.ciclos:
            return None
        c = self.ciclos[-1]
        if not c["fundo_anterior"] or c["fundo_anterior"] <= 0:
            return None
        return math.log(c["topo"] / c["fundo_anterior"])

    def estado(self) -> Dict:
        preco = self.close
        if not preco:
            return {"estado": "indefinido"}
        meses = lambda t0: (self.ts - t0) / MES_MS
        if self.topo_conf is not None:
            perna = math.log(self.topo_conf / self.fundo_ciclo) if self.fundo_ciclo else None
            queda_log = math.log(self.topo_conf / self.min_desde_topo)
            r_min = queda_log / perna if perna else None
            r_preco = math.log(self.topo_conf / preco) / perna if perna else None
            recuperacao = math.log(preco / self.min_desde_topo) / queda_log if queda_log > 0 else 0.0
            t = meses(self.ts_topo_conf)
            queda = 1 - self.min_desde_topo / self.topo_conf
            criterios = {"retracao_log": r_min is not None and r_min >= self.retracao_terminal, "tempo": t >= self.meses_terminal,
                         "queda": queda >= self.queda_terminal}
            base = {"fase_ciclo": "correcao", "topo": self.topo_conf, "fundo_perna": self.fundo_ciclo, "minimo": self.min_desde_topo,
                    "retracao_log_minimo": round(r_min, 3) if r_min is not None else None, "retracao_log_preco": round(r_preco, 3) if r_preco is not None else None,
                    "meses_desde_topo": round(t, 1), "queda_pct": round(queda * 100, 1), "recuperacao_log": round(recuperacao, 3),
                    "criterios_terminal": criterios}
            if recuperacao >= self.recuperacao_fim and t >= self.meses_minimos_correcao:
                # correção terminou estruturalmente; perna nova do mínimo até o máximo desde o mínimo
                alta = math.log(self.max_desde_min / self.min_desde_topo) if self.max_desde_min else 0.0
                recuo = math.log(self.max_desde_min / preco) / alta if alta > 0 else 0.0
                if recuo >= 0.786:
                    return {**base, "estado": "recuo_profundo", "direcao": "hold", "recuo_log": round(recuo, 3),
                            "leitura": "perna nova recuou mais de 0,786: reversão em dúvida, aguardar"}
                if recuo >= 0.382:
                    return {**base, "estado": "zona_onda_2", "direcao": "buy", "recuo_log": round(recuo, 3),
                            "leitura": "recuo de 0,382..0,786 da perna nova: zona de onda 2/4, comprar escalonado"}
                return {**base, "estado": "novo_impulso", "direcao": "buy", "recuo_log": round(recuo, 3),
                        "leitura": "preço recuperou >= 0,382 (log) da queda: correção de ciclo terminada, novo impulso"}
            if sum(criterios.values()) >= 2:
                return {**base, "estado": "fundo_terminal", "direcao": "buy",
                        "leitura": "correção de ciclo em zona de término (retração log, tempo, profundidade): acumular escalonado, não vender"}
            if t < 3 or (r_min is not None and r_min < 0.2):
                return {**base, "estado": "correcao_inicial", "direcao": "sell",
                        "leitura": "topo de ciclo confirmado há pouco: correção no início, vender/hedge"}
            return {**base, "estado": "correcao_em_curso", "direcao": "memoria",
                    "leitura": "correção de ciclo em andamento, ainda fora da zona de término: seguir as contagens"}
        # perna de alta em andamento (sem topo confirmado)
        alta = math.log(self.ath / self.fundo_ciclo) if self.fundo_ciclo else 0.0
        anterior = self._perna_anterior()
        extensao = alta / anterior if anterior else None
        recuo = math.log(self.ath / preco) / alta if alta > 0 else 0.0
        t = meses(self.ts_fundo)
        base = {"fase_ciclo": "impulso", "ath": self.ath, "fundo_perna": self.fundo_ciclo, "extensao_log": round(alta, 3),
                "extensao_vs_ciclo_anterior": round(extensao, 3) if extensao is not None else None, "meses_desde_fundo": round(t, 1),
                "recuo_log": round(recuo, 3), "queda_desde_ath_pct": round((1 - preco / self.ath) * 100, 1)}
        if extensao is not None and extensao >= self.extensao_madura:
            return {**base, "estado": "impulso_maduro", "direcao": "memoria_venda",
                    "leitura": f"perna de alta madura ({extensao:.2f} da perna do ciclo anterior): não perseguir; vender quando as contagens virarem"}
        if recuo >= 0.786:
            return {**base, "estado": "recuo_profundo", "direcao": "hold", "leitura": "recuo > 0,786 da perna: estrutura em dúvida"}
        if recuo >= 0.382:
            return {**base, "estado": "zona_onda_2", "direcao": "buy", "leitura": "recuo 0,382..0,786 da perna de alta: zona de onda 2/4"}
        return {**base, "estado": "impulso_alta", "direcao": "buy", "leitura": "perna de alta imatura com recuo raso: comprar recuos"}


def aplicar_contexto(vivas: List[Dict], estado: str, peso_fn, fases_continuacao) -> Dict[str, float]:
    """Pesos das hipóteses vivas ajustados pelo contexto de superciclo."""
    m = MULTIPLICADORES.get(estado, {})
    pesos = {}
    for h in vivas:
        w = peso_fn(h)
        cont = h.get("fase") in fases_continuacao
        if h["vies"] == "bear":
            if cont and "bear_cont" in m:
                w *= m["bear_cont"]
            if "bear" in m:
                w *= m["bear"]
        else:
            if cont and "bull_cont" in m:
                w *= m["bull_cont"]
            if "bull" in m:
                w *= m["bull"]
        pesos[h["chave"]] = w
    return pesos
