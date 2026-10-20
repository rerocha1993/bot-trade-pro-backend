"""
Baixa o footprint por minuto da Bybit (BTCUSDT perpétuo linear) num intervalo de datas, em paralelo, usando
``baixar_dia`` de scripts/baixar_negocios_bybit.py (mesmo formato, mesma pasta, pula minutos já gravados; não
apaga nem sobrescreve nada).

    .venv\\Scripts\\python.exe scripts\\baixar_negocios_bybit_periodo.py --inicio 2020-03-25 --fim 2026-10-19 --processos 6

Registra cada dia em dados/negocios/bybit_baixa_log.csv (dia, minutos gravados agora, minutos no arquivo, erro) para
achar buracos depois (dia sem arquivo na Bybit, erro de rede, dia com < 1440 minutos).
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from datetime import date, timedelta
from multiprocessing import Pool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from conselho.coletor_negocios import PASTA_NEGOCIOS  # noqa: E402
from conselho.livro_historico import carregar_dia  # noqa: E402

LOG = os.path.join(PASTA_NEGOCIOS, "bybit_baixa_log.csv")


def _um_dia(dia: str):
    from baixar_negocios_bybit import baixar_dia
    erro = ""
    n = 0
    for tentativa in range(3):
        try:
            n = baixar_dia(dia)
            erro = ""
            break
        except Exception as e:  # rede: tenta de novo
            erro = f"{type(e).__name__}: {e}"[:200]
            time.sleep(5 * (tentativa + 1))
    try:
        total = len({int(r["ts"]) for r in carregar_dia("bybit", dia, PASTA_NEGOCIOS)})
    except Exception as e:
        total, erro = -1, erro or f"leitura: {e}"[:200]
    return dia, n, total, erro


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inicio", required=True)
    ap.add_argument("--fim", required=True)
    ap.add_argument("--processos", type=int, default=6)
    ap.add_argument("--pular_completos", action="store_true", default=True)
    a = ap.parse_args(argv)
    d0, d1 = date.fromisoformat(a.inicio), date.fromisoformat(a.fim)
    dias = []
    d = d0
    while d <= d1:
        s = d.isoformat()
        caminho = os.path.join(PASTA_NEGOCIOS, "bybit", f"{s}.jsonl.gz")
        # dia já completo (1440 minutos) não é baixado de novo
        if a.pular_completos and os.path.exists(caminho):
            try:
                if len({int(r["ts"]) for r in carregar_dia("bybit", s, PASTA_NEGOCIOS)}) >= 1440:
                    d += timedelta(days=1)
                    continue
            except Exception:
                pass
        dias.append(s)
        d += timedelta(days=1)
    print(f"{len(dias)} dias a baixar", flush=True)
    novo = not os.path.exists(LOG)
    t0 = time.time()
    with open(LOG, "a", newline="", encoding="utf-8") as f, Pool(a.processos) as pool:
        w = csv.writer(f)
        if novo:
            w.writerow(["dia", "gravados_agora", "minutos_no_arquivo", "erro"])
        for i, (dia, n, total, erro) in enumerate(pool.imap_unordered(_um_dia, dias), 1):
            w.writerow([dia, n, total, erro])
            f.flush()
            if i % 20 == 0 or erro or total < 1440:
                print(f"{i}/{len(dias)} {dia} +{n} total={total} {erro} ({time.time() - t0:.0f}s)", flush=True)
    print(f"fim ({time.time() - t0:.0f}s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
