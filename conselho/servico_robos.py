# conselho/servico_robos.py
"""
Roda os 4 robôs do conselho (conselho/robos.py) EM SIMULAÇÃO, ao vivo: a cada 30 s avança as posições com as velas de
1 minuto da Bybit pública; a cada vela de 5 minutos fechada monta o contexto (mapa do dia, absorções, livro, funding e
open interest) e pergunta a cada robô sem posição se há plano novo. Nada é enviado à corretora.

Estado em data/robos/estado.json (banca e posição de cada robô; sobrevive a reinício) e cada trade fechado em
data/robos/trades.jsonl. Entradas, 1R e saídas vão para o Telegram quando ele está configurado.
Liga junto da API (api/main.py); ROBOS=0 no .env desliga.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Callable, Dict, List, Optional

from conselho import robos as R

logger = logging.getLogger(__name__)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA = os.path.join(RAIZ, "data", "robos")
PAR = "BTCUSDT"
INTERVALO_S = 30
DIAS_VELAS5 = 12
VALIDADE_DERIVATIVOS_S = 1800


class ServicoRobos:
    def __init__(self, pasta: str = PASTA, telegram=None, relogio: Callable[[], float] = time.time,
                 candles: Optional[Callable[[str, int], List[list]]] = None,
                 contexto: Optional[Callable[[int, List[list]], R.Contexto]] = None):
        self.pasta = pasta
        self.telegram = telegram
        self.relogio = relogio
        self._candles = candles or self._candles_bybit
        self._contexto = contexto or self._contexto_ao_vivo
        self.estado: Dict[str, Dict] = {}
        self.velas5: List[list] = []
        self.ultimo_5m_ms = 0
        self.ultimo_erro: Optional[str] = None
        self.ciclos = 0
        self._deriv: Dict = {"em": 0.0}
        self._lock = threading.Lock()
        self._parar = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.carregar()

    # ------------------------------------------------------------ persistência
    @property
    def arquivo_estado(self) -> str:
        return os.path.join(self.pasta, "estado.json")

    @property
    def arquivo_trades(self) -> str:
        return os.path.join(self.pasta, "trades.jsonl")

    def carregar(self):
        est = {}
        if os.path.exists(self.arquivo_estado):
            try:
                est = json.load(open(self.arquivo_estado, encoding="utf-8"))
            except Exception as e:
                logger.error("estado dos robôs ilegível, começando do zero: %s", e)
        for nome in R.ROBOS:
            e = est.get(nome) or {}
            pos = e.get("posicao")
            self.estado[nome] = {"banca": float(e.get("banca", R.BANCA_INICIAL)),
                                 "posicao": R.Posicao.de_dict(pos) if pos else None}

    def salvar(self):
        os.makedirs(self.pasta, exist_ok=True)
        dados = {n: {"banca": e["banca"], "posicao": e["posicao"].as_dict() if e["posicao"] else None}
                 for n, e in self.estado.items()}
        tmp = self.arquivo_estado + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.arquivo_estado)

    def trades(self, n: int = 200) -> List[Dict]:
        if not os.path.exists(self.arquivo_trades):
            return []
        with open(self.arquivo_trades, encoding="utf-8") as f:
            linhas = [json.loads(x) for x in f if x.strip()]
        return linhas[-n:]

    # ------------------------------------------------------------ thread
    @property
    def ativo(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def iniciar(self):
        if self.ativo:
            return
        self._parar.clear()
        self._thread = threading.Thread(target=self._loop, name="robos", daemon=True)
        self._thread.start()
        logger.info("robôs ligados em simulação: %s", ", ".join(R.ROBOS))

    def parar(self):
        self._parar.set()

    def _loop(self):
        while not self._parar.is_set():
            try:
                self.ciclo()
                self.ultimo_erro = None
            except Exception as e:
                self.ultimo_erro = f"{type(e).__name__}: {e}"
                logger.error("ciclo dos robôs falhou: %s", self.ultimo_erro)
            self._parar.wait(INTERVALO_S)

    # ------------------------------------------------------------ um ciclo
    def ciclo(self) -> List[str]:
        agora_s = int(self.relogio())
        eventos: List[str] = []
        with self._lock:
            eventos += self._avancar_posicoes(agora_s)
            fim_5m_ms = (agora_s * 1000) - (agora_s * 1000) % 300_000
            if fim_5m_ms > self.ultimo_5m_ms:
                self._atualizar_velas5(agora_s)
                self.ultimo_5m_ms = fim_5m_ms
                eventos += self._procurar_sinais(agora_s)
            self.salvar()
        self.ciclos += 1
        return eventos

    def _avancar_posicoes(self, agora_s: int) -> List[str]:
        abertas = [(n, e["posicao"]) for n, e in self.estado.items() if e["posicao"]]
        if not abertas:
            return []
        desde = min(p.ultimo_ts or p.plano.criado_s for _, p in abertas)
        velas = [v for v in self._candles("1m", (desde + 60) * 1000) if v[0] // 1000 + 60 <= agora_s]
        saida = []
        for nome, pos in abertas:
            for v in velas:
                ts = int(v[0] // 1000)
                if ts < pos.plano.criado_s:
                    continue
                for ev in R.passo(pos, ts, float(v[1]), float(v[2]), float(v[3]), float(v[4])):
                    saida.append(f"{nome}:{ev}")
                    self._notificar(nome, pos, ev)
                if pos.status in ("fechada", "expirada"):
                    self._encerrar(nome, pos)
                    break
        return saida

    def _encerrar(self, nome: str, pos: R.Posicao):
        e = self.estado[nome]
        if pos.status == "fechada":
            risco = R.risco_usdt(e["banca"])
            usdt = round(pos.resultado_r * risco, 2)
            e["banca"] = round(e["banca"] + usdt, 2)
            reg = {"robo": nome, "lado": "compra" if pos.plano.lado == 1 else "venda", "criado_s": pos.plano.criado_s,
                   "entrada_s": pos.t1_s, "saida_s": pos.fim_s, "medio": round(pos.medio, 2), "stop": pos.plano.stop,
                   "alvo": pos.plano.alvo, "saida": pos.tipo_saida, "tomou_1r": pos.tomou_1r,
                   "resultado_r": round(pos.resultado_r, 3), "resultado_usdt": usdt, "banca": e["banca"],
                   "motivo": pos.plano.motivo}
            os.makedirs(self.pasta, exist_ok=True)
            with open(self.arquivo_trades, "a", encoding="utf-8") as f:
                f.write(json.dumps(reg, ensure_ascii=False) + "\n")
        e["posicao"] = None

    def _atualizar_velas5(self, agora_s: int):
        desde = self.velas5[-1][0] if self.velas5 else (agora_s - DIAS_VELAS5 * 86400) * 1000
        novas = self._candles("5m", int(desde))
        if novas:
            vistos = {int(v[0]): v for v in self.velas5}
            for v in novas:
                vistos[int(v[0])] = [int(v[0])] + [float(x) for x in v[1:6]]
            corte = (agora_s - DIAS_VELAS5 * 86400) * 1000
            # só velas fechadas
            self.velas5 = [vistos[k] for k in sorted(vistos) if k >= corte and k + 300_000 <= agora_s * 1000]

    def _procurar_sinais(self, agora_s: int) -> List[str]:
        livres = [n for n, e in self.estado.items() if e["posicao"] is None]
        if not livres or len(self.velas5) < 288 * 11:
            return []
        ctx = self._contexto(agora_s, self.velas5)
        saida = []
        for nome in livres:
            try:
                plano = R.ESTRATEGIAS[nome](ctx)
            except Exception as e:
                logger.warning("robô %s falhou ao avaliar: %s: %s", nome, type(e).__name__, e)
                continue
            if plano:
                pos = R.Posicao(plano=plano, ultimo_ts=agora_s - 60)
                self.estado[nome]["posicao"] = pos
                saida.append(f"{nome}:plano")
                self._notificar(nome, pos, "plano")
        return saida

    # ------------------------------------------------------------ dados ao vivo
    @staticmethod
    def _candles_bybit(tf: str, desde_ms: int) -> List[list]:
        from conselho import mercado
        return mercado.candles(PAR, tf, desde_ms, pausa_s=0)

    def _contexto_ao_vivo(self, agora_s: int, velas5: List[list]) -> R.Contexto:
        from conselho import fluxo, mercado
        from conselho.mapa_do_dia import mapa as montar_mapa

        dia_ms = (agora_s * 1000) - (agora_s * 1000) % 86_400_000
        m = montar_mapa(velas5, dia_ms)                     # o mapa fixado à 00:00 de hoje, como nos estudos
        ultimo_5m = (agora_s - agora_s % 300) - 300
        absorcoes, coluna = [], None
        try:
            leitura = fluxo.leitura_recente(agora_s, horas=3)
            absorcoes = [e for e in leitura["absorcoes"] if e["ts"] == ultimo_5m]
            cols = leitura["calor"].get("colunas", [])
            coluna = cols[-1] if cols else None
        except Exception as e:
            logger.warning("leitura de fluxo indisponível neste ciclo: %s", e)
        if agora_s - self._deriv["em"] > VALIDADE_DERIVATIVOS_S:
            try:
                fund = [x[1] for x in mercado.funding(PAR)]
                oi = mercado.open_interest(PAR, (agora_s - 86400 - 600) * 1000, agora_s * 1000)
                self._deriv = {"em": agora_s, "funding_pct": R.percentil(fund[-1], fund) if fund else None,
                               "oi_24h_pct": (oi[-1][1] / oi[0][1] - 1) * 100 if len(oi) > 1 else None}
            except Exception as e:
                logger.warning("funding/OI indisponíveis: %s", e)
        return R.Contexto(agora_s=agora_s, velas5=velas5, mapa=m, absorcoes=absorcoes, calor_ultimo=coluna,
                          funding_pct=self._deriv.get("funding_pct"), oi_24h_pct=self._deriv.get("oi_24h_pct"))

    # ------------------------------------------------------------ avisos e leitura
    def _notificar(self, nome: str, pos: R.Posicao, ev: str):
        if self.telegram is None or not getattr(self.telegram, "ativo", False):
            return
        pl = pos.plano
        lado = "COMPRA" if pl.lado == 1 else "VENDA"
        f = lambda x: f"{x:,.0f}".replace(",", ".")
        cab = f"[simulação] {R.ROBOS[nome]} · {lado}"
        if ev == "plano":
            zona = " · ".join(f"{f(p)} ({w:.0%})" for p, w in pl.fatias)
            ate = time.strftime("%H:%M", time.gmtime(pl.valido_ate_s))
            txt = (f"{cab}\n{pl.motivo}\nLimitadas: {zona} (valem até {ate} UTC)\n"
                   f"Stop {f(pl.stop)} · alvo {f(pl.alvo)} · em 1R realiza 50% e o stop vai ao médio")
        elif ev == "preencheu":
            txt = f"{cab}: entrou, médio {f(pos.medio)}"
        elif ev == "1r":
            txt = f"{cab}: 1R atingido, realizou 50%, stop no médio {f(pos.medio)}"
        elif ev == "expirou":
            txt = f"{cab}: ordens canceladas, o preço não voltou à zona"
        else:
            r = pos.resultado_r or 0.0
            txt = f"{cab}: saiu por {ev}, resultado {r:+.2f} R · banca virtual {self.estado[nome]['banca']:,.2f} USDT"
        try:
            self.telegram.info(txt)
        except Exception as e:
            logger.warning("Telegram falhou para o robô %s: %s", nome, e)

    def status(self) -> Dict:
        trades = self.trades(10_000)
        robos = []
        for nome, e in self.estado.items():
            ts = [t for t in trades if t["robo"] == nome]
            rs = [t["resultado_r"] for t in ts]
            pos = e["posicao"]
            robos.append({
                "robo": nome, "nome": R.ROBOS[nome], "banca": e["banca"], "trades": len(ts),
                "ganhos": sum(1 for r in rs if r > 0), "resultado_r": round(sum(rs), 2),
                "media_r": round(sum(rs) / len(rs), 3) if rs else None,
                "posicao": None if not pos else {
                    "status": pos.status, "lado": "compra" if pos.plano.lado == 1 else "venda",
                    "fatias": pos.plano.fatias, "stop": pos.plano.stop, "stop_atual": pos.stop_cur, "alvo": pos.plano.alvo,
                    "medio": pos.medio, "tomou_1r": pos.tomou_1r, "criado_s": pos.plano.criado_s,
                    "valido_ate_s": pos.plano.valido_ate_s, "motivo": pos.plano.motivo},
            })
        return {"ativo": self.ativo, "ciclos": self.ciclos, "ultimo_erro": self.ultimo_erro,
                "velas5": len(self.velas5), "simulacao": True, "risco_pct": R.RISCO_PCT * 100,
                "banca_inicial": R.BANCA_INICIAL, "robos": robos}


_servico: Optional[ServicoRobos] = None


def get_servico_robos() -> ServicoRobos:
    global _servico
    if _servico is None:
        from conselho.telegram import TelegramAlertService
        _servico = ServicoRobos(telegram=TelegramAlertService())
    return _servico
