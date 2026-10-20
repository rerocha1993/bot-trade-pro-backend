import { useMemo, useState } from 'react'
import { useAbsorcao, useCandles, useNuvensCalor, useNuvensTop, usePresos } from '../api/hooks'
import type { CelulaCalor, EventoAbsorcao, EventoPresos, NuvensCalor } from '../api/types'
import PriceChart from '../components/chart/PriceChart'
import { Header, Page } from '../components/Layout'
import { Card, Chip, Empty, Err, Estado, Loading, Seg } from '../components/ui'
import type { ChartLabel, ChartLevel, ChartMarker, ChartRect } from '../lib/chart-tipos'
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
const MODOS = ['absorcao', 'paredes'] as const
const TFS_PRESOS = ['300', '1800'] as const
const hhmm = (s: number) => new Date(s * 1000).toISOString().slice(11, 16)

/** Escala de cor: frio (só acima do normal) → cor do lado → quente (parede muito acima do normal). */
const ESCALA = {
  bids: [[16, 92, 70, 0.30], [46, 204, 132, 0.62], [236, 232, 110, 0.92]],
  asks: [[112, 30, 42, 0.30], [240, 84, 79, 0.62], [255, 196, 92, 0.92]],
} as const
const FRIO = 2, QUENTE = 12

/** 0 no limite de "acima do normal", 1 em 12x ou mais; escala log para 3x e 6x ficarem bem distintos. */
const nivel = (inten: number) => Math.max(0, Math.min(1, Math.log(inten / FRIO) / Math.log(QUENTE / FRIO)))

function corCalor(lado: 0 | 1, inten: number): string {
  const e = lado === 0 ? ESCALA.bids : ESCALA.asks
  const t = nivel(inten)
  const [a, b, u] = t < 0.5 ? [e[0], e[1], t / 0.5] : [e[1], e[2], (t - 0.5) / 0.5]
  const m = (i: number) => a[i] + (b[i] - a[i]) * u
  return `rgba(${m(0).toFixed(0)},${m(1).toFixed(0)},${m(2).toFixed(0)},${m(3).toFixed(3)})`
}

function retangulos(d: NuvensCalor | undefined): ChartRect[] {
  if (!d) return []
  const out: ChartRect[] = []
  d.colunas.forEach((c, i) => {
    const to = i === d.colunas.length - 1 ? null : c.ts + d.passo_s
    for (const [lo, hi, lado, , inten] of c.celulas) out.push({ from: c.ts, to, top: hi, bottom: lo, color: corCalor(lado, inten) })
  })
  return out
}

/** A nuvem de absorção: do momento em que a parede segurou a agressão até ela sair do livro. */
function nuvensAbsorcao(evs: EventoAbsorcao[]): { rects: ChartRect[]; labels: ChartLabel[] } {
  const rects: ChartRect[] = []
  const labels: ChartLabel[] = []
  for (const e of evs) {
    const lado = e.tipo === 'venda' ? 1 : 0
    const forte = Math.max(e.intensidade, 6)
    rects.push({ from: e.ts, to: e.ate_ts, top: e.alto, bottom: e.baixo, color: corCalor(lado, forte), border: lado ? COR.asks : COR.bids })
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
      <span><b style={{ color: COR.asks }}>Nuvem vermelha</b>: compra agressiva e alavancada (delta forte, OI subindo) batendo numa parede de venda {q ? `${fmt(q.criterio.parede_vezes, 0)}x` : ''} acima do normal, e o preço não passou: compradores presos no topo.</span>
      <span><b style={{ color: COR.bids }}>Nuvem verde</b>: o espelho no fundo, venda agressiva segurada por uma parede de compra.</span>
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
  const [lo, hi, lado, btc, inten] = c
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
  const [fator, setFator] = useState<(typeof FATORES)[number]>('2')
  const [mostrarTop, setMostrarTop] = useState(false)
  const [modo, setModo] = useState<(typeof MODOS)[number]>('absorcao')
  const [verPresos, setVerPresos] = useState(true)
  const [tfPresos, setTfPresos] = useState<(typeof TFS_PRESOS)[number]>('1800')
  const exchanges = EXCHANGES.filter((e) => exs[e]).join(',')
  const candles = useCandles('BTCUSDT', '5m', N_CANDLES)
  const dados = candles.data ?? []
  const inicio = dados.length ? dados[0].time : null
  const qCalor = useNuvensCalor(inicio, exchanges, Number(fator), PASSO_S)
  const qAbs = useAbsorcao(inicio)
  const qPresos = usePresos(inicio, Number(tfPresos), verPresos)
  const qTop = useNuvensTop(exchanges)
  const d = qCalor.data
  const top = qTop.data
  const ultimaVela = dados[dados.length - 1]
  const ultimaCol = d?.colunas.length ? d.colunas[d.colunas.length - 1] : null

  const absorcao = useMemo(() => nuvensAbsorcao(qAbs.data?.eventos ?? []), [qAbs.data])
  const presos = useMemo(() => (verPresos ? marcasPresos(qPresos.data?.eventos ?? [], Number(tfPresos)) : { markers: [], rects: [] }), [verPresos, qPresos.data, tfPresos])
  const rects = useMemo(() => [...(modo === 'paredes' ? retangulos(d) : absorcao.rects), ...presos.rects], [modo, d, absorcao, presos])
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
    const fortes = [...ultimaCol.celulas].sort((a, b) => b[4] - a[4]).slice(0, 12)
    const acima = fortes.filter((c) => c[0] > p).sort((a, b) => b[0] - a[0]).slice(-4)
    const abaixo = fortes.filter((c) => c[1] < p).sort((a, b) => b[0] - a[0]).slice(0, 4)
    return { acima, abaixo, max: Math.max(1, ...fortes.map((c) => c[4])) }
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
        <Card title="Candles de 5 min com as nuvens"
          right={<span style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            <Seg value={modo} options={MODOS} onChange={setModo} labels={{ absorcao: 'Absorção', paredes: 'Todas as paredes' }} />
            {modo === 'paredes' && <>
              <span className="muted" style={{ fontSize: 12 }}>a partir de</span>
              <Seg value={fator} options={FATORES} onChange={setFator} labels={{ '2': '2x', '3': '3x', '5': '5x' }} />
              {EXCHANGES.map((e) => <Chip key={e} on={!!exs[e]} onClick={() => toggleEx(e)}>{NOME_EX[e]}</Chip>)}
            </>}
            <span style={{ width: 8 }} />
            <Chip on={verPresos} onClick={() => setVerPresos(!verPresos)}>Presos</Chip>
            {verPresos && <Seg value={tfPresos} options={TFS_PRESOS} onChange={setTfPresos} labels={{ '300': '5 min', '1800': '30 min' }} />}
            <Chip on={mostrarTop} onClick={() => setMostrarTop(!mostrarTop)}>maiores níveis</Chip>
          </span>}>
          {candles.isPending ? <Loading /> : candles.isError ? <Err e={candles.error} /> : dados.length === 0 ? <Empty>sem candles</Empty> : (
            <PriceChart candles={dados} rects={rects} levels={levels} labels={labels} markers={presos.markers} height={560} />
          )}
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', marginTop: 12, alignItems: 'end' }}>
            {modo === 'paredes' ? <Regua /> : <LegendaAbsorcao q={qAbs.data} />}
            <span className="muted" style={{ fontSize: 12 }}>
              {qCalor.isPending ? 'lendo o livro…' : d && d.colunas.length
                ? `livro gravado de ${new Date(d.colunas[0].ts * 1000).toISOString().slice(11, 16)} a ${new Date(d.colunas[d.colunas.length - 1].ts * 1000).toISOString().slice(11, 16)} UTC · onde não há nuvem, nada acima do normal (ou o coletor estava parado)`
                : 'o coletor ainda não tem livro suficiente neste período'}
            </span>
          </div>
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
