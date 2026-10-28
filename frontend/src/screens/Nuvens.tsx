import { useMemo, useState } from 'react'
import type { LogicalRange } from 'lightweight-charts'
import { useAbsorcao, useCandles, useFootprint, useFunding, useLiquidacoes, useLivroPerp, useNuvensCalor, useNuvensOverlay, useNuvensTop, usePresos } from '../api/hooks'
import type { Candle, CelulaCalor, EventoAbsorcao, EventoPresos, FluxoLiquidacoes, FundingAgregado, LivroPerp, NuvensCategoria, NuvensOverlay, NuvensPonto, PressaoLivro } from '../api/types'
import FootprintChart from '../components/chart/FootprintChart'
import PriceChart from '../components/chart/PriceChart'
import SubChart, { type SerieSub } from '../components/chart/SubChart'
import { Header, Page } from '../components/Layout'
import { Card, Chip, Empty, Err, Estado, Loading, Seg } from '../components/ui'
import type { ChartHeatmap, ChartLabel, ChartLevel, ChartMarker, ChartRect } from '../lib/chart-tipos'
import { fmt, preco as fmtPreco } from '../lib/format'
import { bandasDoPonto, LIVRO_TRDR, RGB_LADO } from '../lib/livroTrdr'

/**
 * Nuvens: mapa de calor do livro agregado (Coinbase + Binance + Bybit) sobre o candle de 5 min.
 * Só acende onde há ordens acima do normal daquela distância do preço; quanto mais ordens, mais quente a cor.
 */
const EXCHANGES = ['coinbase', 'binance', 'bybit'] as const
const NOME_EX: Record<string, string> = { coinbase: 'Coinbase', binance: 'Binance', bybit: 'Bybit' }
const PASSO_S = 300
/** quantos dias o gráfico mostra (velas de 5 min: 288 por dia); os dias fechados vêm do cache da API */
const PERIODOS = ['1', '3', '7'] as const
const VELAS_POR_DIA = 288
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

/** Livro inteiro: o Order Book Depth Overlay do TRDR (regra em lib/livroTrdr.ts). As paredes de `minimo`x o normal
 *  ou mais entram por cima, como as linhas do heatmap. */
const EXCHANGES_SPOT = ['coinbase', 'binance']
const PAREDE_LIVRO = 8, PAREDE_LIVRO_LONGE = 0.003   // colada no preço vira mancha sobre as velas

function imagemLivro(pontos: NuvensPonto[], categorias: NuvensCategoria[], colunas: { ts: number; mid: number; celulas: CelulaCalor[] }[],
                     passo: number, grade: number, minimo: number): ChartHeatmap | null {
  if (!pontos.length || !grade) return null
  const t0 = Math.min(pontos[0].ts, colunas[0]?.ts ?? Infinity)
  const tFim = Math.max(pontos[pontos.length - 1].ts, colunas[colunas.length - 1]?.ts ?? -Infinity)
  const nCols = Math.round((tFim - t0) / passo) + 1
  let pMin = Infinity, pMax = -Infinity
  for (const p of pontos) { pMin = Math.min(pMin, p.mid * (1 - LIVRO_TRDR.ate)); pMax = Math.max(pMax, p.mid * (1 + LIVRO_TRDR.ate)) }
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
    for (const f of bandasDoPonto(p, categorias)) {
      const [r, g, bl] = RGB_LADO[f.lado]
      for (let preco = Math.ceil(f.lo / grade) * grade; preco < f.hi; preco += grade) pinta(ci, preco, r, g, bl, f.alfa)
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
      <span>Igual ao <b>Order Book Depth Overlay</b> do TRDR com as suas configurações: livro spot (Coinbase + Binance, cada uma só nas faixas que o livro dela alcança), faixas de 1–2,5%, 2,5–5% e 5–10% do preço, mínimo de 40, teto de 100, escala fixa.</span>
      <span><b style={{ color: 'rgb(38,166,154)' }}>Verde-água abaixo</b>: naquela faixa a compra tem 70% ou mais do livro (ratio 40 do TRDR); quanto mais forte, mais perto de só compra. <b style={{ color: COR.asks }}>Vermelho acima</b>: o mesmo para a venda. Sem nuvem = livro equilibrado.</span>
      <span><b>Linhas fortes</b>: paredes de {PAREDE_LIVRO}x o normal ou mais, a mais de 0,3% do preço. Para ver todas, use "Todas as paredes".</span>
      <span className="muted">{!q ? 'lendo o livro…' : `${n} velas com livro gravado · `}O livro mostra intenção, não execução: ordem parada pode sumir (spoof). De 1% a 10% quem alcança é a Coinbase; a Binance pára perto de 1%.</span>
    </div>
  )
}

/**
 * Os painéis de baixo, como os do TRDR do usuário, mas cada um mostrando UMA coisa e dizendo o que ela quer dizer agora:
 * o saldo do livro à vista e do alavancado (compra − venda), as liquidações e o funding. Cada série tem um valor por
 * vela do gráfico de cima (null = sem dado), para ficar alinhada.
 */
const absK = (v: number) => { const a = Math.abs(v); return a >= 1e6 ? `${(a / 1e6).toFixed(1)}M` : a >= 1e3 ? `${(a / 1e3).toFixed(0)}k` : a.toFixed(0) }
const FMT_BTC = (v: number) => `${v < 0 ? '−' : '+'}${absK(v)}`
const FMT_USD = (v: number) => `$${absK(v)}`
const FMT_FUNDING = (v: number) => `${v.toFixed(3)}%`
const VERDE = 'rgba(46,204,132,0.8)', VERMELHO = 'rgba(240,84,79,0.8)', NEUTRO = '#8b95a5'
const FUNDING_ALTO = 0.03          // % a cada 8 h: acima disso os comprados estão pagando caro
const UMA_HORA = 3600

type Leitura = { texto: string; cor: string }
type Painel = { titulo: string; explica: string; leitura?: Leitura; series: SerieSub[]; formato: (v: number) => string; height?: number }

/** Saldo do livro (compra − venda) como uma barra por vela e a leitura da última. */
function painelSaldo(titulo: string, explica: string, tempos: number[], saldo: (t: number) => { b: number; a: number } | null): Painel {
  const pts = tempos.map((t) => saldo(t))
  const valores = pts.map((p) => (p ? p.b - p.a : null))
  const ult = [...pts].reverse().find((p) => p)
  let leitura: Leitura | undefined
  if (ult) {
    const fatia = ult.b / Math.max(1e-9, ult.b + ult.a)
    leitura = fatia >= 0.55 ? { texto: `agora: mais compra esperando (${fmt(100 * fatia, 0)}% do livro) · apoio embaixo`, cor: COR.bids }
      : fatia <= 0.45 ? { texto: `agora: mais venda esperando (${fmt(100 * (1 - fatia), 0)}% do livro) · peso em cima`, cor: COR.asks }
      : { texto: `agora: equilibrado (${fmt(100 * fatia, 0)}% compra)`, cor: NEUTRO }
  }
  return { titulo, explica, leitura, formato: FMT_BTC, height: 90,
           series: [{ id: 'saldo', tipo: 'barra', cor: VERDE, valores, cores: valores.map((v) => (v === null ? null : v >= 0 ? VERDE : VERMELHO)) }] }
}

function paineisDeBaixo(tempos: number[], livro: NuvensOverlay | undefined, perp: LivroPerp | undefined, liq: FluxoLiquidacoes | undefined,
                        funding: FundingAgregado | undefined): Painel[] {
  const saida: Painel[] = []
  if (livro) {
    const ks = livro.categorias.map((c, k) => (c.hi <= 0.05 + 1e-9 ? k : -1)).filter((k) => k >= 0)
    const porTs = new Map(livro.pontos.map((p) => [p.ts, p]))
    const soma = (p: NuvensPonto, lado: 'bids' | 'asks') => ks.reduce((s, k) => s + (p[lado][k] ?? 0), 0)
    saida.push(painelSaldo('Livro à vista: quem está esperando (Coinbase + Binance, até 5% do preço)',
      'barra verde = mais ordens de compra paradas do que de venda; vermelha = mais venda; o número é a diferença em BTC',
      tempos, (t) => { const p = porTs.get(t); return p ? { b: soma(p, 'bids'), a: soma(p, 'asks') } : null }))
  }
  if (perp) {
    const porTs = new Map(perp.velas.map((v) => [v.ts, v]))
    saida.push(painelSaldo(`Livro alavancado: quem está esperando (perpétuos Binance + Bybit + OKX, até ${fmt(perp.faixa_pct * 100, 1)}%)`,
      perp.velas.length ? `o mesmo, nos perpétuos; só até ${fmt(perp.faixa_pct * 100, 1)}% do preço, o mais fundo que as corretoras liberam de graça`
        : 'gravando desde agora: o histórico vai enchendo enquanto o coletor estiver aberto',
      tempos, (t) => { const v = porTs.get(t); return v ? { b: v.bids, a: v.asks } : null }))
  }
  if (liq) {
    const porTs = new Map(liq.velas.map((v) => [v.ts, v]))
    const desde = liq.desde
    const valor = (t: number, campo: 'long_usd' | 'short_usd', sinal: number) => (desde === null || t < desde ? null : sinal * (porTs.get(t)?.[campo] ?? 0))
    const fim = tempos[tempos.length - 1] ?? 0
    const ultHora = liq.velas.filter((v) => v.ts > fim - UMA_HORA)
    const L = ultHora.reduce((s, v) => s + v.long_usd, 0), S = ultHora.reduce((s, v) => s + v.short_usd, 0)
    const leitura: Leitura = desde === null ? { texto: 'gravando desde agora', cor: NEUTRO }
      : S > 2 * L && S >= 100_000 ? { texto: `última hora: $${absK(S)} de vendidos fechados à força · isso empurra o preço para cima`, cor: COR.bids }
      : L > 2 * S && L >= 100_000 ? { texto: `última hora: $${absK(L)} de comprados fechados à força · isso empurra o preço para baixo`, cor: COR.asks }
      : { texto: `última hora: pouca liquidação (comprados $${absK(L)}, vendidos $${absK(S)})`, cor: NEUTRO }
    saida.push({
      titulo: 'Liquidações: alavancados fechados à força (Bybit + OKX)', formato: FMT_USD, height: 90, leitura,
      explica: `verde para cima = vendidos (short) liquidados, a corretora compra por eles; vermelho para baixo = comprados (long) liquidados, ela vende${desde !== null ? ` · gravando desde ${hhmm(desde)} UTC` : ''}`,
      series: [
        { id: 'short', tipo: 'barra', cor: VERDE, valores: tempos.map((t) => valor(t, 'short_usd', 1)) },
        { id: 'long', tipo: 'barra', cor: VERMELHO, valores: tempos.map((t) => valor(t, 'long_usd', -1)) },
      ],
    })
  }
  if (funding?.media.length) {
    const degrau = (serie: number[][]) => {
      let k = 0
      return tempos.map((t) => {
        while (k + 1 < serie.length && serie[k + 1][0] <= t * 1000) k++
        return serie.length && serie[k][0] <= t * 1000 ? serie[k][1] * 100 : null
      })
    }
    const EX: Record<string, { cor: string; nome: string; corNome: string }> = {
      bybit: { cor: '#f5a623', nome: 'Bybit', corNome: 'laranja' },
      binance: { cor: '#3d8bfd', nome: 'Binance', corNome: 'azul' },
      okx: { cor: '#8b95a5', nome: 'OKX', corNome: 'cinza' },
    }
    const agora = funding.media[funding.media.length - 1][1] * 100
    const leitura: Leitura = agora >= FUNDING_ALTO ? { texto: `agora ${agora.toFixed(3)}%: alto · muita gente comprada e alavancada, risco de queda forçada`, cor: COR.asks }
      : agora < 0 ? { texto: `agora ${agora.toFixed(3)}%: negativo · muita gente vendida, risco de alta forçada`, cor: COR.bids }
      : { texto: `agora ${agora.toFixed(3)}%: normal · ninguém esticado demais`, cor: NEUTRO }
    const exs = Object.keys(funding.por_exchange)
    saida.push({
      titulo: 'Funding: quanto o comprado paga ao vendido a cada 8 h', formato: FMT_FUNDING, height: 90, leitura,
      explica: `linha branca = média; ${exs.map((ex) => `${EX[ex]?.corNome ?? ''} ${EX[ex]?.nome ?? ex}`).join(', ')} · o normal fica entre 0 e ${FUNDING_ALTO}%`,
      series: [
        ...exs.map((ex): SerieSub => ({ id: ex, tipo: 'linha', cor: EX[ex]?.cor ?? NEUTRO, largura: 1, valores: degrau(funding.por_exchange[ex]) })),
        { id: 'media', tipo: 'linha', cor: '#e8ecf2', largura: 2, valores: degrau(funding.media) },
      ],
    })
  }
  return saida
}

/**
 * A absorção no gráfico: só a nuvem e um rótulo curto ("presos no topo"); eventos a menos de 2 h um do outro dividem
 * o mesmo rótulo, para os textos não se atropelarem com 3 ou 7 dias na tela. A cor diz o lado.
 */
function nuvensAbsorcao(evs: EventoAbsorcao[]): { rects: ChartRect[]; labels: ChartLabel[] } {
  const rects: ChartRect[] = []
  const labels: ChartLabel[] = []
  let ultimoRotulo = -Infinity
  for (const e of [...evs].sort((a, b) => a.ts - b.ts)) {
    const lado = e.tipo === 'venda' ? 1 : 0
    rects.push({ from: e.ts, to: Math.max(e.ate_ts, e.ts + 12 * 300), top: e.alto, bottom: e.baixo, color: 'rgba(0,0,0,0)', border: lado ? COR.asks : COR.bids })
    if (e.ts - ultimoRotulo < 2 * 3600) continue
    ultimoRotulo = e.ts
    labels.push({ time: e.ts, price: lado ? e.alto : e.baixo, color: lado ? COR.asks : COR.bids,
                  text: lado ? 'presos no topo' : 'presos no fundo' })
  }
  return { rects, labels }
}

/**
 * Presos, desenhados nas velas de 5 min do gráfico mesmo quando foram achados na vela de 30 min:
 * - o bloco de 30 min fica sombreado de leve (as 6 velas de 5 min de que o aviso fala);
 * - a seta vai na vela de 5 min onde o nível foi negociado (a de topo mais alto, para compradores presos);
 * - a faixa amarela é o preço de quem ficou preso e acaba quando uma vela FECHA do outro lado dele (os presos saíram
 *   no zero a zero), ou depois de 6 blocos.
 */
const FAIXA_FOOTPRINT_USD = 20

function marcasPresos(evs: EventoPresos[], passo: number, velas: Candle[]): { markers: ChartMarker[]; rects: ChartRect[] } {
  const markers: ChartMarker[] = []
  const rects: ChartRect[] = []
  const passoGrafico = velas.length > 1 ? velas[1].time - velas[0].time : PASSO_S
  for (const e of evs) {
    if (e.confirmado === false) continue
    const comprador = e.lado === 'compradores'
    const nivel = e.preco + FAIXA_FOOTPRINT_USD / 2
    const bloco = velas.filter((v) => v.time >= e.ts && v.time < e.ts + passo)
    const tocaram = bloco.filter((v) => v.low <= e.preco + FAIXA_FOOTPRINT_USD && v.high >= e.preco)
    const candidatas = tocaram.length ? tocaram : bloco
    const alvo = candidatas.reduce<Candle | null>((m, v) => (!m ? v : comprador ? (v.high > m.high ? v : m) : (v.low < m.low ? v : m)), null)
    const tSeta = alvo?.time ?? e.ts
    markers.push({ time: tSeta, side: comprador ? 'sell' : 'buy', text: e.confirmado ? 'presos' : 'presos?' })
    if (bloco.length > 1) {
      rects.push({ from: bloco[0].time, to: bloco[bloco.length - 1].time + passoGrafico,
                   top: Math.max(...bloco.map((v) => v.high)), bottom: Math.min(...bloco.map((v) => v.low)), color: 'rgba(245,192,74,0.07)' })
    }
    const saiu = velas.find((v) => v.time > tSeta && (comprador ? v.close > nivel : v.close < nivel))
    const ultima = velas.length ? velas[velas.length - 1].time + passoGrafico : e.ts + passo
    const meia = nivel * 0.00012
    rects.push({ from: tSeta, to: Math.min(saiu ? saiu.time : ultima, e.ts + passo * 6), top: nivel + meia, bottom: nivel - meia,
                 color: e.confirmado ? 'rgba(245,192,74,0.85)' : 'rgba(245,192,74,0.45)' })
  }
  return { markers, rects }
}

function LegendaAbsorcao({ q }: { q: import('../api/types').FluxoAbsorcao | undefined }) {
  const n = q?.eventos.length ?? 0
  return (
    <div style={{ display: 'grid', gap: 6, maxWidth: 640, fontSize: 12 }}>
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
      <div className="muted" style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 11 }}>
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
  const [periodo, setPeriodo] = useState<(typeof PERIODOS)[number]>('3')
  const [tfFp, setTfFp] = useState<(typeof TFS_FP)[number]>('1800')
  const [linhaFp, setLinhaFp] = useState<(typeof LINHAS_FP)[number]>('50')
  const qFp = useFootprint(Number(tfFp), Number(linhaFp), vista === 'footprint')
  const trocarTfFp = (tf: (typeof TFS_FP)[number]) => { setTfFp(tf); setLinhaFp(LINHA_PADRAO[tf]) }
  const exchanges = EXCHANGES.filter((e) => exs[e]).join(',')
  const candles = useCandles('BTCUSDT', '5m', Number(periodo) * VELAS_POR_DIA)
  const dados = candles.data ?? []
  const inicio = dados.length ? dados[0].time : null
  const qCalor = useNuvensCalor(inicio, exchanges, Number(fator), PASSO_S)
  const qAbs = useAbsorcao(inicio)
  const qLivro = useNuvensOverlay(inicio, EXCHANGES_SPOT.join(','), PASSO_S)
  const qLiq = useLiquidacoes(inicio, PASSO_S)
  const qFunding = useFunding()
  const qPerp = useLivroPerp(inicio, PASSO_S)
  const [range, setRange] = useState<LogicalRange | null>(null)
  const tempos = useMemo(() => dados.map((c) => c.time), [dados])
  const paineis = useMemo(() => paineisDeBaixo(tempos, qLivro.data, qPerp.data, qLiq.data, qFunding.data), [tempos, qLivro.data, qPerp.data, qLiq.data, qFunding.data])
  const qPresos = usePresos(inicio, Number(tfPresos), verPresos)
  const qTop = useNuvensTop(exchanges)
  const d = qCalor.data
  const top = qTop.data
  const ultimaVela = dados[dados.length - 1]
  const ultimaCol = d?.colunas.length ? d.colunas[d.colunas.length - 1] : null

  const absorcao = useMemo(() => nuvensAbsorcao(qAbs.data?.eventos ?? []), [qAbs.data])
  const presos = useMemo(() => (verPresos ? marcasPresos(qPresos.data?.eventos ?? [], Number(tfPresos), dados) : { markers: [], rects: [] }), [verPresos, qPresos.data, tfPresos, dados])
  const rects = useMemo(() => [...(modo === 'paredes' ? [] : absorcao.rects), ...presos.rects], [modo, absorcao, presos])
  const heatmap = useMemo<ChartHeatmap | null>(() => {
    if (!d?.grade_usd) return null
    if (modo === 'paredes') return imagemCalor(d.colunas, d.passo_s, d.grade_usd, 1, Number(fator))
    if (modo === 'livro') return qLivro.data ? imagemLivro(qLivro.data.pontos, qLivro.data.categorias, d.colunas, d.passo_s, d.grade_usd, PAREDE_LIVRO) : null
    return imagemCalor(colunasDoModoAbsorcao([], qAbs.data?.eventos ?? [], d.passo_s, d.grade_usd), d.passo_s, d.grade_usd)
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
            {vista === 'velas' && <Seg value={periodo} options={PERIODOS} onChange={setPeriodo} labels={{ '1': '1 dia', '3': '3 dias', '7': '7 dias' }} />}
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
            <>
              <PriceChart candles={dados} rects={rects} heatmap={heatmap} levels={levels} labels={labels} markers={presos.markers} height={560} onRange={setRange} />
              {paineis.map((p) => <SubChart key={p.titulo} {...p} tempos={tempos} range={range} />)}
            </>
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
