/** Converte respostas da API em overlays do PriceChart. */
import type { Candle, Cenario, NiveisResp, Pivot, Posicao } from '../api/types'
import type { ChartLabel, ChartLevel, ChartMarker, ChartPath, ChartProfile, ChartRect } from './chart-tipos'
import { preco } from './format'

export const GR = '#34d399', RD = '#f87171', AM = '#fbbf24', CY = '#22d3ee', MU = '#8a98a8', MU2 = '#9aa8b8', DIM = '#3b4b60'

/** ZigZag (pivôs) + rótulos de onda do cenário primário. */
export function overlaysElliott(g: { pivots?: Pivot[]; primario?: Cenario | null } | undefined, precoAtual: number | undefined, tsAtual: number | undefined): { paths: ChartPath[]; labels: ChartLabel[]; levels: ChartLevel[] } {
  if (!g) return { paths: [], labels: [], levels: [] }
  const pts = (g.pivots || []).map((p) => ({ time: Math.floor(p.ts / 1000), value: p.preco }))
  if (precoAtual && tsAtual) pts.push({ time: tsAtual, value: precoAtual })
  const paths: ChartPath[] = pts.length >= 2 ? [{ id: 'zigzag', points: pts, color: CY, width: 1, dashed: true }] : []
  const labels: ChartLabel[] = []
  const prim = g.primario
  if (prim?.ondas?.length) {
    for (const o of prim.ondas) {
      if (o.ts_fim && Number.isFinite(o.fim)) labels.push({ time: Math.floor(o.ts_fim / 1000), price: o.fim, text: o.rotulo, color: prim.vies === 'bull' ? CY : AM })
    }
  }
  const levels: ChartLevel[] = []
  if (prim?.invalidacao) levels.push({ price: prim.invalidacao, label: 'invalidação', color: RD, dashed: true })
  ;(prim?.alvos || []).slice(0, 3).forEach((a, i) => levels.push({ price: a, label: `alvo ${i + 1}`, color: GR, dashed: true }))
  return { paths, labels, levels }
}

/** Níveis institucionais (POC/VAH/VAL, VWAP e bandas) e order blocks como retângulos. */
export function overlaysNiveis(n: NiveisResp | undefined, ate: number | undefined): { levels: ChartLevel[]; rects: ChartRect[]; profile: ChartProfile | null; vpProfile: ChartProfile | null } {
  if (!n) return { levels: [], rects: [], profile: null, vpProfile: null }
  const levels: ChartLevel[] = []
  if (n.tpo) {
    levels.push({ price: n.tpo.POC, label: 'POC', color: AM })
    levels.push({ price: n.tpo.VAH, label: 'VAH', color: AM, dashed: true })
    levels.push({ price: n.tpo.VAL, label: 'VAL', color: AM, dashed: true })
  }
  if (n.vwap?.vwap) {
    levels.push({ price: n.vwap.vwap, label: 'VWAP', color: MU2 })
    if (n.vwap.banda_sup) levels.push({ price: n.vwap.banda_sup, label: '+1σ', color: DIM, dashed: true })
    if (n.vwap.banda_inf) levels.push({ price: n.vwap.banda_inf, label: '−1σ', color: DIM, dashed: true })
  }
  const rects: ChartRect[] = []
  const obs = [...(n.order_blocks?.bullish || []).map((b) => ({ ...b, _t: 'bullish' })), ...(n.order_blocks?.bearish || []).map((b) => ({ ...b, _t: 'bearish' }))]
  for (const b of obs.slice(-8)) {
    const zona = b.zona
    const lo = zona ? Math.min(...zona) : (b.fundo ?? b.preco * 0.998), hi = zona ? Math.max(...zona) : (b.topo ?? b.preco * 1.002)
    const from = b.timestamp ? Math.floor(b.timestamp / 1000) : (ate ?? 0)
    const c = b._t === 'bullish' ? GR : RD
    rects.push({ from, to: null, top: hi, bottom: lo, color: c + '1a', border: c + '59' })
  }
  const profile: ChartProfile | null = n.tpo?.perfil?.length ? { rows: n.tpo.perfil, poc: n.tpo.POC, vah: n.tpo.VAH, val: n.tpo.VAL, color: CY } : null
  const vpProfile: ChartProfile | null = n.volume_profile?.perfil?.length ? { rows: n.volume_profile.perfil, poc: n.volume_profile.POC, vah: n.volume_profile.VAH, val: n.volume_profile.VAL, color: AM } : null
  return { levels, rects, profile, vpProfile }
}

function tsSeg(iso: string | null): number | null {
  if (!iso) return null
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z')
  return Number.isNaN(d.getTime()) ? null : Math.floor(d.getTime() / 1000)
}

/** Entradas e saídas das posições, ancoradas no candle mais próximo. */
export function marcadoresPosicoes(pos: Posicao[] | undefined, candles: Candle[]): ChartMarker[] {
  if (!pos?.length || !candles.length) return []
  const times = candles.map((c) => c.time)
  const snap = (t: number) => { let m = times[0]; for (const x of times) { if (x <= t) m = x; else break }; return m }
  const out: ChartMarker[] = []
  for (const p of pos) {
    const t0 = tsSeg(p.aberto_em)
    if (t0 && t0 >= times[0]) out.push({ time: snap(t0), side: p.direcao, text: `${p.direcao === 'buy' ? 'compra' : 'venda'} ${preco(p.preco_entrada)}` })
    const t1 = tsSeg(p.fechado_em)
    if (t1 && t1 >= times[0]) out.push({ time: snap(t1), side: 'exit', text: `saída ${preco(p.preco_saida)}${p.pnl !== null ? ` (${p.pnl >= 0 ? '+' : ''}${preco(p.pnl)})` : ''}` })
  }
  return out
}
