/**
 * Os painéis de baixo do gráfico, cada um mostrando UMA coisa e dizendo o que ela quer dizer agora. A ordem é a do MMT
 * que o Maroja usa (live de 04/11/2026): a distorção, o CVD e o OI do LINEAR (perpétuo em USDT), as liquidações, o CVD e
 * o OI do INVERSE (perpétuo em USD margeado em BTC), o Net Positioning (longs × shorts abertos), o CVD à vista (a
 * Coinbase tem de acompanhar a alta para ela ser saudável), o saldo do livro à vista e do alavancado e o funding.
 * O OI vem em velas, como lá: branca = entrou contrato, colorida = saiu. Cada série tem um valor por
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
/** as cores do MMT: CVD linear amarelo, inverse azul; vela do OI branca quando sobe */
const AMARELO = '#f0d43a', AZUL = '#3d8bfd', AZUL_CLARO = '#7fd0ff', LARANJA = '#f5a623', BRANCO = '#e8ecf2'
const absK = (v: number) => { const a = Math.abs(v); return a >= 1e6 ? `${(a / 1e6).toFixed(1)}M` : a >= 1e3 ? `${(a / 1e3).toFixed(0)}k` : a.toFixed(0) }
const FMT_BTC = (v: number) => `${v < 0 ? '−' : '+'}${absK(v)}`
const FMT_USD = (v: number) => `$${absK(v)}`
const FMT_FUNDING = (v: number) => `${v.toFixed(3)}%`
const FMT_QTD = (v: number) => absK(v)
const VERDE = 'rgba(46,204,132,0.8)', VERMELHO = 'rgba(240,84,79,0.8)', NEUTRO = '#8b95a5'
const FUNDING_ALTO = 0.03          // % a cada 8 h: acima disso os comprados estão pagando caro
const UMA_HORA = 3600
const hhmm = (s: number) => new Date(s * 1000).toISOString().slice(11, 16)
/** o servidor guarda e devolve até 7 dias de livro e de liquidações */
const JANELA_S = 7 * 86400 - 120
/** o livro dos perpétuos e as liquidações vão até velas de 4 h */
export const PASSO_MAX_PAINEIS = 14400

type Leitura = { texto: string; cor: string }
/** `ordem`: a posição na pilha de painéis (a do MMT); os dois grupos de painéis se intercalam por ela */
type Painel = { titulo: string; explica: string; leitura?: Leitura; series: SerieSub[]; formato: (v: number) => string; height?: number; ordem: number }

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
  return { titulo, explica, leitura, formato: FMT_BTC, height: 90, ordem: 0,
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
type CampoCvd = 'perp_binance' | 'perp_bybit' | 'spot_binance' | 'spot_coinbase' | 'inv_binance' | 'inv_bybit'
function cvd(tempos: number[], porTs: Map<number, VelaPos>, campo: CampoCvd) {
  let acc: number | null = null
  return tempos.map((t) => {
    const par = porTs.get(t)?.[campo]
    if (par) acc = (acc ?? 0) + par[0] - par[1]
    return acc
  })
}

/** Saldo a mercado (compra − venda) das fontes de um grupo nas últimas ``n`` velas; null se nenhuma tiver dado. */
function saldoRecente(velas: VelaPos[], campos: CampoCvd[], n: number): number | null {
  let soma: number | null = null
  for (const v of velas.slice(-n)) for (const c of campos) { const par = v[c]; if (par) soma = (soma ?? 0) + par[0] - par[1] }
  return soma
}

/** A leitura do Maroja para OI × CVD nas últimas ``n`` velas: quem entrou ou saiu (OI) e de que lado agrediram (CVD). */
function leituraOi(velas: VelaPos[], oi: 'oi_lin' | 'oi_inv', campos: CampoCvd[], n: number, escala: number): Leitura | undefined {
  const com = velas.slice(-n).filter((v) => v[oi])
  const saldo = saldoRecente(velas, campos, n)
  if (com.length < 2 || saldo === null) return undefined
  const dOi = (com[com.length - 1][oi]![3] - com[0][oi]![0]) / escala
  const oiTxt = `OI ${dOi >= 0 ? '+' : '−'}${absK(Math.abs(dOi))}`, cvdTxt = `${saldo >= 0 ? 'compraram' : 'venderam'} ${absK(Math.abs(saldo))} a mercado`
  const base = `últimas ${n} velas: ${oiTxt} e ${cvdTxt}`
  if (dOi >= 0) return saldo < 0
    ? { texto: `${base} · shorts abrindo (no fundo, se o preço segura, ficam presos)`, cor: COR.asks }
    : { texto: `${base} · longs abrindo (no topo, se o preço não passa, ficam presos)`, cor: COR.bids }
  return saldo >= 0
    ? { texto: `${base} · shorts fechando (stop, liquidação ou realização), não é long novo`, cor: NEUTRO }
    : { texto: `${base} · longs fechando (stop, liquidação ou realização), não é short novo`, cor: NEUTRO }
}

/** Os painéis do posicionamento (GET /api/fluxo/posicionamento): distorção, CVD e OI do linear e do inverse, Net
 *  Positioning e CVD à vista. */
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
    leitura: leituraDist, formato: (v) => (v > 0 ? `alta ×${v}` : v < 0 ? `baixa ×${-v}` : '0'), height: 70, ordem: 10,
    series: [{ id: 'dist', tipo: 'barra', cor: VERDE,
               valores: dist.map((d) => (d?.lado ? (d.lado === 'alta' ? 1 : -1) * d.por.length : null)),
               cores: dist.map((d) => (!d?.lado ? null : d.lado === 'alta' ? (d.spot_confirma ? COR.bids : 'rgba(46,204,132,0.5)')
                                                                           : (d.spot_confirma ? COR.asks : 'rgba(240,84,79,0.5)'))) }],
  })

  // 2) CVD do linear (amarelo, a Bybit como no MMT) e do inverse (azul); 3) OI de cada um em velas
  const leituraCvd = (nome: string, vals: (number | null)[]): Leitura | null => {
    const ok = vals.filter((v): v is number => v !== null)
    if (ok.length <= janela) return null
    const d = ok[ok.length - 1] - ok[ok.length - 1 - janela]
    return { texto: `${nome}, últimas ${janela} velas: ${d >= 0 ? 'comprou' : 'vendeu'} ${absK(Math.abs(d))} BTC a mercado no saldo`, cor: d >= 0 ? COR.bids : COR.asks }
  }
  const velas = pos.velas
  const precoAgora = velas[velas.length - 1].fechamento
  const perpB = cvd(tempos, porTs, 'perp_binance'), perpY = cvd(tempos, porTs, 'perp_bybit')
  saida.push({
    titulo: 'CVD linear: compra − venda a mercado no perpétuo em USDT, somado (BTC)', formato: FMT_BTC, height: 90, ordem: 20,
    explica: 'amarelo = Bybit (do nosso coletor), azul = Binance · caindo com o OI subindo = shorts entrando; subindo com o OI caindo = shorts saindo',
    leitura: leituraCvd(perpY.some((v) => v !== null) ? 'Bybit' : 'Binance', perpY.some((v) => v !== null) ? perpY : perpB) ?? undefined,
    series: [{ id: 'binance', tipo: 'linha', cor: AZUL, largura: 1, valores: perpB },
             { id: 'bybit', tipo: 'linha', cor: AMARELO, largura: 2, valores: perpY }],
  })
  const oiLin = tempos.map((t) => porTs.get(t)?.oi_lin ?? null)
  const ultLin = [...velas].reverse().find((v) => v.oi_lin)?.oi_lin
  saida.push({
    titulo: 'Open interest linear: contratos abertos no perpétuo em USDT (Binance + Bybit, BTC)', formato: FMT_QTD, height: 90, ordem: 30,
    explica: 'vela branca = entrou contrato (gente abrindo posição), laranja = saiu (fechando, stop ou liquidação)' +
      (ultLin ? ` · total agora ${absK(ultLin[3])} BTC` : ''),
    leitura: leituraOi(velas, 'oi_lin', ['perp_binance', 'perp_bybit'], janela, 1),
    series: [{ id: 'oi', tipo: 'vela', cor: BRANCO, corBaixa: LARANJA, valores: oiLin.map((v) => v?.[3] ?? null), velas: oiLin }],
  })
  const invB = cvd(tempos, porTs, 'inv_binance'), invY = cvd(tempos, porTs, 'inv_bybit')
  saida.push({
    titulo: 'CVD inverse: compra − venda a mercado no perpétuo em USD margeado em BTC, somado (BTC)', formato: FMT_BTC, height: 90, ordem: 50,
    explica: 'azul = Binance (COIN-M), azul-claro = Bybit (do nosso coletor, desde 04/11) · é onde o Maroja viu os shorts presos no fundo de 04/11',
    leitura: leituraCvd('Binance inverse', invB) ?? undefined,
    series: [{ id: 'binance', tipo: 'linha', cor: AZUL, largura: 2, valores: invB },
             { id: 'bybit', tipo: 'linha', cor: AZUL_CLARO, largura: 1, valores: invY }],
  })
  // o inverse vem em dólares: divide pelo preço de agora (a forma é a dos contratos, sem andar com o preço)
  const oiInv = tempos.map((t) => { const v = porTs.get(t)?.oi_inv; return v ? (v.map((x) => x / precoAgora) as [number, number, number, number]) : null })
  const ultInv = [...velas].reverse().find((v) => v.oi_inv)?.oi_inv
  saida.push({
    titulo: 'Open interest inverse: contratos abertos no perpétuo margeado em BTC (Binance + Bybit, BTC)', formato: FMT_QTD, height: 90, ordem: 60,
    explica: 'vela branca = entrou contrato, azul = saiu · em BTC ao preço de agora' + (ultInv ? ` · total agora ${absK(ultInv[3] / precoAgora)} BTC ($${absK(ultInv[3])})` : ''),
    leitura: leituraOi(velas, 'oi_inv', ['inv_binance', 'inv_bybit'], janela, precoAgora),
    series: [{ id: 'oi', tipo: 'vela', cor: BRANCO, corBaixa: AZUL, valores: oiInv.map((v) => v?.[3] ?? null), velas: oiInv }],
  })

  // 4) Net Positioning: longs e shorts abertos somados desde a primeira vela (linear + inverse)
  let nl: number | null = null, ns: number | null = null
  const longs: (number | null)[] = [], shorts: (number | null)[] = []
  for (const t of tempos) {
    const np = porTs.get(t)?.np
    if (np) for (const g of [np.lin, np.inv]) if (g) { nl = (nl ?? 0) + g[0]; ns = (ns ?? 0) + g[1] }
    longs.push(nl); shorts.push(ns)
  }
  let leituraNp: Leitura | undefined
  const recentes = velas.slice(-janela).flatMap((v) => (v.np ? [v.np.lin, v.np.inv] : [])).filter((g): g is [number, number] => !!g)
  if (recentes.length) {
    const L = recentes.reduce((a, g) => a + g[0], 0), S = recentes.reduce((a, g) => a + g[1], 0)
    const f = (v: number) => `${v >= 0 ? '+' : '−'}${absK(Math.abs(v))}`
    leituraNp = { texto: `últimas ${janela} velas: longs ${f(L)}, shorts ${f(S)} BTC · ${S > L ? 'entrou mais short' : L > S ? 'entrou mais long' : 'equilibrado'}`,
                  cor: S > L ? COR.asks : L > S ? COR.bids : NEUTRO }
  }
  saida.push({
    titulo: 'Net Positioning: longs e shorts abertos (linear + inverse, BTC, estimativa)', formato: FMT_BTC, height: 90, ordem: 70,
    explica: 'verde = longs, vermelho = shorts · em cada vela o OI que entrou vai para quem agrediu (subiu e compraram = long; subiu e venderam = short) ' +
      'e o que saiu sai de quem fechou (caiu e compraram = short fechando) · a corretora não diz quem abriu: é a mesma conta das plataformas',
    leitura: leituraNp,
    series: [{ id: 'longs', tipo: 'linha', cor: COR.bids, largura: 2, valores: longs },
             { id: 'shorts', tipo: 'linha', cor: COR.asks, largura: 2, valores: shorts }],
  })

  // 5) CVD à vista: a Coinbase acompanhando o preço é o que separa tendência de squeeze
  const spotB = cvd(tempos, porTs, 'spot_binance'), spotC = cvd(tempos, porTs, 'spot_coinbase')
  let leituraSpot = leituraCvd('Coinbase', spotC) ?? leituraCvd('Binance à vista', spotB) ?? undefined
  const sc = saldoRecente(velas, ['spot_coinbase'], janela)
  if (sc !== null && velas.length > janela) {
    const dp = precoAgora - velas[velas.length - 1 - janela].fechamento
    leituraSpot = (dp >= 0) === (sc >= 0)
      ? { texto: `últimas ${janela} velas: a Coinbase ${sc >= 0 ? 'comprou' : 'vendeu'} ${absK(Math.abs(sc))} BTC junto com o preço · o à vista acompanha`, cor: sc >= 0 ? COR.bids : COR.asks }
      : dp >= 0
        ? { texto: `últimas ${janela} velas: o preço subiu e a Coinbase vendeu ${absK(Math.abs(sc))} BTC · o à vista não acompanha a alta (pode ser só squeeze)`, cor: NEUTRO }
        : { texto: `últimas ${janela} velas: o preço caiu e a Coinbase comprou ${absK(Math.abs(sc))} BTC · o à vista compra no recuo`, cor: NEUTRO }
  }
  saida.push({
    titulo: 'CVD à vista: compra − venda a mercado no spot, somado (BTC)', formato: FMT_BTC, height: 90, ordem: 80,
    explica: 'azul-claro = Coinbase (do nosso coletor, desde 20/10), azul = Binance · alta saudável é a Coinbase comprando junto, ao longo do tempo; sem ela, a alta pode ser só squeeze',
    leitura: leituraSpot,
    series: [{ id: 'binance', tipo: 'linha', cor: COR_EX.binance, largura: 1, valores: spotB },
             { id: 'coinbase', tipo: 'linha', cor: COR_EX.coinbase, largura: 2, valores: spotC }],
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
    saida.push({ ...painelSaldo('Livro à vista: quem está esperando (Coinbase + Binance, até 5% do preço)',
      'barra verde = mais ordens de compra paradas do que de venda; vermelha = mais venda; o número é a diferença em BTC',
      tempos, (t) => { const p = porTs.get(t); return p ? { b: soma(p, 'bids'), a: soma(p, 'asks') } : null }), ordem: 90 })
  }
  if (perp) {
    const porTs = new Map(perp.velas.map((v) => [v.ts, v]))
    saida.push({ ...painelSaldo(`Livro alavancado: quem está esperando (perpétuos Binance + Bybit + OKX, até ${fmt(perp.faixa_pct * 100, 1)}%)`,
      perp.velas.length ? `o mesmo, nos perpétuos; só até ${fmt(perp.faixa_pct * 100, 1)}% do preço, o mais fundo que as corretoras liberam de graça`
        : 'gravando desde agora: o histórico vai enchendo enquanto o coletor estiver aberto',
      tempos, (t) => { const v = porTs.get(t); return v ? { b: v.bids, a: v.asks } : null }), ordem: 100 })
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
      titulo: 'Liquidações: alavancados fechados à força (Bybit linear e inverse + OKX)', formato: FMT_USD, height: 90, leitura, ordem: 40,
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
      titulo: 'Funding: quanto o comprado paga ao vendido a cada 8 h', formato: FMT_FUNDING, height: 90, leitura, ordem: 110,
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
  const paineis = useMemo(() => [...paineisPosicionamento(tempos, qPos.data), ...paineisDeBaixo(tempos, qLivro.data, qPerp.data, qLiq.data, qFunding.data)]
    .sort((a, b) => a.ordem - b.ordem),
    [tempos, qPos.data, qLivro.data, qPerp.data, qLiq.data, qFunding.data])
  const carregando = qLivro.isPending || qPerp.isPending || qLiq.isPending || qFunding.isPending || qPos.isPending
  return (
    <div className="gpaineis">
      {paineis.map((p) => <SubChart key={p.titulo} {...p} tempos={tempos} range={range} />)}
      {carregando && <div className="muted" style={{ fontSize: 12, padding: '8px 0' }}>lendo distorção, CVD, open interest, livro, liquidações e funding…</div>}
    </div>
  )
}

const PERPS: CampoCvd[] = ['perp_binance', 'perp_bybit', 'inv_binance', 'inv_bybit']

/** Os painéis da aba Aggr (o aggr.trade que o Maroja usa na live de 04/11/2026): o prêmio da Coinbase, o CVD dos
 *  perpétuos contra o da Coinbase (cada um na sua escala, como lá) e a compra × venda a mercado de cada mercado por vela. */
export function paineisAggr(tempos: number[], pos: Posicionamento | undefined): Painel[] {
  if (!pos || !pos.velas.length) return []
  const porTs = new Map(pos.velas.map((v) => [v.ts, v]))
  const velas = pos.velas
  const janela = pos.limites.janela_velas
  const saida: Painel[] = []

  // 1) prêmio: Coinbase − Binance em % do preço (o "-0.1" do aggr); negativo = o americano vendendo (ou a Binance comprando mais)
  const premio = tempos.map((t) => { const v = porTs.get(t); return v?.premio == null ? null : 100 * v.premio / v.fechamento })
  const ultP = [...velas].reverse().find((v) => v.premio !== null)
  const usd = (v: number) => `${v < 0 ? '−' : '+'}$${fmt(Math.abs(v), 0)}`
  saida.push({
    titulo: 'COINBASE_PREMIUM: preço da Coinbase − preço da Binance (% do preço)', formato: (v) => `${v > 0 ? '+' : ''}${v.toFixed(3)}%`, height: 80, ordem: 10,
    explica: 'acima de zero (verde) = a Coinbase mais cara: o comprador americano puxando · abaixo (vermelho) = mais barata: o americano vendendo, ou o varejo da Binance comprando',
    leitura: !ultP || ultP.premio === null ? { texto: 'esperando o coletor da Coinbase', cor: NEUTRO }
      : { texto: `agora ${pct(100 * ultP.premio / ultP.fechamento, 3)} (${usd(ultP.premio)}) · ${ultP.premio >= 0 ? 'Coinbase comprando mais que a Binance' : 'Coinbase vendendo mais que a Binance'}`,
          cor: ultP.premio >= 0 ? COR.bids : COR.asks },
    series: [{ id: 'premio', tipo: 'base', cor: VERDE, valores: premio }],
  })

  // 2) CVD dos perpétuos (linear + inverse) × Coinbase. Como no aggr, cada linha na sua régua: aqui as duas vão de 0 a 100
  //    do próprio mínimo ao próprio máximo no período, para caberem juntas; o que conta é a direção (os BTC ficam na leitura)
  let acc: number | null = null
  const perp = tempos.map((t) => {
    const v = porTs.get(t)
    for (const c of PERPS) { const par = v?.[c]; if (par) acc = (acc ?? 0) + par[0] - par[1] }
    return acc
  })
  const coinbase = cvd(tempos, porTs, 'spot_coinbase')
  const regua = (vals: (number | null)[]) => {
    const ok = vals.filter((v): v is number => v !== null)
    const lo = Math.min(...ok), hi = Math.max(...ok)
    return vals.map((v) => (v === null || !ok.length ? null : hi > lo ? (100 * (v - lo)) / (hi - lo) : 50))
  }
  const sp = saldoRecente(velas, PERPS, janela), sc = saldoRecente(velas, ['spot_coinbase'], janela)
  let leituraCvd: Leitura | undefined
  if (sp !== null && sc !== null) {
    const lado = (v: number) => (v >= 0 ? 'comprando' : 'vendendo')
    leituraCvd = (sp >= 0) === (sc >= 0)
      ? { texto: `últimas ${janela} velas: os dois ${lado(sp)} (perpétuos ${absK(Math.abs(sp))}, Coinbase ${absK(Math.abs(sc))} BTC)`, cor: sp >= 0 ? COR.bids : COR.asks }
      : { texto: `últimas ${janela} velas: perpétuos ${lado(sp)} ${absK(Math.abs(sp))} e Coinbase ${lado(sc)} ${absK(Math.abs(sc))} BTC · ` +
          (sp >= 0 ? 'alta só do alavancado, sem o à vista' : 'o à vista comprando enquanto o alavancado vende'), cor: NEUTRO }
  }
  saida.push({
    titulo: 'CVD: PERP × Coinbase (compra − venda a mercado, somado)', formato: () => '', height: 200, ordem: 20,
    explica: 'amarelo PERP = perpétuos (linear + inverse, Binance + Bybit), azul Coinbase = Coinbase à vista · cada linha na sua régua, como no aggr.trade: ' +
      'o que importa é a direção · alta saudável = as duas subindo; só o amarelo subindo = alavancado (squeeze)',
    leitura: leituraCvd,
    series: [{ id: 'perp', tipo: 'linha', cor: AMARELO, largura: 1, valores: regua(perp), etiqueta: 'PERP' },
             { id: 'coinbase', tipo: 'linha', cor: AZUL, largura: 2, valores: regua(coinbase), etiqueta: 'Coinbase' }],
  })

  // 3) compra (para cima) e venda (para baixo) a mercado em cada vela, por mercado
  const mercados: [string, CampoCvd[], number][] = [['Coinbase à vista', ['spot_coinbase'], 30], ['Binance à vista', ['spot_binance'], 40],
                                                      ['Perpétuos (linear + inverse)', PERPS, 50]]
  for (const [nome, campos, ordem] of mercados) {
    const lados = tempos.map((t) => {
      const v = porTs.get(t)
      let c = 0, s = 0, tem = false
      for (const k of campos) { const par = v?.[k]; if (par) { c += par[0]; s += par[1]; tem = true } }
      return tem ? [c, s] : null
    })
    const saldo = saldoRecente(velas, campos, janela)
    saida.push({
      titulo: `${nome}: compra e venda a mercado por vela (BTC)`, formato: FMT_QTD, height: 70, ordem,
      explica: 'branco para cima = compraram a mercado, vermelho para baixo = venderam',
      leitura: saldo === null ? undefined
        : { texto: `últimas ${janela} velas: ${saldo >= 0 ? 'compraram' : 'venderam'} ${absK(Math.abs(saldo))} BTC a mais`, cor: saldo >= 0 ? COR.bids : COR.asks },
      series: [{ id: 'compra', tipo: 'barra', cor: 'rgba(232,236,242,0.75)', valores: lados.map((l) => (l ? l[0] : null)) },
               { id: 'venda', tipo: 'barra', cor: VERMELHO, valores: lados.map((l) => (l ? -l[1] : null)) }],
    })
  }
  return saida
}

/** A aba Aggr: os painéis acima e as liquidações, alinhados às velas do gráfico. ``cima`` = só o prêmio (que no aggr fica
 *  em cima do preço); sem ele, o resto. Os dois pedem os mesmos dados (o react-query reaproveita). */
export function PaineisAggr({ tempos, range, passo, cima = false }: { tempos: number[]; range: LogicalRange | null; passo: number; cima?: boolean }) {
  const inicio = inicioPaineis(tempos, passo)
  const qPos = usePosicionamento(inicio, passo)
  const qLiq = useLiquidacoes(inicio, passo)
  const paineis = useMemo(() => [...paineisAggr(tempos, qPos.data),
                                  ...paineisDeBaixo(tempos, undefined, undefined, qLiq.data, undefined).map((p) => ({ ...p, ordem: 60 }))]
    .filter((p) => (p.ordem < 20) === cima).sort((a, b) => a.ordem - b.ordem), [tempos, qPos.data, qLiq.data, cima])
  return (
    <div className="gpaineis">
      {paineis.map((p) => <SubChart key={p.titulo} {...p} tempos={tempos} range={range} />)}
      {!cima && (qPos.isPending || qLiq.isPending) && <div className="muted" style={{ fontSize: 12, padding: '8px 0' }}>lendo prêmio, CVD, negócios e liquidações…</div>}
    </div>
  )
}
