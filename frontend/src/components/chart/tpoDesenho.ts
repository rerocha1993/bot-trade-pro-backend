/**
 * Desenho do TPO de 30 min dentro do gráfico (primitiva da lightweight-charts), no jeito do TPO da TradingView:
 * o perfil de cada dia encostado no começo do dia, a área de valor mais clara, a faixa do POC em amarelo, e as linhas
 * de POC, VAH e VAL atravessando o dia e seguindo (tracejadas) até o preço voltar a tocar. Nível que ninguém tocou
 * ainda (virgem) vai até a borda direita, com o nome e a data.
 *
 * Junção: os dias escolhidos (`selecao`) ficam marcados; quando o composto deles chega, os perfis desses dias somem e
 * no lugar entra um perfil só, do começo do primeiro ao fim do último, com POC, VAH e VAL próprios.
 */
import type {
  IChartApi, ISeriesApi, ISeriesPrimitive, ISeriesPrimitivePaneRenderer, ISeriesPrimitivePaneView, Logical,
  SeriesAttachedParameter, Time,
} from 'lightweight-charts'
import type { TpoComposto, TpoDia, TpoGrafico } from '../../api/types'

type Alvo = Parameters<ISeriesPrimitivePaneRenderer['draw']>[0]

export const COR_TPO = {
  poc: '#f5c04a',
  borda: '#7aa2ff',
  valor: 'rgba(127,216,222,0.30)',
  fora: 'rgba(127,216,222,0.11)',
  pocFaixa: 'rgba(245,192,74,0.70)',
  selecao: 'rgba(245,192,74,0.06)',
  selecaoBorda: 'rgba(245,192,74,0.55)',
}
/** dias escolhidos para juntar: início (s) do primeiro e do último */
export type Selecao = { de: number; ate: number }
type Rotulo = { y: number; texto: string; cor: string }
/** o perfil ocupa no máximo esta fração da largura do dia */
const LARGURA_PERFIL = 0.82
const FONTE = "10.5px 'DM Mono', monospace"

const ddmm = (t: number) => { const d = new Date(t * 1000); return `${String(d.getUTCDate()).padStart(2, '0')}/${String(d.getUTCMonth() + 1).padStart(2, '0')}` }

export class TpoDesenho implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null
  private series: ISeriesApi<'Candlestick'> | null = null
  private pedirDesenho: (() => void) | null = null
  private dados: TpoGrafico | null = null
  private selecao: Selecao | null = null
  private composto: TpoComposto | null = null
  private view: ISeriesPrimitivePaneView = {
    zOrder: () => 'bottom',
    renderer: () => ({ draw: (alvo: Alvo) => this.desenhar(alvo) }),
  }

  private logico: (t: number) => number | null
  private formatar: (p: number) => string

  /** `logico(t)`: posição (índice de vela, pode ser fracionária ou fora dos dados) do instante t em segundos */
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
  set(d: TpoGrafico | null) { this.dados = d; this.pedirDesenho?.() }
  setJuncao(selecao: Selecao | null, composto: TpoComposto | null) {
    this.selecao = selecao; this.composto = composto; this.pedirDesenho?.()
  }

  /** o dia cujo perfil está na coluna x (coordenada do gráfico), para o clique escolher o dia */
  diaEm(x: number): TpoDia | null {
    if (!this.dados || !this.chart) return null
    const meia = this.chart.timeScale().options().barSpacing / 2
    for (const d of this.dados.dias) {
      const xi = this.x(d.inicio), xf = this.x(d.fim)
      if (xi !== null && xf !== null && x >= xi - meia && x < xf - meia) return d
    }
    return null
  }

  private x(t: number): number | null {
    const l = this.logico(t)
    if (l === null || !this.chart) return null
    return this.chart.timeScale().logicalToCoordinate(l as Logical)
  }
  private y(p: number): number | null {
    const c = this.series?.priceToCoordinate(p)
    return c === null || c === undefined ? null : c
  }

  private desenhar(alvo: Alvo) {
    const tpo = this.dados
    if (!tpo || !tpo.dias.length || !this.chart || !this.series) return
    const meia = this.chart.timeScale().options().barSpacing / 2
    alvo.useMediaCoordinateSpace(({ context: ctx, mediaSize }) => {
      const W = mediaSize.width
      ctx.save()
      ctx.beginPath(); ctx.rect(0, 0, W, mediaSize.height); ctx.clip()
      const sel = this.selecao
      const dentro = (d: TpoDia) => !!sel && d.inicio >= sel.de && d.inicio <= sel.ate
      const comp = sel && this.composto && this.composto.inicio === sel.de && this.composto.n_dias > 1 ? this.composto : null
      const soltos = comp ? tpo.dias.filter((d) => !dentro(d)) : tpo.dias
      const maxCont = Math.max(1, ...soltos.map((d) => Math.max(...d.contagens)))
      const rotulos: Rotulo[] = []
      if (sel) this.marcarSelecao(ctx, sel, tpo.dias, meia, mediaSize.height)
      for (const d of soltos) {
        const xi = this.x(d.inicio), xf = this.x(d.fim)
        if (xi === null || xf === null) continue
        const x0 = xi - meia, x1 = xf - meia
        if (x0 < W && x1 > 0) this.perfil(ctx, d, tpo.tick, x0, x1, maxCont)
        this.linhas(ctx, d, x0, x1, W, rotulos, ddmm(d.inicio))
      }
      if (comp) {
        const xi = this.x(comp.inicio), xf = this.x(comp.fim)
        if (xi !== null && xf !== null) {
          const x0 = xi - meia, x1 = xf - meia
          if (x0 < W && x1 > 0) this.perfil(ctx, comp, tpo.tick, x0, x1, Math.max(1, ...comp.contagens))
          this.linhas(ctx, comp, x0, x1, W, rotulos, `${ddmm(comp.inicio)}–${ddmm(comp.fim - 1)}`)
        }
      }
      // nome dos níveis virgens na borda direita, sem um em cima do outro
      ctx.font = FONTE; ctx.textBaseline = 'middle'; ctx.textAlign = 'right'
      let ultimoY = -100
      for (const r of rotulos.sort((a, b) => a.y - b.y)) {
        const y = Math.max(r.y - 7, ultimoY + 13)
        ultimoY = y
        const w = ctx.measureText(r.texto).width + 8
        ctx.fillStyle = 'rgba(5,7,12,0.82)'
        ctx.fillRect(W - w - 4, y - 6.5, w, 13)
        ctx.fillStyle = r.cor
        ctx.fillText(r.texto, W - 8, y)
      }
      ctx.restore()
    })
  }

  /** faixa clara com borda tracejada em volta dos dias escolhidos */
  private marcarSelecao(ctx: CanvasRenderingContext2D, sel: Selecao, dias: TpoDia[], meia: number, H: number) {
    const ultimo = dias.filter((d) => d.inicio <= sel.ate).pop()
    const xi = this.x(sel.de), xf = ultimo ? this.x(ultimo.fim) : null
    if (xi === null || xf === null) return
    const x0 = xi - meia, x1 = xf - meia
    ctx.fillStyle = COR_TPO.selecao
    ctx.fillRect(x0, 0, x1 - x0, H)
    ctx.strokeStyle = COR_TPO.selecaoBorda; ctx.lineWidth = 1; ctx.setLineDash([3, 4])
    ctx.beginPath(); ctx.moveTo(x0 + 0.5, 0); ctx.lineTo(x0 + 0.5, H); ctx.moveTo(x1 - 0.5, 0); ctx.lineTo(x1 - 0.5, H); ctx.stroke()
    ctx.setLineDash([])
  }

  private perfil(ctx: CanvasRenderingContext2D, d: TpoDia, tick: number, x0: number, x1: number, maxCont: number) {
    const porTpo = ((x1 - x0) * LARGURA_PERFIL) / maxCont
    const iPoc = Math.floor(d.poc / tick + 1e-9) - d.base_i
    d.contagens.forEach((c, k) => {
      if (!c) return
      const lo = (d.base_i + k) * tick, hi = lo + tick
      const ya = this.y(hi), yb = this.y(lo)
      if (ya === null || yb === null) return
      const meio = lo + tick / 2
      ctx.fillStyle = k === iPoc ? COR_TPO.pocFaixa : meio >= d.val && meio <= d.vah ? COR_TPO.valor : COR_TPO.fora
      const alto = Math.max(1, yb - ya - (yb - ya > 3 ? 1 : 0))
      ctx.fillRect(x0, ya, Math.max(1, c * porTpo), alto)
    })
  }

  private linhas(ctx: CanvasRenderingContext2D, d: TpoDia, x0: number, x1: number, W: number, rotulos: Rotulo[], quando: string) {
    for (const nome of ['vah', 'val', 'poc'] as const) {
      const y = this.y(d[nome])
      if (y === null) continue
      const cor = nome === 'poc' ? COR_TPO.poc : COR_TPO.borda
      // dentro do dia: contínua
      ctx.strokeStyle = cor; ctx.lineWidth = nome === 'poc' ? 1.5 : 1; ctx.setLineDash([])
      ctx.beginPath(); ctx.moveTo(Math.max(x0, -10), y); ctx.lineTo(Math.min(x1, W + 10), y); ctx.stroke()
      if (d.aberto) continue
      // depois do dia: tracejada até o toque, ou até a borda direita se ainda está virgem
      const toque = d.toques[nome]
      const xt = toque === null ? W : this.x(toque)
      if (xt === null || xt <= x1 || x1 > W) continue
      ctx.globalAlpha = 0.75; ctx.lineWidth = 1; ctx.setLineDash([4, 4])
      ctx.beginPath(); ctx.moveTo(Math.max(x1, -10), y); ctx.lineTo(Math.min(xt, W), y); ctx.stroke()
      ctx.globalAlpha = 1; ctx.setLineDash([])
      if (toque === null) rotulos.push({ y, cor, texto: `${nome.toUpperCase()} ${quando} ${this.formatar(d[nome])}` })
    }
  }
}
