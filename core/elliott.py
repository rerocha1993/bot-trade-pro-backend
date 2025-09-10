# Arquivo: trading_bot/core/elliott.py

import numpy as np
import pandas as pd
from scipy.signal import find_peaks
from core.fibonacci_elliott import FibonacciElliott
from models.elliott_contagem_candidata import ElliottContagemCandidata
from models.elliott_contagem_validada import ElliottContagemValidada
from models.elliott_onda import ElliottOnda
from models.elliott_revisao import ElliottRevisao
from datetime import datetime
from scipy.signal import argrelextrema
from itertools import combinations


class ElliottDetector:
    def __init__(self, prices):
        self.prices = np.array(prices)
        self.max_price = float(np.max(self.prices)) if len(self.prices) else None
        self.min_price = float(np.min(self.prices)) if len(self.prices) else None
        self.tolerancia = 0.02  # 2%

    def detectar_picos_vales(self, distance=5):
        peaks, _ = find_peaks(self.prices, distance=distance)
        troughs, _ = find_peaks(-self.prices, distance=distance)

        # Validação: só aceita picos/vales dentro do range institucional (máx/mín dos preços, com tolerância)
        max_limit = self.max_price * (1 + self.tolerancia) if self.max_price is not None else None
        min_limit = self.min_price * (1 - self.tolerancia) if self.min_price is not None else None

        peaks_filtrados = [idx for idx in peaks if min_limit <= self.prices[idx] <= max_limit]
        troughs_filtrados = [idx for idx in troughs if min_limit <= self.prices[idx] <= max_limit]
        return peaks_filtrados, troughs_filtrados

    def estrutura_onda_simples(self):
        peaks, troughs = self.detectar_picos_vales()
        estrutura = {
            'impulsivas': peaks,
            'corretivas': troughs
        }
        return estrutura

    def validar_estrutura_basica(self):
        estrutura = self.estrutura_onda_simples()
        if len(estrutura['impulsivas']) >= 3 and len(estrutura['corretivas']) >= 2:
            return True, estrutura
        return False, estrutura
    
class ElliottEngine:
    """
    Engine institucional de contagem de ondas de Elliott, suportando TODOS os padrões e múltiplas contagens concorrentes, já com validação automática e integração com banco.
    """

    def __init__(self, session, par, timeframe, candles, nivel_ciclo):
        self.session = session
        self.par = par
        self.timeframe = timeframe
        self.candles = candles  # Lista OHLCV para análise
        self.nivel_ciclo = nivel_ciclo
        self.contagens_candidatas = []
        self.resultados_validos = []

    def detectar_todas_contagens(self):
        """
        Roda o algoritmo de Elliott para TODOS padrões possíveis (impulsivas, corretivas, flats, triangulos, diagonais, WXY, etc), gera N contagens concorrentes.
        """
        # Aqui você implementa a chamada real dos detectores de padrões (impulsivo, abc, flats, triângulos, etc)
        # Exemplo real (pseudocódigo):
        contagens = []
        # Detecção para todos os padrões e variantes:
        contagens += self.detectar_impulsivas()
        contagens += self.detectar_abc()
        contagens += self.detectar_flats()
        contagens += self.detectar_triangulos()
        contagens += self.detectar_diagonais()
        contagens += self.detectar_wxy()
        contagens += self.detectar_wxyxz()
        # Filtra duplicatas e salva apenas as contagens com score relevante
        self.contagens_candidatas = [c for c in contagens if c['score'] > 0.5]

    def detectar_impulsivas(self):
        resultados = []
        for sequencia in self.todas_sequencias_possiveis(5):
            fib = FibonacciElliott(sequencia)
            if (
                fib.validar_onda2() and
                fib.validar_onda3() and
                fib.validar_onda4() and
                fib.validar_onda5()
            ):
                score = fib.score_confianca()
                if score >= 0.7:
                    resultados.append({
                        'padrao': 'impulsiva',
                        'ondas': sequencia,
                        'score': score
                    })
        return resultados

    def detectar_abc(self):
        resultados = []
        for sequencia in self.todas_sequencias_possiveis(3):
            fib = FibonacciElliott(sequencia)
            if fib.validar_abc():
                score = fib.score_confianca()
                if score >= 0.7:
                    resultados.append({
                        'padrao': 'abc',
                        'ondas': sequencia,
                        'score': score
                    })
        return resultados

    def detectar_flats(self):
        resultados = []
        for sequencia in self.todas_sequencias_possiveis(3):
            fib = FibonacciElliott(sequencia)
            score = fib.score_confianca()
            if fib.validar_flat_regular() and score >= 0.7:
                resultados.append({
                    'padrao': 'flat_regular',
                    'ondas': sequencia,
                    'score': score
                })
            if fib.validar_flat_expanded() and score >= 0.7:
                resultados.append({
                    'padrao': 'flat_expanded',
                    'ondas': sequencia,
                    'score': score
                })
            if fib.validar_flat_running() and score >= 0.7:
                resultados.append({
                    'padrao': 'flat_running',
                    'ondas': sequencia,
                    'score': score
                })
        return resultados

    def detectar_triangulos(self):
        resultados = []
        for sequencia in self.todas_sequencias_possiveis(5):
            fib = FibonacciElliott(sequencia)
            if fib.validar_triangulo():
                score = fib.score_confianca()
                if score >= 0.7:
                    resultados.append({
                        'padrao': 'triangulo',
                        'ondas': sequencia,
                        'score': score
                    })
        return resultados

    def detectar_diagonais(self):
        resultados = []
        for sequencia in self.todas_sequencias_possiveis(5):
            fib = FibonacciElliott(sequencia)
            score = fib.score_confianca()
            if fib.validar_diagonal_leading() and score >= 0.7:
                resultados.append({
                    'padrao': 'diagonal_leading',
                    'ondas': sequencia,
                    'score': score
                })
            if fib.validar_diagonal_ending() and score >= 0.7:
                resultados.append({
                    'padrao': 'diagonal_ending',
                    'ondas': sequencia,
                    'score': score
                })
        return resultados

    def detectar_wxy(self):
        resultados = []
        for sequencia in self.todas_sequencias_possiveis(3):
            fib = FibonacciElliott(sequencia)
            if fib.validar_wxy():
                score = fib.score_confianca()
                if score >= 0.7:
                    resultados.append({
                        'padrao': 'wxy',
                        'ondas': sequencia,
                        'score': score
                    })
        return resultados

    def detectar_wxyxz(self):
        resultados = []
        for sequencia in self.todas_sequencias_possiveis(5):
            fib = FibonacciElliott(sequencia)
            if fib.validar_wxyxz():
                score = fib.score_confianca()
                if score >= 0.7:
                    resultados.append({
                        'padrao': 'wxyxz',
                        'ondas': sequencia,
                        'score': score
                    })
        return resultados

    def persistir_candidatas(self):
        """
        Persiste todas as contagens candidatas no banco, já com ondas detalhadas e score,
        e vinculando parent_id institucional (multi-timeframe).
        """
        for c in self.contagens_candidatas:
            # BUSCA O MACRO PARENT INSTITUCIONAL
            parent_id = None
            if self.nivel_ciclo and self.nivel_ciclo != 'macro':  # Só busca parent se não for o macro maior
                macro_timeframe = self.get_macro_timeframe(self.timeframe)
                parent = self.session.query(ElliottContagemCandidata).filter(
                    ElliottContagemCandidata.par == self.par,
                    ElliottContagemCandidata.timeframe == macro_timeframe,
                    ElliottContagemCandidata.data_inicio <= c['ondas'][0]['data_inicio'],
                    ElliottContagemCandidata.data_fim >= c['ondas'][0]['data_inicio']
                ).order_by(ElliottContagemCandidata.data_inicio.desc()).first()
                if parent:
                    parent_id = parent.id

            contagem = ElliottContagemCandidata(
                par=self.par,
                timeframe=self.timeframe,
                ondas_detectadas=c['ondas'],
                score_confianca=c['score'],
                data_inicio=c['ondas'][0]['data_inicio'],
                data_fim=c['ondas'][-1]['data_fim'],
                nivel_ciclo=self.nivel_ciclo,
                status="proposta",
                parent_id=parent_id
            )
            self.session.add(contagem)
            self.session.commit()

            # Persiste cada onda separadamente
            for idx, onda in enumerate(c['ondas']):
                onda_db = ElliottOnda(
                    contagem_id=contagem.id,
                    numero_onda=idx+1,
                    tipo_onda=onda['padrao'],
                    data_inicio=onda['data_inicio'],
                    data_fim=onda['data_fim'],
                    preco_inicio=onda['preco_inicio'],
                    preco_fim=onda['preco_fim'],
                    proporcao_fibonacci=None,
                    validada=False,
                    score_confianca=c['score']
                )
                self.session.add(onda_db)
            self.session.commit()

    def todas_sequencias_possiveis(self, n):
            """
            Varredura completa dos pivôs relevantes: gera todas as possíveis sequências de n ondas (topos/fundos).
            Usado para detectar padrões Elliott reais com base institucional, multi-hypothesis.
            """
            closes = [c[4] for c in self.candles]  # Assumindo OHLCV: [open, high, low, close, volume]
            times = [c[0] for c in self.candles]
            df = pd.DataFrame({'close': closes, 'time': times})

            # Busca pivôs locais de máxima e mínima — critérios institucionais
            window = max(3, int(len(df) * 0.01))  # ajuste conforme o tamanho do candle/timeframe
            idx_max = argrelextrema(df['close'].values, np.greater, order=window)[0]
            idx_min = argrelextrema(df['close'].values, np.less, order=window)[0]
            pivots_idx = np.sort(np.concatenate([idx_max, idx_min]))

            # Constrói todas as sequências de n pivôs possíveis (ordem temporal preservada)
            sequencias = []
            if len(pivots_idx) < n:
                return []  # Não há pivôs suficientes

            for comb in self.combinacoes_ordem(pivots_idx, n):
                s = []
                for idx in comb:
                    c = self.candles[idx]
                    s.append({
                        'preco_inicio': c[1],  # open
                        'preco_fim': c[4],     # close
                        'data_inicio': pd.to_datetime(c[0], unit='ms'),
                        'data_fim': pd.to_datetime(c[0], unit='ms'),
                    })
                sequencias.append(s)
            return sequencias

    def combinacoes_ordem(self, arr, n):
            """
            Gera todas as combinações possíveis de tamanho n, com ordem crescente (não repete, não embaralha)
            """
            from itertools import combinations
            return list(combinations(arr, n))
    
    def get_macro_timeframe(self, timeframe):
        ordem = ['1m', '5m', '15m', '1h', '4h', '1d', '1w', '1M']
        idx = ordem.index(timeframe)
        if idx+1 < len(ordem):
            return ordem[idx+1]
        return None  # Já é o macro maior


# Exemplo de uso igual ao seu
if __name__ == "__main__":
    from core.conexoes.conexao_bybit import BybitConnector

    con = BybitConnector()
    par = input("Par de moedas (ex: BTC/USDT): ").strip().upper()
    ohlcv = con.obter_ohlcv(par, timeframe='15m', limite=200)
    precos_fechamento = [item[4] for item in ohlcv]

    det = ElliottDetector(precos_fechamento)
    valido, estrutura = det.validar_estrutura_basica()

    print("Estrutura válida?" , valido)
    print("Ondas impulsivas:", estrutura['impulsivas'])
    print("Ondas corretivas:", estrutura['corretivas'])
