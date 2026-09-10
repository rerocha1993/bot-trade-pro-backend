# core/barras_fluxo.py
"""
BARRAS DE FLUXO: fecha a barra por quantidade negociada, não por relógio.

Candle de tempo é uma amostragem arbitrária. Na madrugada parada um candle de 1m é ruído puro; num momento
agitado ele esconde três movimentos dentro de si. Por isso a contagem de Elliott em 1m troca de fase quase a
cada leitura: não é o mercado que muda, é a régua que é ruim.

A barra de fluxo fecha quando passa uma quantidade combinada de negócio:

    tipo 'volume'  -> a cada N unidades do ativo (N BTC)
    tipo 'dolar'   -> a cada N dólares negociados (qty * preço)
    tipo 'tick'    -> a cada N negócios

Assim cada barra carrega a MESMA quantidade de informação, e delta, absorção e desequilíbrio ficam
comparáveis entre si. Mercado parado gera poucas barras; mercado agitado gera muitas — que é exatamente o
ritmo em que o scalp deveria decidir.

TAMANHO AUTOMÁTICO (tamanho=0): a régua se calibra pelo fluxo observado, mirando uma barra a cada
`segundos_alvo` em média. Um número fixo de BTC significaria coisas muito diferentes às 3h e às 15h.

Um negócio que estoura a barra é PARTIDO entre a barra que fecha e a próxima, para que todas tenham o mesmo
tamanho. Nada aqui fala com a corretora: entra negócio, sai barra.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from statistics import median
from typing import Deque, Dict, List, Optional, Sequence

TIPOS = ("volume", "dolar", "tick")


@dataclass
class Barra:
    """Uma barra fechada. `delta` é a agressão líquida: comprado a mercado menos vendido a mercado."""
    inicio_ms: int
    fim_ms: int
    abertura: float
    maxima: float
    minima: float
    fechamento: float
    volume: float = 0.0
    delta: float = 0.0
    negocios: int = 0
    # volume agredido por faixa de preço, para achar onde o fluxo se concentrou (absorção)
    por_preco: Dict[float, float] = field(default_factory=dict)

    @property
    def razao_delta(self) -> float:
        """Delta como fração do volume da barra (-1 = só venda a mercado, +1 = só compra)."""
        return self.delta / self.volume if self.volume > 0 else 0.0

    @property
    def alta(self) -> bool:
        return self.fechamento > self.abertura

    @property
    def duracao_s(self) -> float:
        return max(self.fim_ms - self.inicio_ms, 0) / 1000.0

    def as_ohlcv(self) -> List[float]:
        """No formato que o resto do sistema já entende: [ts, abertura, máxima, mínima, fechamento, volume]."""
        return [self.inicio_ms, self.abertura, self.maxima, self.minima, self.fechamento, self.volume]

    def as_dict(self) -> Dict:
        return {"inicio_ms": self.inicio_ms, "fim_ms": self.fim_ms, "abertura": self.abertura,
                "maxima": self.maxima, "minima": self.minima, "fechamento": self.fechamento,
                "volume": round(self.volume, 6), "delta": round(self.delta, 6),
                "razao_delta": round(self.razao_delta, 4), "negocios": self.negocios,
                "duracao_s": round(self.duracao_s, 1)}


def _passo(preco: float, agrupamento_pct: float) -> float:
    return max(preco * agrupamento_pct, 1e-9)


class AgregadorBarras:
    """
    Consome negócios e devolve barras fechadas.

    Só recebe negócios NOVOS: quem chama controla o cursor (o `MotorFluxo` faz isso pelo `seq` do websocket).
    Reprocessar a mesma lista contaria o volume duas vezes.
    """

    def __init__(self, tipo: str = "volume", tamanho: float = 0.0, max_barras: int = 400,
                 segundos_alvo: float = 30.0, agrupamento_pct: float = 0.0005,
                 recalibrar_a_cada_s: float = 300.0):
        tipo = (tipo or "volume").strip().lower()
        if tipo not in TIPOS:
            raise ValueError(f"tipo de barra inválido: {tipo!r} (use {', '.join(TIPOS)})")
        if tamanho < 0:
            raise ValueError("tamanho da barra não pode ser negativo")
        if segundos_alvo <= 0:
            raise ValueError("segundos_alvo tem que ser positivo")
        self.tipo = tipo
        self.tamanho = float(tamanho)          # 0 = calibra sozinho pelo fluxo
        self.segundos_alvo = float(segundos_alvo)
        self.agrupamento_pct = float(agrupamento_pct)
        # a recalibração é por RELÓGIO DE MERCADO, não por contagem de barras. Contando barras, o ajuste
        # chegava justamente quando não podia: com a régua grande demais as barras ficam lentas, então 60
        # delas levavam duas horas — num teste de 5 dias a régua terminou 4x maior do que o dia pedia.
        self.recalibrar_a_cada_s = float(recalibrar_a_cada_s)
        self.fechadas: Deque[Barra] = deque(maxlen=int(max_barras))
        self.parcial: Optional[Barra] = None
        self._acumulado = 0.0                  # quanto da barra em formação já foi preenchido
        # amostra recente do fluxo, (timestamp_ms, medida). Limitada de propósito: a régua tem que refletir o
        # ritmo de agora, e não a média do dia inteiro
        self._janela_calibragem_ms = int(max(segundos_alvo * 8, 240) * 1000)
        self._calibragem: Deque[tuple] = deque(maxlen=60000)
        self._calibrado_em_ms = 0
        self._tamanho_pendente = 0.0           # regua nova esperando a barra atual fechar
        self._tamanho_anterior = 0.0
        self.negocios_vistos = 0
        self.lacunas = 0                       # negócios perdidos, contados por quem alimenta

    # ------------------------------------------------------------------ régua
    def _medida(self, preco: float, qty: float) -> float:
        if self.tipo == "volume":
            return qty
        if self.tipo == "dolar":
            return qty * preco
        return 1.0                              # tick

    @property
    def calibrado(self) -> bool:
        return self.tamanho > 0

    def _calibrar(self) -> None:
        """
        Estima o tamanho da barra pelo fluxo observado, mirando uma barra a cada `segundos_alvo`.

        Usa a MÉDIA do fluxo por segundo, sem poda. Isso é deliberado, e custou três tentativas erradas.

        A conta certa para "uma barra a cada N segundos" é a média, por construção: régua = média x N faz o
        número de barras bater com o tempo decorrido. Toda tentativa de "robustecer" a estimativa encolheu a
        régua, porque em BTC o volume por segundo é absurdamente torto — num dia real medido aqui, a mediana
        por segundo foi 0,006 BTC contra uma média de 0,44, ou seja, 74x menor. A maioria dos segundos é
        quase vazia e alguns poucos carregam o dia inteiro.

            - mediana pura: régua 3x pequena, 41 mil barras num dia em vez de 2.880
            - poda no percentil 95: cortava justamente os segundos que carregam o volume
            - teto em 20x a mediana: teto de 0,12 quando a média era 0,44 — cortava quase tudo

        Sem poda, a baleia isolada infla a régua por uma janela. E é para o lado certo que isso erra: régua
        grande demais dá barra lenta e robô quieto; régua pequena demais dá ordem em cima de ruído. A
        recalibração periódica desfaz o exagero sozinha — e chega mais rápido justamente quando o mercado
        acelera, porque aí as barras fecham mais depressa.

        A amostra é sempre a JANELA RECENTE, nunca tudo o que já se viu. Misturar negócios de horas atrás
        com os de agora enche o meio de segundos vazios, e aí a conta desaba: foi assim que a régua saiu em
        0,1 BTC e o dia virou 275 mil barras de nada.
        """
        if not self._calibragem:
            return
        fim = int(self._calibragem[-1][0])
        inicio = fim - self._janela_calibragem_ms
        amostra_bruta = [(ts, m) for ts, m in self._calibragem if ts >= inicio]
        # precisa de amostra suficiente: pelo menos 4 janelas-alvo de observação e 200 negócios
        if not amostra_bruta or fim - int(amostra_bruta[0][0]) < self.segundos_alvo * 4000 or len(amostra_bruta) < 200:
            return
        por_segundo: Dict[int, float] = {}
        for ts, medida in amostra_bruta:
            s = ts // 1000
            por_segundo[s] = por_segundo.get(s, 0.0) + medida
        # segundos sem nenhum negócio também são mercado parado: contam como zero
        primeiro, ultimo = min(por_segundo), max(por_segundo)
        amostra = [por_segundo.get(s, 0.0) for s in range(primeiro, ultimo + 1)]
        if not amostra:
            return
        fluxo_s = sum(amostra) / len(amostra)
        if fluxo_s <= 0:
            return
        novo = fluxo_s * self.segundos_alvo
        self._calibrado_em_ms = fim
        if self.parcial is None:
            self.tamanho = novo
        else:
            # NUNCA no meio de uma barra. Trocar a regua com barra aberta a recorta retroativamente: uma
            # barra que ja tinha 90 BTC fechava declarando 10, e o resto virava um punhado de barras
            # sinteticas no mesmo milissegundo e no mesmo preco. A janela do gatilho ficava toda fantasma.
            self._tamanho_pendente = novo

    # ------------------------------------------------------------------ ingestão
    def ingerir(self, trades: Sequence[Dict]) -> List[Barra]:
        """
        Recebe negócios NOVOS ({'price', 'qty', 'side', 'timestamp'}) e devolve as barras que fecharam agora.

        Enquanto a régua não está calibrada, os negócios só alimentam a calibração: é melhor não decidir nada
        do que decidir em cima de barras de tamanho arbitrário.
        """
        trades = [t for t in (trades or []) if float(t.get("qty") or 0) > 0]
        if not trades:
            return []
        trades = sorted(trades, key=lambda t: int(t["timestamp"]))
        self.negocios_vistos += len(trades)
        # a amostra de calibragem é alimentada SEMPRE: é ela que deixa a régua acompanhar a mudança de ritmo
        # do mercado ao longo do dia, e ela só serve se for recente
        for t in trades:
            self._calibragem.append((int(t["timestamp"]), self._medida(float(t["price"]), float(t["qty"]))))
        if not self.calibrado:
            self._calibrar()
            if not self.calibrado:
                return []
        elif (self.recalibrar_a_cada_s
              and int(trades[-1]["timestamp"]) - self._calibrado_em_ms >= self.recalibrar_a_cada_s * 1000):
            # o ritmo muda ao longo do dia; a régua acompanha, mas nunca no meio de uma barra, e se a
            # amostra recente não der para calibrar, segue valendo a régua que já estava de pé
            self._calibrar()
        novas: List[Barra] = []
        for t in trades:
            novas.extend(self._ingerir_um(t))
        return novas

    def _ingerir_um(self, t: Dict) -> List[Barra]:
        preco = float(t["price"])
        restante = float(t["qty"])
        ts = int(t["timestamp"])
        compra = str(t.get("side", "")).lower() == "buy"
        passo = _passo(preco, self.agrupamento_pct)
        chave = round(round(preco / passo) * passo, 2)
        fechadas: List[Barra] = []
        while restante > 0:
            if self.parcial is None:
                if self._tamanho_pendente:      # a regua nova so vale a partir de uma barra nova
                    self.tamanho, self._tamanho_pendente = self._tamanho_pendente, 0.0
                self.parcial = Barra(inicio_ms=ts, fim_ms=ts, abertura=preco, maxima=preco,
                                     minima=preco, fechamento=preco)
                self._acumulado = 0.0
            b = self.parcial
            falta = self.tamanho - self._acumulado
            medida_total = self._medida(preco, restante)
            if medida_total <= falta or self.tipo == "tick":
                # o negócio inteiro cabe (tick nunca é partido: um negócio é indivisível na contagem)
                usada, medida_usada = restante, medida_total
                restante = 0.0
            else:
                # parte o negócio para que toda barra tenha exatamente o mesmo tamanho
                usada = restante * (falta / medida_total)
                medida_usada = falta
                restante -= usada
            b.fim_ms = ts
            b.maxima = max(b.maxima, preco)
            b.minima = min(b.minima, preco)
            b.fechamento = preco
            b.volume += usada
            b.delta += usada if compra else -usada
            b.negocios += 1
            b.por_preco[chave] = b.por_preco.get(chave, 0.0) + usada
            self._acumulado += medida_usada
            if self._acumulado >= self.tamanho - 1e-12:
                self.fechadas.append(b)
                fechadas.append(b)
                self._tamanho_anterior = self.tamanho
                self.parcial = None
                self._acumulado = 0.0
        return fechadas

    # ------------------------------------------------------------------ leitura
    def ohlcv(self, n: Optional[int] = None) -> List[List[float]]:
        barras = list(self.fechadas)
        if n:
            barras = barras[-n:]
        return [b.as_ohlcv() for b in barras]

    def ultimas(self, n: int) -> List[Barra]:
        return list(self.fechadas)[-n:]

    def status(self) -> Dict:
        ritmo = None
        if len(self.fechadas) >= 5:
            ritmo = round(median([b.duracao_s for b in self.ultimas(30)]), 1)
        return {"tipo": self.tipo, "tamanho": round(self.tamanho, 6), "calibrado": self.calibrado,
                "barras": len(self.fechadas), "negocios_vistos": self.negocios_vistos,
                "lacunas": self.lacunas, "segundos_alvo": self.segundos_alvo, "ritmo_s": ritmo}
