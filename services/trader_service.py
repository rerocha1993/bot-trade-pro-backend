# services/trader_service.py
"""
O TRADER (leitura de grau maior que orienta todos os bots de um par).

Mantém a memória hierárquica de contagens (ciclo semanal manda no primário diário) e o contexto de superciclo em
escala log, evoluídos candle a candle desde 2011 e persistidos em data/trader_<PAR>.pkl. Cada chamada só processa
os candles diários novos (custo ~0); a primeira construção percorre toda a história (alguns minutos).

    TraderService().leitura("BTCUSDT")  -> {'direcao', 'superciclo': {...}, 'subordinado', 'primaria', 'vivas', 'ciclo', ...}

A leitura entra em:
    - AnaliseMultiGrau(trader=...)  : veto/redução conforme estado de superciclo (nunca vender fundo terminal, não perseguir
                                      impulso maduro, etc.)
    - HedgeDial                      : hedge 0% em impulso de alta / fundo terminal; permitido em impulso maduro; máximo
                                      em correção inicial
    - API /elliott/trader
"""
from __future__ import annotations

import logging
import os
import pickle
import threading
import time
from typing import Dict, List, Optional

import pandas as pd

from core.elliott_pro.calibracao import Calibrador
from core.elliott_pro.memoria import MemoriaHierarquica
from core.market_data import reamostrar

logger = logging.getLogger(__name__)
PASTA = os.path.join("data")
ARQUIVO_BTC = os.path.join("data", "historico", "BTCUSD_bitstamp_1d.csv")
_LOCK = threading.Lock()
_CACHE: Dict[str, tuple] = {}
DIA = 86_400_000


class TraderService:
    def __init__(self, connector=None, backtest_service=None):
        self.connector = connector
        self.backtests = backtest_service

    # ------------------------------------------------------------- dados diários
    def _diario(self, par: str) -> List[List[float]]:
        par = par.replace("/", "").upper()
        serie: List[List[float]] = []
        if par == "BTCUSDT" and os.path.exists(ARQUIVO_BTC):
            df = pd.read_csv(ARQUIVO_BTC).sort_values("timestamp")
            serie = df[["timestamp", "open", "high", "low", "close", "volume"]].values.tolist()
        elif self.backtests is not None:
            try:
                serie = self.backtests.historico(par, "1d", 3650)
            except Exception as e:
                logger.warning("histórico diário indisponível para %s: %s", par, e)
        # completa com os candles diários FECHADOS mais recentes da exchange (base Bybit; diferença de basis é pequena)
        if self.connector is not None:
            try:
                recentes = self.connector.obter_ohlcv(par, "1d", 30, somente_fechados=True)
                ultimo = int(serie[-1][0]) if serie else 0
                for c in recentes:
                    if int(c[0]) > ultimo:
                        serie.append([int(c[0])] + [float(x) for x in c[1:6]])
            except Exception as e:
                logger.debug("sem candles recentes da exchange: %s", e)
        for c in serie:
            c[0] = int(c[0])
        return serie

    # ------------------------------------------------------------- memória persistida
    @staticmethod
    def _arquivo(par: str) -> str:
        return os.path.join(PASTA, f"trader_{par.replace('/', '').upper()}.pkl")

    def _carregar(self, par: str) -> Optional[Dict]:
        caminho = self._arquivo(par)
        if not os.path.exists(caminho):
            return None
        try:
            with open(caminho, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            logger.warning("memória do trader corrompida (%s): reconstruindo", e)
            return None

    def _salvar(self, par: str, estado: Dict):
        os.makedirs(PASTA, exist_ok=True)
        tmp = self._arquivo(par) + ".tmp"
        with open(tmp, "wb") as f:
            pickle.dump(estado, f)
        os.replace(tmp, self._arquivo(par))

    def _evoluir(self, par: str, serie: List[List[float]], estado: Optional[Dict], janela_d: int = 400, janela_w: int = 300) -> Dict:
        if estado is None:
            estado = {"memoria": MemoriaHierarquica(calibrador=Calibrador()), "ultimo_ts": 0, "wi": 0, "par": par}
        mem: MemoriaHierarquica = estado["memoria"]
        w1 = reamostrar(serie, "1d", "1w")
        wi = estado.get("wi", 0)
        t0 = time.time()
        novos = 0
        for i, c in enumerate(serie):
            if c[0] <= estado["ultimo_ts"]:
                continue
            novos += 1
            mem.superciclo.passo(c[0], c[2], c[3], c[4])
            if i < 30:
                continue
            while wi < len(w1) and w1[wi][0] + 7 * DIA <= c[0] + DIA:
                if wi >= 30:
                    win_w = w1[max(0, wi - janela_w + 1):wi + 1]
                    mem.ciclo.passo(win_w, w1[wi][2], w1[wi][3], w1[wi][4], w1[wi][0])
                wi += 1
            win_d = serie[max(0, i - janela_d + 1):i + 1]
            mem.primario.passo(win_d, c[2], c[3], c[4], c[0])
            estado["ultimo_ts"] = c[0]
        estado["wi"] = wi
        if novos:
            logger.info("trader %s: %d candles diários novos em %.1fs", par, novos, time.time() - t0)
            self._salvar(par, estado)
        return estado

    # ------------------------------------------------------------- leitura
    def leitura(self, par: str = "BTCUSDT", preco: Optional[float] = None, cache_seg: int = 900) -> Dict:
        par = par.replace("/", "").upper()
        item = _CACHE.get(par)
        if item and time.time() - item[0] < cache_seg and preco is None:
            return item[1]
        with _LOCK:
            serie = self._diario(par)
            if len(serie) < 60:
                return {"par": par, "direcao": "hold", "erro": "histórico diário insuficiente", "superciclo": {"estado": "indefinido"}}
            estado = self._evoluir(par, serie, self._carregar(par))
            mem: MemoriaHierarquica = estado["memoria"]
            p = float(preco) if preco else float(serie[-1][4])
            # leitura no preço atual sem alterar a memória (superciclo lê close; ajusta temporariamente)
            close_antigo = mem.superciclo.close
            mem.superciclo.close = p
            try:
                res = mem.trader(int(serie[-1][0]), p)
            finally:
                mem.superciclo.close = close_antigo
            res["par"] = par
            res["ultimo_candle"] = int(serie[-1][0])
            res["ciclos_fechados"] = mem.superciclo.ciclos
            if preco is None:
                _CACHE[par] = (time.time(), res)
            return res

    def reconstruir(self, par: str = "BTCUSDT") -> Dict:
        """Apaga a memória persistida e evolui de novo desde o início (após mudar regras/calibração)."""
        par = par.replace("/", "").upper()
        try:
            os.remove(self._arquivo(par))
        except FileNotFoundError:
            pass
        _CACHE.pop(par, None)
        return self.leitura(par, cache_seg=0)
