/**
 * Gráfico da tela Gráfico, no jeito da TradingView: velas e volume de qualquer moeda e corretora, legenda O/H/L/C que
 * segue o cursor, histórico que carrega sozinho quando você arrasta para a esquerda e a vela aberta atualizando.
 *
 * Os dados ficam num ref (não no estado do React): trocar de moeda zera tudo, arrastar acrescenta velas antigas no
 * começo e o relógio só mexe na última vela (`update`), sem redesenhar o gráfico inteiro.
 */
import {
  ColorType, CrosshairMode, LineStyle, createChart,
  type IChartApi, type IPriceLine, type ISeriesApi, type Logical, type LogicalRange, type MouseEventParams, type Time, type UTCTimestamp,
} from 'lightweight-charts'
import { useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../../api/client'
import type { NuvensOverlay, TpoComposto, TpoDia, TpoGrafico, VelasGrafico } from '../../api/types'
import type { ChartLevel, ChartMarker } from '../../lib/chart-tipos'
import { copiar } from '../../lib/fibo'
import { modeloDe, novoId, VIS_PADRAO, type Desenho } from '../../lib/desenhos'
import { CamadasDesenho, type Camadas } from './camadasDesenho'
import { DesenhosPrimitiva, type ParteDesenho } from './desenhosPrimitiva'
import { FERRAMENTA } from './ferramentas'
import { NuvensDesenho } from './nuvensDesenho'
import { LARGURA_ESCALA } from './SubChart'
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
/** dois cliques no mesmo desenho em menos que isso: abre a configuração */
const DUPLO_MS = 400
/** ímã fraco: só gruda quando o ponteiro está a menos que isso (px) da abertura, máxima, mínima ou fechamento */
const IMA_FRACO_PX = 14

export type Ima = 'nao' | 'fraco' | 'forte'
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
const fechamento = (k: Vela) => ({ time: k.t as UTCTimestamp, value: k.c })
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
  /** as velas carregadas, em ordem: os painéis de baixo põem um valor por vela e os presos procuram a saída */
  onVelas?: (velas: Vela[]) => void
  /** camadas de order flow: mapa de calor atrás das velas, contornos, faixas e rótulos na frente */
  camadas?: Camadas | null
  /** setas em cima/embaixo das velas (presos) */
  marcadores?: ChartMarker[]
  /** linhas horizontais com rótulo na escala (maiores níveis do livro) */
  niveis?: ChartLevel[]
  /** arrasto e zoom: os painéis de baixo seguem o mesmo intervalo */
  onRange?: (r: LogicalRange | null) => void
  /** desenhos à mão (as ferramentas da TradingView, components/chart/ferramentas.ts) */
  desenhos?: Desenho[]
  /** um desenho novo, arrastado ou apagado: a lista inteira como ficou */
  onDesenhos?: (l: Desenho[]) => void
  desenhoSel?: string | null
  onDesenhoSel?: (id: string | null) => void
  /** duplo clique num desenho: abre a configuração dele */
  onDesenhoConfig?: (id: string) => void
  /** ferramenta ligada (o tipo): o próximo clique marca o ponto 1 e o seguinte (ou soltar depois de arrastar) o 2 */
  ferramenta?: string | null
  /** acabou de desenhar: a tela decide se a ferramenta continua ligada ("ficar no modo desenho") */
  onFerramentaPronta?: () => void
  /** ímã: o ponto gruda na abertura, máxima, mínima ou fechamento da vela (fraco = só quando perto) */
  ima?: Ima
  /** travar todos: dá para selecionar, mas não arrastar */
  travarTodos?: boolean
  /** esconder todos os desenhos */
  ocultarTodos?: boolean
  /** preço como linha do fechamento, como no aggr.trade (as velas ficam escondidas, o resto segue igual) */
  emLinha?: boolean
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

export default function GraficoTV({ simbolo, tempo, onInfo, vivoMs = 4000, tpo = null, selecao = null, composto = null, nuvens = null, onDia, onVelas, onRange, camadas = null, marcadores, niveis,
  desenhos, onDesenhos, desenhoSel = null, onDesenhoSel, onDesenhoConfig, ferramenta = null, onFerramentaPronta, ima = 'nao',
  travarTodos = false, ocultarTodos = false, emLinha = false }: Props) {
  const el = useRef<HTMLDivElement>(null)
  const chart = useRef<IChartApi | null>(null)
  const velas = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const vols = useRef<ISeriesApi<'Histogram'> | null>(null)
  const linhaPreco = useRef<ISeriesApi<'Line'> | null>(null)
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
  const avisarVelas = useRef(onVelas)
  avisarVelas.current = onVelas
  const avisarRange = useRef(onRange)
  avisarRange.current = onRange
  // os ouvintes do mouse são criados uma vez: leem os desenhos de agora por aqui
  const des = useRef({ lista: desenhos ?? [], sel: desenhoSel, ferramenta, ima, travarTodos, onDesenhos, onDesenhoSel, onDesenhoConfig, onFerramentaPronta })
  des.current = { lista: desenhos ?? [], sel: desenhoSel, ferramenta, ima, travarTodos, onDesenhos, onDesenhoSel, onDesenhoConfig, onFerramentaPronta }
  const primDesenhos = useRef<DesenhosPrimitiva | null>(null)
  const cancelarDesenho = useRef<() => void>(() => {})
  const marcas = useRef<ChartMarker[]>([])
  const linhas = useRef<IPriceLine[]>([])
  const desenhoCamadas = useRef<CamadasDesenho | null>(null)
  /** setas só em velas que existem no gráfico (a biblioteca exige o tempo exato de uma vela) */
  const aplicarMarcas = () => {
    const s = velas.current
    if (!s) return
    const existe = new Set(dados.current.map((k) => k.t))
    s.setMarkers(marcas.current.filter((m) => existe.has(m.time)).sort((a, b) => a.time - b.time).map((m) => ({
      time: m.time as UTCTimestamp, position: m.side === 'sell' ? 'aboveBar' as const : 'belowBar' as const,
      color: m.color ?? '#f5c04a', shape: m.side === 'sell' ? 'arrowDown' as const : 'arrowUp' as const, text: m.text,
    })))
  }
  const tempos = () => { avisarVelas.current?.([...dados.current]); aplicarMarcas() }
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
      // a mesma largura de escala dos painéis de baixo, para as velas ficarem uma em cima da outra
      rightPriceScale: { borderColor: 'rgba(255,255,255,0.08)', scaleMargins: { top: 0.06, bottom: 0.22 }, minimumWidth: LARGURA_ESCALA },
      timeScale: { borderColor: 'rgba(255,255,255,0.08)', timeVisible: true, secondsVisible: false, rightOffset: 8 },
      crosshair: { mode: CrosshairMode.Normal, vertLine: { color: 'rgba(232,236,242,0.3)', labelBackgroundColor: '#2a2e39' }, horzLine: { color: 'rgba(232,236,242,0.3)', labelBackgroundColor: '#2a2e39' } },
      localization: { locale: 'pt-BR' },
    })
    const s = c.addCandlestickSeries({ upColor: ALTA, downColor: BAIXA, borderVisible: false, wickUpColor: ALTA, wickDownColor: BAIXA, priceLineStyle: LineStyle.Dotted })
    const v = c.addHistogramSeries({ priceScaleId: 'vol', priceFormat: { type: 'volume' }, lastValueVisible: false, priceLineVisible: false })
    linhaPreco.current = c.addLineSeries({ color: '#e8b4c4', lineWidth: 1, priceLineStyle: LineStyle.Dotted, crosshairMarkerVisible: false, visible: false })
    c.priceScale('vol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
    const formatar = (p: number) => { const u = dados.current[dados.current.length - 1]; const k = casas(u ? u.c : p); return p.toLocaleString('pt-BR', { minimumFractionDigits: k, maximumFractionDigits: k }) }
    const logico = (t: number) => indiceDe(dados.current, t, passoAtual.current)
    const nuvensDesenho = new NuvensDesenho(logico)
    s.attachPrimitive(nuvensDesenho)                     // antes do TPO: fica atrás dele
    desenhoNuvens.current = nuvensDesenho
    const camadasDesenho = new CamadasDesenho(logico)
    s.attachPrimitive(camadasDesenho)
    desenhoCamadas.current = camadasDesenho
    const tpoDesenho = new TpoDesenho(logico, formatar)
    s.attachPrimitive(tpoDesenho)
    desenhoTpo.current = tpoDesenho
    const prim = new DesenhosPrimitiva(logico, formatar, () => passoAtual.current)
    s.attachPrimitive(prim)
    primDesenhos.current = prim
    if (import.meta.env.DEV) (window as unknown as { __desenhos: DesenhosPrimitiva }).__desenhos = prim   // para testar no navegador
    chart.current = c; velas.current = s; vols.current = v

    const aoMover = (p: MouseEventParams<Time>) => {
      const k = p.seriesData.get(s) as { open: number; high: number; low: number; close: number } | undefined
      if (!p.time || !k) { setLegenda(null); return }
      const t = p.time as number
      const achada = dados.current.find((d) => d.t === t)
      setLegenda({ t, o: k.open, h: k.high, l: k.low, c: k.close, v: achada?.v ?? 0 })
    }
    c.subscribeCrosshairMove(aoMover)
    const aoMudarVista = (r: LogicalRange | null) => avisarRange.current?.(r)
    c.timeScale().subscribeVisibleLogicalRangeChange(aoMudarVista)
    // clique pelo ponteiro, não pelo subscribeClick: a biblioteca descarta o 2º clique se vier em menos de 0,5 s
    // (vira duplo clique), e juntar dois dias é justamente clicar num e logo no outro
    const caixa = el.current
    // o ouvinte de captura dos desenhos roda antes: quando o clique é deles, o gráfico não arrasta e o TPO não escolhe dia
    let consumido = false
    let apertou: { x: number; y: number } | null = null
    const aoApertar = (e: PointerEvent) => { apertou = e.button === 0 && !consumido ? { x: e.clientX, y: e.clientY } : null }
    const aoSoltar = (e: PointerEvent) => {
      const a = apertou
      apertou = null
      if (consumido) { consumido = false; return }
      if (!a || Math.hypot(e.clientX - a.x, e.clientY - a.y) > ARRASTO_PX) return     // foi arrasto, não clique
      const x = e.clientX - caixa.getBoundingClientRect().left
      if (x > c.timeScale().width()) return                                            // em cima da escala de preço
      const dia = tpoDesenho.diaEm(x)
      if (dia) aoEscolherDia.current?.(dia, e.shiftKey)
    }

    // ---------------------------------------------------------------- desenhos com o mouse
    let criando: { fase: 1 | 2; x: number; y: number; d: Desenho } | null = null
    let arrasto: { id: string; parte: ParteDesenho; t0: number; p0: number; orig: Desenho; mexeu: boolean } | null = null
    let ultimoClique = { id: '', em: 0 }
    const travar = (sim: boolean) => c.applyOptions({ handleScroll: !sim, handleScale: !sim })
    /** instante da vela na coluna x (fora dos dados, conta pelo tamanho da vela) */
    const tempoDoX = (x: number): number | null => {
      const d = dados.current
      const x0 = c.timeScale().logicalToCoordinate(0 as Logical)
      if (!d.length || x0 === null) return null
      const i = Math.round((x - x0) / c.timeScale().options().barSpacing)
      if (i < 0) return d[0].t + i * passoAtual.current
      if (i >= d.length) return d[d.length - 1].t + (i - d.length + 1) * passoAtual.current
      return d[i].t
    }
    const ponto = (e: PointerEvent, comIma: boolean) => {
      const r = caixa.getBoundingClientRect()
      const x = e.clientX - r.left, y = e.clientY - r.top
      const t = tempoDoX(x), p = s.coordinateToPrice(y)
      if (t === null || p === null) return null
      const modo = des.current.ima
      const k = comIma && modo !== 'nao' ? dados.current.find((d) => d.t === t) : undefined
      if (!k) return { t, p: p as number }
      const dist = (v: number) => Math.abs((s.priceToCoordinate(v) ?? 1e9) - y)
      const perto = [k.o, k.h, k.l, k.c].reduce((a, b) => (dist(b) < dist(a) ? b : a))
      return modo === 'forte' || dist(perto) <= IMA_FRACO_PX ? { t, p: perto } : { t, p: p as number }
    }
    const terminar = () => {
      const d = criando?.d
      criando = null
      prim.setRascunho(null)
      travar(false)
      const D = des.current
      D.onFerramentaPronta?.()
      if (!d) return
      const [a, b] = d.pts
      if (b && a.t === b.t && a.p === b.p) return                                          // nem saiu do lugar
      D.onDesenhos?.([...D.lista, d])
      D.onDesenhoSel?.(d.id)
    }
    cancelarDesenho.current = () => { if (criando) { criando = null; prim.setRascunho(null); travar(false) } }
    const aoApertarDesenho = (e: PointerEvent) => {
      if (e.button !== 0) return
      const r = caixa.getBoundingClientRect()
      const x = e.clientX - r.left, y = e.clientY - r.top
      if (x > c.timeScale().width()) return                                            // escala de preço
      const D = des.current
      const f = D.ferramenta ? FERRAMENTA[D.ferramenta] : null
      if (f || criando) {
        const pt = ponto(e, true)
        if (!pt) return
        consumido = true; travar(true)
        if (!criando && f) {
          const d: Desenho = { id: novoId(), tipo: f.tipo, pts: Array.from({ length: f.pontos }, () => ({ ...pt })), cfg: modeloDe(f.tipo, f.padrao()), vis: copiar(VIS_PADRAO) }
          criando = { fase: 1, x: e.clientX, y: e.clientY, d }
          if (f.pontos === 1) { terminar(); return }                                    // um clique só (linha horizontal)
          prim.setRascunho(d)
        } else if (criando) {
          const pts = [...criando.d.pts]; pts[pts.length - 1] = pt
          criando.d = { ...criando.d, pts }; terminar()
        }
        return
      }
      const acerto = prim.acertar(x, y)
      if (!acerto) { if (D.sel) D.onDesenhoSel?.(null); return }
      consumido = true; travar(true)
      const agora = Date.now()
      if (ultimoClique.id === acerto.id && agora - ultimoClique.em < DUPLO_MS) { ultimoClique = { id: '', em: 0 }; D.onDesenhoConfig?.(acerto.id) }
      else ultimoClique = { id: acerto.id, em: agora }
      if (D.sel !== acerto.id) D.onDesenhoSel?.(acerto.id)
      const orig = D.lista.find((d) => d.id === acerto.id)
      if (!orig || orig.travado || D.travarTodos) return                                // travado: seleciona, não arrasta
      const pt = ponto(e, acerto.parte !== 'corpo')
      if (pt) arrasto = { ...acerto, t0: pt.t, p0: pt.p, orig, mexeu: false }
    }
    const aoMoverDesenho = (e: PointerEvent) => {
      if (criando) {
        const pt = ponto(e, true)
        if (pt) { const pts = [...criando.d.pts]; pts[pts.length - 1] = pt; criando.d = { ...criando.d, pts }; prim.setRascunho(criando.d) }
        return
      }
      if (arrasto) {
        const a = arrasto, o = a.orig
        const pt = ponto(e, a.parte !== 'corpo')
        if (!pt) return
        a.mexeu = true
        const pts = typeof a.parte === 'number' ? o.pts.map((p, i) => (i === a.parte ? pt : p))
          : o.pts.map((p) => ({ t: p.t + pt.t - a.t0, p: p.p + pt.p - a.p0 }))
        const novo = { ...o, pts }
        prim.set(prim.todos().map((d) => (d.id === novo.id ? novo : d)), a.id)
        return
      }
      if (!(e.target instanceof Node) || !caixa.contains(e.target)) return
      const r = caixa.getBoundingClientRect()
      const D = des.current
      const acerto = D.ferramenta ? null : prim.acertar(e.clientX - r.left, e.clientY - r.top)
      const travado = acerto && (D.travarTodos || D.lista.find((d) => d.id === acerto.id)?.travado)
      caixa.style.cursor = D.ferramenta ? 'crosshair' : acerto ? (travado ? 'pointer' : acerto.parte === 'corpo' ? 'move' : 'pointer') : ''
    }
    const aoSoltarDesenho = (e: PointerEvent) => {
      if (criando) {
        if (criando.fase === 1) {
          if (Math.hypot(e.clientX - criando.x, e.clientY - criando.y) > ARRASTO_PX) terminar()   // arrastou: o 2º ponto é aqui
          else { criando.fase = 2; travar(false) }                                                // clicou: espera o 2º clique
        }
        return
      }
      if (!arrasto) return
      const a = arrasto
      arrasto = null
      travar(false)
      if (a.mexeu) des.current.onDesenhos?.(prim.todos())
    }
    const segurar = (e: Event) => { if (consumido) e.stopPropagation() }
    caixa.addEventListener('pointerdown', aoApertarDesenho, true)
    caixa.addEventListener('mousedown', segurar, true)
    caixa.addEventListener('touchstart', segurar, true)
    window.addEventListener('pointermove', aoMoverDesenho)
    window.addEventListener('pointerup', aoSoltarDesenho)
    caixa.addEventListener('pointerdown', aoApertar)
    caixa.addEventListener('pointerup', aoSoltar)
    const ro = new ResizeObserver(() => { if (el.current) c.applyOptions({ width: el.current.clientWidth, height: el.current.clientHeight }) })
    ro.observe(el.current)
    return () => {
      ro.disconnect(); c.unsubscribeCrosshairMove(aoMover); caixa.removeEventListener('pointerdown', aoApertar); caixa.removeEventListener('pointerup', aoSoltar)
      caixa.removeEventListener('pointerdown', aoApertarDesenho, true); caixa.removeEventListener('mousedown', segurar, true); caixa.removeEventListener('touchstart', segurar, true)
      window.removeEventListener('pointermove', aoMoverDesenho); window.removeEventListener('pointerup', aoSoltarDesenho)
      c.remove(); chart.current = null; velas.current = null; vols.current = null; linhas.current = []; desenhoCamadas.current = null; primDesenhos.current = null
    }
  }, [])

  // trocar de moeda ou de tempo: zera e busca de novo
  useEffect(() => {
    velas.current?.applyOptions({ visible: !emLinha })
    linhaPreco.current?.applyOptions({ visible: emLinha })
  }, [emLinha])

  useEffect(() => {
    const c = chart.current, s = velas.current, v = vols.current
    if (!c || !s || !v) return
    const geracao = ++estado.current.geracao
    estado.current.buscandoAntigas = false
    estado.current.fimDoHistorico = false
    dados.current = []
    s.setData([]); v.setData([]); linhaPreco.current?.setData([])
    tempos()
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
        linhaPreco.current?.applyOptions({ priceFormat: { type: 'price', precision: dec, minMove: 10 ** -dec } })
      }
      s.setData(d.map(vela)); v.setData(d.map(volume)); linhaPreco.current?.setData(d.map(fechamento))
      tempos()
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
        linhaPreco.current?.setData(dados.current.map(fechamento))
        tempos()
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
  useEffect(() => { desenhoCamadas.current?.set(camadas ?? { heatmap: null, rects: [], labels: [] }) }, [camadas])
  useEffect(() => { marcas.current = marcadores ?? []; aplicarMarcas() }, [marcadores])   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const s = velas.current
    if (!s) return
    for (const l of linhas.current) s.removePriceLine(l)
    linhas.current = (niveis ?? []).map((n) => s.createPriceLine({ price: n.price, color: n.color, lineWidth: 1,
      lineStyle: n.dashed ? LineStyle.Dashed : LineStyle.Solid, axisLabelVisible: true, title: n.label }))
  }, [niveis])
  useEffect(() => { desenhoTpo.current?.setJuncao(selecao, composto) }, [selecao, composto])
  useEffect(() => { primDesenhos.current?.set(desenhos ?? [], desenhoSel) }, [desenhos, desenhoSel])
  useEffect(() => { primDesenhos.current?.setTempo(tempo) }, [tempo])
  useEffect(() => { primDesenhos.current?.setEscondidos(ocultarTodos) }, [ocultarTodos])
  // desligar a ferramenta (botão ou Esc) no meio do desenho joga fora o ponto 1
  useEffect(() => { if (!ferramenta) cancelarDesenho.current() }, [ferramenta])

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
        let novas = false
        for (const k of r.velas.map(daApi)) {
          const d = dados.current, ult = d[d.length - 1]
          if (!ult || k.t < ult.t) continue
          if (k.t === ult.t) d[d.length - 1] = k
          else { d.push(k); novas = true }
          velas.current?.update(vela(k)); vols.current?.update(volume(k)); linhaPreco.current?.update(fechamento(k))
        }
        if (novas) tempos()
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
