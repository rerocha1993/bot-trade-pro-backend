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

/**
 * Mapa de calor como imagem: `rgba` tem nCols × nRows pixels (linha 0 = preço mais alto). A coluna c começa em
 * t0 + c·passo; a linha r cobre [pBase + (nRows−1−r)·grade, pBase + (nRows−r)·grade]. O gráfico estica a imagem com
 * suavização, o que dá o aspecto de nuvem em vez de listras de retângulos.
 */
export interface ChartHeatmap {
  t0: number
  passo: number
  nCols: number
  pBase: number
  grade: number
  nRows: number
  rgba: Uint8ClampedArray
}
