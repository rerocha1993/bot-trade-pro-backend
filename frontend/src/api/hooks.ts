import { useQuery } from '@tanstack/react-query'
import { api } from './client'
import type { AvisosUltimos, FluxoAbsorcao, FluxoFootprint, FluxoLiquidacoes, FluxoPresos, FundingAgregado, MapaDoDia, NuvensCalor, NuvensOverlay, NuvensTop, RobosStatus, TradeRobo } from './types'
import { candlesDaApi } from './adapters'

/** Candles públicos da Bybit, servidos pela API do conselho (timestamp em ms na API, em segundos no gráfico). */
export const useCandles = (par: string, timeframe: string, limite = 300) => useQuery({
  queryKey: ['candles', par, timeframe, limite], refetchInterval: 30_000,
  queryFn: async () => candlesDaApi((await api.get<{ candles: number[][] }>('/api/mercado/candles', { par, timeframe, limite })).candles),
})

export const useAvisosMapa = () => useQuery({
  queryKey: ['avisos-mapa'], refetchInterval: 60_000,
  queryFn: () => api.get<MapaDoDia>('/api/avisos/mapa'),
})

export const useAvisosUltimos = (n = 50) => useQuery({
  queryKey: ['avisos-ultimos', n], refetchInterval: 60_000,
  queryFn: () => api.get<AvisosUltimos>('/api/avisos/ultimos', { n }),
})

/** Nuvens do TRDR: overlay por categoria a partir do primeiro candle do gráfico (segundos) e os top levels de agora. */
export const useNuvensOverlay = (inicio: number | null, exchanges: string, passo = 300) => useQuery({
  queryKey: ['nuvens-overlay', inicio, exchanges, passo], enabled: inicio !== null, refetchInterval: 60_000,
  queryFn: () => api.get<NuvensOverlay>('/api/nuvens/overlay', { inicio: inicio as number, exchanges, passo }),
})

export const useNuvensTop = (exchanges: string) => useQuery({
  queryKey: ['nuvens-top', exchanges], refetchInterval: 60_000,
  queryFn: () => api.get<NuvensTop>('/api/nuvens/top', { exchanges }),
})

/** Mapa de calor: células de preço com `fator` vezes o normal da distância, a partir do primeiro candle (segundos). */
export const useNuvensCalor = (inicio: number | null, exchanges: string, fator: number, passo = 300) => useQuery({
  queryKey: ['nuvens-calor', inicio, exchanges, fator, passo], enabled: inicio !== null, refetchInterval: 60_000,
  queryFn: () => api.get<NuvensCalor>('/api/nuvens/calor', { inicio: inicio as number, exchanges, fator, passo }),
})

export const usePresos = (inicio: number | null, passo: number, ligado: boolean) => useQuery({
  queryKey: ['presos', inicio, passo], enabled: ligado && inicio !== null, refetchInterval: 60_000,
  queryFn: () => api.get<FluxoPresos>('/api/fluxo/presos', { inicio: inicio as number, passo }),
})

export const useAbsorcao = (inicio: number | null) => useQuery({
  queryKey: ['absorcao', inicio], enabled: inicio !== null, refetchInterval: 60_000,
  queryFn: () => api.get<FluxoAbsorcao>('/api/fluxo/absorcao', { inicio: inicio as number }),
})

export const useFootprint = (passo: number, linha: number, ligado: boolean, n = 150) => useQuery({
  queryKey: ['footprint', passo, linha, n], enabled: ligado, refetchInterval: 30_000,
  queryFn: () => api.get<FluxoFootprint>('/api/fluxo/footprint', { passo, linha, n }),
})

export const useRobos = () => useQuery({
  queryKey: ['robos'], refetchInterval: 15_000,
  queryFn: () => api.get<RobosStatus>('/api/robos'),
})

export const useTradesRobos = () => useQuery({
  queryKey: ['robos-trades'], refetchInterval: 30_000,
  queryFn: () => api.get<{ trades: TradeRobo[] }>('/api/robos/trades', { n: 300 }),
})

/** Liquidações dos perpétuos (Bybit + OKX) por vela, a partir do primeiro candle do gráfico (segundos). */
export const useLiquidacoes = (inicio: number | null, passo = 300) => useQuery({
  queryKey: ['liquidacoes', inicio, passo], enabled: inicio !== null, refetchInterval: 60_000,
  queryFn: () => api.get<FluxoLiquidacoes>('/api/fluxo/liquidacoes', { inicio: inicio as number, passo }),
})

/** Funding de Bybit, Binance e OKX e a média entre eles (muda de 8 em 8 h). */
export const useFunding = () => useQuery({
  queryKey: ['funding'], refetchInterval: 10 * 60_000,
  queryFn: () => api.get<FundingAgregado>('/api/mercado/funding'),
})
