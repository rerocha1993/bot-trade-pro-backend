"""
A calibração acerta o ALVO. Isso dá LUCRO depois da taxa?

    python scripts/calibracao_lucro.py                       # modelo treinado até 2024, avaliado de 2024 em diante
    python scripts/calibracao_lucro.py --modelo data/calibracao_elliott.json --desde 2012-01-01

O modelo de calibração prevê P(1º alvo antes da invalidação) e acerta bem: nas contagens mais confiantes, 9 de 10
batem o alvo. Mas um alvo colado no preço bate quase sempre — e o modelo usa a distância do alvo como variável.
Esta conta transforma cada amostra num trade:

    entrada no fechamento do candle, stop na invalidação da contagem, alvo no 1º alvo
    resultado em R:  +rr se bateu o alvo, −1 se a invalidação veio antes
    custo em R:      taxa de ida e volta (entrada maker; saída maker no alvo, taker + slippage no stop)
                     dividida pelo risco em % do preço (distância da invalidação x ATR% do candle)

e mede o resultado LÍQUIDO por faixa de probabilidade. Duas leituras:

    por amostra       média de todas as contagens da faixa (a mesma contagem se repete candle a candle)
    sem sobreposição  um trade por vez: na faixa, pega a contagem mais provável do candle e só abre outro depois
                      que este terminar — o que o robô de fato conseguiria fazer

Limitação dita: o dataset descarta as contagens que não bateram nem alvo nem invalidação dentro do horizonte
(60 candles). Um robô de verdade sairia delas por tempo, com resultado entre os dois.
"""
import argparse
import datetime as dt
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.elliott_pro.calibracao import FASES, NUMERICAS, PADROES, TFS  # noqa: E402
from core.executor_real import TAXA_MAKER, TAXA_TAKER  # noqa: E402

FONTES = {"1d": "BTCUSD_bitstamp_1d.csv", "4h": "BTCUSD_bitstamp_4h.csv", "1h": "BTCUSD_bitstamp_1h.csv"}
DUR_MS = {"1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
SLIPPAGE = 0.0002
FAIXAS = [0.0, 0.45, 0.55, 0.65, 0.75, 0.85, 1.01]


def atr_pct(tf: str) -> pd.Series:
    """ATR de Wilder (14) em fração do preço, indexado pelo timestamp do candle — a mesma régua da calibração."""
    df = pd.read_csv(os.path.join("data", "historico", FONTES[tf])).sort_values("timestamp")
    ant = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - ant).abs(), (df["low"] - ant).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    return pd.Series((atr / df["close"]).values, index=df["timestamp"].astype("int64").values)


def probabilidades(d: pd.DataFrame, modelo: dict) -> np.ndarray:
    """O Calibrador.prob vetorizado (mesmos pesos, padronização e mistura com a tabela padrão|fase)."""
    X = [d[k].astype(float).values for k in NUMERICAS]
    for lista, col in ((PADROES, "padrao"), (FASES, "fase"), (TFS, "timeframe")):
        X += [(d[col] == v).astype(float).values for v in lista]
    X.append((d["vies"] == "bull").astype(float).values)
    X = np.vstack(X).T
    n = len(NUMERICAS)
    X[:, :n] = (X[:, :n] - np.array(modelo["mu"])) / np.array(modelo["sd"])
    z = np.hstack([X, np.ones((len(X), 1))]) @ np.array(modelo["pesos"])
    p = 1 / (1 + np.exp(-np.clip(z, -30, 30)))
    tab = modelo.get("tabela") or {}
    chave = (d["padrao"] + "|" + d["fase"]).values
    taxa = np.array([tab[k]["taxa"] if k in tab and tab[k].get("n", 0) >= 30 else np.nan for k in chave])
    return np.where(np.isnan(taxa), p, 0.7 * p + 0.3 * taxa)


def resultado_r(d: pd.DataFrame) -> pd.DataFrame:
    risco_pct = d["dist_inv_atr"] * d["atr_pct"]
    alvo_pct = d["dist_alvo_atr"] * d["atr_pct"]
    custo_ganho = 2 * TAXA_MAKER
    custo_perda = TAXA_MAKER + TAXA_TAKER + SLIPPAGE
    d = d.assign(risco_pct=risco_pct, alvo_pct=alvo_pct)
    d["bruto_r"] = np.where(d["y"] == 1, d["alvo_pct"] / d["risco_pct"], -1.0)
    d["custo_r"] = np.where(d["y"] == 1, custo_ganho, custo_perda) / d["risco_pct"]
    d["liquido_r"] = d["bruto_r"] - d["custo_r"]
    return d


def tabela_faixas(d: pd.DataFrame) -> pd.DataFrame:
    d = d.assign(faixa=pd.cut(d["p"], FAIXAS, right=False))
    g = d.groupby("faixa", observed=True)
    return pd.DataFrame({
        "amostras": g.size(), "acerto": g["y"].mean().round(3), "prev": g["p"].mean().round(3),
        "risco_%": (g["risco_pct"].median() * 100).round(2), "alvo_%": (g["alvo_pct"].median() * 100).round(2),
        "bruto_R": g["bruto_r"].mean().round(3), "custo_R": g["custo_r"].mean().round(3), "liquido_R": g["liquido_r"].mean().round(3),
    })


def valor_esperado(d: pd.DataFrame) -> pd.Series:
    """
    O que a probabilidade calibrada promete em R, já com custo: p x (alvo/risco) − (1 − p) − custo esperado.
    É o jeito certo de usar a calibração: probabilidade alta com alvo colado no preço não paga a conta.
    """
    rr = d["alvo_pct"] / d["risco_pct"]
    custo = (d["p"] * 2 * TAXA_MAKER + (1 - d["p"]) * (TAXA_MAKER + TAXA_TAKER + SLIPPAGE)) / d["risco_pct"]
    return d["p"] * rr - (1 - d["p"]) - custo


def sem_sobreposicao(d: pd.DataFrame, tf: str, minimo: float, alinhado: bool, col: str = "p") -> dict:
    """Um trade por vez: a melhor contagem do candle, se passar do mínimo; o próximo só depois do fim."""
    x = d[d[col] >= minimo]
    if alinhado:
        x = x[x["margem_vies"] > 0]
    x = x.sort_values(["ts", col], ascending=[True, False]).drop_duplicates("ts")
    livre, trades = 0, []
    for r in x.itertuples(index=False):
        if r.ts < livre:
            continue
        trades.append(r)
        livre = r.ts + (r.candles_ate + 1) * DUR_MS[tf]
    if not trades:
        return {"trades": 0}
    t = pd.DataFrame(trades)
    anos = t["ts"].apply(lambda v: dt.datetime.fromtimestamp(v / 1000, dt.timezone.utc).year)
    return {"trades": len(t), "acerto": round(t["y"].mean(), 3), "bruto_R": round(t["bruto_r"].mean(), 3),
            "liquido_R": round(t["liquido_r"].mean(), 3), "soma_R": round(t["liquido_r"].sum(), 1),
            "por_ano_R": {int(a): round(v, 1) for a, v in t.groupby(anos)["liquido_r"].sum().items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default=os.path.join("data", "calibracao_elliott_ate_2024-01-01.json"))
    ap.add_argument("--desde", default="2024-01-01", help="avalia só amostras a partir desta data (fora do treino)")
    ap.add_argument("--salvar")
    a = ap.parse_args()
    modelo = json.load(open(a.modelo, encoding="utf-8"))
    desde = int(dt.datetime.fromisoformat(a.desde).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
    print(f"modelo {a.modelo} ({modelo['amostras']} amostras de treino) | avaliação desde {a.desde}")
    d = pd.read_csv(os.path.join("data", "calibracao_dataset.csv"))
    d = d[d["ts"] >= desde].copy()
    partes = []
    for tf in ("1h", "4h", "1d"):
        x = d[d["timeframe"] == tf].copy()
        x["atr_pct"] = x["ts"].map(atr_pct(tf))
        partes.append(x.dropna(subset=["atr_pct"]))
    d = pd.concat(partes)
    d = d[(d["dist_inv_atr"] > 0) & (d["atr_pct"] > 0)]
    d["p"] = probabilidades(d, modelo)
    d = resultado_r(d)
    d["ev"] = valor_esperado(d)
    relatorio ={"modelo": a.modelo, "desde": a.desde, "timeframes": {}}
    pd.set_option("display.width", 200)
    for tf in ("1h", "4h", "1d"):
        x = d[d["timeframe"] == tf]
        if x.empty:
            continue
        print(f"\n=== {tf}: {len(x)} amostras ===")
        tab = tabela_faixas(x)
        print(tab.to_string())
        simul = {}
        for minimo in (0.45, 0.55, 0.65, 0.75, 0.85):
            for alinhado in (False, True):
                r = sem_sobreposicao(x, tf, minimo, alinhado)
                simul[f"p>={minimo:.2f}{' alinhado' if alinhado else ''}"] = r
                if r["trades"]:
                    print(f"  um por vez, p >= {minimo:.2f}{' e a favor do consenso' if alinhado else '':<24} "
                          f"{r['trades']:>5} trades  acerto {r['acerto']:.0%}  bruto {r['bruto_R']:+.3f}R  "
                          f"líquido {r['liquido_R']:+.3f}R  soma {r['soma_R']:+.1f}R  por ano {r['por_ano_R']}")
        for minimo in (0.0, 0.05, 0.10, 0.20, 0.30):
            r = sem_sobreposicao(x, tf, minimo, True, col="ev")
            simul[f"ev>={minimo:.2f} alinhado"] = r
            if r["trades"]:
                print(f"  um por vez, valor esperado >= {minimo:+.2f}R, a favor do consenso "
                      f"{r['trades']:>5} trades  acerto {r['acerto']:.0%}  bruto {r['bruto_R']:+.3f}R  "
                      f"líquido {r['liquido_R']:+.3f}R  soma {r['soma_R']:+.1f}R  por ano {r['por_ano_R']}")
        relatorio["timeframes"][tf] = {"faixas": tab.reset_index().astype({"faixa": str}).to_dict("records"), "um_por_vez": simul}
    if a.salvar:
        with open(a.salvar, "w", encoding="utf-8") as f:
            json.dump(relatorio, f, ensure_ascii=False, indent=2, default=str)
        print(f"\nrelatório em {a.salvar}")


if __name__ == "__main__":
    main()
