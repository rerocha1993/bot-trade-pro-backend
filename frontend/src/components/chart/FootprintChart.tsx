import { useEffect, useRef, useState } from 'react'
import {
  ColorType, CrosshairMode, createChart,
  type CustomData, type CustomSeriesOptions, type CustomSeriesPricePlotValues, type CustomSeriesWhitespaceData,
  type IChartApi, type ICustomSeriesPaneRenderer, type ICustomSeriesPaneView, type ISeriesApi,
  type PaneRendererCustomData, type PriceToCoordinateConverter, type Time, type UTCTimestamp,
  customSeriesDefaultOptions,
} from 'lightweight-charts'
import type { CanvasRenderingTarget2D } from 'fancy-canvas'
import type { EventoPresos, VelaFootprint } from '../../api/types'

/**
 * Footprint no gráfico do TradingView (lightweight-charts, série customizada): arrastar, zoom com a roda ou dois
 * dedos, eixo de preço que estica. O desenho muda com o zoom, como no TradingView:
 *   - perto: em cada linha de preço, venda agredida à esquerda e compra agredida à direita, com os números;
 *   - médio: só as barras coloridas por linha;
 *   - longe: vela normal.
 * POC da vela com contorno, desequilíbrio diagonal de 3:1 em negrito, presos com contorno amarelo e etiqueta.
 * O delta de cada vela fica num histograma embaixo, como o volume do TradingView.
 */
const COR = {
  fundo: '#0b0f14', grade: 'rgba(255,255,255,0.045)', texto: '#c7cfda', fraco: '#6b7685',
  compra: '#3d8bfd', venda: '#f0544f', alta: '#2ecc84', baixa: '#f0544f', presos: '#f5c04a', poc: 'rgba(255,255,255,0.8)',
}
const DESEQUILIBRIO = 3
const ESPACO_NUMEROS = 78       // largura da vela (px) a partir da qual aparecem os números
const ALTURA_NUMEROS = 11       // altura da linha (px) a partir da qual aparecem os números

interface FpDado extends CustomData<Time> {
  time: UTCTimestamp
  o: number; h: number; l: number; c: number
  delta: number; poc: number | null
  linhas: [number, number, number][]
  presos: EventoPresos[]
}
interface FpOpcoes extends CustomSeriesOptions { linha: number }

const num = (v: number) => (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v >= 100 ? v.toFixed(0) : v >= 10 ? v.toFixed(1) : v.toFixed(2))

class Desenho implements ICustomSeriesPaneRenderer {
  dados: PaneRendererCustomData<Time, FpDado> | null = null
  linha = 50

  draw(target: CanvasRenderingTarget2D, preco: PriceToCoordinateConverter): void {
    const d = this.dados
    if (!d || !d.visibleRange) return
    const faixa = d.visibleRange
    target.useMediaCoordinateSpace(({ context: g }) => {
      const barras = d.bars.slice(faixa.from, faixa.to)
      if (!barras.length) return
      const w = d.barSpacing
      const y = (p: number) => preco(p) ?? 0
      const ref = barras[barras.length - 1].originalData.c
      const alturaLinha = Math.abs(y(ref) - y(ref + this.linha))
      const numeros = w >= ESPACO_NUMEROS && alturaLinha >= ALTURA_NUMEROS
      const celulas = w >= 12 && alturaLinha >= 2.5
      const maior = Math.max(1e-9, ...barras.flatMap((b) => b.originalData.linhas.map(([, cp, vd]) => Math.max(cp, vd))))
      const fonte = Math.min(11, Math.max(8, Math.floor(alturaLinha - 3)))

      for (const b of barras) {
        const v = b.originalData
        const subiu = v.c >= v.o
        const corVela = subiu ? COR.alta : COR.baixa
        const x0 = b.x - w / 2 + 1, x1 = b.x + w / 2 - 1
        // vela: estreita à esquerda quando há células; cheia quando o zoom está longe
        const larguraVela = celulas ? Math.max(3, Math.min(10, w * 0.1)) : Math.max(1, w * 0.7)
        const xv = celulas ? x0 + 2 : b.x - larguraVela / 2
        g.strokeStyle = corVela
        g.lineWidth = 1
        g.beginPath(); g.moveTo(xv + larguraVela / 2, y(v.h)); g.lineTo(xv + larguraVela / 2, y(v.l)); g.stroke()
        g.fillStyle = corVela
        const ya = y(Math.max(v.o, v.c)), yb = y(Math.min(v.o, v.c))
        g.fillRect(xv, ya, larguraVela, Math.max(1, yb - ya))
        if (!celulas) continue

        const xa = xv + larguraVela + 3, meio = (xa + x1) / 2, meia = (x1 - xa) / 2
        const mapa = new Map(v.linhas.map(([p, cp, vd]) => [Math.round(p / this.linha), { cp, vd }]))
        for (const [p, cp, vd] of v.linhas) {
          const yt = y(p + this.linha), yf = y(p)
          const h = Math.max(1, yf - yt - (alturaLinha > 6 ? 1 : 0))
          g.fillStyle = 'rgba(240,84,79,0.30)'
          g.fillRect(meio - (vd / maior) * meia, yt, (vd / maior) * meia, h)
          g.fillStyle = 'rgba(61,139,253,0.32)'
          g.fillRect(meio, yt, (cp / maior) * meia, h)
          if (!numeros) continue
          const k = Math.round(p / this.linha)
          const compraForte = cp >= 1 && cp >= DESEQUILIBRIO * Math.max(mapa.get(k - 1)?.vd ?? 0, 1e-9)
          const vendaForte = vd >= 1 && vd >= DESEQUILIBRIO * Math.max(mapa.get(k + 1)?.cp ?? 0, 1e-9)
          g.textBaseline = 'middle'
          g.font = `${vendaForte ? 'bold ' : ''}${fonte}px ui-monospace, Menlo, Consolas, monospace`
          g.fillStyle = vendaForte ? COR.venda : COR.texto
          g.textAlign = 'right'
          g.fillText(num(vd), meio - 3, (yt + yf) / 2)
          g.font = `${compraForte ? 'bold ' : ''}${fonte}px ui-monospace, Menlo, Consolas, monospace`
          g.fillStyle = compraForte ? COR.compra : COR.texto
          g.textAlign = 'left'
          g.fillText(num(cp), meio + 3, (yt + yf) / 2)
        }
        if (v.poc !== null && alturaLinha >= 4) {
          g.strokeStyle = COR.poc
          g.lineWidth = 1
          g.strokeRect(xa + 0.5, y(v.poc + this.linha) + 0.5, x1 - xa - 1, Math.abs(y(v.poc) - y(v.poc + this.linha)) - 1)
        }
        for (const e of v.presos) {
          if (e.confirmado === false) continue
          const p = Math.floor(e.preco / this.linha) * this.linha
          const yt = y(p + this.linha), yf = y(p)
          g.strokeStyle = COR.presos
          g.lineWidth = e.confirmado ? 2.5 : 1.5
          g.setLineDash(e.confirmado ? [] : [4, 3])
          g.strokeRect(xa - 1, yt - 1, x1 - xa + 2, yf - yt + 2)
          g.setLineDash([])
          g.lineWidth = 1
          if (w >= 50) {
            g.font = 'bold 10px system-ui, sans-serif'
            const texto = `${e.lado === 'compradores' ? 'compradores' : 'vendedores'} presos${e.confirmado ? '' : '?'}`
            const tw = Math.min(g.measureText(texto).width + 10, w - 4)
            const ye = e.lado === 'compradores' ? yt - 16 : yf + 2
            g.fillStyle = COR.presos
            g.fillRect(meio - tw / 2, ye, tw, 14)
            g.fillStyle = '#1a1405'
            g.textAlign = 'center'
            g.textBaseline = 'middle'
            g.fillText(texto, meio, ye + 7, tw - 4)
          }
        }
      }
    })
  }
}

class VistaFootprint implements ICustomSeriesPaneView<Time, FpDado, FpOpcoes> {
  desenho = new Desenho()
  linha = 50                      // altura da linha de preço em US$; trocada pelo componente antes do setData
  renderer(): ICustomSeriesPaneRenderer { return this.desenho }
  update(dados: PaneRendererCustomData<Time, FpDado>): void {
    this.desenho.dados = dados
    this.desenho.linha = this.linha
  }
  priceValueBuilder(v: FpDado): CustomSeriesPricePlotValues { return [v.l, v.h, v.c] }
  isWhitespace(v: FpDado | CustomSeriesWhitespaceData<Time>): v is CustomSeriesWhitespaceData<Time> {
    return (v as FpDado).c === undefined
  }
  defaultOptions(): FpOpcoes { return { ...customSeriesDefaultOptions, linha: 50 } }
}

const hora = (s: number) => new Date(s * 1000).toISOString().slice(5, 16).replace('T', ' ')

export default function FootprintChart({ velas, linha, height = 600 }: { velas: VelaFootprint[]; linha: number; height?: number }) {
  const caixa = useRef<HTMLDivElement>(null)
  const chart = useRef<IChartApi | null>(null)
  const serie = useRef<ISeriesApi<'Custom', Time, FpDado | CustomSeriesWhitespaceData<Time>, FpOpcoes> | null>(null)
  const deltas = useRef<ISeriesApi<'Histogram'> | null>(null)
  const vista = useRef<VistaFootprint | null>(null)
  const porTs = useRef(new Map<number, VelaFootprint>())
  const primeiraCarga = useRef(true)
  const [sob, setSob] = useState<VelaFootprint | null>(null)

  useEffect(() => {
    if (!caixa.current) return
    const c = createChart(caixa.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: COR.fundo }, textColor: COR.fraco, fontSize: 11 },
      grid: { vertLines: { color: COR.grade }, horzLines: { color: COR.grade } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: 'rgba(255,255,255,0.08)', scaleMargins: { top: 0.05, bottom: 0.18 } },
      timeScale: { borderColor: 'rgba(255,255,255,0.08)', timeVisible: true, secondsVisible: false, barSpacing: 120,
                   minBarSpacing: 2, rightOffset: 2 },
    })
    const vf = new VistaFootprint()
    vf.linha = linha
    vista.current = vf
    const s = c.addCustomSeries(vf, { priceLineColor: '#e8edf3', priceLineStyle: 2 })
    const h = c.addHistogramSeries({ priceScaleId: 'delta', priceFormat: { type: 'volume' }, lastValueVisible: false, priceLineVisible: false })
    c.priceScale('delta').applyOptions({ scaleMargins: { top: 0.9, bottom: 0 } })
    c.subscribeCrosshairMove((p) => {
      const ts = typeof p.time === 'number' ? p.time : null
      setSob(ts !== null ? porTs.current.get(ts) ?? null : null)
    })
    chart.current = c
    serie.current = s
    deltas.current = h
    primeiraCarga.current = true
    return () => { c.remove(); chart.current = null; serie.current = null; deltas.current = null }
    // o gráfico é criado uma vez; dados e linha entram pelo efeito de baixo
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const s = serie.current, h = deltas.current, c = chart.current
    if (!s || !h || !c) return
    if (vista.current) vista.current.linha = linha
    porTs.current = new Map(velas.map((v) => [v.ts, v]))
    s.setData(velas.map((v) => ({
      time: v.ts as UTCTimestamp, o: v.abertura, h: v.maxima, l: v.minima, c: v.fechamento,
      delta: v.delta, poc: v.poc, linhas: v.linhas, presos: v.presos,
    })))
    h.setData(velas.map((v) => ({ time: v.ts as UTCTimestamp, value: Math.abs(v.delta),
                                    color: v.delta >= 0 ? 'rgba(61,139,253,0.35)' : 'rgba(240,84,79,0.35)' })))
    if (primeiraCarga.current && velas.length) {
      // começa perto o bastante para ler os números das últimas velas
      c.timeScale().applyOptions({ barSpacing: 120 })
      c.timeScale().scrollToRealTime()
      primeiraCarga.current = false
    }
  }, [velas, linha])

  const l = sob ?? velas[velas.length - 1]
  return (
    <div style={{ position: 'relative' }}>
      <div ref={caixa} style={{ height, borderRadius: 10, overflow: 'hidden' }} />
      {l && (
        <div className="mono" style={{ position: 'absolute', left: 10, top: 8, fontSize: 11, color: COR.texto, pointerEvents: 'none',
                                       background: 'rgba(11,15,20,0.75)', padding: '4px 8px', borderRadius: 6, lineHeight: 1.6, zIndex: 3 }}>
          <span style={{ color: COR.fraco }}>{hora(l.ts)} UTC</span>{'  '}
          A {l.abertura.toFixed(0)} M {l.maxima.toFixed(0)} m {l.minima.toFixed(0)} F {l.fechamento.toFixed(0)}<br />
          <span style={{ color: COR.compra }}>compra {num(l.compra)}</span>{'  '}
          <span style={{ color: COR.venda }}>venda {num(l.venda)}</span>{'  '}
          <span style={{ color: l.delta >= 0 ? COR.compra : COR.venda }}>Δ {l.delta >= 0 ? '+' : '−'}{num(Math.abs(l.delta))}</span>
          {l.presos.filter((e) => e.confirmado !== false).map((e) => (
            <span key={e.lado} style={{ color: COR.presos }}>{'  '}{e.lado} presos em {e.preco.toFixed(0)}{e.confirmado ? '' : '?'}</span>
          ))}
        </div>
      )}
    </div>
  )
}
