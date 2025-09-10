import numpy as np

class VWAPCalculator:
    def __init__(self, ohlcv):
        self.ohlcv = ohlcv
        self.prices = np.array([c[4] for c in ohlcv])  # Preço de fechamento
        self.volumes = np.array([c[5] for c in ohlcv])  # Volume
        self.timestamps = np.array([c[0] for c in ohlcv])
        # Adição: armazenar high/low para validação de range
        self.highs = np.array([c[2] for c in ohlcv]) if len(ohlcv[0]) > 2 else self.prices
        self.lows = np.array([c[3] for c in ohlcv]) if len(ohlcv[0]) > 3 else self.prices

    def vwap(self, anchor_idx=0):
        prices = self.prices[anchor_idx:]
        volumes = self.volumes[anchor_idx:]
        if np.sum(volumes) == 0:
            return None
        vwap_value = np.sum(prices * volumes) / np.sum(volumes)
        # Validação: VWAP dentro do range dos candles do período
        max_high = np.max(self.highs[anchor_idx:]) if len(self.highs) else None
        min_low = np.min(self.lows[anchor_idx:]) if len(self.lows) else None
        if max_high is not None and min_low is not None:
            if vwap_value > max_high * 1.02 or vwap_value < min_low * 0.98:
                return None
        return vwap_value

    def vwap_bandas(self, anchor_idx=0, desvios=[1,2]):
        vwap_value = self.vwap(anchor_idx)
        if vwap_value is None:
            return None
        prices = self.prices[anchor_idx:]
        volumes = self.volumes[anchor_idx:]
        desvios_out = {}
        mean = vwap_value
        variance = np.sum(volumes * (prices - mean)**2) / np.sum(volumes)
        stddev = np.sqrt(variance)
        max_high = np.max(self.highs[anchor_idx:]) if len(self.highs) else None
        min_low = np.min(self.lows[anchor_idx:]) if len(self.lows) else None
        for n in desvios:
            upper = vwap_value + n * stddev
            lower = vwap_value - n * stddev
            # Validação: bandas dentro do range dos candles (+/-2% tolerância)
            if max_high is not None and upper > max_high * 1.02:
                upper = max_high
            if min_low is not None and lower < min_low * 0.98:
                lower = min_low
            desvios_out[f"+{n}σ"] = upper
            desvios_out[f"-{n}σ"] = lower
        return {"vwap": vwap_value, "bandas": desvios_out}

    def vwap_intraday(self):
        start_of_day_idx = self._index_inicio_dia()
        return self.vwap_bandas(anchor_idx=start_of_day_idx)

    def _index_inicio_dia(self):
        from datetime import datetime
        now = datetime.utcnow()
        for idx, ts in enumerate(self.timestamps):
            dt = datetime.utcfromtimestamp(ts/1000)  # ajuste se seu timestamp está em ms
            if dt.hour == 0 and dt.minute == 0:
                return idx
        return 0

    def obter_vwap_atual(self):
        return self.vwap(anchor_idx=0)
    
    def obter_vwap_ultimos(self, n):
        anchor_idx = max(0, len(self.prices) - n)
        return self.vwap(anchor_idx=anchor_idx)
