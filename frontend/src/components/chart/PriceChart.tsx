/**
 * Gráfico de preço com Lightweight Charts (TradingView) e overlays desenhados por primitiva:
 * caminhos (ZigZag, VWAP), rótulos de ondas, níveis (linhas de preço), retângulos (order blocks),
 * perfil lateral (TPO / Volume Profile) e marcadores de entradas e saídas.
 */
import {
  ColorType, CrosshairMode, LineStyle, PriceScaleMode, createChart,
  type IChartApi, type IPriceLine, type ISeriesApi, type ISeriesPrimitive, type ISeriesPrimitivePaneRenderer,
  type ISeriesPrimitivePaneView, type SeriesAttachedParameter, type SeriesMarker, type Time, type UTCTimestamp,
} from 'lightweight-charts'
import { useEffect, useRef } from 'react'
import type { Candle } from '../../api/types'

import type { ChartLabel, ChartLevel, ChartMarker, ChartPath, ChartProfile, ChartRect } from '../../lib/chart-tipos'

interface OverlayData { rects: ChartRect[]; profile: ChartProfile | null; labels: ChartLabel[] }
type DrawTarget = Parameters<ISeriesPrimitivePaneRenderer['draw']>[0]

const MONO = "11px 'IBM Plex Mono', monospace"

class Overlay implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null
  private series: ISeriesApi<'Candlestick'> | null = null
  private requestUpdate: (() => void) | null = null
  private data: OverlayData = { rects: [], profile: null, labels: [] }
  private view: ISeriesPrimitivePaneView = {
    zOrder: () => 'normal',
    renderer: () => ({ draw: (target: DrawTarget) => this.draw(target) }),
  }

  attached(p: SeriesAttachedParameter<Time>) {
    this.chart = p.chart
    this.series = p.series as ISeriesApi<'Candlestick'>
    this.requestUpdate = p.requestUpdate
  }
  detached() { this.chart = null; this.series = null; this.requestUpdate = null }
  paneViews() { return [this.view] }
  updateAllViews() { /* nada a recalcular: desenha direto */ }
  set(d: OverlayData) { this.data = d; this.requestUpdate?.() }

  private x(time: number): number | null {
    const c = this.chart?.timeScale().timeToCoordinate(time as UTCTimestamp)
    return c === null || c === undefined ? null : c
  }
  private y(price: number): number | null {
    const c = this.series?.priceToCoordinate(price)
    return c === null || c === undefined ? null : c
  }

  private draw(target: DrawTarget) {
    if (!this.chart || !this.series) return
    const range = this.chart.timeScale().getVisibleRange()
    target.useMediaCoordinateSpace(({ context: ctx, mediaSize }) => {
      const W = mediaSize.width, H = mediaSize.height
      ctx.save()
      ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.clip()
      // retângulos (order blocks, zonas)
      for (const r of this.data.rects) {
        if (range && r.from > (range.to as number)) continue
        let x1 = this.x(r.from)
        if (x1 === null) x1 = range && r.from < (range.from as number) ? 0 : null
        if (x1 === null) continue
        let x2 = r.to === null ? W : this.x(r.to)
        if (x2 === null) x2 = range && r.to !== null && r.to > (range.to as number) ? W : W
        const y1 = this.y(r.top), y2 = this.y(r.bottom)
        if (y1 === null || y2 === null) continue
        ctx.fillStyle = r.color
        ctx.fillRect(x1, Math.min(y1, y2), Math.max(x2 - x1, 2), Math.max(Math.abs(y2 - y1), 1))
        if (r.border) {
          ctx.strokeStyle = r.border; ctx.lineWidth = 1
          ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y1); ctx.moveTo(x1, y2); ctx.lineTo(x2, y2); ctx.stroke()
        }
      }
      // perfil lateral (TPO / VP) encostado na direita
      const p = this.data.profile
      if (p && p.rows.length) {
        const maxW = W * 0.18
        const maxV = Math.max(...p.rows.map((r) => r.valor)) || 1
        for (const r of p.rows) {
          const y1 = this.y(r.hi), y2 = this.y(r.lo)
          if (y1 === null || y2 === null) continue
          const w = Math.max(1.5, (r.valor / maxV) * maxW)
          const mid = (r.lo + r.hi) / 2
          const isPoc = p.poc !== undefined && Math.abs(mid - p.poc) <= (r.hi - r.lo)
          const inVa = p.vah !== undefined && p.val !== undefined && mid >= p.val && mid <= p.vah
          ctx.fillStyle = isPoc ? (p.color || '#22d3ee') + 'cc' : inVa ? 'rgba(122,141,163,0.45)' : 'rgba(90,105,124,0.22)'
          ctx.fillRect(W - w, Math.min(y1, y2), w, Math.max(Math.abs(y2 - y1) - 1, 1))
        }
      }
      // rótulos (ondas de Elliott, pivôs)
      ctx.font = MONO; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
      for (const l of this.data.labels) {
        const x = this.x(l.time), y = this.y(l.price)
        if (x === null || y === null) continue
        const w = ctx.measureText(l.text).width + 6
        const yy = y - 12
        ctx.fillStyle = 'rgba(11,15,20,0.85)'
        ctx.fillRect(x - w / 2, yy - 8, w, 16)
        ctx.fillStyle = l.color
        ctx.fillText(l.text, x, yy)
      }
      ctx.restore()
    })
  }
}

interface Props {
  candles: Candle[]
  paths?: ChartPath[]
  labels?: ChartLabel[]
  levels?: ChartLevel[]
  rects?: ChartRect[]
  profile?: ChartProfile | null
  markers?: ChartMarker[]
  logScale?: boolean
  height?: number
}

function precisao(p: number): { precision: number; minMove: number } {
  if (p >= 1000) return { precision: 0, minMove: 1 }
  if (p >= 1) return { precision: 2, minMove: 0.01 }
  return { precision: 4, minMove: 0.0001 }
}

function ordenar<T extends { time: number }>(pts: T[]): T[] {
  const m = new Map<number, T>()
  for (const p of pts) if (Number.isFinite(p.time)) m.set(Math.floor(p.time), { ...p, time: Math.floor(p.time) })
  return [...m.values()].sort((a, b) => a.time - b.time)
}

export default function PriceChart({ candles, paths = [], labels = [], levels = [], rects = [], profile = null, markers = [], logScale = false, height = 430 }: Props) {
  const el = useRef<HTMLDivElement>(null)
  const chart = useRef<IChartApi | null>(null)
  const serie = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const overlay = useRef<Overlay | null>(null)
  const linhas = useRef<Map<string, ISeriesApi<'Line'>>>(new Map())
  const priceLines = useRef<IPriceLine[]>([])
  const nCandles = useRef(0)

  useEffect(() => {
    if (!el.current) return
    const c = createChart(el.current, {
      height,
      layout: { background: { type: ColorType.Solid, color: '#111820' }, textColor: '#8a98a8', fontFamily: "'IBM Plex Mono', monospace", fontSize: 10 },
      grid: { vertLines: { color: '#151e28' }, horzLines: { color: '#151e28' } },
      rightPriceScale: { borderColor: '#233040', scaleMargins: { top: 0.08, bottom: 0.08 } },
      timeScale: { borderColor: '#233040', timeVisible: true, secondsVisible: false, rightOffset: 6 },
      crosshair: { mode: CrosshairMode.Normal, vertLine: { color: '#35465a', labelBackgroundColor: '#233040' }, horzLine: { color: '#35465a', labelBackgroundColor: '#233040' } },
      handleScroll: true, handleScale: true,
    })
    const s = c.addCandlestickSeries({
      upColor: '#34d399', downColor: '#f87171', borderVisible: false, wickUpColor: '#34d399', wickDownColor: '#f87171',
      priceLineColor: '#e6edf3', priceLineStyle: LineStyle.Dotted,
    })
    const ov = new Overlay()
    s.attachPrimitive(ov)
    chart.current = c; serie.current = s; overlay.current = ov
    const ro = new ResizeObserver(() => { if (el.current) c.applyOptions({ width: el.current.clientWidth }) })
    ro.observe(el.current)
    c.applyOptions({ width: el.current.clientWidth })
    return () => { ro.disconnect(); c.remove(); chart.current = null; serie.current = null; overlay.current = null; linhas.current.clear(); priceLines.current = [] }
  }, [height])

  useEffect(() => {
    chart.current?.priceScale('right').applyOptions({ mode: logScale ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal })
  }, [logScale])

  useEffect(() => {
    const s = serie.current
    if (!s) return
    const dados = ordenar(candles)
    if (dados.length) s.applyOptions({ priceFormat: { type: 'price', ...precisao(dados[dados.length - 1].close) } })
    s.setData(dados.map((k) => ({ time: k.time as UTCTimestamp, open: k.open, high: k.high, low: k.low, close: k.close })))
    if (dados.length !== nCandles.current) { chart.current?.timeScale().fitContent(); nCandles.current = dados.length }
  }, [candles])

  useEffect(() => {
    const c = chart.current
    if (!c) return
    const vistos = new Set<string>()
    for (const p of paths) {
      vistos.add(p.id)
      let ls = linhas.current.get(p.id)
      if (!ls) {
        ls = c.addLineSeries({ priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
        linhas.current.set(p.id, ls)
      }
      ls.applyOptions({ color: p.color, lineWidth: (p.width || 1) as 1 | 2 | 3 | 4, lineStyle: p.dashed ? LineStyle.Dashed : LineStyle.Solid })
      ls.setData(ordenar(p.points).map((q) => ({ time: q.time as UTCTimestamp, value: q.value })))
    }
    for (const [id, ls] of [...linhas.current.entries()]) if (!vistos.has(id)) { c.removeSeries(ls); linhas.current.delete(id) }
  }, [paths])

  useEffect(() => {
    const s = serie.current
    if (!s) return
    for (const pl of priceLines.current) s.removePriceLine(pl)
    priceLines.current = levels.filter((l) => Number.isFinite(l.price)).map((l) => s.createPriceLine({
      price: l.price, color: l.color, lineWidth: 1, lineStyle: l.dashed ? LineStyle.Dashed : LineStyle.Solid, axisLabelVisible: true, title: l.label,
    }))
  }, [levels])

  useEffect(() => {
    const s = serie.current
    if (!s) return
    const ms: SeriesMarker<Time>[] = ordenar(markers).map((m) => ({
      time: m.time as UTCTimestamp,
      position: m.side === 'buy' ? 'belowBar' : 'aboveBar',
      color: m.side === 'buy' ? '#34d399' : m.side === 'sell' ? '#f87171' : m.side === 'exit' ? '#fbbf24' : '#8a98a8',
      shape: m.side === 'buy' ? 'arrowUp' : m.side === 'sell' ? 'arrowDown' : 'circle',
      text: m.text,
    }))
    s.setMarkers(ms)
  }, [markers])

  useEffect(() => {
    overlay.current?.set({ rects, profile, labels })
  }, [rects, profile, labels])

  return <div ref={el} style={{ width: '100%', height }} />
}
