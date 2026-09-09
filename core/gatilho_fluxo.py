# core/gatilho_fluxo.py
"""
GATILHO DE FLUXO: o momento da entrada sai da fita, não do relógio.

O contexto (core/contexto_fluxo.py) diz de que lado dá para operar e em que preços. Aqui se decide QUANDO,
lendo as barras de fluxo (core/barras_fluxo.py) e o livro. São três leituras:

    A) ABSORÇÃO NO NÍVEL (reversão)
       Vendedor agredindo em cima de um suporte e o suporte não cede. A agressão foi absorvida por quem
       estava passivo ali; quando ela acaba, o preço volta. É a entrada de melhor qualidade do scalp,
       porque o stop fica logo abaixo do nível que acabou de provar que segura.

    B) CONTINUAÇÃO COM FLUXO
       Preço recua até um nível a favor da direção do contexto e a agressão vira a favor ali. Entra na
       retomada, não no meio do movimento.

    C) VETOS (não perseguir)
       - preço longe de qualquer nível: entrar aqui é perseguir, com o stop no vazio
       - esforço sem resultado na continuação: muita agressão a favor e preço parado quer dizer que tem
         alguém grande passivo do outro lado. Note que a MESMA observação confirma a absorção, porque lá a
         agressão é contra a entrada: é o sinal que se inverte conforme o lado de quem está agredindo.

Nada aqui envia ordem, e nada aqui decide direção sozinho: uma leitura de fluxo contra a direção que o
contexto permite é descartada. Elliott continua sendo a lei — só parou de ser cronômetro.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Dict, List, Optional, Sequence

from core.barras_fluxo import Barra
from core.contexto_fluxo import Contexto, Nivel


@dataclass(frozen=True)
class ParametrosFluxo:
    """
    Números do gatilho. Ficam num objeto só para poderem ser calibrados e testados sem caçar constante
    espalhada pelo código.
    """
    barras_janela: int = 5           # quantas barras fechadas o gatilho lê
    barras_minimas: int = 20         # histórico mínimo antes de operar
    limiar_delta: float = 0.25       # |delta acumulado| / volume da janela
    limiar_book: float = 0.15        # desequilíbrio de livro que conta como contra
    tolerancia_nivel: float = 0.0015  # o quanto o preço pode estar longe do nível e ainda "estar nele"
    folga_nivel: float = 0.0008      # o quanto o preço pode furar o nível sem que ele seja considerado perdido
    max_dist_nivel: float = 0.004    # além disso é perseguir: sem nível, sem entrada
    deslocamento_minimo: float = 0.5  # esforço x resultado, em ranges médios de barra
    absorcao_minima: float = 0.30    # concentração de volume NO PREÇO para chamar de absorção
    # banda estreita de propósito: absorção é briga por UM preço. Com a tolerância larga (0,15%) a
    # concentração dava 100% em toda entrada e o filtro não filtrava nada — foi o que o backtest mostrou.
    banda_absorcao: float = 0.0004
    # a agressão tem que estar SECANDO, não só existindo. Sem isto, "absorção num suporte" vira faca caindo:
    # num dia de queda o preço para em todo nível por um minuto e depois passa por cima.
    esgotamento_maximo: float = 0.7   # delta da última barra x média das anteriores da janela
    rejeicao_minima: float = 0.5      # onde a última barra fechou dentro do próprio range (0 = no fundo)

    def __post_init__(self):
        if self.barras_janela < 2:
            raise ValueError("a janela do gatilho precisa de pelo menos 2 barras")
        if self.barras_minimas < self.barras_janela:
            raise ValueError("o histórico mínimo não pode ser menor que a janela")
        if not (0 < self.limiar_delta < 1):
            raise ValueError("limiar_delta é uma fração do volume: tem que ficar entre 0 e 1")
        if self.folga_nivel > self.tolerancia_nivel:
            raise ValueError("a folga para furar o nível não pode ser maior que a tolerância de estar nele")


PADRAO = ParametrosFluxo()


def _hold(motivo: str, **extra) -> Dict:
    return {"acao": "hold", "motivo": motivo, "forca": 0.0, "gatilho": None, "nivel": None, **extra}


class GatilhoFluxo:
    """Lê as barras de fluxo e diz se é hora de entrar. Sem estado: cada chamada olha a janela atual."""

    def __init__(self, parametros: Optional[ParametrosFluxo] = None):
        self.p = parametros or PADRAO

    # ------------------------------------------------------------------ métricas
    def _janela(self, barras: Sequence[Barra]) -> List[Barra]:
        return list(barras)[-self.p.barras_janela:]

    @staticmethod
    def _razao_delta(janela: Sequence[Barra]) -> float:
        vol = sum(b.volume for b in janela)
        return sum(b.delta for b in janela) / vol if vol > 0 else 0.0

    @staticmethod
    def _range_medio(barras: Sequence[Barra]) -> float:
        faixas = [b.maxima - b.minima for b in barras if b.maxima > b.minima]
        return mean(faixas) if faixas else 0.0

    def _deslocamento(self, janela: Sequence[Barra], barras: Sequence[Barra]) -> float:
        """Quanto o preço andou na janela, medido em ranges médios de barra (resultado do esforço)."""
        rng = self._range_medio(barras)
        if rng <= 0:
            return 0.0
        return (janela[-1].fechamento - janela[0].abertura) / rng

    @staticmethod
    def _concentracao(janela: Sequence[Barra], nivel: float, tolerancia: float) -> float:
        """Fração do volume da janela negociada em cima do nível — o tamanho da briga naquele preço."""
        total = sum(b.volume for b in janela)
        if total <= 0:
            return 0.0
        no_nivel = 0.0
        for b in janela:
            for preco, vol in b.por_preco.items():
                if abs(preco - nivel) <= nivel * tolerancia:
                    no_nivel += vol
        return no_nivel / total

    # ------------------------------------------------------------------ leituras
    def _absorcao(self, janela: Sequence[Barra], nivel: Nivel, razao: float, preco: float) -> Optional[Dict]:
        """
        Agressão CONTRA o nível que o nível aguentou, e que já está SECANDO.

        Num suporte: vendedor batendo na oferta, o fundo não cede, e as últimas ordens já vêm menores que as
        primeiras. Quando a agressão acaba, sobra o lado passivo — e o stop cabe logo abaixo do nível.

        As duas últimas condições (esgotamento e rejeição) não estavam aqui na primeira versão, e o backtest
        cobrou: num dia de queda o motor comprou sete suportes seguidos e perdeu em todos. Num mercado que
        desce, o preço PARA em todo nível por um minuto antes de passar por cima — "agressão presente e
        nível intacto" descreve tanto uma absorção quanto uma faca caindo. O que separa as duas é a agressão
        estar diminuindo e a barra fechar longe do fundo.
        """
        compra = nivel.tipo == "suporte"
        contra = razao < -self.p.limiar_delta if compra else razao > self.p.limiar_delta
        if not contra:
            return None
        limite = nivel.preco * (1 - self.p.folga_nivel) if compra else nivel.preco * (1 + self.p.folga_nivel)
        aguentou = (min(b.minima for b in janela) >= limite) if compra else (max(b.maxima for b in janela) <= limite)
        if not aguentou:
            return None
        ultima = janela[-1]
        virou = ultima.fechamento >= ultima.abertura if compra else ultima.fechamento <= ultima.abertura
        if not virou:
            return None
        # a última barra fechou longe do extremo contra nós? (a mecha que mostra a rejeição do preço)
        faixa = ultima.maxima - ultima.minima
        if faixa > 0:
            posicao = ((ultima.fechamento - ultima.minima) if compra else (ultima.maxima - ultima.fechamento)) / faixa
            if posicao < self.p.rejeicao_minima:
                return None
        # a agressão está secando? Compara o último esforço com o esforço médio das barras anteriores
        anteriores = [abs(b.delta) for b in janela[:-1]]
        media_anterior = mean(anteriores) if anteriores else 0.0
        if media_anterior > 0 and abs(ultima.delta) > media_anterior * self.p.esgotamento_maximo:
            return None
        conc = self._concentracao(janela, nivel.preco, self.p.banda_absorcao)
        if conc < self.p.absorcao_minima:
            return None
        secando = (f", e a agressão está secando (última barra a "
                   f"{abs(ultima.delta) / media_anterior:.0%} do esforço anterior)") if media_anterior > 0 else ""
        return {"acao": "buy" if compra else "sell", "gatilho": "absorcao",
                "forca": round(min(abs(razao) / 0.5, 1.0) * min(conc / 0.5, 1.0) + 0.2, 3),
                "motivo": (f"Absorção no {nivel.tipo} {nivel.preco:,.2f} ({nivel.fonte}): agressão "
                           f"{'vendedora' if compra else 'compradora'} de {abs(razao):.0%} do volume, "
                           f"{conc:.0%} dele no preço do nível, o nível segurou{secando}")}

    def _continuacao(self, janela: Sequence[Barra], barras: Sequence[Barra], nivel: Nivel, razao: float,
                     imbalance: Optional[float]) -> Optional[Dict]:
        """
        Recuo até um nível a favor e a agressão virando ali: entra na retomada, não no meio do movimento.

        Aqui entra-se JUNTO com a agressão, então o teste de esforço x resultado é obrigatório: muito delta
        comprador e preço parado significa que tem alguém grande vendendo passivo em cima — quem compra
        nessa hora está comprando exatamente o que esse alguém quer vender. Na absorção é o contrário: lá a
        agressão é CONTRA a entrada, e o preço parado é a confirmação de que ela não está passando.
        """
        compra = nivel.tipo == "suporte"
        a_favor = razao > self.p.limiar_delta if compra else razao < -self.p.limiar_delta
        if not a_favor:
            return None
        ultima = janela[-1]
        if (ultima.fechamento <= ultima.abertura) if compra else (ultima.fechamento >= ultima.abertura):
            return None
        desloc = self._deslocamento(janela, barras)
        andou = desloc if compra else -desloc
        if andou < self.p.deslocamento_minimo:
            return None
        if imbalance is not None:
            contra_livro = imbalance < -self.p.limiar_book if compra else imbalance > self.p.limiar_book
            if contra_livro:
                return None
        return {"acao": "buy" if compra else "sell", "gatilho": "continuacao",
                "forca": round(min(abs(razao) / 0.5, 1.0), 3),
                "motivo": (f"Retomada no {nivel.tipo} {nivel.preco:,.2f} ({nivel.fonte}): agressão "
                           f"{'compradora' if compra else 'vendedora'} de {abs(razao):.0%} do volume e o "
                           f"preço andou {andou:+.1f} range de barra a favor"
                           + (f", livro {imbalance:+.2f}" if imbalance is not None else ""))}

    # ------------------------------------------------------------------ decisão
    def avaliar(self, barras: Sequence[Barra], contexto: Contexto, preco: float,
                imbalance: Optional[float] = None) -> Dict:
        """
        Devolve {'acao', 'motivo', 'forca', 'gatilho', 'nivel', 'metricas'}.

        Só sai 'buy'/'sell' se o contexto permitir aquele lado: o fluxo escolhe a hora, nunca o lado.
        """
        barras = list(barras)
        metricas: Dict = {}
        if len(barras) < self.p.barras_minimas:
            return _hold(f"Fluxo ainda sem histórico: {len(barras)} de {self.p.barras_minimas} barras",
                         metricas=metricas)
        if contexto.direcao == "hold":
            return _hold(f"Contexto não libera nenhum lado: {contexto.motivo[:200]}", metricas=metricas)

        janela = self._janela(barras)
        razao = self._razao_delta(janela)
        metricas = {"razao_delta": round(razao, 4), "volume_janela": round(sum(b.volume for b in janela), 4),
                    "deslocamento": round(self._deslocamento(janela, barras), 2),
                    "range_medio": round(self._range_medio(barras), 2),
                    "imbalance": None if imbalance is None else round(imbalance, 3)}

        # o nível mais próximo, de qualquer lado: é ele que define onde o stop cabe
        candidatos = [n for n in contexto.niveis if n.distancia_pct(preco) <= self.p.max_dist_nivel]
        nivel = min(candidatos, key=lambda n: n.distancia_pct(preco)) if candidatos else None
        if nivel is None:
            return _hold(f"Sem nível por perto (mais de {self.p.max_dist_nivel:.2%} do mais próximo): "
                         f"entrar aqui é perseguir, e o stop ficaria no vazio", metricas=metricas)
        metricas["nivel"] = nivel.as_dict()

        no_nivel = nivel.distancia_pct(preco) <= self.p.tolerancia_nivel
        if not no_nivel:
            return _hold(f"Nível {nivel.fonte} em {nivel.preco:,.2f} ainda a "
                         f"{nivel.distancia_pct(preco):.2%}: esperando o preço chegar nele",
                         metricas=metricas, nivel=nivel.as_dict())

        for leitura in (self._absorcao(janela, nivel, razao, preco),
                        self._continuacao(janela, barras, nivel, razao, imbalance)):
            if not leitura:
                continue
            if not contexto.permite(leitura["acao"]):
                return _hold(f"{leitura['motivo']} — mas o contexto só libera "
                             f"{contexto.direcao}: sinal descartado", metricas=metricas, nivel=nivel.as_dict())
            return {**leitura, "nivel": nivel.as_dict(), "nivel_obj": nivel, "metricas": metricas}
        return _hold(f"No {nivel.tipo} {nivel.preco:,.2f} ({nivel.fonte}), sem gatilho de fluxo: "
                     f"delta {razao:+.0%} do volume", metricas=metricas, nivel=nivel.as_dict())
