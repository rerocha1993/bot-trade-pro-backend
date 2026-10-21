import { useMemo, useState } from 'react'
import { useAbsorcao, useCandles, useFootprint, useNuvensCalor, useNuvensOverlay, useNuvensTop, usePresos } from '../api/hooks'
import type { CelulaCalor, EventoAbsorcao, EventoPresos, NuvensCategoria, NuvensOverlay, NuvensPonto, PressaoLivro } from '../api/types'
import FootprintChart from '../components/chart/FootprintChart'
import PriceChart from '../components/chart/PriceChart'
import { Header, Page } from '../components/Layout'
import { Card, Chip, Empty, Err, Estado, Loading, Seg } from '../components/ui'
import type { ChartHeatmap, ChartLabel, ChartLevel, ChartMarker, ChartRect } from '../lib/chart-tipos'
import { fmt, preco as fmtPreco } from '../lib/format'

/**
 * Nuvens: mapa de calor do livro agregado (Coinbase + Binance + Bybit) sobre o candle de 5 min.
 * Só acende onde há ordens acima do normal daquela distância do preço; quanto mais ordens, mais quente a cor.
 */
const EXCHANGES = ['coinbase', 'binance', 'bybit'] as const
const NOME_EX: Record<string, string> = { coinbase: 'Coinbase', binance: 'Binance', bybit: 'Bybit' }
const PASSO_S = 300
const N_CANDLES = 288
const FATORES = ['2', '3', '5'] as const
const COR = { bids: '#2ecc84', asks: '#f0544f', presos: '#f5c04a' }
const MODOS = ['absorcao', 'livro', 'paredes'] as const
const TFS_PRESOS = ['300', '1800'] as const
const VISTAS = ['velas', 'footprint'] as const
const TFS_FP = ['300', '900', '1800', '3600', '14400'] as const
const LINHAS_FP = ['10', '20', '50', '100', '250', '500'] as const
/** altura de linha que cabe em cada tempo gráfico (o usuário pode trocar) */
const LINHA_PADRAO: Record<(typeof TFS_FP)[number], (typeof LINHAS_FP)[number]> = { '300': '20', '900': '50', '1800': '50', '3600': '100', '14400': '250' }
const hhmm = (s: number) => new Date(s * 1000).toISOString().slice(11, 16)

/** Escala de cor: frio (só acima do normal) → cor do lado → quente (parede muito acima do normal). */
const ESCALA = {
  bids: [[16, 92, 70, 0.30], [46, 204, 132, 0.62], [236, 232, 110, 0.92]],
  asks: [[112, 30, 42, 0.30], [240, 84, 79, 0.62], [255, 196, 92, 0.92]],
} as const
const FRIO = 2, QUENTE = 12

/** 0 no limite de "acima do normal", 1 em 12x ou mais; escala log para 3x e 6x ficarem bem distintos. */
const nivel = (inten: number) => Math.max(0, Math.min(1, Math.log(inten / FRIO) / Math.log(QUENTE / FRIO)))

/** Cor do mapa de calor em números (0–255 e alfa 0–1): frio → cor do lado → quente. */
function corRGBA(lado: 0 | 1, inten: number): [number, number, number, number] {
  const e = lado === 0 ? ESCALA.bids : ESCALA.asks
  const t = nivel(inten)
  const [a, b, u] = t < 0.5 ? [e[0], e[1], t / 0.5] : [e[1], e[2], (t - 0.5) / 0.5]
  const m = (i: number) => a[i] + (b[i] - a[i]) * u
  return [m(0), m(1), m(2), m(3)]
}

function corCalor(lado: 0 | 1, inten: number): string {
  const [r, g, b, a] = corRGBA(lado, inten)
  return `rgba(${r.toFixed(0)},${g.toFixed(0)},${b.toFixed(0)},${a.toFixed(3)})`
}

/** Força de uma célula: a maior entre a régua histórica e a das vizinhas. */
const forca = (c: CelulaCalor) => Math.max(c[4], c[5] ?? 0)

/**
 * Monta a imagem do mapa de calor: uma coluna por passo de tempo, uma linha por faixa da grade. `fatorAlfa` < 1 deixa a
 * nuvem mais transparente (a pressão do modo Absorção é uma nuvem fraca).
 */
function imagemCalor(colunas: { ts: number; celulas: CelulaCalor[] }[], passo: number, grade: number, fatorAlfa = 1, minimo = 0): ChartHeatmap | null {
  const cols = colunas.map((c) => ({ ts: c.ts, celulas: c.celulas.filter((x) => forca(x) >= minimo) })).filter((c) => c.celulas.length)
  if (!cols.length || !grade) return null
  const t0 = cols[0].ts
  const nCols = Math.round((cols[cols.length - 1].ts - t0) / passo) + 1
  let pMin = Infinity, pMax = -Infinity
  for (const c of cols) for (const x of c.celulas) { pMin = Math.min(pMin, x[0]); pMax = Math.max(pMax, x[1]) }
  const pBase = Math.floor(pMin / grade) * grade
  const nRows = Math.max(1, Math.round((Math.ceil(pMax / grade) * grade - pBase) / grade))
  if (nCols * nRows > 4_000_000) return null
  const rgba = new Uint8ClampedArray(nCols * nRows * 4)
  for (const c of cols) {
    const ci = Math.round((c.ts - t0) / passo)
    for (const x of c.celulas) {
      const ri = nRows - 1 - Math.round((x[0] - pBase) / grade)
      if (ri < 0 || ri >= nRows) continue
      const [r, g, b, a] = corRGBA(x[2], forca(x))
      const o = (ri * nCols + ci) * 4
      if (a * fatorAlfa * 255 <= rgba[o + 3]) continue          // duas células no mesmo pixel: fica a mais forte
      rgba[o] = r; rgba[o + 1] = g; rgba[o + 2] = b; rgba[o + 3] = Math.round(a * fatorAlfa * 255)
    }
  }
  return { t0, passo, nCols, pBase, grade, nRows, rgba }
}

/**
 * O modo Absorção como colunas do mapa de calor: a pressão entra fria (nuvem fraca) e a absorção entra quente, na
 * faixa da parede e uma faixa acima e abaixo, por pelo menos 6 velas (nuvem forte). A imagem suavizada faz o resto.
 */
const FORCA_PRESSAO = 5, FORCA_ABSORCAO = 14, VELAS_ABSORCAO = 12, ALTURA_ABSORCAO = 3

function colunasDoModoAbsorcao(ps: PressaoLivro[], evs: EventoAbsorcao[], passo: number, grade: number): { ts: number; celulas: CelulaCalor[] }[] {
  const por = new Map<number, CelulaCalor[]>()
  const por_em = (ts: number, c: CelulaCalor) => { const l = por.get(ts) ?? []; l.push(c); por.set(ts, l) }
  // pressão: a faixa da parede e uma de cada lado, um pouco mais fraca
  for (const p of ps) {
    const lado = p.tipo === 'venda' ? 1 : 0
    for (let k = -1; k <= 1; k++) por_em(p.ts, [p.baixo + k * grade, p.alto + k * grade, lado, p.btc, k === 0 ? FORCA_PRESSAO : FORCA_PRESSAO * 0.7])
  }
  // absorção: nuvem quente em volta da parede, esmaecendo para cima/baixo e para a frente no tempo
  for (const e of evs) {
    const lado = e.tipo === 'venda' ? 1 : 0
    const fim = Math.max(e.ate_ts, e.ts + VELAS_ABSORCAO * passo)
    const n = Math.round((fim - e.ts) / passo)
    for (let j = 0; j < n; j++) {
      const tempo = 1 - 0.55 * (j / Math.max(1, n - 1))
      for (let k = -ALTURA_ABSORCAO; k <= ALTURA_ABSORCAO; k++) {
        const altura = 1 - 0.2 * Math.abs(k)
        por_em(e.ts + j * passo, [e.baixo + k * grade, e.alto + k * grade, lado, e.parede_btc, Math.max(2.2, FORCA_ABSORCAO * tempo * altura)])
      }
    }
  }
  return [...por.entries()].sort((a, b) => a[0] - b[0]).map(([ts, celulas]) => ({ ts, celulas }))
}

/**
 * Livro inteiro: o Order Book Depth Overlay do TRDR com as configurações do usuário (21/10/2026): profundidade de 1%
 * (inclusive) a 10%, só spot (Coinbase + Binance), opacidade até 100%, mínimo de 40% para cada lado, escala fixa.
 * Por vela, soma o BTC de compra e de venda entre 1% e 10% do preço; a fatia de cada lado vira a opacidade da faixa
 * dele (verde de 1% a 10% abaixo, vermelha de 1% a 10% acima): 40% ou menos não aparece, 100% fica opaca.
 * As paredes de `minimo`x o normal ou mais entram por cima, como as linhas do heatmap.
 */
const LIVRO = { de: 0.01, ate: 0.10, opacidadeMax: 1.0, minCompra: 40, minVenda: 40 }
const EXCHANGES_SPOT = ['coinbase', 'binance']
const PAREDE_LIVRO = 8, PAREDE_LIVRO_LONGE = 0.003   // colada no preço vira mancha sobre as velas
const RGB_LADO = [[46, 204, 132], [240, 84, 79]] as const
/** fatia do lado em % → opacidade, na escala fixa do TRDR: do mínimo (0) a 100% (opacidadeMax) */
const opacidadeLivro = (fatia: number, minimo: number) => (fatia <= minimo ? 0 : LIVRO.opacidadeMax * (fatia - minimo) / (100 - minimo))

function imagemLivro(pontos: NuvensPonto[], categorias: NuvensCategoria[], colunas: { ts: number; mid: number; celulas: CelulaCalor[] }[],
                     passo: number, grade: number, minimo: number): ChartHeatmap | null {
  const ks = categorias.map((c, k) => (c.lo >= LIVRO.de - 1e-9 && c.hi <= LIVRO.ate + 1e-9 ? k : -1)).filter((k) => k >= 0)
  if (!pontos.length || !ks.length || !grade) return null
  const t0 = Math.min(pontos[0].ts, colunas[0]?.ts ?? Infinity)
  const tFim = Math.max(pontos[pontos.length - 1].ts, colunas[colunas.length - 1]?.ts ?? -Infinity)
  const nCols = Math.round((tFim - t0) / passo) + 1
  let pMin = Infinity, pMax = -Infinity
  for (const p of pontos) { pMin = Math.min(pMin, p.mid * (1 - LIVRO.ate)); pMax = Math.max(pMax, p.mid * (1 + LIVRO.ate)) }
  const pBase = Math.floor(pMin / grade) * grade
  const nRows = Math.max(1, Math.ceil((pMax - pBase) / grade))
  if (nCols * nRows > 4_000_000) return null
  const rgba = new Uint8ClampedArray(nCols * nRows * 4)
  const pinta = (ci: number, preco: number, r: number, g: number, b: number, a: number) => {
    const ri = nRows - 1 - Math.round((preco - pBase) / grade)
    if (ri < 0 || ri >= nRows || ci < 0 || ci >= nCols) return
    const o = (ri * nCols + ci) * 4
    rgba[o] = r; rgba[o + 1] = g; rgba[o + 2] = b; rgba[o + 3] = Math.round(a * 255)
  }
  for (const p of pontos) {
    const ci = Math.round((p.ts - t0) / passo)
    const b = ks.reduce((s, k) => s + (p.bids[k] ?? 0), 0)
    const a = ks.reduce((s, k) => s + (p.asks[k] ?? 0), 0)
    if (b + a <= 0) continue
    for (const lado of [0, 1] as const) {
      const alfa = lado === 0 ? opacidadeLivro(100 * b / (b + a), LIVRO.minCompra) : opacidadeLivro(100 * a / (b + a), LIVRO.minVenda)
      if (alfa <= 0) continue
      const [r, g, bl] = RGB_LADO[lado]
      const lo = lado === 0 ? p.mid * (1 - LIVRO.ate) : p.mid * (1 + LIVRO.de)
      const hi = lado === 0 ? p.mid * (1 - LIVRO.de) : p.mid * (1 + LIVRO.ate)
      for (let preco = Math.ceil(lo / grade) * grade; preco < hi; preco += grade) pinta(ci, preco, r, g, bl, alfa)
    }
  }
  for (const c of colunas) {
    const ci = Math.round((c.ts - t0) / passo)
    for (const x of c.celulas) {
      if (forca(x) < minimo || Math.abs((x[0] + x[1]) / 2 / c.mid - 1) < PAREDE_LIVRO_LONGE) continue
      const [r, g, b, a] = corRGBA(x[2], forca(x))
      pinta(ci, x[0], r, g, b, Math.max(a, 0.75))
    }
  }
  return { t0, passo, nCols, pBase, grade, nRows, rgba }
}

function LegendaLivro({ q }: { q: NuvensOverlay | undefined }) {
  const n = q?.pontos.length ?? 0
  return (
    <div style={{ display: 'grid', gap: 6, maxWidth: 640, fontSize: 12 }}>
      <span>Igual ao <b>Order Book Depth Overlay</b> do TRDR com as suas configurações: livro spot (Coinbase + Binance) de 1% a 10% do preço, mínimo de 40% de cada lado, opacidade até 100%, escala fixa.</span>
      <span><b style={{ color: COR.bids }}>Faixa verde</b> (1% a 10% abaixo): quanto mais da liquidez dessa distância é de compra, mais forte. <b style={{ color: COR.asks }}>Faixa vermelha</b> (1% a 10% acima): o mesmo para a venda. Com 40% ou menos, o lado some.</span>
      <span><b>Linhas fortes</b>: paredes de {PAREDE_LIVRO}x o normal ou mais, a mais de 0,3% do preço. Para ver todas, use "Todas as paredes".</span>
      <span className="muted">{!q ? 'lendo o livro…' : `${n} velas com livro gravado · `}O livro mostra intenção, não execução: ordem parada pode sumir (spoof). De 1% a 10% quem alcança é a Coinbase; a Binance pára perto de 1%.</span>
    </div>
  )
}

/** A nuvem de absorção: do momento em que a parede segurou a agressão até ela sair do livro. */
function nuvensAbsorcao(evs: EventoAbsorcao[]): { rects: ChartRect[]; labels: ChartLabel[] } {
  const rects: ChartRect[] = []
  const labels: ChartLabel[] = []
  for (const e of evs) {
    const lado = e.tipo === 'venda' ? 1 : 0
    rects.push({ from: e.ts, to: Math.max(e.ate_ts, e.ts + 12 * 300), top: e.alto, bottom: e.baixo, color: 'rgba(0,0,0,0)', border: lado ? COR.asks : COR.bids })
    labels.push({ time: e.ts, price: lado ? e.alto : e.baixo, color: lado ? COR.asks : COR.bids,
                  text: `absorção ${fmt(e.intensidade, 0)}x · delta ${e.delta_btc > 0 ? '+' : ''}${fmt(e.delta_btc, 0)} · OI +${fmt(e.oi_var_pct, 2)}%` })
  }
  return { rects, labels }
}

/** Presos: seta na vela e uma faixa amarela no preço onde ficaram presos, por 6 velas. */
function marcasPresos(evs: EventoPresos[], passo: number): { markers: ChartMarker[]; rects: ChartRect[] } {
  const markers: ChartMarker[] = []
  const rects: ChartRect[] = []
  for (const e of evs) {
    if (e.confirmado === false) continue
    const comprador = e.lado === 'compradores'
    markers.push({ time: e.ts, side: comprador ? 'sell' : 'buy', text: e.confirmado ? 'presos' : 'presos?' })
    const meia = e.preco * 0.00012
    rects.push({ from: e.ts, to: e.ts + passo * 6, top: e.preco + meia, bottom: e.preco - meia,
                 color: e.confirmado ? 'rgba(245,192,74,0.85)' : 'rgba(245,192,74,0.45)' })
  }
  return { markers, rects }
}

function LegendaAbsorcao({ q }: { q: import('../api/types').FluxoAbsorcao | undefined }) {
  const n = q?.eventos.length ?? 0
  return (
    <div style={{ display: 'grid', gap: 6, maxWidth: 640, fontSize: 12 }}>
      <span><b style={{ color: COR.asks }}>Nuvem fraca</b>: parede pesada colada no preço ({q ? `${fmt(q.criterio.pressao_vezes, 0)}x` : ''} as faixas vizinhas): a pressão está ali, ainda sem a distorção.</span>
      <span><b style={{ color: COR.asks }}>Nuvem forte com contorno (vermelha)</b>: compra agressiva entre as 10% maiores do dia, com OI subindo, batendo numa parede {q ? `${fmt(q.criterio.parede_vezes, 0)}x` : ''} mais grossa que as vizinhas, e o preço não passou: compradores presos no topo.</span>
      <span><b style={{ color: COR.bids }}>Verde</b>: o espelho no fundo, venda agressiva segurada por uma parede de compra.</span>
      <span><b style={{ color: COR.presos }}>Faixa amarela com seta</b>: presos no footprint (quem agrediu no topo ou no fundo da vela e ficou do lado errado); "presos?" ainda espera as próximas velas.</span>
      <span className="muted">{!q ? 'lendo…' : q.velas_com_livro_e_negocios < 24
        ? `a absorção precisa de ~2 h de livro e negócios juntos para saber o que é normal; hoje há ${q.velas_com_livro_e_negocios} velas${q.desde ? ` desde ${hhmm(q.desde)} UTC` : ''}`
        : `${n} absorç${n === 1 ? 'ão' : 'ões'} no período · nada disso foi medido contra sorteio ainda: é leitura, não sinal`}</span>
    </div>
  )
}

function Regua() {
  const grad = (lado: 0 | 1) => `linear-gradient(90deg, ${[2, 3, 4.5, 7, 12].map((x) => corCalor(lado, x)).join(', ')})`
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '6px 10px', alignItems: 'center', maxWidth: 420 }}>
      <span className="muted" style={{ fontSize: 12 }}>compra</span><div style={{ height: 10, borderRadius: 5, background: grad(0) }} />
      <span className="muted" style={{ fontSize: 12 }}>venda</span><div style={{ height: 10, borderRadius: 5, background: grad(1) }} />
      <span />
      <div className="muted" style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
        <span>2x o normal</span><span>5x</span><span>12x ou mais</span>
      </div>
    </div>
  )
}

function ParedeBarra({ c, preco, max }: { c: CelulaCalor; preco: number; max: number }) {
  const [lo, hi, lado, btc] = c
  const inten = forca(c)
  const meio = (lo + hi) / 2
  const dist = (meio / preco - 1) * 100
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '92px 1fr 120px', gap: 10, alignItems: 'center', padding: '6px 0' }}>
      <span className="mono" style={{ color: lado === 0 ? COR.bids : COR.asks }}>{fmtPreco(meio)}</span>
      <div style={{ height: 14, borderRadius: 7, background: 'var(--line, rgba(255,255,255,0.06))' }}>
        <div style={{ height: '100%', width: `${Math.max(6, (inten / max) * 100)}%`, borderRadius: 7, background: corCalor(lado, inten) }} />
      </div>
      <span className="muted" style={{ fontSize: 12, textAlign: 'right' }}>{fmt(inten, 1)}x · {fmt(btc, 0)} BTC · {dist > 0 ? '+' : ''}{fmt(dist, 2)}%</span>
    </div>
  )
}

export default function Nuvens() {
  const [exs, setExs] = useState<Record<string, boolean>>({ coinbase: true, binance: true, bybit: true })
  const [fator, setFator] = useState<(typeof FATORES)[number]>('3')
  const [mostrarTop, setMostrarTop] = useState(false)
  const [modo, setModo] = useState<(typeof MODOS)[number]>('absorcao')
  const [verPresos, setVerPresos] = useState(true)
  const [tfPresos, setTfPresos] = useState<(typeof TFS_PRESOS)[number]>('1800')
  const [vista, setVista] = useState<(typeof VISTAS)[number]>('velas')
  const [tfFp, setTfFp] = useState<(typeof TFS_FP)[number]>('1800')
  const [linhaFp, setLinhaFp] = useState<(typeof LINHAS_FP)[number]>('50')
  const qFp = useFootprint(Number(tfFp), Number(linhaFp), vista === 'footprint')
  const trocarTfFp = (tf: (typeof TFS_FP)[number]) => { setTfFp(tf); setLinhaFp(LINHA_PADRAO[tf]) }
  const exchanges = EXCHANGES.filter((e) => exs[e]).join(',')
  const candles = useCandles('BTCUSDT', '5m', N_CANDLES)
  const dados = candles.data ?? []
  const inicio = dados.length ? dados[0].time : null
  const qCalor = useNuvensCalor(inicio, exchanges, Number(fator), PASSO_S)
  const qAbs = useAbsorcao(inicio)
  const qLivro = useNuvensOverlay(modo === 'livro' ? inicio : null, EXCHANGES_SPOT.join(','), PASSO_S)
  const qPresos = usePresos(inicio, Number(tfPresos), verPresos)
  const qTop = useNuvensTop(exchanges)
  const d = qCalor.data
  const top = qTop.data
  const ultimaVela = dados[dados.length - 1]
  const ultimaCol = d?.colunas.length ? d.colunas[d.colunas.length - 1] : null

  const absorcao = useMemo(() => nuvensAbsorcao(qAbs.data?.eventos ?? []), [qAbs.data])
  const presos = useMemo(() => (verPresos ? marcasPresos(qPresos.data?.eventos ?? [], Number(tfPresos)) : { markers: [], rects: [] }), [verPresos, qPresos.data, tfPresos])
  const rects = useMemo(() => [...(modo === 'paredes' ? [] : absorcao.rects), ...presos.rects], [modo, absorcao, presos])
  const heatmap = useMemo<ChartHeatmap | null>(() => {
    if (!d?.grade_usd) return null
    if (modo === 'paredes') return imagemCalor(d.colunas, d.passo_s, d.grade_usd, 1, Number(fator))
    if (modo === 'livro') return qLivro.data ? imagemLivro(qLivro.data.pontos, qLivro.data.categorias, d.colunas, d.passo_s, d.grade_usd, PAREDE_LIVRO) : null
    return imagemCalor(colunasDoModoAbsorcao(qAbs.data?.pressao ?? [], qAbs.data?.eventos ?? [], d.passo_s, d.grade_usd), d.passo_s, d.grade_usd)
  }, [modo, d, qAbs.data, qLivro.data, fator])
  const labels = useMemo(() => (modo === 'absorcao' ? absorcao.labels : []), [modo, absorcao])
  const levels = useMemo<ChartLevel[]>(() => {
    if (!mostrarTop || !top) return []
    return [
      ...top.bids.slice(0, 5).map((n) => ({ price: n.preco, label: `${fmt(n.qtd, 0)}`, color: COR.bids, dashed: true })),
      ...top.asks.slice(0, 5).map((n) => ({ price: n.preco, label: `${fmt(n.qtd, 0)}`, color: COR.asks, dashed: true })),
    ]
  }, [mostrarTop, top])

  // as paredes mais fortes de agora, as 4 mais perto do preço em cada lado
  const paredes = useMemo(() => {
    if (!ultimaCol || !ultimaVela) return { acima: [] as CelulaCalor[], abaixo: [] as CelulaCalor[], max: 1 }
    const p = ultimaVela.close
    const fortes = [...ultimaCol.celulas].sort((a, b) => forca(b) - forca(a)).slice(0, 12)
    const acima = fortes.filter((c) => c[0] > p).sort((a, b) => b[0] - a[0]).slice(-4)
    const abaixo = fortes.filter((c) => c[1] < p).sort((a, b) => b[0] - a[0]).slice(0, 4)
    return { acima, abaixo, max: Math.max(1, ...fortes.map((c) => forca(c))) }
  }, [ultimaCol, ultimaVela])

  const toggleEx = (e: string) => {
    const novo = { ...exs, [e]: !exs[e] }
    if (Object.values(novo).some(Boolean)) setExs(novo)
  }
  const semBase = d ? Object.entries(d.base).filter(([, n]) => n < 20).map(([e]) => NOME_EX[e] ?? e) : []

  return (
    <>
      <Header titulo="Nuvens do livro" par="BTCUSDT" eyebrow="Order flow"
        subtitulo="A nuvem só aparece quando há distorção: muita gente agredindo a mercado, alavancada, contra uma parede grande no livro (Coinbase + Binance + Bybit), e o preço sem atravessar. Em “Todas as paredes” você vê o livro inteiro acima do normal; o botão Presos marca as velas onde ficou gente presa." />
      <Page>
        <Card title={vista === 'footprint' ? `Footprint ${Number(tfFp) >= 3600 ? `${Number(tfFp) / 3600}h` : `${Number(tfFp) / 60} min`}` : 'Candles de 5 min com as nuvens'}
          right={<span style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            <Seg value={vista} options={VISTAS} onChange={setVista} labels={{ velas: 'Velas', footprint: 'Footprint' }} />
            <span style={{ width: 8 }} />
            {vista === 'footprint' ? <>
              <Seg value={tfFp} options={TFS_FP} onChange={trocarTfFp} labels={{ '300': '5m', '900': '15m', '1800': '30m', '3600': '1h', '14400': '4h' }} />
              <span className="muted" style={{ fontSize: 12 }}>linha de</span>
              <Seg value={linhaFp} options={LINHAS_FP} onChange={setLinhaFp} labels={{ '10': '$10', '20': '$20', '50': '$50', '100': '$100', '250': '$250', '500': '$500' }} />
            </> : <>
            <Seg value={modo} options={MODOS} onChange={setModo} labels={{ absorcao: 'Absorção', livro: 'Livro inteiro', paredes: 'Todas as paredes' }} />
            {modo === 'paredes' && <>
              <span className="muted" style={{ fontSize: 12 }}>a partir de</span>
              <Seg value={fator} options={FATORES} onChange={setFator} labels={{ '2': '2x', '3': '3x', '5': '5x' }} />
              {EXCHANGES.map((e) => <Chip key={e} on={!!exs[e]} onClick={() => toggleEx(e)}>{NOME_EX[e]}</Chip>)}
            </>}
            <span style={{ width: 8 }} />
            <Chip on={verPresos} onClick={() => setVerPresos(!verPresos)}>Presos</Chip>
            {verPresos && <Seg value={tfPresos} options={TFS_PRESOS} onChange={setTfPresos} labels={{ '300': '5 min', '1800': '30 min' }} />}
            <Chip on={mostrarTop} onClick={() => setMostrarTop(!mostrarTop)}>maiores níveis</Chip>
            </>}
          </span>}>
          {vista === 'footprint' ? (
            qFp.isPending ? <Loading /> : qFp.isError ? <Err e={qFp.error} /> : !qFp.data?.velas.length ? <Empty>ainda sem negócios gravados para o footprint</Empty> : <>
              <FootprintChart velas={qFp.data.velas} linha={qFp.data.linha_usd} />
              <div className="muted" style={{ fontSize: 12, marginTop: 10, display: 'grid', gap: 4 }}>
                <span>Arraste para os lados, use a roda do mouse ou dois dedos para o zoom; arraste o eixo de preço para esticar. Chegando perto, cada linha mostra a <b style={{ color: COR.asks }}>venda a mercado</b> à esquerda e a <b style={{ color: '#3d8bfd' }}>compra a mercado</b> à direita (BTC, Bybit perpétuo). Contorno branco é o POC da vela; número em negrito é desequilíbrio de 3 para 1; as barras embaixo são o delta.</span>
                <span><b style={{ color: COR.presos }}>Contorno amarelo</b>: onde ficou gente presa (entrou forte no topo ou no fundo da vela e o preço fechou do outro lado); tracejado = ainda esperando as próximas velas. Δ embaixo é compra menos venda da vela.</span>
              </div>
            </>
          ) : candles.isPending ? <Loading /> : candles.isError ? <Err e={candles.error} /> : dados.length === 0 ? <Empty>sem candles</Empty> : (
            <PriceChart candles={dados} rects={rects} heatmap={heatmap} levels={levels} labels={labels} markers={presos.markers} height={560} />
          )}
          {vista === 'velas' && <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', marginTop: 12, alignItems: 'end' }}>
            {modo === 'paredes' ? <Regua /> : modo === 'livro' ? <LegendaLivro q={qLivro.data} /> : <LegendaAbsorcao q={qAbs.data} />}
            <span className="muted" style={{ fontSize: 12 }}>
              {qCalor.isPending ? 'lendo o livro…' : d && d.colunas.length
                ? `livro gravado de ${new Date(d.colunas[0].ts * 1000).toISOString().slice(11, 16)} a ${new Date(d.colunas[d.colunas.length - 1].ts * 1000).toISOString().slice(11, 16)} UTC · onde não há nuvem, nada acima do normal (ou o coletor estava parado)`
                : 'o coletor ainda não tem livro suficiente neste período'}
            </span>
          </div>}
          {semBase.length > 0 && <div style={{ marginTop: 10 }}><span className="alerta-pill">Ainda sem histórico para comparar em {semBase.join(', ')}: precisa de ~10 min de coleta.</span></div>}
        </Card>

        <Card title="Paredes de agora" sub="as mais fortes perto do preço; a barra é quantas vezes acima do normal">
          <Estado query={qCalor}>
            {!ultimaVela || (!paredes.acima.length && !paredes.abaixo.length) ? <Empty>nenhuma parede acima do normal agora</Empty> : (
              <div>
                {paredes.acima.map((c) => <ParedeBarra key={`a${c[0]}`} c={c} preco={ultimaVela.close} max={paredes.max} />)}
                <div style={{ display: 'grid', gridTemplateColumns: '92px 1fr', gap: 10, alignItems: 'center', padding: '8px 0' }}>
                  <span className="mono">{fmtPreco(ultimaVela.close)}</span>
                  <div style={{ borderTop: '1px dashed var(--muted)', opacity: 0.6 }} />
                </div>
                {paredes.abaixo.map((c) => <ParedeBarra key={`b${c[0]}`} c={c} preco={ultimaVela.close} max={paredes.max} />)}
              </div>
            )}
          </Estado>
        </Card>

        <details>
          <summary className="muted" style={{ cursor: 'pointer', fontSize: 13 }}>ver detalhes de cada corretora</summary>
          <Card title="O que cada corretora alcança" sub="profundidade que a API pública devolve">
            <table className="table">
              <thead><tr><th>corretora</th><th className="r">snapshots de base</th><th>limite</th></tr></thead>
              <tbody>
                {(d?.exchanges ?? []).map((e) => (
                  <tr key={e}>
                    <td className="sans">{NOME_EX[e] ?? e}</td>
                    <td className="r">{d?.base[e] ?? 0}</td>
                    <td className="muted" style={{ whiteSpace: 'normal' }}>{d?.limitacoes[e]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </details>
      </Page>
    </>
  )
}
