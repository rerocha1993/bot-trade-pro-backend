/**
 * Todos os desenhos à mão no gráfico (primitiva da lightweight-charts): cada um pela sua ferramenta
 * (ferramentas.ts), as alças do selecionado, os rótulos na escala de preço (linha horizontal e os pontos do
 * selecionado) e na escala de tempo (os pontos do selecionado), como a TradingView mostra.
 *
 * Também responde o que está debaixo do mouse (`acertar`): uma alça do selecionado ou o corpo de um desenho, do mais
 * novo para o mais velho. Quem cuida do mouse é o GraficoTV.
 */
import type {
  IChartApi, ISeriesApi, ISeriesPrimitive, ISeriesPrimitiveAxisView, ISeriesPrimitivePaneRenderer, ISeriesPrimitivePaneView,
  SeriesAttachedParameter, Time,
} from 'lightweight-charts'
import { visivelNoTempo, type Desenho } from '../../lib/desenhos'
import { xDoIndice } from './coordenada'
import { FERRAMENTA, type Geo, type Px } from './ferramentas'
import type { VelaG } from './ferramentasBase'

type Alvo = Parameters<ISeriesPrimitivePaneRenderer['draw']>[0]
export type ParteDesenho = number | 'corpo'
export type Acerto = { id: string; parte: ParteDesenho }

const RAIO_ALCA = 5
const COR_ALCA = '#2962ff'
const COR_ROTULO_SEL = '#2962ff'
const DIAS = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb']
const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']

/** "qua 05 nov '26 14:30" em UTC, como o rótulo da TradingView na escala de tempo */
function rotuloTempo(t: number): string {
  const d = new Date(t * 1000)
  const p2 = (n: number) => String(n).padStart(2, '0')
  return `${DIAS[d.getUTCDay()]} ${p2(d.getUTCDate())} ${MESES[d.getUTCMonth()]} '${String(d.getUTCFullYear()).slice(2)} ${p2(d.getUTCHours())}:${p2(d.getUTCMinutes())}`
}

function corDoTexto(fundo: string): string {
  const m = /^#([0-9a-f]{6})$/i.exec(fundo)
  if (!m) return '#ffffff'
  const n = parseInt(m[1], 16)
  const luz = (0.299 * (n >> 16) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255
  return luz > 0.6 ? '#131722' : '#ffffff'
}

export class DesenhosPrimitiva implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null
  private series: ISeriesApi<'Candlestick'> | null = null
  private pedirDesenho: (() => void) | null = null
  private lista: Desenho[] = []
  private rascunho: Desenho | null = null
  private sel: string | null = null
  private tempo = '30m'
  private escondidos = false
  private largura = 0
  private altura = 0
  private view: ISeriesPrimitivePaneView = {
    zOrder: () => 'top',
    renderer: () => ({ draw: (alvo: Alvo) => this.desenhar(alvo) }),
  }

  private logico: (t: number) => number | null
  private formatar: (p: number) => string
  private passo: () => number
  private dados: () => VelaG[]

  constructor(logico: (t: number) => number | null, formatar: (p: number) => string, passo: () => number, dados: () => VelaG[]) {
    this.logico = logico
    this.formatar = formatar
    this.passo = passo
    this.dados = dados
  }

  attached(p: SeriesAttachedParameter<Time>) {
    this.chart = p.chart
    this.series = p.series as ISeriesApi<'Candlestick'>
    this.pedirDesenho = p.requestUpdate
  }
  detached() { this.chart = null; this.series = null; this.pedirDesenho = null }
  paneViews() { return [this.view] }
  updateAllViews() { /* desenha direto no draw */ }

  set(lista: Desenho[], sel: string | null) { this.lista = lista; this.sel = sel; this.pedirDesenho?.() }
  setRascunho(d: Desenho | null) { this.rascunho = d; this.pedirDesenho?.() }
  setTempo(t: string) { this.tempo = t; this.pedirDesenho?.() }
  setEscondidos(sim: boolean) { this.escondidos = sim; this.pedirDesenho?.() }
  todos(): Desenho[] { return this.lista }

  /** os que aparecem agora: não escondidos, visíveis neste tempo gráfico e de uma ferramenta conhecida */
  private visiveis(): Desenho[] {
    if (this.escondidos) return []
    return this.lista.filter((d) => !d.oculto && FERRAMENTA[d.tipo] && visivelNoTempo(d.vis, this.tempo))
  }

  private x(t: number): number | null {
    const l = this.logico(t)
    if (l === null || !this.chart) return null
    return xDoIndice(this.chart, l)
  }
  private y(p: number): number | null {
    const c = this.series?.priceToCoordinate(p)
    return c === null || c === undefined ? null : c
  }
  private px(d: Desenho): Px[] | null {
    if (FERRAMENTA[d.tipo]?.tela) {                // preso à tela: frações da largura e da altura
      const W = this.largura || (this.chart?.timeScale().width() ?? 0), H = this.altura || 600
      return d.pts.map((p) => ({ x: p.t * W, y: p.p * H }))
    }
    const out: Px[] = []
    for (const p of d.pts) {
      const x = this.x(p.t), y = this.y(p.p)
      if (x === null || y === null) return null
      out.push({ x, y })
    }
    return out
  }
  private geo(selecionado: boolean): Geo {
    const W = this.largura || (this.chart?.timeScale().width() ?? 0)
    return {
      W, H: this.altura || 600, formatar: this.formatar, y: (p) => this.y(p), x: (t) => this.x(t), passo: this.passo(), selecionado,
      velas: (t1, t2) => {
        const v = this.dados()
        let i = 0, j = v.length
        while (i < j) { const m = (i + j) >> 1; if (v[m].t < t1) i = m + 1; else j = m }
        const out: VelaG[] = []
        for (let k = i; k < v.length && v[k].t <= t2; k++) out.push(v[k])
        return out
      },
      redesenhar: () => this.pedirDesenho?.(),
    }
  }
  /** onde ficam as alças do desenho (a ferramenta pode pôr fora dos pontos, como o canal de regressão) */
  private alcasDe(d: Desenho, px: Px[], selecionado: boolean): Px[] {
    const f = FERRAMENTA[d.tipo]
    return f?.alcas ? f.alcas(d, px, this.geo(selecionado)) : px
  }

  acertar(x: number, y: number): Acerto | null {
    const vis = this.visiveis()
    const sel = vis.find((d) => d.id === this.sel)
    if (sel) {
      const px = this.px(sel)
      const al = px ? this.alcasDe(sel, px, true) : []
      for (let i = 0; i < al.length; i++) if (Math.hypot(x - al[i].x, y - al[i].y) <= RAIO_ALCA + 3) return { id: sel.id, parte: i }
    }
    const ordem = sel ? [sel, ...vis.filter((d) => d !== sel).reverse()] : [...vis].reverse()
    for (const d of ordem) {
      const px = this.px(d)
      if (px && FERRAMENTA[d.tipo].acertar(x, y, d, px, this.geo(d === sel))) return { id: d.id, parte: 'corpo' }
    }
    return null
  }

  private desenhar(alvo: Alvo) {
    if (!this.chart || !this.series) return
    const lista = this.rascunho ? [...this.visiveis(), this.rascunho] : this.visiveis()
    if (!lista.length) return
    alvo.useMediaCoordinateSpace(({ context: ctx, mediaSize }) => {
      this.largura = mediaSize.width
      this.altura = mediaSize.height
      ctx.save()
      ctx.beginPath(); ctx.rect(0, 0, mediaSize.width, mediaSize.height); ctx.clip()
      for (const d of lista) {
        const px = this.px(d)
        if (!px) continue
        const comAlcas = d.id === this.sel || d === this.rascunho
        ctx.save()
        FERRAMENTA[d.tipo].desenhar(ctx, d, px, this.geo(comAlcas))
        ctx.restore()
        if (comAlcas) this.alcas(ctx, this.alcasDe(d, px, true), !!d.travado)
      }
      ctx.restore()
    })
  }

  private alcas(ctx: CanvasRenderingContext2D, px: Px[], travado: boolean) {
    ctx.setLineDash([])
    for (const p of px) {
      ctx.beginPath(); ctx.arc(p.x, p.y, RAIO_ALCA, 0, Math.PI * 2)
      ctx.fillStyle = travado ? COR_ALCA : '#0b0f17'; ctx.fill()
      ctx.strokeStyle = COR_ALCA; ctx.lineWidth = 1.5; ctx.stroke()
    }
  }

  // ---------------------------------------------------------------- rótulos nas escalas

  private selecionadoOuRascunho(): Desenho | null {
    if (this.rascunho) return this.rascunho
    return this.visiveis().find((d) => d.id === this.sel) ?? null
  }

  priceAxisViews(): readonly ISeriesPrimitiveAxisView[] {
    const views: ISeriesPrimitiveAxisView[] = []
    for (const d of this.visiveis()) {
      for (const r of FERRAMENTA[d.tipo].rotulosPreco?.(d) ?? []) {
        views.push({ coordinate: () => this.y(r.preco) ?? -100, text: () => this.formatar(r.preco), textColor: () => corDoTexto(r.cor), backColor: () => r.cor })
      }
    }
    const s = this.selecionadoOuRascunho()
    // a linha horizontal já tem o rótulo dela na escala: não repete o do selecionado
    if (s && !FERRAMENTA[s.tipo]?.tela && !FERRAMENTA[s.tipo]?.soTempo && !FERRAMENTA[s.tipo]?.rotulosPreco?.(s).length) for (const p of s.pts) {
      views.push({ coordinate: () => this.y(p.p) ?? -100, text: () => this.formatar(p.p), textColor: () => '#ffffff', backColor: () => COR_ROTULO_SEL })
    }
    return views
  }

  timeAxisViews(): readonly ISeriesPrimitiveAxisView[] {
    const views: ISeriesPrimitiveAxisView[] = []
    for (const d of this.visiveis()) {
      for (const r of FERRAMENTA[d.tipo].rotulosTempo?.(d) ?? []) {
        views.push({ coordinate: () => this.x(r.t) ?? -100, text: () => rotuloTempo(r.t), textColor: () => corDoTexto(r.cor), backColor: () => r.cor })
      }
    }
    const s = this.selecionadoOuRascunho()
    const f = s ? FERRAMENTA[s.tipo] : null
    if (s && f && !f.soPreco && !f.tela && !f.rotulosTempo?.(s).length) {
      for (const p of s.pts) views.push({ coordinate: () => this.x(p.t) ?? -100, text: () => rotuloTempo(p.t), textColor: () => '#ffffff', backColor: () => COR_ROTULO_SEL })
    }
    return views
  }
}
