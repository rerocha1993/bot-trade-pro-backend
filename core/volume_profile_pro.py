import numpy as np
import pandas as pd

class VolumeProfilePRO:
    def __init__(self, ohlcv, num_bins=30):
        """
        ohlcv: lista OHLCV
        num_bins: quantidade de bins para granularidade do histograma
        """
        self.ohlcv = ohlcv
        closes = [c[4] for c in ohlcv]
        vols = [c[5] for c in ohlcv]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        self.min_price = min(closes)
        self.max_price = max(closes)
        self.candle_max_high = max(highs)
        self.candle_min_low = min(lows)
        self.num_bins = num_bins

        # Calcula bins de preço
        self.bin_edges = np.linspace(self.min_price, self.max_price, num_bins + 1)
        self.bin_labels = 0.5 * (self.bin_edges[:-1] + self.bin_edges[1:])

        # Volume histogram
        self.hist, _ = np.histogram(closes, bins=self.bin_edges, weights=vols)

    def hvn_lvn(self, n=3, tolerancia=0.02):
        # HVN = bins com maior volume; LVN = bins com menor volume (> 0)
        idx_sort = np.argsort(self.hist)
        lvn_idx = idx_sort[:n]
        hvn_idx = idx_sort[-n:]

        # Adiciona filtro: só retorna zonas dentro do range do candle analisado
        max_limit = self.candle_max_high * (1 + tolerancia)
        min_limit = self.candle_min_low * (1 - tolerancia)

        lvns = [float(self.bin_labels[i]) for i in lvn_idx
                if min_limit <= self.bin_labels[i] <= max_limit]
        hvns = [float(self.bin_labels[i]) for i in hvn_idx
                if min_limit <= self.bin_labels[i] <= max_limit]

        return {
            "HVN": hvns,
            "LVN": lvns
        }

    def rejection_zones(self, min_vol=0.0, max_vol=0.05, tolerancia=0.02):
        # Price rejection = bins onde volume é muito baixo em relação ao total
        total_vol = np.sum(self.hist)
        percent_vol = self.hist / total_vol
        max_limit = self.candle_max_high * (1 + tolerancia)
        min_limit = self.candle_min_low * (1 - tolerancia)
        return [float(self.bin_labels[i]) for i, pct in enumerate(percent_vol)
                if min_vol < pct < max_vol and min_limit <= self.bin_labels[i] <= max_limit]

    def top_volume_zones(self, pct=0.7, tolerancia=0.02):
        # Retorna zonas que acumulam X% do volume (zona de valor institucional)
        total = np.sum(self.hist)
        idx_sort = np.argsort(self.hist)[::-1]  # maior para menor
        cumul = 0
        area = []
        max_limit = self.candle_max_high * (1 + tolerancia)
        min_limit = self.candle_min_low * (1 - tolerancia)
        for i in idx_sort:
            price = float(self.bin_labels[i])
            if min_limit <= price <= max_limit:
                cumul += self.hist[i]
                area.append(price)
                if cumul / total >= pct:
                    break
        return sorted(area)

    def price_signal(self, preco_atual, tolerancia=0.02):
        nodes = self.hvn_lvn(tolerancia=tolerancia)
        if preco_atual in nodes["HVN"]:
            return {"acao": "defesa", "motivo": f"Institucional defendendo em HVN {preco_atual}"}
        if preco_atual in nodes["LVN"]:
            return {"acao": "rejeicao", "motivo": f"Price rejection em LVN {preco_atual}"}
        rej = self.rejection_zones(tolerancia=tolerancia)
        if preco_atual in rej:
            return {"acao": "rejeicao", "motivo": f"Zona de rejeição (baixa liquidez) em {preco_atual}"}
        return {"acao": "hold", "motivo": "Sem trigger profile"}

    def to_dataframe(self):
        # Facilita export para painel/plot avançado
        return pd.DataFrame({"bin": self.bin_labels, "volume": self.hist})

    def export_heatmap(self):
        # Retorna matriz pronta para heatmap (para visual pro ou debug)
        return self.bin_labels.tolist(), self.hist.tolist()
