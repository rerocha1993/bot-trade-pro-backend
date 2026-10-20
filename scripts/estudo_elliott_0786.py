# scripts/estudo_elliott_0786.py
"""
Elliott — hipótese do método Tradeiros: "80–90% das vezes que o preço passa de 0,786 não é onda 2"
(docs/tradeiros/contagem_metodo.md §10.4; plano_gestao.md seção 4, passo 6). ESTUDO DESCRITIVO, não estratégia.
CRITÉRIO ESCRITO ANTES DE RODAR; nada é ajustado depois.

FONTE: data/cenarios/{1h,4h}.jsonl.gz (contagens históricas sem olhar o futuro, geradas por scripts/cenarios_historicos.py
  sobre candles BTCUSD da Bitstamp; por isso a continuação é medida nos mesmos candles:
  data/historico/BTCUSD_bitstamp_{1h,4h}.csv). Cobertura: 1h 2021-10..2026-09, 4h 2021-06..2026-09.
HIPÓTESE = cada cenário com fase "onda_2", identificado por (viés, invalidação). Conta-se a 1ª vez que aparece (t0, no
  fechamento do candle t0). Origem O = invalidação (início da onda 1). Fim da onda 1 E = extremo (máxima no viés de
  alta, mínima no de baixa) do candle cuja mínima (máxima) é O até t0, inclusive. Para os cenários "impulso" (onda 1
  confirmada) o motor dá E pelos alvos 0,5/0,618; a reconstrução é conferida contra ele.
  Descarta: origem não encontrada nos 400 candles anteriores; L = |E − O| nulo; origem já perdida entre E e t0.
RETRAÇÃO (alta): r = (E − mínima)/(E − O); espelho na baixa. Para θ ∈ {0,5; 0,618; 0,786; 0,886}: o cruzamento é o
  1º candle t ≥ t0 em que a retração acumulada desde E atinge θ, sem que antes (de t0 até ele) a máxima tenha passado E
  (aí a onda 2 já acabou: onda 3). Se em t0 a retração já passou θ, o cruzamento é t0.
DESFECHO, a partir do candle do cruzamento: "perde a origem" se a mínima fica abaixo de O (no próprio candle do
  cruzamento também conta) antes de a máxima passar E; "onda 2 sobreviveu" se a máxima passa E antes; os dois no mesmo
  candle = ambíguo; nada em 60 candles = indefinido.
MEDIDA PRINCIPAL: P(perde a origem | cruzou θ) = perdeu ÷ TODOS os cruzamentos (indefinido e ambíguo contam como não
  perdeu). Secundária: perdeu ÷ (perdeu + sobreviveu).
CRITÉRIO (escrito antes): a regra do Tradeiros VALE num tempo gráfico se, para θ = 0,786, a medida principal ≥ 70%
  (o limiar de contagem_metodo.md §10.4; eles dizem 80–90%), com ≥ 30 cruzamentos. 1h e 4h julgados separadamente.
COMPARAÇÃO (descritiva, não muda o veredito):
  (i) passeio aleatório sem tendência: a partir de exatamente θ, P(atinge O antes de E) = θ (ruína do jogador);
  (ii) DATA SORTEADA: para cada cruzamento, 20 candles sorteados do mesmo tempo gráfico e do mesmo período (com 60
      candles à frente); E' e O' postos às mesmas distâncias percentuais do fechamento do candle do cruzamento até E e
      O; desfecho igual, a partir do candle seguinte ao sorteado. Mede quanto da taxa é só geometria + tendência.
  Se a taxa observada não fica 2 EP acima do sorteio, "passou 0,786" diz o mesmo que a distância ao stop, não sobre a
  onda. Quebras: período (treino/validação/holdout como no plano), viés, tipo de cenário, cenário principal ou não.
Saídas: data/estudo_elliott_0786.csv e data/estudo_elliott_0786_resumo.md.
"""
from __future__ import annotations

import gzip
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from conselho import regua as R  # noqa: E402

SAIDA = RAIZ / "data" / "estudo_elliott_0786.csv"
SAIDA_MD = RAIZ / "data" / "estudo_elliott_0786_resumo.md"
LIMIARES = [0.5, 0.618, 0.786, 0.886]
HORIZ = 60
BUSCA_ORIGEM = 400
LIMIAR_REGRA = 0.70
N_SORTEIOS = 20
SEMENTE = 20261020


def carregar(tf):
    df = pd.read_csv(RAIZ / "data" / "historico" / f"BTCUSD_bitstamp_{tf}.csv").drop_duplicates("timestamp")
    df = df.sort_values("timestamp").reset_index(drop=True)
    return (df["timestamp"].to_numpy(np.int64), df["high"].to_numpy(float), df["low"].to_numpy(float),
            df["close"].to_numpy(float))


def hipoteses(tf, ts, hi, lo):
    pos = {int(t): i for i, t in enumerate(ts)}
    vistos = {}
    with gzip.open(RAIZ / "data" / "cenarios" / f"{tf}.jsonl.gz", "rt") as fh:
        for linha in fh:
            reg = json.loads(linha)
            cs = reg["cenarios"]
            topo = max(cs, key=lambda c: c["prob"]) if cs else None
            for c in cs:
                if c["fase"] != "onda_2":
                    continue
                chave = (c["vies"], round(c["inv"], 2))
                if chave in vistos:
                    continue
                vistos[chave] = {"t0": reg["ts"], "vies": c["vies"], "O": c["inv"], "padrao": c["padrao"],
                                 "prob": c["prob"], "principal": c is topo, "alvos": c["alvos"]}
    out = []
    for h in vistos.values():
        i0 = pos.get(int(h["t0"]))
        if i0 is None:
            continue
        up = h["vies"] == "bull"
        O = h["O"]
        a = max(0, i0 - BUSCA_ORIGEM)
        serie = lo if up else hi
        cand = np.flatnonzero(np.abs(serie[a:i0 + 1] - O) <= 1e-6 * O)
        if not len(cand):
            continue
        io = a + int(cand[-1])
        if up:
            iE = io + int(np.argmax(hi[io:i0 + 1]))
            E = float(hi[iE])
            perdeu_antes = lo[io + 1:i0 + 1].min() < O if i0 > io else False
        else:
            iE = io + int(np.argmin(lo[io:i0 + 1]))
            E = float(lo[iE])
            perdeu_antes = hi[io + 1:i0 + 1].max() > O if i0 > io else False
        L = abs(E - O)
        if L <= 0 or perdeu_antes or iE == io:
            continue
        E_motor = None
        if h["padrao"] == "impulso" and len(h["alvos"]) >= 2:
            s = 1 if up else -1
            t = s * (h["alvos"][0] - h["alvos"][1]) / 0.118
            E_motor = h["alvos"][0] + s * 0.5 * t
        out.append({**h, "i0": i0, "io": io, "iE": iE, "E": E, "L": L, "L_pct": L / O, "E_motor": E_motor})
    return out


def desfecho(up, O, E, i_ini, hi, lo, n, incluir_ini=True):
    """'perdeu' | 'sobreviveu' | 'ambiguo' | 'indefinido' a partir de i_ini (60 candles)."""
    for k in range(i_ini, min(i_ini + HORIZ, n)):
        perde = lo[k] < O if up else hi[k] > O
        passa = (hi[k] > E if up else lo[k] < E) if (k > i_ini or incluir_ini) else False
        if perde and passa:
            return "ambiguo"
        if perde:
            return "perdeu"
        if passa:
            return "sobreviveu"
    return "indefinido" if i_ini + HORIZ <= n else None


def rodar(tf):
    t_ini = time.time()
    ts, hi, lo, cl = carregar(tf)
    n = len(ts)
    hs = hipoteses(tf, ts, hi, lo)
    rng = np.random.default_rng(SEMENTE + (1 if tf == "4h" else 0))
    per_idx = {}
    for nome, a, z in R.PERIODOS:
        t_a = int(pd.Timestamp(a, tz="UTC").timestamp() * 1000)
        t_z = int(pd.Timestamp(z, tz="UTC").timestamp() * 1000) + R.DIA_MS
        per_idx[nome] = np.flatnonzero((ts >= t_a) & (ts < t_z) & (np.arange(n) + HORIZ < n))
    linhas = []
    for h in hs:
        up = h["vies"] == "bull"
        O, E, L, i0, iE = h["O"], h["E"], h["L"], h["i0"], h["iE"]
        per = R.periodo_de(int(ts[i0]))
        base = {"tf": tf, "data": R.data_de(int(ts[i0])), "periodo": per, "vies": h["vies"], "padrao": h["padrao"],
                "tipo": "impulso" if h["padrao"] == "impulso" else "corretivo_completo", "principal": h["principal"],
                "prob": h["prob"], "O": O, "E": E, "L_pct": h["L_pct"],
                "E_motor": h["E_motor"], "dif_E_motor": (abs(h["E_motor"] - E) / L) if h["E_motor"] else np.nan}
        # retração acumulada desde E, candle a candle a partir de t0
        ext = (lo[iE:i0 + 1].min() if up else hi[iE:i0 + 1].max())
        r0 = (E - ext) / L if up else (ext - E) / L
        base["r0"] = r0
        for th in LIMIARES:
            nivel = E - th * L if up else E + th * L
            ix = None
            if r0 >= th:
                ix = i0
            else:
                for k in range(i0 + 1, min(i0 + 1 + 2000, n)):
                    if (up and hi[k] > E) or (not up and lo[k] < E):
                        break
                    if (up and lo[k] <= nivel) or (not up and hi[k] >= nivel):
                        ix = k
                        break
            reg = dict(base)
            reg["theta"] = th
            if ix is None:
                reg["cruzou"] = False
                linhas.append(reg)
                continue
            res = desfecho(up, O, E, ix, hi, lo, n, incluir_ini=False)
            if res is None:
                reg["cruzou"] = False
                linhas.append(reg)
                continue
            reg.update({"cruzou": True, "desfecho": res, "perdeu": res == "perdeu",
                        "candles_ate_cruzar": ix - i0})
            # data sorteada: mesmas distâncias percentuais do fechamento do cruzamento
            c = cl[ix]
            up_d = (E - c) / c if up else (c - E) / c
            dn_d = (c - O) / c if up else (O - c) / c
            pool = per_idx.get(per, np.array([], int))
            if len(pool):
                acertos = 0
                for j in rng.choice(pool, N_SORTEIOS):
                    cj = cl[j]
                    if dn_d <= 0:
                        acertos += 1
                        continue
                    E2 = cj * (1 + up_d) if up else cj * (1 - up_d)
                    O2 = cj * (1 - dn_d) if up else cj * (1 + dn_d)
                    acertos += desfecho(up, O2, E2, j + 1, hi, lo, n) == "perdeu"
                reg["ctrl_sorteio"] = acertos / N_SORTEIOS
            linhas.append(reg)
    df = pd.DataFrame(linhas)
    print(f"  {tf}: {len(hs)} hipóteses, {len(df)} linhas ({time.time() - t_ini:.0f}s)")
    return df


def tabela(df, filtro_nome, filtro):
    out = []
    for th in LIMIARES:
        s = df[(df.theta == th) & (df.cruzou == True)]
        s = s[filtro(s)] if filtro else s
        n = len(s)
        if n == 0:
            out.append(f"| {filtro_nome} | {th} | 0 | - | - | - | - | - |")
            continue
        p = s.perdeu.mean()
        ep = np.sqrt(p * (1 - p) / n)
        dec = s[s.desfecho.isin(["perdeu", "sobreviveu"])]
        pdec = dec.perdeu.mean() if len(dec) else np.nan
        ctrl = s.ctrl_sorteio.mean()
        out.append(f"| {filtro_nome} | {th} | {n} | {R.pct(p)} ± {100 * ep:.0f} | {R.pct(pdec)} ({len(dec)}) | "
                   f"{R.pct(ctrl)} | {R.pct(th)} | {'sim' if p >= ctrl + 2 * ep else 'não'} |")
    return out


def resumo(df):
    out = ["# Elliott — \"passou de 0,786 → não é onda 2\" (hipótese do Tradeiros; passo 6 do plano, início)\n",
           "Gerado por `scripts/estudo_elliott_0786.py` (regra e critério no docstring, escritos antes de rodar). "
           "Estudo descritivo sobre `data/cenarios/{1h,4h}.jsonl.gz` (motor de Elliott do projeto, sem olhar o futuro), "
           "continuação medida nos mesmos candles BTCUSD Bitstamp. Horizonte de 60 candles.\n"]
    out.append("## Hipóteses de onda 2\n")
    out.append("| TF | hipóteses (viés, invalidação) únicas | alta | baixa | impulso | corretivo completo | principal | L mediano | E reconstruído = motor (impulso) |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    vered = {}
    for tf in ("1h", "4h"):
        b = df[(df.tf == tf) & (df.theta == LIMIARES[0])]
        conf = b.dif_E_motor.dropna()
        out.append(f"| {tf} | {len(b)} | {int((b.vies == 'bull').sum())} | {int((b.vies == 'bear').sum())} | "
                   f"{int((b.tipo == 'impulso').sum())} | {int((b.tipo != 'impulso').sum())} | {int(b.principal.sum())} | "
                   f"{100 * b.L_pct.median():.2f}% | {R.pct((conf < 0.01).mean()) if len(conf) else '-'} de {len(conf)} |")
    out.append("")
    out.append("## P(perde a origem | cruzou θ)\n")
    out.append("Principal = perdeu ÷ todos os cruzamentos (± EP binomial); decididos = perdeu ÷ (perdeu + sobreviveu). "
               "Sorteio = mesmas distâncias a partir de datas sorteadas do mesmo período (20 por cruzamento). "
               "Passeio = ruína do jogador a partir de exatamente θ. Critério da regra: θ = 0,786 com principal ≥ 70% "
               "e n ≥ 30.\n")
    for tf in ("1h", "4h"):
        d = df[df.tf == tf]
        out.append(f"### {tf}\n")
        out.append("| corte | θ | cruzamentos | perdeu a origem (principal) | entre decididos (n) | sorteio | passeio | ≥ sorteio + 2 EP |")
        out.append("|---|---|---|---|---|---|---|---|")
        out += tabela(d, "todos", None)
        for per, _, _ in R.PERIODOS:
            out += [x for x in tabela(d, per, lambda s, p=per: s.periodo == p) if "| 0.786 |" in x]
        for v in ("bull", "bear"):
            out += [x for x in tabela(d, v, lambda s, v=v: s.vies == v) if "| 0.786 |" in x]
        for tp in ("impulso", "corretivo_completo"):
            out += [x for x in tabela(d, tp, lambda s, tp=tp: s.tipo == tp) if "| 0.786 |" in x]
        out += [x for x in tabela(d, "principal", lambda s: s.principal == True) if "| 0.786 |" in x]
        out.append("")
        s = d[(d.theta == 0.786) & (d.cruzou == True)]
        n = len(s)
        p = s.perdeu.mean() if n else np.nan
        ep = np.sqrt(p * (1 - p) / n) if n else np.nan
        ctrl = s.ctrl_sorteio.mean() if n else np.nan
        if n < 30:
            v = "INCONCLUSIVO"
        elif p >= LIMIAR_REGRA:
            v = "VALE (≥ 70%)"
        else:
            v = "NÃO VALE (< 70%)"
        vered[tf] = (v, n, p, ep, ctrl)
        out.append("Desfechos em θ = 0,786: " + ", ".join(f"{k} {int(x)}" for k, x in s.desfecho.value_counts().items()) + "\n")
    out.append("## Veredito pelo critério\n")
    for tf, (v, n, p, ep, ctrl) in vered.items():
        out.append(f"- **{tf}: {v}** — n = {n}, perdeu a origem em {R.pct(p)} ± {100 * ep:.0f} pp; data sorteada "
                   f"{R.pct(ctrl)}; passeio aleatório 79%.")
    out.append("")
    return out, vered


def main():
    t0 = time.time()
    df = pd.concat([rodar(tf) for tf in ("1h", "4h")], ignore_index=True)
    df.to_csv(SAIDA, index=False)
    md, vered = resumo(df)
    SAIDA_MD.write_text("\n".join(md), encoding="utf-8")
    for tf, v in vered.items():
        print(tf, v)
    print(f"total {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
