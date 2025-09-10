from datetime import datetime
import pandas as pd
import numpy as np

class TPOProfile:
    def __init__(self, prices, interval=50.0, tolerancia=0.02, range_min=None, range_max=None, bins=20):
        self.interval = interval
        self.bins = bins
        self.tolerancia = tolerancia

        # Permite limitar o range analisado, ex: diário/semanal ou range institucional externo
        filtered_prices = prices
        if range_min is not None or range_max is not None:
            filtered_prices = [
                p for p in prices 
                if (range_min is None or p >= range_min) and (range_max is None or p <= range_max)
            ]
        self.df = pd.DataFrame({'price': filtered_prices})
        self.df['bin'] = (self.df['price'] // self.interval) * self.interval

        self.min_price = self.df['price'].min()
        self.max_price = self.df['price'].max()

    def freq_table(self):
        freq = (
            self.df
            .groupby('bin')
            .size()
            .reset_index(name='freq')
            .sort_values('bin')
            .reset_index(drop=True)
        )
        return freq

    def calculate_poc_val_vah(self):
        freq = self.freq_table()
        total = freq['freq'].sum()
        freq_sorted = freq.sort_values('freq', ascending=False).reset_index(drop=True)

        cumul = 0
        area_bins = []
        for _, row in freq_sorted.iterrows():
            cumul += row['freq']
            area_bins.append(row['bin'])
            if cumul / total >= 0.7:
                break

        poc = freq.loc[freq['freq'].idxmax(), 'bin']
        vah = max(area_bins)
        val = min(area_bins)

        # Ajuste: nunca retorna valores fora do range dos candles + tolerância
        max_limit = self.max_price * (1 + self.tolerancia)
        min_limit = self.min_price * (1 - self.tolerancia)
        vah = min(vah, max_limit)
        val = max(val, min_limit)
        poc = min(max(poc, min_limit), max_limit)

        return {'POC': poc, 'VAL': val, 'VAH': vah, 'freq': freq}

    def find_single_prints(self, freq):
        single_prints = freq[freq['freq'] == 1]['bin'].tolist()
        max_limit = self.max_price * (1 + self.tolerancia)
        min_limit = self.min_price * (1 - self.tolerancia)
        return [b for b in single_prints if min_limit <= b <= max_limit]

    def shape_profile(self, freq):
        counts = freq['freq'].values
        peak_idx = np.argmax(counts)
        top = counts[:peak_idx]
        bottom = counts[peak_idx+1:]
        if len(top) and len(bottom):
            if np.mean(top) < counts[peak_idx] and np.mean(bottom) < counts[peak_idx]:
                return "D"
            elif np.mean(top) > np.mean(bottom):
                return "P"
            elif np.mean(bottom) > np.mean(top):
                return "b"
        return "Unknown"

    def hvn_lvn(self, freq, n=3):
        top_hvn = freq.sort_values('freq', ascending=False).head(n)['bin'].tolist()
        low_lvn = freq.sort_values('freq', ascending=True).head(n)['bin'].tolist()
        max_limit = self.max_price * (1 + self.tolerancia)
        min_limit = self.min_price * (1 - self.tolerancia)
        hvn_filtrado = [b for b in top_hvn if min_limit <= b <= max_limit]
        lvn_filtrado = [b for b in low_lvn if min_limit <= b <= max_limit]
        return {'HVN': hvn_filtrado, 'LVN': lvn_filtrado}

    def analisar(self):
        res = self.calculate_poc_val_vah()
        freq = res['freq']
        single_prints = self.find_single_prints(freq)
        shape = self.shape_profile(freq)
        hvn_lvn = self.hvn_lvn(freq)
        return {
            'POC': res['POC'],
            'VAL': res['VAL'],
            'VAH': res['VAH'],
            'shape': shape,
            'single_prints': single_prints,
            'HVN': hvn_lvn['HVN'],
            'LVN': hvn_lvn['LVN']
        }

    def sinal_estrategico(self, preco_atual):
        res = self.analisar()
        if preco_atual in res['single_prints']:
            return {'acao': 'reversao', 'motivo': f'Single Print (Rejeição institucional) em {preco_atual}'}
        if preco_atual > res['VAH']:
            return {'acao': 'buy', 'motivo': f'Acima da VAH (Breakout ou armadilha em {res["VAH"]})'}
        if preco_atual < res['VAL']:
            return {'acao': 'sell', 'motivo': f'Abaixo da VAL (Breakdown ou armadilha em {res["VAL"]})'}
        if preco_atual in res['HVN']:
            return {'acao': 'defesa', 'motivo': f'Defesa institucional em HVN {preco_atual}'}
        if preco_atual in res['LVN']:
            return {'acao': 'rejeicao', 'motivo': f'Rejeição em LVN {preco_atual}'}
        return {'acao': 'hold', 'motivo': 'Sem trigger institucional'}
