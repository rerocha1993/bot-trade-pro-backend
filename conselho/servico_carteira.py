# conselho/servico_carteira.py
"""
A carteira do Tradeiros (conselho/tradeiros/carteira.py) EM SIMULAÇÃO, ao vivo: 1 BTC de colateral no inverse para o
Shaka e 1 para o Maroja, desde `CARTEIRA_INICIO` (padrão 28/10/2026, o dia em que voltou ao sistema). Nada vai para
a corretora.

A cada bloco de 30 min fechado: busca velas e derivativos recentes (conselho/tradeiros/recentes.py), soma por cima
dos CSVs do projeto e roda a carteira do início até o último bloco de 30 min FECHADO, com as mesmas regras e custos do
backtest (scripts/backtest_tradeiros.py).

O passado não pode mudar depois: as APIs só devolvem as últimas semanas (open interest e long/short 40 dias, funding
~66 dias, velas de 30 min ~25 dias). Por isso ficam guardados em data/carteira/:
    velas_30m.csv   as velas de 30 min fechadas desde o início − 30 dias
    leituras.pkl    a leitura do dia e o mapa de Elliott de cada dia já planejado (feitos à 00:00 só com o que tinha
                    fechado; não dependem da carteira, então servem aos dois operadores e nunca são refeitos)
    funding.json    o funding de cada 8 h desde o início
Uma leitura só é guardada quando nenhuma busca falhou; com falha, o dia é refeito no próximo bloco.

O resultado vai para data/carteira/estado.json e para a tela Carteira. Liga junto da API; CARTEIRA=0 no .env desliga.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import pickle
import threading
import time
from typing import Callable, Dict, Optional, Tuple

import pandas as pd

from conselho.tpo import BLOCO_MS
from conselho.tradeiros import recentes as REC
from conselho.tradeiros.carteira import Carteira
from conselho.tradeiros.elliott_mapa import MapaElliott
from conselho.tradeiros.leitura import Dados, LeituraDiaria
from conselho.tradeiros.regras import PERFIS, planejar

logger = logging.getLogger(__name__)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA = os.path.join(RAIZ, "data", "carteira")
INICIO = os.getenv("CARTEIRA_INICIO", "2026-10-28")
INTERVALO_S = 60               # de minuto em minuto olha se fechou um bloco de 30 min; só então recalcula (~10 s)
OPERADORES = ("shaka", "maroja")
#: o range e o Elliott olham para trás: as velas de 30 min guardadas começam 30 dias antes do início
FOLGA_VELAS_MS = 30 * 86_400_000
#: quantos dias de decisões vão na resposta da API (a tela usa só as de hoje)
DIAS_LOG = 3
DIA_MS = 86_400_000


def inicio_ms(texto: str = INICIO) -> int:
    return int(dt.datetime.fromisoformat(texto).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


class ServicoCarteira:
    def __init__(self, pasta: str = PASTA, raiz: str = RAIZ, inicio: Optional[int] = None,
                 buscar: Callable[[int], Dict] = REC.buscar, relogio: Callable[[], float] = time.time):
        self.pasta = pasta
        self.raiz = raiz
        self.inicio = inicio if inicio is not None else inicio_ms()
        self._buscar = buscar
        self.relogio = relogio
        self.ultimo: Optional[Dict] = None
        self.ultimo_erro: Optional[str] = None
        self._lock = threading.Lock()
        self._parar = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._tentou_fim: Optional[int] = None
        try:
            with open(self.arquivo_estado, encoding="utf-8") as f:
                self.ultimo = json.load(f)
        except (OSError, ValueError):
            pass
        self.leituras: Dict[int, Tuple] = {}
        try:
            with open(self.arquivo_leituras, "rb") as f:
                self.leituras = pickle.load(f)
        except FileNotFoundError:
            pass
        except (OSError, ValueError, pickle.UnpicklingError, EOFError, AttributeError, ImportError):
            logger.warning("carteira: leituras guardadas ilegíveis; os dias serão lidos de novo")
        self.funding: Dict[int, float] = {}
        try:
            with open(self.arquivo_funding, encoding="utf-8") as f:
                self.funding = {int(k): float(v) for k, v in json.load(f).items()}
        except (OSError, ValueError):
            pass

    @property
    def arquivo_estado(self) -> str:
        return os.path.join(self.pasta, "estado.json")

    @property
    def arquivo_velas(self) -> str:
        return os.path.join(self.pasta, "velas_30m.csv")

    @property
    def arquivo_leituras(self) -> str:
        return os.path.join(self.pasta, "leituras.pkl")

    @property
    def arquivo_funding(self) -> str:
        return os.path.join(self.pasta, "funding.json")

    def _gravar(self, caminho: str, escrever: Callable, binario: bool = False) -> None:
        """Escreve num .tmp e troca de uma vez: um reinício no meio da escrita não deixa o arquivo pela metade."""
        os.makedirs(self.pasta, exist_ok=True)
        tmp = caminho + ".tmp"
        with open(tmp, "wb" if binario else "w", **({} if binario else {"encoding": "utf-8", "newline": ""})) as f:
            escrever(f)
        os.replace(tmp, caminho)

    # ------------------------------------------------------------ o que fica guardado
    def _guardar_velas(self, novas: Optional[pd.DataFrame], agora: int) -> Optional[pd.DataFrame]:
        """Junta as velas FECHADAS novas às guardadas (no mesmo instante vale a nova) e devolve tudo desde início −
        folga. A vela aberta nunca é gravada: se a busca seguinte falhar, ela contaria como fechada."""
        try:
            antigas = pd.read_csv(self.arquivo_velas)
        except (OSError, ValueError):
            antigas = None
        if novas is not None:
            novas = novas[novas["timestamp"] + BLOCO_MS <= agora]
        if novas is None or novas.empty:
            return antigas
        juntas = novas if antigas is None else pd.concat([antigas[~antigas["timestamp"].isin(novas["timestamp"])], novas])
        juntas = juntas[juntas["timestamp"] >= self.inicio - FOLGA_VELAS_MS].sort_values("timestamp")
        self._gravar(self.arquivo_velas, lambda f: juntas.to_csv(f, index=False))
        return juntas.reset_index(drop=True)

    def _guardar_funding(self, novo: Dict[int, float]) -> Dict[int, float]:
        """Funding desde o início: o guardado mais o que a API devolveu agora (ela só tem ~66 dias)."""
        antes = dict(self.funding)
        self.funding.update({t: v for t, v in novo.items() if t >= self.inicio - DIA_MS})
        if self.funding != antes:
            self._gravar(self.arquivo_funding,
                         lambda f: json.dump({str(k): v for k, v in sorted(self.funding.items())}, f))
        return self.funding

    def _planejadores(self, dados: Dados, guardar: bool) -> Tuple[Dict[str, Callable], Callable[[], int]]:
        """Um planejador por operador. A leitura e o Elliott de cada dia são feitos uma vez, valem para os dois e,
        com `guardar`, ficam para sempre em self.leituras. Devolve também quantos dias novos foram lidos."""
        cache = {"leitura": None, "mapa": None, "novos": 0}

        def ler(ts: int) -> Tuple:
            if ts in self.leituras:
                return self.leituras[ts]
            if cache["leitura"] is None:
                cache["leitura"], cache["mapa"] = LeituraDiaria(dados), MapaElliott(dados)
            par = (cache["leitura"].ler(ts), cache["mapa"].ler(ts))
            if guardar:
                self.leituras[ts] = par
                cache["novos"] += 1
            return par

        def para(pf):
            return lambda ts, hedge_atual: planejar(*ler(ts), pf, hedge_atual)

        return {nome: para(PERFIS[nome]) for nome in OPERADORES}, lambda: cache["novos"]

    # ------------------------------------------------------------ cálculo
    def calcular(self) -> Dict:
        agora = int(self.relogio() * 1000)
        rec = self._buscar(agora)
        falhas = rec.get("falhas", [])
        velas30 = self._guardar_velas(rec.get("30m"), agora)
        if velas30 is not None:
            # a vela aberta fica de fora: o bloco só conta depois de fechado, como no backtest
            rec["30m"] = velas30[velas30["timestamp"] + BLOCO_MS <= agora]
        dados = Dados.do_projeto(self.raiz, recentes=rec, intraday_dias=45)
        funding = self._guardar_funding(dict(zip(dados.funding[0], dados.funding[1])))
        fim = agora // BLOCO_MS * BLOCO_MS
        saida = {"atualizado_ms": agora, "inicio_ms": self.inicio, "fim_ms": fim, "falhas": falhas, "operadores": {}}
        planejadores, novos = self._planejadores(dados, guardar=not falhas)
        for nome in OPERADORES:
            saida["operadores"][nome] = Carteira(dados.blocos, planejadores[nome], PERFIS[nome], funding,
                                                 guardar_log=True).executar(self.inicio, fim, fechar_no_fim=False)
        if novos():
            self._gravar(self.arquivo_leituras, lambda f: pickle.dump(self.leituras, f), binario=True)
        self._gravar(self.arquivo_estado, lambda f: json.dump(saida, f, ensure_ascii=False))
        with self._lock:
            self.ultimo = saida
            self.ultimo_erro = None
        return saida

    # ------------------------------------------------------------ laço
    def _loop(self):
        while not self._parar.is_set():
            fim = int(self.relogio() * 1000) // BLOCO_MS * BLOCO_MS
            try:
                # uma tentativa por bloco: com erro, tenta de novo só no bloco seguinte (sem martelar as corretoras)
                if fim != self._tentou_fim and fim != (self.ultimo or {}).get("fim_ms"):
                    self._tentou_fim = fim
                    self.calcular()
            except Exception as e:                                   # noqa: BLE001 — tenta de novo na próxima volta
                logger.exception("carteira: falhou")
                with self._lock:
                    self.ultimo_erro = f"{type(e).__name__}: {e}"
            self._parar.wait(INTERVALO_S)

    def iniciar(self):
        if self._thread and self._thread.is_alive():
            return
        self._parar.clear()
        self._thread = threading.Thread(target=self._loop, name="carteira", daemon=True)
        self._thread.start()

    def parar(self):
        self._parar.set()
        if self._thread:
            self._thread.join(timeout=30)                           # deixa terminar a escrita em curso

    def status(self) -> Dict:
        """O último cálculo, com as decisões só dos últimos DIAS_LOG dias (a lista inteira cresce para sempre)."""
        with self._lock:
            ultimo, erro = self.ultimo, self.ultimo_erro
        if ultimo:
            corte = ultimo["fim_ms"] // DIA_MS * DIA_MS - (DIAS_LOG - 1) * DIA_MS
            ultimo = {**ultimo, "operadores": {n: {**o, "log": [x for x in (o.get("log") or []) if x["ts"] >= corte]}
                                               for n, o in ultimo["operadores"].items()}}
        return {"ultimo": ultimo, "erro": erro, "intervalo_s": INTERVALO_S,
                "ativo": bool(self._thread and self._thread.is_alive())}


_servico: Optional[ServicoCarteira] = None


def get_servico_carteira() -> ServicoCarteira:
    global _servico
    if _servico is None:
        _servico = ServicoCarteira()
    return _servico
