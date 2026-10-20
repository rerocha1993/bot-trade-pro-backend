# core/elliott_pro/calibracao.py
"""
Calibração estatística dos cenários de Elliott com histórico.

1) construir_dataset(ohlcv, timeframe): replay do ScenarioEngine candle a candle. Para cada cenário
   gerado registra as FEATURES (padrão, fase, viés, score bruto, offset, completo, distância ao alvo
   e à invalidação em ATR, R:R, probabilidades brutas, regime) e o RESULTADO olhando os próximos
   `horizonte` candles: 1 se o 1º alvo foi atingido antes da invalidação, 0 se a invalidação veio
   antes, descartado se nenhum dos dois.
2) treinar(dataset): regressão logística (numpy, sem dependência externa) com one-hot + padronização,
   L2, e uma tabela de calibração por padrão/fase (taxa de acerto histórica) usada como reforço.
3) Calibrador: carrega o modelo (JSON) e devolve P(sucesso) para um cenário; o ScenarioEngine
   usa isso para reordenar/ponderar e o StrategyEngine para exigir um mínimo e dimensionar.
"""
from __future__ import annotations

import json
import math
import os
import time
from typing import Dict, List, Optional, Sequence

import numpy as np

from conselho.indicadores import atr as calc_atr
from .pivots import zigzag_atr
from .scenarios import ScenarioEngine

ARQUIVO_PADRAO = os.path.join("data", "calibracao_elliott.json")
PADROES = ["impulso", "diagonal_leading", "diagonal_ending", "zigzag", "flat_regular", "flat_expandido", "flat_running",
           "triangulo_contratil", "triangulo_barreira", "triangulo_expansivo", "duplo_tres", "triplo_tres", "consolidacao"]
FASES = ["onda_1", "onda_2", "inicio_onda_3", "meio_onda_3", "final_onda_3", "onda_4", "onda_5", "correcao_a", "correcao_b",
         "correcao_c", "triangulo", "consolidacao", "indefinido"]
TFS = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]
NUMERICAS = ["score", "prob_bruta", "offset", "completo", "dist_alvo_atr", "dist_inv_atr", "rr", "margem_vies", "n_cenarios",
             "eficiencia", "vol_rel", "impulso_horizonte"]


# --------------------------------------------------------------- features
def features_cenario(c: Dict, preco: float, atr_v: float, resumo: Dict, timeframe: str, regime: Dict = None) -> Dict:
    alvos = c.get("alvos") or []
    inv = c.get("invalidacao")
    dist_alvo = abs(alvos[0] - preco) / atr_v if (alvos and atr_v) else 0.0
    dist_inv = abs(preco - inv) / atr_v if (inv is not None and atr_v) else 0.0
    rr = (dist_alvo / dist_inv) if dist_inv else 0.0
    regime = regime or {}
    return {
        "padrao": c.get("padrao", "indefinido"), "fase": c.get("fase", "indefinido"), "vies": c.get("vies", "bull"),
        "timeframe": timeframe, "horizonte": c.get("horizonte", "impulso"),
        "score": float(c.get("score", 0.0)), "prob_bruta": float(c.get("probabilidade", 0.0)),
        "offset": float(c.get("offset", 0)), "completo": 1.0 if c.get("completo", True) else 0.0,
        "dist_alvo_atr": min(dist_alvo, 30.0), "dist_inv_atr": min(dist_inv, 30.0), "rr": min(rr, 10.0),
        "margem_vies": float(resumo.get("prob_bull", 0) - resumo.get("prob_bear", 0)) * (1 if c.get("vies") == "bull" else -1),
        "n_cenarios": float(resumo.get("n_cenarios", 0)),
        "eficiencia": float(regime.get("eficiencia", 0.0)), "vol_rel": float(regime.get("vol_rel", 1.0)),
        "impulso_horizonte": 1.0 if c.get("horizonte") == "impulso" else 0.0,
    }


def _regime_simples(janela: Sequence) -> Dict:
    closes = np.array([c[4] for c in janela[-40:]], dtype=float)
    if len(closes) < 10:
        return {"eficiencia": 0.0, "vol_rel": 1.0}
    liquido = abs(closes[-1] - closes[0])
    caminho = float(np.sum(np.abs(np.diff(closes)))) or 1e-9
    a_curto = calc_atr(janela[-20:], 14) or 0.0
    a_longo = calc_atr(janela[-120:], 100) or a_curto or 1e-9
    return {"eficiencia": liquido / caminho, "vol_rel": (a_curto / a_longo) if a_longo else 1.0}


# ---------------------------------------------------------------- dataset
def construir_dataset(ohlcv: Sequence, timeframe: str, fator_atr: float = 2.0, janela: int = 300, horizonte: int = 60,
                      passo: int = 1, max_cenarios: int = 6, verbose: bool = True) -> List[Dict]:
    """Replay sem look-ahead: em cada candle i usa ohlcv[i-janela+1:i+1] e olha ohlcv[i+1:i+1+horizonte]."""
    dados = [list(map(float, c[:6])) for c in ohlcv]
    n = len(dados)
    linhas: List[Dict] = []
    t0 = time.time()
    for i in range(janela, n - horizonte, passo):
        win = dados[i - janela + 1:i + 1]
        preco = win[-1][4]
        try:
            piv, limiar = zigzag_atr(win, fator_atr=fator_atr)
            a = calc_atr(win, 14) or 0.0
            eng = ScenarioEngine(piv, preco, limiar, a)
            res = eng.analisar()
        except Exception:
            continue
        if not res["cenarios"]:
            continue
        regime = _regime_simples(win)
        futuro = dados[i + 1:i + 1 + horizonte]
        for c in res["cenarios"][:max_cenarios]:
            alvos = c.get("alvos") or []
            inv = c.get("invalidacao")
            if not alvos or inv is None:
                continue
            alvo = alvos[0]
            up = c["vies"] == "bull"
            resultado = None
            for k, f in enumerate(futuro):
                hi, lo = f[2], f[3]
                bateu_alvo = hi >= alvo if up else lo <= alvo
                bateu_inv = lo <= inv if up else hi >= inv
                if bateu_alvo and bateu_inv:
                    resultado = 0  # conservador: no mesmo candle assume invalidação primeiro
                    break
                if bateu_alvo:
                    resultado = 1
                    break
                if bateu_inv:
                    resultado = 0
                    break
            if resultado is None:
                continue
            f = features_cenario(c, preco, a, res, timeframe, regime)
            f["y"] = resultado
            f["ts"] = int(win[-1][0])
            f["candles_ate"] = k + 1
            linhas.append(f)
        if verbose and (i - janela) % (passo * 2000) == 0:
            print(f"  {timeframe}: candle {i}/{n} ({len(linhas)} amostras, {time.time() - t0:.0f}s)")
    return linhas


# ----------------------------------------------------------------- modelo
def _one_hot(valor: str, lista: List[str]) -> List[float]:
    return [1.0 if valor == x else 0.0 for x in lista]


def vetor(f: Dict) -> List[float]:
    return ([f.get(k, 0.0) for k in NUMERICAS] + _one_hot(f.get("padrao"), PADROES) + _one_hot(f.get("fase"), FASES)
            + _one_hot(f.get("timeframe"), TFS) + [1.0 if f.get("vies") == "bull" else 0.0])


def treinar(linhas: List[Dict], l2: float = 1.0, epocas: int = 400, lr: float = 0.1, verbose: bool = True) -> Dict:
    if len(linhas) < 200:
        raise ValueError(f"amostras insuficientes para treinar ({len(linhas)})")
    X = np.array([vetor(f) for f in linhas], dtype=float)
    y = np.array([f["y"] for f in linhas], dtype=float)
    n_num = len(NUMERICAS)
    mu = X[:, :n_num].mean(axis=0)
    sd = X[:, :n_num].std(axis=0) + 1e-9
    Xn = X.copy()
    Xn[:, :n_num] = (X[:, :n_num] - mu) / sd
    Xn = np.hstack([Xn, np.ones((len(Xn), 1))])
    w = np.zeros(Xn.shape[1])
    m = len(y)
    for ep in range(epocas):
        z = Xn @ w
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        grad = Xn.T @ (p - y) / m + l2 * np.r_[w[:-1], 0.0] / m
        w -= lr * grad
    z = Xn @ w
    p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
    ll = float(-np.mean(y * np.log(p + 1e-9) + (1 - y) * np.log(1 - p + 1e-9)))
    acc = float(np.mean((p >= 0.5) == (y == 1)))
    base = float(y.mean())
    # tabela por padrão/fase (taxa histórica com suavização)
    tabela: Dict[str, Dict] = {}
    for f in linhas:
        k = f"{f['padrao']}|{f['fase']}"
        t = tabela.setdefault(k, {"n": 0, "s": 0})
        t["n"] += 1
        t["s"] += f["y"]
    for k, t in tabela.items():
        t["taxa"] = round((t["s"] + 5 * base) / (t["n"] + 5), 4)
    # calibração em decis (confiabilidade)
    ordem = np.argsort(p)
    decis = []
    for d in range(10):
        idx = ordem[d * m // 10:(d + 1) * m // 10]
        if len(idx):
            decis.append({"prev_media": round(float(p[idx].mean()), 3), "real": round(float(y[idx].mean()), 3), "n": int(len(idx))})
    modelo = {"versao": 1, "criado_em": int(time.time()), "amostras": int(m), "taxa_base": round(base, 4),
              "logloss": round(ll, 4), "acuracia": round(acc, 4), "pesos": [round(float(x), 6) for x in w],
              "mu": [float(x) for x in mu], "sd": [float(x) for x in sd], "numericas": NUMERICAS, "padroes": PADROES,
              "fases": FASES, "timeframes": TFS, "tabela": tabela, "decis": decis}
    if verbose:
        print(f"treino: {m} amostras, taxa base {base:.3f}, acurácia {acc:.3f}, logloss {ll:.3f}")
    return modelo


def salvar_modelo(modelo: Dict, caminho: str = ARQUIVO_PADRAO):
    os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(modelo, f, ensure_ascii=False)


class Calibrador:
    """Aplica o modelo treinado: P(alvo antes da invalidação) para um cenário."""

    def __init__(self, caminho: str = None, modelo: Optional[Dict] = None):
        self.modelo = modelo
        caminho = caminho or os.getenv("CALIBRACAO_ARQUIVO") or ARQUIVO_PADRAO
        self.caminho = caminho
        if self.modelo is None and caminho and os.path.exists(caminho):
            with open(caminho, "r", encoding="utf-8") as f:
                self.modelo = json.load(f)
        self.ativo = self.modelo is not None
        if self.ativo:
            self.w = np.array(self.modelo["pesos"], dtype=float)
            self.mu = np.array(self.modelo["mu"], dtype=float)
            self.sd = np.array(self.modelo["sd"], dtype=float)

    def prob(self, f: Dict) -> Optional[float]:
        if not self.ativo:
            return None
        x = np.array(vetor(f), dtype=float)
        n_num = len(NUMERICAS)
        x[:n_num] = (x[:n_num] - self.mu) / self.sd
        z = float(np.dot(np.r_[x, 1.0], self.w))
        p = 1.0 / (1.0 + math.exp(-max(-30, min(30, z))))
        # mistura com a taxa histórica do par padrão/fase (reduz variância quando o modelo extrapola)
        t = (self.modelo.get("tabela") or {}).get(f"{f.get('padrao')}|{f.get('fase')}")
        if t and t.get("n", 0) >= 30:
            p = 0.7 * p + 0.3 * t["taxa"]
        return round(p, 4)

    def aplicar(self, resumo: Dict, preco: float, atr_v: float, timeframe: str, regime: Dict = None) -> Dict:
        """Adiciona prob_sucesso a cada cenário e reordena por score x prob_sucesso."""
        if not self.ativo or not resumo.get("cenarios"):
            return resumo
        for c in resumo["cenarios"]:
            c["prob_sucesso"] = self.prob(features_cenario(c, preco, atr_v, resumo, timeframe, regime))
        resumo["cenarios"].sort(key=lambda c: -(c["probabilidade"] * (c.get("prob_sucesso") or 0.0)))
        resumo["primario"] = resumo["cenarios"][0]
        resumo["alternativos"] = resumo["cenarios"][1:5]
        resumo["fase"] = resumo["primario"]["fase"]
        resumo["direcao"] = resumo["primario"]["direcao_trade"]
        resumo["invalidacao"] = resumo["primario"].get("invalidacao")
        resumo["alvos"] = resumo["primario"].get("alvos", [])
        resumo["calibrado"] = True
        return resumo
