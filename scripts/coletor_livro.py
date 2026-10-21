"""
COMO USAR: na raiz do projeto, clique duas vezes em coletor_livro.bat (ou rode
  .venv\\Scripts\\python.exe scripts\\coletor_livro.py) e deixe a janela aberta; Ctrl+C para parar.
Grava o livro de BTC (Coinbase, Binance, Bybit) a cada 30 s em dados/livro/<exchange>/<dia>.jsonl.gz e os negócios
a mercado e as liquidações dos perpétuos, por minuto, em dados/negocios/ e dados/liquidacoes/ (--sem-negocios desliga os dois);
log em logs/coletor_livro.log. Opções: --intervalo 30  --duracao 180 (segundos; sem = infinito)
  --exchanges coinbase,binance,bybit  --pasta dados/livro  --silencioso (sem log no console).
"""
from __future__ import annotations

import argparse
import os
import signal
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from conselho.coletor_livro import (  # noqa: E402
    BUSCADORES, INTERVALO_PADRAO_S, PASTA_DADOS, ColetorLivro, configurar_log,
)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Coletor do livro de ordens de BTC (só leitura).")
    ap.add_argument("--intervalo", type=float, default=INTERVALO_PADRAO_S, help="segundos entre snapshots")
    ap.add_argument("--duracao", type=float, default=None, help="parar após N segundos (padrão: infinito)")
    ap.add_argument("--exchanges", default=",".join(BUSCADORES), help="lista separada por vírgula")
    ap.add_argument("--pasta", default=PASTA_DADOS, help="pasta raiz dos arquivos jsonl.gz")
    ap.add_argument("--silencioso", action="store_true", help="não espelhar o log no console")
    ap.add_argument("--sem-negocios", action="store_true", help="não coletar os negócios (footprint)")
    args = ap.parse_args(argv)

    log = configurar_log(console=not args.silencioso)
    pedidas = [e.strip().lower() for e in args.exchanges.split(",") if e.strip()]
    desconhecidas = [e for e in pedidas if e not in BUSCADORES]
    if desconhecidas:
        log.error("exchanges desconhecidas: %s (válidas: %s)", desconhecidas, list(BUSCADORES))
        return 2
    buscadores = {e: BUSCADORES[e] for e in pedidas}

    coletor = ColetorLivro(raiz=args.pasta, intervalo_s=args.intervalo, buscadores=buscadores)
    if not args.sem_negocios:
        # negócios a mercado (quem agrediu) para o footprint, a absorção e os presos; mesmo sinal de parada
        from conselho.coletor_negocios import ColetorNegocios
        ColetorNegocios(parar=coletor.parar).iniciar()
        # liquidações dos perpétuos (Bybit + OKX), para o painel de liquidações
        from conselho.coletor_liquidacoes import ColetorLiquidacoes
        ColetorLiquidacoes(parar=coletor.parar).iniciar()
        # livro dos perpétuos perto do preço (Binance, Bybit, OKX), para o painel do livro perpétuo
        from conselho.coletor_livro_perp import ColetorLivroPerp
        ColetorLivroPerp(parar=coletor.parar).iniciar()

    def _parar(signum, frame):  # noqa: ARG001
        log.info("sinal %s recebido, parando...", signum)
        coletor.parar.set()

    signal.signal(signal.SIGINT, _parar)
    signal.signal(signal.SIGTERM, _parar)

    try:
        coletor.rodar(duracao_s=args.duracao)
    except KeyboardInterrupt:
        coletor.parar.set()
    return 0


if __name__ == "__main__":
    sys.exit(main())
