/**
 * Painel embaixo do gráfico de preço (como os do TRDR: livro, liquidações, funding), com o mesmo eixo de tempo.
 *
 * O Lightweight Charts espaça as barras por posição, não por horário: por isso cada série chega com UM ponto por vela
 * do gráfico de cima (`tempos`), e o painel segue o arrasto e o zoom de lá pelo intervalo lógico (`range`).
 */
import { ColorType, CrosshairMode, createChart, type IChartApi, type ISeriesApi, type LogicalRange, type UTCTimestamp } from 'lightweight-charts'
import { useEffect, useRef } from 'react'
import { LARGURA_ESCALA } from './PriceChart'

export interface SerieSub {
  id: string
  tipo: 'barra' | 'linha'
  cor: string
  /** um valor por tempo de `tempos` (null = sem dado naquela vela) */
  valores: (number | null)[]
  /** cor por barra (opcional) */
  cores?: (string | null)[]
  /** espessura da linha (só para `linha`) */
  largura?: number
}

interface Props {
  titulo: string
  /** uma linha explicando as cores, embaixo do título */
  explica?: string
  /** a leitura de agora, num selo colorido ao lado do título */
  leitura?: { texto: string; cor: string }
  tempos: number[]
  series: SerieSub[]
  range: LogicalRange | null
  formato?: (v: number) => string
  height?: number
}

export default function SubChart({ titulo, explica, leitura, tempos, series, range, formato, height = 90 }: Props) {
  const el = useRef<HTMLDivElement>(null)
  const chart = useRef<IChartApi | null>(null)
  const ss = useRef<Map<string, ISeriesApi<'Histogram'> | ISeriesApi<'Line'>>>(new Map())

  useEffect(() => {
    if (!el.current) return
    const c = createChart(el.current, {
      height,
      layout: { background: { type: ColorType.Solid, color: 'rgba(0,0,0,0)' }, textColor: '#4d5766', fontFamily: "'DM Mono', monospace", fontSize: 10, attributionLogo: false },
      grid: { vertLines: { color: 'rgba(255,255,255,0.03)' }, horzLines: { color: 'rgba(255,255,255,0.04)' } },
      rightPriceScale: { borderColor: 'rgba(255,255,255,0.06)', scaleMargins: { top: 0.12, bottom: 0.08 }, minimumWidth: LARGURA_ESCALA },
      timeScale: { borderColor: 'rgba(255,255,255,0.06)', timeVisible: true, secondsVisible: false, rightOffset: 6, visible: false },
      crosshair: { mode: CrosshairMode.Normal, vertLine: { color: 'rgba(232,236,242,0.2)', labelVisible: false }, horzLine: { color: 'rgba(232,236,242,0.2)', labelBackgroundColor: '#1a2130' } },
      handleScroll: false, handleScale: false,
      localization: formato ? { priceFormatter: formato } : undefined,
    })
    chart.current = c
    const ro = new ResizeObserver(() => { if (el.current) c.applyOptions({ width: el.current.clientWidth }) })
    ro.observe(el.current)
    c.applyOptions({ width: el.current.clientWidth })
    return () => { ro.disconnect(); c.remove(); chart.current = null; ss.current.clear() }
  }, [height, formato])

  useEffect(() => {
    const c = chart.current
    if (!c) return
    const vistos = new Set<string>()
    for (const s of series) {
      vistos.add(s.id)
      let serie = ss.current.get(s.id)
      if (!serie) {
        serie = s.tipo === 'barra'
          ? c.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false, base: 0 })
          : c.addLineSeries({ priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false })
        ss.current.set(s.id, serie)
      }
      serie.applyOptions(s.tipo === 'linha' ? { color: s.cor, lineWidth: (s.largura ?? 2) as 1 | 2 | 3 | 4 } : { color: s.cor })
      // um ponto por vela; sem dado vira "espaço em branco", que mantém o alinhamento com o gráfico de cima
      serie.setData(tempos.map((t, i) => {
        const v = s.valores[i]
        if (v === null || v === undefined || !Number.isFinite(v)) return { time: t as UTCTimestamp }
        const cor = s.cores?.[i]
        return cor ? { time: t as UTCTimestamp, value: v, color: cor } : { time: t as UTCTimestamp, value: v }
      }))
    }
    for (const [id, serie] of [...ss.current.entries()]) if (!vistos.has(id)) { c.removeSeries(serie); ss.current.delete(id) }
  }, [series, tempos])

  useEffect(() => {
    if (chart.current && range) chart.current.timeScale().setVisibleLogicalRange(range)
  }, [range, series, tempos])

  return (
    <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 10, marginTop: 6 }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', fontSize: 12 }}>
        <b style={{ color: '#e8ecf2', fontWeight: 600 }}>{titulo}</b>
        {leitura && <span style={{ color: leitura.cor, border: `1px solid ${leitura.cor}`, borderRadius: 999, padding: '1px 9px', fontSize: 11 }}>{leitura.texto}</span>}
      </div>
      {explica && <div className="muted" style={{ fontSize: 11, marginTop: 3 }}>{explica}</div>}
      <div ref={el} style={{ width: '100%', height }} />
    </div>
  )
}
