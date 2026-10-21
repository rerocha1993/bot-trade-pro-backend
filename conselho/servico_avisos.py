# services/avisos_service.py
"""
Serviço de avisos do conselho (só informa, nunca opera). Thread no molde da manutenção do BotManager, a cada 60 s:
monta o mapa do dia (conselho/mapa_do_dia.py) com candles de 5 min da Bybit pública, avalia os avisos
(conselho/avisos.py: mapa às 00:00/08:00/13:30 UTC e proximidade de 0,2% a nível do composto, naked POC ou
abertura semanal, um por nível por dia), grava cada aviso em data/avisos.jsonl e manda pelo Telegram quando ativo.
Desligado por padrão: liga com SERVICO_AVISOS=1 no .env (api/main.py). Rotas: GET /api/avisos/ultimos e /mapa.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from conselho.avisos import Aviso, Estado, avaliar, avisos_de_fluxo
from conselho.mapa_do_dia import CANDLE_MS, DIA_MS, Mapa, mapa as montar_mapa

logger = logging.getLogger(__name__)

PAR = "BTCUSDT"
DIAS_HISTORICO = 36                      # composto de 10 dias + janela de 30 dias do pivô virgem
INTERVALO_S = 60
VALIDADE_MAPA_S = 60
INTERVALO_FLUXO_S = 300          # a leitura de fluxo (absorção e presos) roda a cada 5 min
CAMINHO_PADRAO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "avisos.jsonl")


class AvisosService:
    """
    `obter_candles(desde_ms) -> [[ts, o, h, l, c, v], ...]` (5 min) e `obter_preco() -> float | None` são injetados:
    ao vivo vêm do conector público da Bybit; nos testes, de listas sintéticas. Os candles ficam em memória e
    cada ciclo só busca o que falta desde o último candle guardado.
    """

    def __init__(self, obter_candles: Callable[[int], Sequence[Sequence[float]]], obter_preco: Callable[[], Optional[float]],
                 telegram=None, caminho: str = CAMINHO_PADRAO, intervalo_s: int = INTERVALO_S,
                 relogio: Callable[[], float] = time.time,
                 obter_fluxo: Optional[Callable[[float], Tuple[List[Dict], List[Dict]]]] = None,
                 intervalo_fluxo_s: int = INTERVALO_FLUXO_S):
        self.obter_candles = obter_candles
        self.obter_preco = obter_preco
        self.telegram = telegram
        self.caminho = caminho
        self.intervalo_s = intervalo_s
        self.relogio = relogio
        self.obter_fluxo = obter_fluxo          # (agora_s) -> (presos, absorcoes); ver conselho/fluxo.py
        self.intervalo_fluxo_s = intervalo_fluxo_s
        self.ultimo_fluxo_em: float = 0.0
        self.estado = Estado()
        self.candles: List[list] = []
        self.ultimo_mapa: Optional[Mapa] = None
        self.ultimo_mapa_em: float = 0.0
        self.ultimo_erro: Optional[str] = None
        self.ciclos = 0
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._parar = threading.Event()

    # ------------------------------------------------------------ thread
    @property
    def ativo(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def iniciar(self):
        if self.ativo:
            return
        self.estado = Estado.de_registros(self.ultimos(500))        # não repete o que já saiu antes de reiniciar
        self._parar.clear()
        self._thread = threading.Thread(target=self._loop, name="avisos", daemon=True)
        self._thread.start()
        logger.info("serviço de avisos ligado (a cada %d s, arquivo %s)", self.intervalo_s, self.caminho)

    def parar(self):
        self._parar.set()

    def _loop(self):
        while not self._parar.is_set():
            try:
                self.ciclo()
            except Exception as e:
                self.ultimo_erro = f"{type(e).__name__}: {e}"
                logger.error("ciclo de avisos falhou: %s", self.ultimo_erro)
            self._parar.wait(self.intervalo_s)

    # ------------------------------------------------------------ um ciclo
    def _atualizar_candles(self, agora_ms: int):
        desde = self.candles[-1][0] if self.candles else agora_ms - DIAS_HISTORICO * DIA_MS
        novos = self.obter_candles(int(desde))
        if novos:
            vistos = {int(c[0]): c for c in self.candles}
            for c in novos:
                vistos[int(c[0])] = [int(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5] or 0)]
            corte = agora_ms - DIAS_HISTORICO * DIA_MS
            self.candles = [vistos[k] for k in sorted(vistos) if k >= corte]

    def montar_mapa(self, agora_ms: Optional[int] = None) -> Mapa:
        agora_ms = int(agora_ms if agora_ms is not None else self.relogio() * 1000)
        with self._lock:
            self._atualizar_candles(agora_ms)
            m = montar_mapa(self.candles, agora_ms)
            self.ultimo_mapa, self.ultimo_mapa_em = m, self.relogio()
            return m

    def ciclo(self, agora_ms: Optional[int] = None) -> List[Aviso]:
        agora_ms = int(agora_ms if agora_ms is not None else self.relogio() * 1000)
        m = self.montar_mapa(agora_ms)
        preco = None
        try:
            preco = self.obter_preco()
        except Exception as e:
            logger.warning("preço atual indisponível, usando o último fechamento: %s", e)
        preco = float(preco) if preco else m.preco
        avisos = avaliar(m, preco, self.estado)
        agora_s = agora_ms / 1000.0
        if self.obter_fluxo is not None and agora_s - self.ultimo_fluxo_em >= self.intervalo_fluxo_s:
            self.ultimo_fluxo_em = agora_s
            try:
                presos, absorcoes = self.obter_fluxo(agora_s)
                avisos += avisos_de_fluxo(presos, absorcoes, preco, self.estado, agora_s)
            except Exception as e:
                logger.warning("leitura de fluxo falhou neste ciclo: %s: %s", type(e).__name__, e)
        for a in avisos:
            self._gravar(a)
            self._enviar(a)
        self.ciclos += 1
        self.ultimo_erro = None
        return avisos

    def _gravar(self, a: Aviso):
        os.makedirs(os.path.dirname(self.caminho) or ".", exist_ok=True)
        with open(self.caminho, "a", encoding="utf-8") as f:
            f.write(json.dumps(a.as_dict(), ensure_ascii=False) + "\n")

    def _enviar(self, a: Aviso):
        if self.telegram is None or not getattr(self.telegram, "ativo", False):
            return
        try:
            nota = "" if a.ressalva in a.texto else f"\n({a.ressalva})"
            self.telegram.info(f"{a.titulo}\n{a.texto}{nota}")
        except Exception as e:
            logger.warning("Telegram falhou no aviso %s: %s", a.id, e)

    # ------------------------------------------------------------ leitura (rotas)
    def ultimos(self, n: int = 50) -> List[Dict]:
        """Os últimos `n` avisos gravados, do mais novo para o mais antigo."""
        if not os.path.exists(self.caminho):
            return []
        out = []
        with open(self.caminho, encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    out.append(json.loads(linha))
                except json.JSONDecodeError:
                    continue
        return list(reversed(out[-n:]))

    def mapa_atual(self) -> Mapa:
        """Mapa de agora: o do último ciclo se for recente, senão monta um (a rota funciona mesmo com a thread desligada)."""
        if self.ultimo_mapa is not None and self.relogio() - self.ultimo_mapa_em < VALIDADE_MAPA_S:
            return self.ultimo_mapa
        return self.montar_mapa()

    def status(self) -> Dict:
        return {"ativo": self.ativo, "intervalo_s": self.intervalo_s, "ciclos": self.ciclos, "ultimo_erro": self.ultimo_erro,
                "candles": len(self.candles), "telegram": bool(self.telegram is not None and getattr(self.telegram, "ativo", False)),
                "arquivo": self.caminho}


_service: Optional[AvisosService] = None


def get_avisos_service() -> AvisosService:
    """Instância única ligada à API pública da Bybit (conselho/mercado.py); a thread só sobe com `iniciar()`."""
    global _service
    if _service is None:
        from conselho import mercado
        from conselho.telegram import TelegramAlertService

        def candles(desde_ms: int):
            return mercado.candles(PAR, "5m", int(desde_ms))

        def preco():
            return mercado.preco(PAR)

        def fluxo_agora(agora_s: float):
            from conselho import fluxo
            r = fluxo.leitura_recente(agora_s)
            return r["presos"], r["absorcoes"]

        _service = AvisosService(candles, preco, telegram=TelegramAlertService(), obter_fluxo=fluxo_agora)
    return _service
