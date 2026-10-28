/**
 * As camadas de order flow do BTC para o gráfico (vieram da antiga aba Nuvens):
 *
 *   absorção        nuvem quente onde a compra (ou venda) agressiva e alavancada bateu numa parede e o preço não
 *                   passou, com o rótulo "presos no topo" / "presos no fundo"
 *   todas as paredes  mapa de calor com o livro acima do normal (Coinbase + Binance + Bybit)
 *   presos          seta na vela onde ficou gente presa no footprint e a faixa amarela no preço deles, até uma vela
 *                   fechar do outro lado (os presos saíram no zero a zero) ou 6 blocos
 *
 * Tudo vira os tipos de lib/chart-tipos.ts; o gráfico só desenha.
 */
import type { CelulaCalor, EventoAbsorcao, EventoPresos } from '../api/types'
import { corRGBA, forca } from './calor'
import type { ChartHeatmap, ChartLabel, ChartMarker, ChartRect } from './chart-tipos'

export const COR_FLUXO = { bids: '#2ecc84', asks: '#f0544f', presos: '#f5c04a' }

/**
 * Imagem do mapa de calor: uma coluna por passo de tempo, uma linha por faixa da grade. `fatorAlfa` < 1 deixa a nuvem
 * mais transparente; `minimo` esconde as células mais fracas que isso.
 */
export function imagemCalor(colunas: { ts: number; celulas: CelulaCalor[] }[], passo: number, grade: number, fatorAlfa = 1, minimo = 0): ChartHeatmap | null {
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
 * A absorção como colunas do mapa de calor: nuvem quente na faixa da parede e até 3 faixas acima e abaixo, por pelo
 * menos 12 velas de 5 min, esmaecendo para a frente no tempo. A imagem suavizada faz o resto.
 */
const FORCA_ABSORCAO = 14, VELAS_ABSORCAO = 12, ALTURA_ABSORCAO = 3

export function colunasDaAbsorcao(evs: EventoAbsorcao[], passo: number, grade: number): { ts: number; celulas: CelulaCalor[] }[] {
  const por = new Map<number, CelulaCalor[]>()
  for (const e of evs) {
    const lado = e.tipo === 'venda' ? 1 : 0
    const fim = Math.max(e.ate_ts, e.ts + VELAS_ABSORCAO * passo)
    const n = Math.round((fim - e.ts) / passo)
    for (let j = 0; j < n; j++) {
      const tempo = 1 - 0.55 * (j / Math.max(1, n - 1))
      for (let k = -ALTURA_ABSORCAO; k <= ALTURA_ABSORCAO; k++) {
        const altura = 1 - 0.2 * Math.abs(k)
        const l = por.get(e.ts + j * passo) ?? []
        l.push([e.baixo + k * grade, e.alto + k * grade, lado, e.parede_btc, Math.max(2.2, FORCA_ABSORCAO * tempo * altura)])
        por.set(e.ts + j * passo, l)
      }
    }
  }
  return [...por.entries()].sort((a, b) => a[0] - b[0]).map(([ts, celulas]) => ({ ts, celulas }))
}

/** Contorno e rótulo de cada absorção; eventos a menos de 2 h um do outro dividem o mesmo rótulo. */
export function marcasAbsorcao(evs: EventoAbsorcao[]): { rects: ChartRect[]; labels: ChartLabel[] } {
  const rects: ChartRect[] = []
  const labels: ChartLabel[] = []
  let ultimoRotulo = -Infinity
  for (const e of [...evs].sort((a, b) => a.ts - b.ts)) {
    const venda = e.tipo === 'venda'
    rects.push({ from: e.ts, to: Math.max(e.ate_ts, e.ts + VELAS_ABSORCAO * 300), top: e.alto, bottom: e.baixo,
                 color: 'rgba(0,0,0,0)', border: venda ? COR_FLUXO.asks : COR_FLUXO.bids })
    if (e.ts - ultimoRotulo < 2 * 3600) continue
    ultimoRotulo = e.ts
    labels.push({ time: e.ts, price: venda ? e.alto : e.baixo, color: venda ? COR_FLUXO.asks : COR_FLUXO.bids,
                  text: venda ? 'presos no topo' : 'presos no fundo' })
  }
  return { rects, labels }
}

/** vela do gráfico: início (s), máxima, mínima e fechamento */
type VelaG = { t: number; h: number; l: number; c: number }
const FAIXA_FOOTPRINT_USD = 20

/**
 * Presos no tempo do gráfico. `passo` é o bloco em que o presos foi achado (5 ou 30 min); `tf` é a vela do gráfico.
 * - a seta vai na vela onde o nível foi negociado dentro do bloco (a de topo mais alto, para compradores presos);
 *   se a vela do gráfico é maior que o bloco, vai na vela que contém o bloco;
 * - o bloco fica sombreado de leve quando ocupa mais de uma vela;
 * - a faixa amarela é o preço de quem ficou preso e acaba quando uma vela FECHA do outro lado dele, ou em 6 blocos.
 */
export function marcasPresos(evs: EventoPresos[], passo: number, velas: VelaG[], tf: number): { markers: ChartMarker[]; rects: ChartRect[] } {
  const setas = new Map<number, { side: 'buy' | 'sell'; n: number; confirmados: number }>()
  const rects: ChartRect[] = []
  // a última vela ainda está aberta: não conta como saída dos presos
  const fechadas = velas.slice(0, -1)
  for (const e of evs) {
    if (e.confirmado === false) continue
    const comprador = e.lado === 'compradores'
    const nivel = e.preco + FAIXA_FOOTPRINT_USD / 2
    const bloco = velas.filter((v) => v.t >= e.ts && v.t < e.ts + passo)
    let tSeta: number
    if (bloco.length) {
      const tocaram = bloco.filter((v) => v.l <= e.preco + FAIXA_FOOTPRINT_USD && v.h >= e.preco)
      const alvo = (tocaram.length ? tocaram : bloco).reduce((m, v) => (comprador ? (v.h > m.h ? v : m) : (v.l < m.l ? v : m)))
      tSeta = alvo.t
      if (bloco.length > 1) {
        rects.push({ from: bloco[0].t, to: bloco[bloco.length - 1].t + tf, top: Math.max(...bloco.map((v) => v.h)),
                     bottom: Math.min(...bloco.map((v) => v.l)), color: 'rgba(245,192,74,0.07)' })
      }
    } else {
      tSeta = Math.floor(e.ts / tf) * tf
    }
    // uma seta por vela: em 4h ou 1D vários presos de 5 min caem na mesma vela
    const s = setas.get(tSeta) ?? { side: comprador ? 'sell' as const : 'buy' as const, n: 0, confirmados: 0 }
    s.n += 1
    if (e.confirmado) s.confirmados += 1
    setas.set(tSeta, s)
    // a saída só conta depois que o bloco fechou (antes disso o preso ainda nem existe)
    const saiu = fechadas.find((v) => v.t >= e.ts + passo && (comprador ? v.c > nivel : v.c < nivel))
    const ultima = velas.length ? velas[velas.length - 1].t + tf : e.ts + passo
    const meia = nivel * 0.00012
    rects.push({ from: tSeta, to: Math.min(saiu ? saiu.t : ultima, Math.max(e.ts + passo * 6, tSeta + tf)), top: nivel + meia,
                 bottom: nivel - meia, color: e.confirmado ? 'rgba(245,192,74,0.85)' : 'rgba(245,192,74,0.45)' })
  }
  const markers: ChartMarker[] = [...setas.entries()].map(([time, s]) => ({
    time, side: s.side, text: `${s.confirmados ? 'presos' : 'presos?'}${s.n > 1 ? ` ×${s.n}` : ''}`,
  }))
  return { markers, rects }
}
