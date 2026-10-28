/**
 * Gráfico da tela Gráfico, no jeito da TradingView: velas e volume de qualquer moeda e corretora, legenda O/H/L/C que
 * segue o cursor, histórico que carrega sozinho quando você arrasta para a esquerda e a vela aberta atualizando.
 *
 * Os dados ficam num ref (não no estado do React): trocar de moeda zera tudo, arrastar acrescenta velas antigas no
 * começo e o relógio só mexe na última vela (`update`), sem redesenhar o gráfico inteiro.
 */
import {
  ColorType, CrosshairMode, LineStyle, createChart,
  type IChartApi, type ISeriesApi, type LogicalRange, type MouseEventParams, type Time, type UTCTimestamp,
} from 'lightweight-charts'
import { useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../../api/client'
import type { NuvensOverlay, TpoComposto, TpoDia, TpoGrafico, VelasGrafico } from '../../api/types'
import { NuvensDesenho } from './nuvensDesenho'
import { TpoDesenho, type Selecao } from './tpoDesenho'

export type Vela = { t: number; o: number; h: number; l: number; c: number; v: number }

/** O que a tela de cima precisa saber do gráfico. */
export type InfoGrafico = { ultimo: Vela | null; anterior: Vela | null; nuvem: boolean; erro: string | null; carregando: boolean }

export const SEGUNDOS: Record<string, number> = { '1m': 60, '5m': 300, '15m': 900, '30m': 1800, '1h': 3600, '4h': 14400, '1d': 86400 }
const N_INICIAL = 800
const N_ANTIGAS = 600
const VELAS_NA_TELA = 160
const CARREGAR_QUANDO_FALTAM = 30
/** o ponteiro andou menos que isso entre apertar e soltar: é clique */
const ARRASTO_PX = 5
const N_MAX_API = 2000
const ALTA = '#26a69a', BAIXA = '#ef5350'

/** Casas decimais pelo tamanho do preço: BTC com 2, moedas de centavos com 4 a 6, memecoins com até 10. */
export function casas(preco: number): number {
  if (!Number.isFinite(preco) || preco <= 0) return 2
  if (preco >= 100) return 2
  if (preco >= 1) return 4
  return Math.min(10, Math.ceil(-Math.log10(preco)) + 4)
}

export function volumeCurto(v: number): string {
  const a = Math.abs(v)
  return a >= 1e9 ? `${(v / 1e9).toFixed(2)}B` : a >= 1e6 ? `${(v / 1e6).toFixed(2)}M` : a >= 1e3 ? `${(v / 1e3).toFixed(2)}K` : v.toFixed(a >= 10 ? 0 : 2)
}

const daApi = (r: number[]): Vela => ({ t: r[0], o: r[1], h: r[2], l: r[3], c: r[4], v: r[5] })
const vela = (k: Vela) => ({ time: k.t as UTCTimestamp, open: k.o, high: k.h, low: k.l, close: k.c })
const volume = (k: Vela) => ({ time: k.t as UTCTimestamp, value: k.v, color: k.c >= k.o ? 'rgba(38,166,154,0.45)' : 'rgba(239,83,80,0.45)' })
const buscar = (simbolo: string, tempo: string, n: number, ate?: number) =>
  api.get<VelasGrafico>('/api/grafico/velas', { simbolo, tempo, n, ate })

interface Props {
  simbolo: string
  tempo: string
  onInfo?: (i: InfoGrafico) => void
  /** a vela aberta é perguntada de tanto em tanto (ms) */
  vivoMs?: number
  /** TPO de 30 min por dia para desenhar no gráfico (null = desligado) */
  tpo?: TpoGrafico | null
  /** dias escolhidos para juntar e o composto deles (quando já chegou) */
  selecao?: Selecao | null
  composto?: TpoComposto | null
  /** nuvens do livro (Order Book Depth Overlay do TRDR), um ponto por vela; null = desligadas */
  nuvens?: NuvensOverlay | null
  /** clique em cima do perfil de um dia (com Shift ou não) */
  onDia?: (dia: TpoDia, shift: boolean) => void
}

/** Índice de vela (fracionário) do instante t: entre duas velas interpola; antes ou depois dos dados, extrapola pelo
 *  tamanho da vela. É o que deixa o TPO de um dia desenhar mesmo começando fora do que foi carregado. */
function indiceDe(d: Vela[], t: number, passo: number): number | null {
  if (!d.length) return null
  if (t <= d[0].t) return (t - d[0].t) / passo
  const n = d.length - 1
  if (t >= d[n].t) return n + (t - d[n].t) / passo
  let a = 0, b = n
  while (b - a > 1) { const m = (a + b) >> 1; if (d[m].t <= t) a = m; else b = m }
  return a + (t - d[a].t) / (d[b].t - d[a].t)
}

export default function GraficoTV({ simbolo, tempo, onInfo, vivoMs = 4000, tpo = null, selecao = null, composto = null, nuvens = null, onDia }: Props) {
  const el = useRef<HTMLDivElement>(null)
  const chart = useRef<IChartApi | null>(null)
  const velas = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const vols = useRef<ISeriesApi<'Histogram'> | null>(null)
  const dados = useRef<Vela[]>([])
  const desenhoTpo = useRef<TpoDesenho | null>(null)
  const desenhoNuvens = useRef<NuvensDesenho | null>(null)
  const passoAtual = useRef(SEGUNDOS[tempo] ?? 60)
  passoAtual.current = SEGUNDOS[tempo] ?? 60
  const estado = useRef({ geracao: 0, buscandoAntigas: false, fimDoHistorico: false, nuvem: false })
  const avisar = useRef(onInfo)
  avisar.current = onInfo
  const aoEscolherDia = useRef(onDia)
  aoEscolherDia.current = onDia
  const [legenda, setLegenda] = useState<Vela | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(true)

  const info = (extra: Partial<InfoGrafico> = {}) => {
    const d = dados.current
    avisar.current?.({ ultimo: d[d.length - 1] ?? null, anterior: d[d.length - 2] ?? null, nuvem: estado.current.nuvem,
      erro: null, carregando: false, ...extra })
  }

  // o gráfico é criado uma vez; tamanho segue a caixa
  useEffect(() => {
    if (!el.current) return
    const c = createChart(el.current, {
      layout: { background: { type: ColorType.Solid, color: 'rgba(0,0,0,0)' }, textColor: '#8b95a5', fontFamily: "'DM Mono', monospace", fontSize: 11, attributionLogo: false },
      grid: { vertLines: { color: 'rgba(255,255,255,0.035)' }, horzLines: { color: 'rgba(255,255,255,0.045)' } },
      rightPriceScale: { borderColor: 'rgba(255,255,255,0.08)', scaleMargins: { top: 0.06, bottom: 0.22 } },
      timeScale: { borderColor: 'rgba(255,255,255,0.08)', timeVisible: true, secondsVisible: false, rightOffset: 8 },
      crosshair: { mode: CrosshairMode.Normal, vertLine: { color: 'rgba(232,236,242,0.3)', labelBackgroundColor: '#2a2e39' }, horzLine: { color: 'rgba(232,236,242,0.3)', labelBackgroundColor: '#2a2e39' } },
      localization: { locale: 'pt-BR' },
    })
    const s = c.addCandlestickSeries({ upColor: ALTA, downColor: BAIXA, borderVisible: false, wickUpColor: ALTA, wickDownColor: BAIXA, priceLineStyle: LineStyle.Dotted })
    const v = c.addHistogramSeries({ priceScaleId: 'vol', priceFormat: { type: 'volume' }, lastValueVisible: false, priceLineVisible: false })
    c.priceScale('vol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
    const formatar = (p: number) => { const u = dados.current[dados.current.length - 1]; const k = casas(u ? u.c : p); return p.toLocaleString('pt-BR', { minimumFractionDigits: k, maximumFractionDigits: k }) }
    const logico = (t: number) => indiceDe(dados.current, t, passoAtual.current)
    const nuvensDesenho = new NuvensDesenho(logico)
    s.attachPrimitive(nuvensDesenho)                     // antes do TPO: fica atrás dele
    desenhoNuvens.current = nuvensDesenho
    const tpoDesenho = new TpoDesenho(logico, formatar)
    s.attachPrimitive(tpoDesenho)
    desenhoTpo.current = tpoDesenho
    chart.current = c; velas.current = s; vols.current = v

    const aoMover = (p: MouseEventParams<Time>) => {
      const k = p.seriesData.get(s) as { open: number; high: number; low: number; close: number } | undefined
      if (!p.time || !k) { setLegenda(null); return }
      const t = p.time as number
      const achada = dados.current.find((d) => d.t === t)
      setLegenda({ t, o: k.open, h: k.high, l: k.low, c: k.close, v: achada?.v ?? 0 })
    }
    c.subscribeCrosshairMove(aoMover)
    // clique pelo ponteiro, não pelo subscribeClick: a biblioteca descarta o 2º clique se vier em menos de 0,5 s
    // (vira duplo clique), e juntar dois dias é justamente clicar num e logo no outro
    const caixa = el.current
    let apertou: { x: number; y: number } | null = null
    const aoApertar = (e: PointerEvent) => { apertou = e.button === 0 ? { x: e.clientX, y: e.clientY } : null }
    const aoSoltar = (e: PointerEvent) => {
      const a = apertou
      apertou = null
      if (!a || Math.hypot(e.clientX - a.x, e.clientY - a.y) > ARRASTO_PX) return     // foi arrasto, não clique
      const x = e.clientX - caixa.getBoundingClientRect().left
      if (x > c.timeScale().width()) return                                            // em cima da escala de preço
      const dia = tpoDesenho.diaEm(x)
      if (dia) aoEscolherDia.current?.(dia, e.shiftKey)
    }
    caixa.addEventListener('pointerdown', aoApertar)
    caixa.addEventListener('pointerup', aoSoltar)
    const ro = new ResizeObserver(() => { if (el.current) c.applyOptions({ width: el.current.clientWidth, height: el.current.clientHeight }) })
    ro.observe(el.current)
    return () => { ro.disconnect(); c.unsubscribeCrosshairMove(aoMover); caixa.removeEventListener('pointerdown', aoApertar); caixa.removeEventListener('pointerup', aoSoltar); c.remove(); chart.current = null; velas.current = null; vols.current = null }
  }, [])

  // trocar de moeda ou de tempo: zera e busca de novo
  useEffect(() => {
    const c = chart.current, s = velas.current, v = vols.current
    if (!c || !s || !v) return
    const geracao = ++estado.current.geracao
    estado.current.buscandoAntigas = false
    estado.current.fimDoHistorico = false
    dados.current = []
    s.setData([]); v.setData([])
    s.priceScale().applyOptions({ autoScale: true })      // arrastar a escala desliga; moeda nova começa ajustada
    setErro(null); setCarregando(true); setLegenda(null)
    avisar.current?.({ ultimo: null, anterior: null, nuvem: false, erro: null, carregando: true })

    buscar(simbolo, tempo, N_INICIAL).then((r) => {
      if (geracao !== estado.current.geracao) return
      const d = r.velas.map(daApi)
      dados.current = d
      estado.current.nuvem = r.nuvem
      const ultimo = d[d.length - 1]
      if (ultimo) {
        const dec = casas(ultimo.c)
        s.applyOptions({ priceFormat: { type: 'price', precision: dec, minMove: 10 ** -dec } })
      }
      s.setData(d.map(vela)); v.setData(d.map(volume))
      c.timeScale().setVisibleLogicalRange({ from: d.length - VELAS_NA_TELA, to: d.length + 8 })
      setCarregando(false)
      info()
    }).catch((e) => {
      if (geracao !== estado.current.geracao) return
      const msg = e instanceof ApiError && e.status === 404 ? `${simbolo} não existe nessa corretora` : `não deu para buscar ${simbolo}: ${e.message ?? e}`
      setErro(msg); setCarregando(false)
      avisar.current?.({ ultimo: null, anterior: null, nuvem: false, erro: msg, carregando: false })
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [simbolo, tempo])

  // arrastar para a esquerda até perto do começo: busca as velas anteriores e mantém a vista no mesmo lugar
  useEffect(() => {
    const c = chart.current
    if (!c) return
    const aoRolar = (r: LogicalRange | null) => {
      const st = estado.current
      if (!r || r.from > CARREGAR_QUANDO_FALTAM || st.buscandoAntigas || st.fimDoHistorico || !dados.current.length) return
      st.buscandoAntigas = true
      const geracao = st.geracao
      const primeira = dados.current[0].t
      buscar(simbolo, tempo, N_ANTIGAS, primeira - SEGUNDOS[tempo]).then((resp) => {
        if (geracao !== st.geracao) return
        const antigas = resp.velas.map(daApi).filter((k) => k.t < primeira)
        if (!antigas.length) { st.fimDoHistorico = true; return }
        const vista = c.timeScale().getVisibleLogicalRange()
        dados.current = [...antigas, ...dados.current]
        velas.current?.setData(dados.current.map(vela)); vols.current?.setData(dados.current.map(volume))
        if (vista) c.timeScale().setVisibleLogicalRange({ from: vista.from + antigas.length, to: vista.to + antigas.length })
      }).catch(() => { /* tenta de novo no próximo arrasto */ }).finally(() => {
        if (geracao === st.geracao) st.buscandoAntigas = false
      })
    }
    c.timeScale().subscribeVisibleLogicalRangeChange(aoRolar)
    return () => c.timeScale().unsubscribeVisibleLogicalRangeChange(aoRolar)
  }, [simbolo, tempo])

  useEffect(() => { desenhoTpo.current?.set(tpo) }, [tpo])
  useEffect(() => { desenhoNuvens.current?.set(nuvens) }, [nuvens])
  useEffect(() => { desenhoTpo.current?.setJuncao(selecao, composto) }, [selecao, composto])

  // vela aberta: pergunta as 2 últimas e atualiza (ou acrescenta quando abre uma nova)
  useEffect(() => {
    const id = setInterval(() => {
      const geracao = estado.current.geracao
      if (!dados.current.length || document.hidden) return
      const passo = SEGUNDOS[tempo]
      const ultima = dados.current[dados.current.length - 1].t
      // aba escondida, PC dormindo ou rede fora: pede todas as velas desde a última conhecida, senão o vão some
      const faltam = Math.min(N_MAX_API, Math.ceil((Date.now() / 1000 - ultima) / passo) + 1)
      buscar(simbolo, tempo, Math.max(2, faltam)).then((r) => {
        if (geracao !== estado.current.geracao) return
        for (const k of r.velas.map(daApi)) {
          const d = dados.current, ult = d[d.length - 1]
          if (!ult || k.t < ult.t) continue
          if (k.t === ult.t) d[d.length - 1] = k
          else d.push(k)
          velas.current?.update(vela(k)); vols.current?.update(volume(k))
        }
        info()
      }).catch(() => { /* a próxima volta tenta de novo */ })
    }, vivoMs)
    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [simbolo, tempo, vivoMs])

  const mostrada = legenda ?? dados.current[dados.current.length - 1] ?? null
  const dec = mostrada ? casas(mostrada.c) : 2
  const cor = mostrada && mostrada.c >= mostrada.o ? ALTA : BAIXA
  return (
    <div className="gtv">
      <div ref={el} className="gtv-canvas" />
      {mostrada && (
        <div className="gtv-legenda mono">
          {(['o', 'h', 'l', 'c'] as const).map((k) => (
            <span key={k}><span className="muted">{k.toUpperCase()}</span> <span style={{ color: cor }}>{mostrada[k].toLocaleString('pt-BR', { minimumFractionDigits: dec, maximumFractionDigits: dec })}</span></span>
          ))}
          <span style={{ color: cor }}>{mostrada.o ? `${mostrada.c >= mostrada.o ? '+' : ''}${((mostrada.c / mostrada.o - 1) * 100).toFixed(2)}%` : ''}</span>
          <span><span className="muted">Vol</span> {volumeCurto(mostrada.v)}</span>
        </div>
      )}
      {carregando && <div className="gtv-aviso">carregando {simbolo}…</div>}
      {erro && <div className="gtv-aviso err">{erro}</div>}
    </div>
  )
}
