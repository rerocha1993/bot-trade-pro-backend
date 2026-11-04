/**
 * Desenho dos Fibonacci de retração no gráfico (primitiva da lightweight-charts): níveis, fundo entre eles, linha de
 * tendência entre os dois pontos e os rótulos "0.618(81.234,50)" no lugar escolhido — como a ferramenta da TradingView.
 * O selecionado mostra as duas alças (os pontos) para arrastar.
 *
 * Também responde onde o mouse está (`acertar`): numa alça, numa linha, ou no fundo do selecionado. Quem cuida do
 * mouse é o GraficoTV; aqui só se desenha e se mede.
 */
import type {
  IChartApi, ISeriesApi, ISeriesPrimitive, ISeriesPrimitivePaneRenderer, ISeriesPrimitivePaneView,
  SeriesAttachedParameter, Time,
} from 'lightweight-charts'
import { comAlfa, niveisDe, tracos, type Fibo } from '../../lib/fibo'
import { xDoIndice } from './coordenada'

type Alvo = Parameters<ISeriesPrimitivePaneRenderer['draw']>[0]
export type ParteFibo = 'p1' | 'p2' | 'corpo'
export type AcertoFibo = { id: string; parte: ParteFibo }

const RAIO_ALCA = 5
/** distância (px) até a linha que ainda conta como em cima dela */
const PERTO_PX = 5
const COR_ALCA = '#2962ff'

type Geometria = { x1: number; y1: number; x2: number; y2: number; esq: number; dir: number; niveis: { valor: number; preco: number; cor: string; y: number }[] }

export class FiboDesenho implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null
  private series: ISeriesApi<'Candlestick'> | null = null
  private pedirDesenho: (() => void) | null = null
  private fibos: Fibo[] = []
  private rascunho: Fibo | null = null
  private selecionado: string | null = null
  private largura = 0
  private view: ISeriesPrimitivePaneView = {
    zOrder: () => 'top',
    renderer: () => ({ draw: (alvo: Alvo) => this.desenhar(alvo) }),
  }

  private logico: (t: number) => number | null
  private formatar: (p: number) => string

  constructor(logico: (t: number) => number | null, formatar: (p: number) => string) {
    this.logico = logico
    this.formatar = formatar
  }

  attached(p: SeriesAttachedParameter<Time>) {
    this.chart = p.chart
    this.series = p.series as ISeriesApi<'Candlestick'>
    this.pedirDesenho = p.requestUpdate
  }
  detached() { this.chart = null; this.series = null; this.pedirDesenho = null }
  paneViews() { return [this.view] }
  updateAllViews() { /* desenha direto no draw */ }

  set(fibos: Fibo[], selecionado: string | null) { this.fibos = fibos; this.selecionado = selecionado; this.pedirDesenho?.() }
  setRascunho(f: Fibo | null) { this.rascunho = f; this.pedirDesenho?.() }
  todos(): Fibo[] { return this.fibos }

  private x(t: number): number | null {
    const l = this.logico(t)
    if (l === null || !this.chart) return null
    return xDoIndice(this.chart, l)
  }
  private y(p: number): number | null {
    const c = this.series?.priceToCoordinate(p)
    return c === null || c === undefined ? null : c
  }

  private geometria(f: Fibo, W: number): Geometria | null {
    const x1 = this.x(f.t1), x2 = this.x(f.t2), y1 = this.y(f.p1), y2 = this.y(f.p2)
    if (x1 === null || x2 === null || y1 === null || y2 === null) return null
    const niveis = []
    for (const n of niveisDe(f)) {
      const y = this.y(n.preco)
      if (y !== null) niveis.push({ ...n, y })
    }
    return { x1, y1, x2, y2, niveis, esq: f.cfg.estenderEsq ? 0 : Math.min(x1, x2), dir: f.cfg.estenderDir ? W : Math.max(x1, x2) }
  }

  /** o que está debaixo do ponto (x, y): alça do selecionado primeiro, depois as linhas do mais novo ao mais velho */
  acertar(x: number, y: number): AcertoFibo | null {
    const W = this.largura || (this.chart?.timeScale().width() ?? 0)
    const sel = this.fibos.find((f) => f.id === this.selecionado)
    const ordem = sel ? [sel, ...this.fibos.filter((f) => f !== sel).reverse()] : [...this.fibos].reverse()
    for (const f of ordem) {
      const g = this.geometria(f, W)
      if (!g) continue
      if (f === sel) {
        if (Math.hypot(x - g.x1, y - g.y1) <= RAIO_ALCA + 3) return { id: f.id, parte: 'p1' }
        if (Math.hypot(x - g.x2, y - g.y2) <= RAIO_ALCA + 3) return { id: f.id, parte: 'p2' }
      }
      const dentroX = x >= g.esq - PERTO_PX && x <= g.dir + PERTO_PX
      if (dentroX && g.niveis.some((n) => Math.abs(y - n.y) <= PERTO_PX)) return { id: f.id, parte: 'corpo' }
      if (f.cfg.tendencia.ligada && distSegmento(x, y, g.x1, g.y1, g.x2, g.y2) <= PERTO_PX) return { id: f.id, parte: 'corpo' }
      if (f === sel && dentroX && g.niveis.length > 1) {
        const ys = g.niveis.map((n) => n.y)
        if (y >= Math.min(...ys) && y <= Math.max(...ys)) return { id: f.id, parte: 'corpo' }
      }
    }
    return null
  }

  private desenhar(alvo: Alvo) {
    if (!this.chart || !this.series) return
    const lista = this.rascunho ? [...this.fibos, this.rascunho] : this.fibos
    if (!lista.length) return
    alvo.useMediaCoordinateSpace(({ context: ctx, mediaSize }) => {
      const W = mediaSize.width
      this.largura = W
      ctx.save()
      ctx.beginPath(); ctx.rect(0, 0, W, mediaSize.height); ctx.clip()
      for (const f of lista) {
        const g = this.geometria(f, W)
        if (g) this.um(ctx, f, g, W, f.id === this.selecionado || f === this.rascunho)
      }
      ctx.restore()
    })
  }

  private um(ctx: CanvasRenderingContext2D, f: Fibo, g: Geometria, W: number, comAlcas: boolean) {
    const c = f.cfg
    const { esq, dir, niveis } = g
    // fundo: cada faixa entre dois níveis com a cor do nível de cima (o de valor maior), como na TradingView
    if (c.fundo && c.transparencia < 100) {
      const alfa = (100 - c.transparencia) / 100
      for (let i = 1; i < niveis.length; i++) {
        const a = niveis[i - 1], b = niveis[i]
        ctx.fillStyle = comAlfa(b.cor, alfa)
        ctx.fillRect(esq, Math.min(a.y, b.y), dir - esq, Math.abs(b.y - a.y))
      }
    }
    ctx.lineWidth = c.larguraNiveis
    ctx.setLineDash(tracos(c.estiloNiveis, c.larguraNiveis))
    for (const n of niveis) {
      ctx.strokeStyle = n.cor
      const y = Math.round(n.y) + (c.larguraNiveis % 2 ? 0.5 : 0)
      ctx.beginPath(); ctx.moveTo(esq, y); ctx.lineTo(dir, y); ctx.stroke()
    }
    ctx.setLineDash([])
    if (c.tendencia.ligada) {
      ctx.strokeStyle = c.tendencia.cor; ctx.lineWidth = c.tendencia.largura
      ctx.setLineDash(tracos(c.tendencia.estilo, c.tendencia.largura))
      ctx.beginPath(); ctx.moveTo(g.x1, g.y1); ctx.lineTo(g.x2, g.y2); ctx.stroke()
      ctx.setLineDash([])
    }
    if (c.rotulos || c.precos) {
      ctx.font = `${c.fonte}px 'DM Mono', monospace`
      ctx.textBaseline = c.vertical === 'cima' ? 'bottom' : c.vertical === 'baixo' ? 'top' : 'middle'
      const dy = c.vertical === 'cima' ? -2 : c.vertical === 'baixo' ? 2 : 0
      for (const n of niveis) {
        const nome = c.rotuloComo === 'percentual' ? `${+(n.valor * 100).toFixed(1)}%` : String(+n.valor.toFixed(4))
        const texto = (c.rotulos ? nome : '') + (c.precos ? (c.rotulos ? `(${this.formatar(n.preco)})` : this.formatar(n.preco)) : '')
        const w = ctx.measureText(texto).width
        let x: number
        if (c.horizontal === 'centro') { x = (esq + dir) / 2 - w / 2 }
        else if (c.horizontal === 'direita') { x = dir + 4; if (x + w > W) x = dir - w - 4 }
        else { x = esq - w - 4; if (x < 0) x = esq + 4 }
        ctx.fillStyle = n.cor
        ctx.textAlign = 'left'
        ctx.fillText(texto, x, n.y + dy)
      }
    }
    if (comAlcas) {
      for (const [x, y] of [[g.x1, g.y1], [g.x2, g.y2]]) {
        ctx.beginPath(); ctx.arc(x, y, RAIO_ALCA, 0, Math.PI * 2)
        ctx.fillStyle = '#0b0f17'; ctx.fill()
        ctx.strokeStyle = COR_ALCA; ctx.lineWidth = 1.5; ctx.stroke()
      }
    }
  }
}

function distSegmento(px: number, py: number, ax: number, ay: number, bx: number, by: number): number {
  const dx = bx - ax, dy = by - ay
  const l2 = dx * dx + dy * dy
  const t = l2 ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / l2)) : 0
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy))
}
