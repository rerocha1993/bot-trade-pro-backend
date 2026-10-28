/**
 * As camadas de order flow dentro do gráfico (lib/camadasFluxo.ts): o mapa de calor (absorção ou todas as paredes)
 * atrás das velas, como uma imagem esticada com suavização (nuvem), e na frente os contornos, as faixas dos presos e
 * os rótulos. O tempo vira posição pelo `logico(t)` do gráfico, então funciona em qualquer tempo de vela.
 */
import type {
  IChartApi, ISeriesApi, ISeriesPrimitive, ISeriesPrimitivePaneRenderer, ISeriesPrimitivePaneView,
  SeriesAttachedParameter, Time,
} from 'lightweight-charts'
import type { ChartHeatmap, ChartLabel, ChartRect } from '../../lib/chart-tipos'
import { xDoIndice } from './coordenada'

type Alvo = Parameters<ISeriesPrimitivePaneRenderer['draw']>[0]
type Ctx = CanvasRenderingContext2D
const FONTE = "11px 'DM Mono', monospace"

export interface Camadas { heatmap: ChartHeatmap | null; rects: ChartRect[]; labels: ChartLabel[] }

export class CamadasDesenho implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null
  private series: ISeriesApi<'Candlestick'> | null = null
  private pedirDesenho: (() => void) | null = null
  private dados: Camadas = { heatmap: null, rects: [], labels: [] }
  private imagem: { de: ChartHeatmap; canvas: HTMLCanvasElement } | null = null
  private fundo: ISeriesPrimitivePaneView = {
    zOrder: () => 'bottom',
    renderer: () => ({ draw: (alvo: Alvo) => this.desenhar(alvo, (ctx) => this.heatmap(ctx)) }),
  }
  private frente: ISeriesPrimitivePaneView = {
    zOrder: () => 'top',
    renderer: () => ({ draw: (alvo: Alvo) => this.desenhar(alvo, (ctx, W) => { this.retangulos(ctx, W); this.rotulos(ctx) }) }),
  }

  private logico: (t: number) => number | null

  constructor(logico: (t: number) => number | null) {
    this.logico = logico
  }

  attached(p: SeriesAttachedParameter<Time>) {
    this.chart = p.chart
    this.series = p.series as ISeriesApi<'Candlestick'>
    this.pedirDesenho = p.requestUpdate
  }
  detached() { this.chart = null; this.series = null; this.pedirDesenho = null }
  paneViews() { return [this.fundo, this.frente] }
  updateAllViews() { /* desenha direto */ }
  set(d: Camadas) { this.dados = d; this.pedirDesenho?.() }

  private x(t: number): number | null {
    const l = this.logico(t)
    if (l === null || !this.chart) return null
    return xDoIndice(this.chart, l)
  }
  private y(p: number): number | null {
    const c = this.series?.priceToCoordinate(p)
    return c === null || c === undefined ? null : c
  }

  private desenhar(alvo: Alvo, fazer: (ctx: Ctx, W: number) => void) {
    if (!this.chart || !this.series) return
    alvo.useMediaCoordinateSpace(({ context: ctx, mediaSize }) => {
      ctx.save()
      ctx.beginPath(); ctx.rect(0, 0, mediaSize.width, mediaSize.height); ctx.clip()
      fazer(ctx, mediaSize.width)
      ctx.restore()
    })
  }

  private heatmap(ctx: Ctx) {
    const h = this.dados.heatmap
    if (!h || !h.nCols || !h.nRows) return
    if (!this.imagem || this.imagem.de !== h) {
      const cv = document.createElement('canvas')
      cv.width = h.nCols
      cv.height = h.nRows
      const g = cv.getContext('2d')
      if (!g) return
      g.putImageData(new ImageData(new Uint8ClampedArray(h.rgba), h.nCols, h.nRows), 0, 0)
      this.imagem = { de: h, canvas: cv }
    }
    // a coluna c cobre [t0 + c·passo, t0 + (c+1)·passo): a imagem vai do começo da 1ª ao fim da última
    const xa = this.x(h.t0), xb = this.x(h.t0 + h.nCols * h.passo)
    const yTopo = this.y(h.pBase + h.nRows * h.grade), yBase = this.y(h.pBase)
    if (xa === null || xb === null || yTopo === null || yBase === null) return
    const meia = this.chart!.timeScale().options().barSpacing / 2
    ctx.imageSmoothingEnabled = true
    ctx.imageSmoothingQuality = 'high'
    ctx.drawImage(this.imagem.canvas, xa - meia, yTopo, xb - xa, yBase - yTopo)
  }

  private retangulos(ctx: Ctx, W: number) {
    const meia = this.chart!.timeScale().options().barSpacing / 2
    for (const r of this.dados.rects) {
      const xa = this.x(r.from), xb = r.to === null ? W + meia : this.x(r.to)
      const y1 = this.y(r.top), y2 = this.y(r.bottom)
      if (xa === null || xb === null || y1 === null || y2 === null) continue
      const x1 = xa - meia, x2 = xb - meia
      if (x2 < 0 || x1 > W) continue
      ctx.fillStyle = r.color
      ctx.fillRect(x1, Math.min(y1, y2), Math.max(x2 - x1, 2), Math.max(Math.abs(y2 - y1), 1))
      if (r.border) {
        ctx.strokeStyle = r.border; ctx.lineWidth = 1
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y1); ctx.moveTo(x1, y2); ctx.lineTo(x2, y2); ctx.stroke()
      }
    }
  }

  private rotulos(ctx: Ctx) {
    ctx.font = FONTE; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
    for (const l of this.dados.labels) {
      const xc = this.x(l.time), y = this.y(l.price)
      if (xc === null || y === null) continue
      const x = xc - this.chart!.timeScale().options().barSpacing / 2
      const w = ctx.measureText(l.text).width + 8
      const yy = y - 13
      ctx.fillStyle = 'rgba(5,7,12,0.85)'
      ctx.fillRect(x - w / 2, yy - 8, w, 16)
      ctx.fillStyle = l.color
      ctx.fillText(l.text, x, yy)
    }
  }
}
