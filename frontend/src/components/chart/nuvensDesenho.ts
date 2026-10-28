/**
 * As nuvens do livro (Order Book Depth Overlay do TRDR) dentro do gráfico: em cada vela, as faixas de distância que
 * acendem pela regra de lib/livroTrdr.ts, verde abaixo do preço e vermelha acima, uma coluna da largura da vela, sem
 * vão entre velas vizinhas. Fica atrás das velas e do TPO.
 */
import type {
  IChartApi, ISeriesApi, ISeriesPrimitive, ISeriesPrimitivePaneRenderer, ISeriesPrimitivePaneView,
  SeriesAttachedParameter, Time,
} from 'lightweight-charts'
import type { NuvensOverlay } from '../../api/types'
import { bandasDoPonto, RGB_LADO, type BandaLivro } from '../../lib/livroTrdr'
import { xDoIndice } from './coordenada'

type Alvo = Parameters<ISeriesPrimitivePaneRenderer['draw']>[0]

export class NuvensDesenho implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null
  private series: ISeriesApi<'Candlestick'> | null = null
  private pedirDesenho: (() => void) | null = null
  /** as faixas acesas de cada vela, calculadas uma vez quando o dado chega */
  private colunas: { ts: number; bandas: BandaLivro[] }[] = []
  private view: ISeriesPrimitivePaneView = {
    zOrder: () => 'bottom',
    renderer: () => ({ draw: (alvo: Alvo) => this.desenhar(alvo) }),
  }

  private logico: (t: number) => number | null

  /** `logico(t)`: posição (índice de vela, pode ser fracionária) do instante t em segundos */
  constructor(logico: (t: number) => number | null) {
    this.logico = logico
  }

  attached(p: SeriesAttachedParameter<Time>) {
    this.chart = p.chart
    this.series = p.series as ISeriesApi<'Candlestick'>
    this.pedirDesenho = p.requestUpdate
  }
  detached() { this.chart = null; this.series = null; this.pedirDesenho = null }
  paneViews() { return [this.view] }
  updateAllViews() { /* desenha direto no draw */ }
  set(d: NuvensOverlay | null) {
    this.colunas = d ? d.pontos.map((p) => ({ ts: p.ts, bandas: bandasDoPonto(p, d.categorias) })).filter((c) => c.bandas.length) : []
    this.pedirDesenho?.()
  }

  private desenhar(alvo: Alvo) {
    if (!this.colunas.length || !this.chart || !this.series) return
    const chart = this.chart
    const largura = chart.timeScale().options().barSpacing
    const s = this.series
    alvo.useMediaCoordinateSpace(({ context: ctx, mediaSize }) => {
      const W = mediaSize.width
      for (const c of this.colunas) {
        const l = this.logico(c.ts)
        if (l === null) continue
        const x = xDoIndice(chart, l, largura)
        if (x === null || x + largura < 0 || x - largura > W) continue
        // arredonda as bordas no pixel para colunas vizinhas encostarem sem vão nem sobreposição
        const x0 = Math.round(x - largura / 2), x1 = Math.round(x + largura / 2)
        for (const b of c.bandas) {
          const ya = s.priceToCoordinate(b.hi), yb = s.priceToCoordinate(b.lo)
          if (ya === null || yb === null) continue
          const [r, g, bl] = RGB_LADO[b.lado]
          ctx.fillStyle = `rgba(${r},${g},${bl},${b.alfa.toFixed(3)})`
          ctx.fillRect(x0, Math.round(ya), x1 - x0, Math.round(yb) - Math.round(ya))
        }
      }
    })
  }
}
