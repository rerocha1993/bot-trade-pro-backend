/**
 * Tipos dos overlays do gráfico.
 *
 * Ficam aqui, e não dentro do componente, para que `lib/overlays.ts` possa produzir overlays sem depender de
 * um componente de UI. A direção correta é componente -> lib, nunca lib -> componente.
 */
export interface ChartPath {
  id: string
  points: { time: number; value: number }[]
  color: string
  width?: number
  dashed?: boolean
}

export interface ChartLabel {
  time: number
  price: number
  text: string
  color: string
}

export interface ChartLevel {
  price: number
  label: string
  color: string
  dashed?: boolean
}

export interface ChartRect {
  from: number
  to: number | null
  top: number
  bottom: number
  color: string
  border?: string
}

export interface ChartProfile {
  rows: { lo: number; hi: number; valor: number }[]
  poc?: number
  vah?: number
  val?: number
  color?: string
}

export interface ChartMarker {
  time: number
  side: 'buy' | 'sell' | 'exit' | 'info'
  text?: string
}
