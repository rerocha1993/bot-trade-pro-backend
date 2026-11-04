/**
 * Os painéis de baixo do gráfico, como os do TRDR, cada um mostrando UMA coisa e dizendo o que ela quer dizer agora:
 * a distorção (preço para um lado, alavancados apostando no outro), o CVD alavancado e o à vista, o open interest,
 * o saldo do livro à vista e do alavancado (compra − venda), as liquidações e o funding. Cada série tem um valor por
 * vela do gráfico de cima (`tempos`; null = sem dado), para ficar alinhada, e o painel segue o arrasto de lá (`range`).
 *
 * São dados do BTC (livro da Coinbase e da Binance, perpétuos de Binance, Bybit e OKX); o servidor guarda até 7 dias,
 * então velas mais antigas que isso ficam em branco.
 */
import type { LogicalRange } from 'lightweight-charts'
import { useMemo } from 'react'
import { useFunding, useLiquidacoes, useLivroPerp, useNuvensOverlay, usePosicionamento } from '../../api/hooks'
import type { DistorcaoVela, FluxoLiquidacoes, FundingAgregado, LivroPerp, NuvensOverlay, NuvensPonto, Posicionamento } from '../../api/types'
import { fmt } from '../../lib/format'
import type { ChartMarker } from '../../lib/chart-tipos'
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

const pct = (v: number, casas = 2) => `${v > 0 ? '+' : ''}${fmt(v, casas)}%`
const COR_EX = { binance: '#3d8bfd', bybit: '#f5a623', coinbase: '#7fb3ff' }
type VelaPos = Posicionamento['velas'][number]

/** O que a distorção de uma vela quer dizer, em uma frase. */
function fraseDistorcao(d: DistorcaoVela): string {
  const quem = d.lado === 'alta' ? 'short' : 'long'
  const motivos = [
    d.por.includes('agressao') && d.perp_pct !== null && `o perpétuo ${d.lado === 'alta' ? 'vendeu' : 'comprou'} ${fmt(Math.abs(d.perp_pct), 0)}% do volume a mercado`,
    d.por.includes('contas') && d.contas_pp !== null && `${fmt(Math.abs(d.contas_pp), 1)} p.p. das contas da Binance viraram ${quem}`,
  ].filter(Boolean).join(' e ')
  return `preço ${pct(d.preco_pct)}, ${motivos}, OI ${pct(d.oi_pct ?? 0)}: gente abrindo ${quem} contra ${d.lado === 'alta' ? 'a alta' : 'a queda'}` +
    (d.spot_confirma ? ' · o à vista empurra o preço' : '')
}

/** CVD de uma fonte: soma de (compra − venda) vela a vela, desde a primeira vela em que ela aparece. */
function cvd(tempos: number[], porTs: Map<number, VelaPos>, campo: 'perp_binance' | 'perp_bybit' | 'spot_binance' | 'spot_coinbase') {
  let acc: number | null = null
  return tempos.map((t) => {
    const par = porTs.get(t)?.[campo]
    if (par) acc = (acc ?? 0) + par[0] - par[1]
    return acc
  })
}

/** Os painéis do posicionamento (GET /api/fluxo/posicionamento): distorção, CVD alavancado e à vista, open interest. */
export function paineisPosicionamento(tempos: number[], pos: Posicionamento | undefined): Painel[] {
  if (!pos || !pos.velas.length) return []
  const porTs = new Map(pos.velas.map((v) => [v.ts, v]))
  const lim = pos.limites
  const janela = lim.janela_velas
  const saida: Painel[] = []

  // 1) distorção: barra para cima = de alta (gente vendida contra a alta), para baixo = de baixa; dupla com os dois motivos
  const dist = tempos.map((t) => porTs.get(t)?.distorcao ?? null)
  const recente = pos.velas.slice(-janela).reverse().find((v) => v.distorcao?.lado)
  const ultima = pos.velas[pos.velas.length - 1].distorcao
  const leituraDist: Leitura = recente?.distorcao
    ? { texto: `${recente.distorcao.lado === 'alta' ? 'DE ALTA' : 'DE BAIXA'} às ${hhmm(recente.ts)} UTC: ${fraseDistorcao(recente.distorcao)}`,
        cor: recente.distorcao.lado === 'alta' ? COR.bids : COR.asks }
    : { texto: ultima ? `agora sem distorção · preço ${pct(ultima.preco_pct)}, perpétuo ${pct(ultima.perp_pct ?? 0, 0)} do volume, OI ${pct(ultima.oi_pct ?? 0)}` : 'agora sem distorção', cor: NEUTRO }
  saida.push({
    titulo: `Distorção: o preço vai para um lado e os alavancados apostam no outro (janela de ${janela} velas)`,
    explica: `verde para cima = de alta: o preço subiu (≥ ${fmt(lim.preco_pct ?? 0, 2)}%), o OI subiu e os alavancados ficaram vendidos ` +
      `(perpétuo vendendo ≥ ${fmt(lim.perp_pct ?? 0, 1)}% do volume, ou ≥ ${fmt(lim.contas_pp ?? 0, 2)} p.p. das contas da Binance indo para short): combustível para alta forçada; ` +
      'vermelho para baixo = o espelho; barra dupla = os dois motivos; cor forte = o à vista empurra o preço · leitura para o olho, não medida contra sorteio',
    leitura: leituraDist, formato: (v) => (v > 0 ? `alta ×${v}` : v < 0 ? `baixa ×${-v}` : '0'), height: 70,
    series: [{ id: 'dist', tipo: 'barra', cor: VERDE,
               valores: dist.map((d) => (d?.lado ? (d.lado === 'alta' ? 1 : -1) * d.por.length : null)),
               cores: dist.map((d) => (!d?.lado ? null : d.lado === 'alta' ? (d.spot_confirma ? COR.bids : 'rgba(46,204,132,0.5)')
                                                                           : (d.spot_confirma ? COR.asks : 'rgba(240,84,79,0.5)'))) }],
  })

  // 2) CVD alavancado e à vista
  const leituraCvd = (nome: string, vals: (number | null)[]): Leitura | null => {
    const ok = vals.filter((v): v is number => v !== null)
    if (ok.length <= janela) return null
    const d = ok[ok.length - 1] - ok[ok.length - 1 - janela]
    return { texto: `${nome}, últimas ${janela} velas: ${d >= 0 ? 'comprou' : 'vendeu'} ${absK(Math.abs(d))} BTC a mercado no saldo`, cor: d >= 0 ? COR.bids : COR.asks }
  }
  const perpB = cvd(tempos, porTs, 'perp_binance'), perpY = cvd(tempos, porTs, 'perp_bybit')
  saida.push({
    titulo: 'CVD alavancado: compra − venda a mercado nos perpétuos, somado (BTC)', formato: FMT_BTC, height: 90,
    explica: 'azul = Binance, laranja = Bybit (do nosso coletor) · subindo = alavancados comprando a mercado; preço subindo com o CVD caindo = vendidos entrando contra a alta',
    leitura: leituraCvd('Binance', perpB) ?? undefined,
    series: [{ id: 'binance', tipo: 'linha', cor: COR_EX.binance, largura: 2, valores: perpB },
             { id: 'bybit', tipo: 'linha', cor: COR_EX.bybit, largura: 1, valores: perpY }],
  })
  const spotB = cvd(tempos, porTs, 'spot_binance'), spotC = cvd(tempos, porTs, 'spot_coinbase')
  saida.push({
    titulo: 'CVD à vista: compra − venda a mercado no spot, somado (BTC)', formato: FMT_BTC, height: 90,
    explica: 'azul = Binance, azul-claro = Coinbase (do nosso coletor, desde 20/10) · o à vista é quem compra o BTC de verdade, sem alavancagem',
    leitura: (leituraCvd('Coinbase', spotC) ?? leituraCvd('Binance à vista', spotB)) ?? undefined,
    series: [{ id: 'binance', tipo: 'linha', cor: COR_EX.binance, largura: 1, valores: spotB },
             { id: 'coinbase', tipo: 'linha', cor: COR_EX.coinbase, largura: 2, valores: spotC }],
  })

  // 3) open interest: quanto entrou (verde) ou saiu (vermelho) em cada vela, nas corretoras que têm as duas pontas
  const variacao = tempos.map((t, i) => {
    const a = i > 0 ? porTs.get(tempos[i - 1]) : undefined, b = porTs.get(t)
    if (!a || !b) return null
    const exs = (['binance', 'bybit', 'okx'] as const).filter((ex) => a.oi[ex] !== null && b.oi[ex] !== null)
    return exs.length ? exs.reduce((s, ex) => s + (b.oi[ex] as number) - (a.oi[ex] as number), 0) : null
  })
  const ultOi = [...pos.velas].reverse().find((v) => v.oi_total !== null)
  const dOi = ultima?.oi_pct ?? null
  saida.push({
    titulo: 'Open interest: contratos abertos entrando e saindo (Binance + Bybit + OKX, BTC)', formato: FMT_BTC, height: 80,
    explica: 'verde = o OI subiu na vela (gente nova abrindo posição), vermelho = caiu (fechando ou liquidada)' +
      (ultOi?.oi_total ? ` · total agora ${absK(ultOi.oi_total)} BTC` : ''),
    leitura: dOi === null ? undefined
      : { texto: `últimas ${janela} velas: OI ${pct(dOi)} · ${dOi > 0 ? 'gente abrindo posição' : 'gente fechando posição'}`, cor: dOi > 0 ? COR.bids : COR.asks },
    series: [{ id: 'doi', tipo: 'barra', cor: VERDE, valores: variacao, cores: variacao.map((v) => (v === null ? null : v >= 0 ? VERDE : VERMELHO)) }],
  })
  return saida
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
/** Onde os pedidos dos painéis começam: na primeira vela carregada, mas no máximo 7 dias atrás (arredondado à vela, para
 *  não mudar a cada render). A tela usa o mesmo início para as marcas da distorção e reaproveita o pedido. */
export const inicioPaineis = (tempos: number[], passo: number) =>
  tempos.length ? Math.max(tempos[0], Math.floor((Date.now() / 1000 - JANELA_S) / passo) * passo + passo) : null

/** Setas da distorção no gráfico de preço: verde embaixo = de alta, vermelha em cima = de baixa; só na primeira vela de
 *  cada sequência, para não encher o gráfico. */
export function marcasDistorcao(pos: Posicionamento | undefined): ChartMarker[] {
  const saida: ChartMarker[] = []
  let anterior: string | null = null
  for (const v of pos?.velas ?? []) {
    const lado = v.distorcao?.lado ?? null
    if (lado && lado !== anterior) {
      saida.push({ time: v.ts, side: lado === 'alta' ? 'buy' : 'sell', color: lado === 'alta' ? COR.bids : COR.asks,
                   text: `D${v.distorcao!.por.length > 1 ? '×2' : ''}` })
    }
    anterior = lado
  }
  return saida
}

export default function PaineisFluxo({ tempos, range, passo }: { tempos: number[]; range: LogicalRange | null; passo: number }) {
  const inicio = inicioPaineis(tempos, passo)
  const qLivro = useNuvensOverlay(inicio, 'coinbase,binance', passo)
  const qPerp = useLivroPerp(inicio, passo)
  const qLiq = useLiquidacoes(inicio, passo)
  const qFunding = useFunding()
  const qPos = usePosicionamento(inicio, passo)
  const paineis = useMemo(() => [...paineisPosicionamento(tempos, qPos.data), ...paineisDeBaixo(tempos, qLivro.data, qPerp.data, qLiq.data, qFunding.data)],
    [tempos, qPos.data, qLivro.data, qPerp.data, qLiq.data, qFunding.data])
  const carregando = qLivro.isPending || qPerp.isPending || qLiq.isPending || qFunding.isPending || qPos.isPending
  return (
    <div className="gpaineis">
      {paineis.map((p) => <SubChart key={p.titulo} {...p} tempos={tempos} range={range} />)}
      {carregando && <div className="muted" style={{ fontSize: 12, padding: '8px 0' }}>lendo distorção, CVD, open interest, livro, liquidações e funding…</div>}
    </div>
  )
}
