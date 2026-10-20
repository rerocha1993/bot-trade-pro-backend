import { useQuery } from '@tanstack/react-query'
import { api } from './client'
import type { AvisosUltimos, MapaDoDia, NuvensOverlay, NuvensTop } from './types'
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
