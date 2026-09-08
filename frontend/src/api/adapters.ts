/** Conversões da resposta crua da API para os modelos do painel. Camada de dados: não importa nada de UI. */
import type { Candle } from './types'

/** Candles da API (timestamp em ms) para o formato do gráfico (timestamp em segundos). */
export function candlesDaApi(raw: number[][] | undefined): Candle[] {
  if (!raw) return []
  return raw.map((c) => ({
    time: Math.floor(c[0] / 1000),
    open: c[1],
    high: c[2],
    low: c[3],
    close: c[4],
    volume: c[5],
  }))
}
