/**
 * Os painéis de baixo do gráfico, como os do TRDR, cada um mostrando UMA coisa e dizendo o que ela quer dizer agora:
 * o saldo do livro à vista e do alavancado (compra − venda), as liquidações e o funding. Cada série tem um valor por
 * vela do gráfico de cima (`tempos`; null = sem dado), para ficar alinhada, e o painel segue o arrasto de lá (`range`).
 *
 * São dados do BTC (livro da Coinbase e da Binance, perpétuos de Binance, Bybit e OKX); o servidor guarda até 7 dias,
 * então velas mais antigas que isso ficam em branco.
 */
import type { LogicalRange } from 'lightweight-charts'
import { useMemo } from 'react'
import { useFunding, useLiquidacoes, useLivroPerp, useNuvensOverlay } from '../../api/hooks'
import type { FluxoLiquidacoes, FundingAgregado, LivroPerp, NuvensOverlay, NuvensPonto } from '../../api/types'
import { fmt } from '../../lib/format'
import SubChart, { type SerieSub } from './SubChart'

const COR = { bids: '#2ecc84', asks: '#f0544f' }
const absK = (v: number) => { const a = Math.abs(v); return a >= 1e6 ? `${(a / 1e6).toFixed(1)}M` : a >= 1e3 ? `${(a / 1e3).toFixed(0)}k` : a.toFixed(0) }
const FMT_BTC = (v: number) => `${v < 0 ? '−' : '+'}${absK(v)}`
const FMT_USD = (v: number) => `$${absK(v)}`
const FMT_FUNDING = (v: number) => `${v.toFixed(3)}%`
const VERDE = 'rgba(46,204,132,0.8)', VERMELHO = 'rgba(240,84,79,0.8)', NEUTRO = '#8b95a5'
const FUNDING_ALTO = 0.03          // % a cada 8 h: acima disso os comprados estão pagando caro
const UMA_HORA = 3600
const hhmm = (s: number) => new Date(s * 1000).toISOString().slice(11, 16)
/** o servidor guarda e devolve até 7 dias de livro e de liquidações */
const JANELA_S = 7 * 86400 - 120
/** o livro dos perpétuos e as liquidações vão até velas de 4 h */
export const PASSO_MAX_PAINEIS = 14400

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

export function paineisDeBaixo(tempos: number[], livro: NuvensOverlay | undefined, perp: LivroPerp | undefined, liq: FluxoLiquidacoes | undefined,
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

/** Os painéis de baixo da tela Gráfico: busca o que falta e desenha um SubChart por painel, alinhado às velas. */
export default function PaineisFluxo({ tempos, range, passo }: { tempos: number[]; range: LogicalRange | null; passo: number }) {
  // o pedido começa na primeira vela carregada, mas no máximo 7 dias atrás (arredondado à vela, para não mudar a cada render)
  const inicio = tempos.length ? Math.max(tempos[0], Math.floor((Date.now() / 1000 - JANELA_S) / passo) * passo + passo) : null
  const qLivro = useNuvensOverlay(inicio, 'coinbase,binance', passo)
  const qPerp = useLivroPerp(inicio, passo)
  const qLiq = useLiquidacoes(inicio, passo)
  const qFunding = useFunding()
  const paineis = useMemo(() => paineisDeBaixo(tempos, qLivro.data, qPerp.data, qLiq.data, qFunding.data),
    [tempos, qLivro.data, qPerp.data, qLiq.data, qFunding.data])
  const carregando = qLivro.isPending || qPerp.isPending || qLiq.isPending || qFunding.isPending
  return (
    <div className="gpaineis">
      {paineis.map((p) => <SubChart key={p.titulo} {...p} tempos={tempos} range={range} />)}
      {carregando && <div className="muted" style={{ fontSize: 12, padding: '8px 0' }}>lendo livro, liquidações e funding…</div>}
    </div>
  )
}
