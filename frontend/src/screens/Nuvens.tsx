import { useMemo, useState } from 'react'
import { useCandles, useNuvensOverlay, useNuvensTop } from '../api/hooks'
import type { NuvensOverlay, NuvensPonto } from '../api/types'
import PriceChart from '../components/chart/PriceChart'
import { Header, Page } from '../components/Layout'
import { Card, Chip, Empty, Err, Estado, KPI, Loading, Tag } from '../components/ui'
import type { ChartLevel, ChartRect } from '../lib/chart-tipos'
import { fmt, preco as fmtPreco } from '../lib/format'

/** As nuvens do TRDR: o livro agregado (Coinbase + Binance + Bybit) desenhado em bandas em volta do candle de 5 min. */
const EXCHANGES = ['coinbase', 'binance', 'bybit'] as const
const NOME_EX: Record<string, string> = { coinbase: 'Coinbase', binance: 'Binance', bybit: 'Bybit' }
const PASSO_S = 300           // um ponto por candle de 5 min
const N_CANDLES = 288         // 24 h de candles de 5 min
const COR = { bids: '#2ecc84', asks: '#f0544f' }

const horaUTC = (s: number) => `${new Date(s * 1000).toISOString().slice(11, 16)} UTC`
const diaHoraUTC = (s: number) => `${new Date(s * 1000).toISOString().slice(0, 10)} ${horaUTC(s)}`

/** Opacidade proporcional à vantagem do lado na categoria: 5% sem vantagem, até 40% com o outro lado vazio. */
function corBanda(lado: 'bids' | 'asks', forca: number): string {
  const v = lado === 'bids' ? Math.max(0, forca) : Math.max(0, -forca)
  const a = 0.05 + 0.35 * Math.min(1, v)
  return lado === 'bids' ? `rgba(46,204,132,${a.toFixed(3)})` : `rgba(240,84,79,${a.toFixed(3)})`
}

function bandas(d: NuvensOverlay | undefined, ligadas: boolean[]): ChartRect[] {
  if (!d) return []
  const out: ChartRect[] = []
  const pts = d.pontos
  pts.forEach((p, i) => {
    if (!p.mid) return
    const to = i === pts.length - 1 ? null : p.ts + d.passo_s
    d.categorias.forEach((c, k) => {
      if (!ligadas[k]) return
      if (p.bids[k] > 0) out.push({ from: p.ts, to, top: p.mid * (1 - c.lo), bottom: p.mid * (1 - c.hi), color: corBanda('bids', p.forca[k]) })
      if (p.asks[k] > 0) out.push({ from: p.ts, to, top: p.mid * (1 + c.hi), bottom: p.mid * (1 + c.lo), color: corBanda('asks', p.forca[k]) })
    })
  })
  return out
}

function Legenda({ categorias, ligadas, onToggle }: { categorias: NuvensOverlay['categorias']; ligadas: boolean[]; onToggle: (k: number) => void }) {
  return (
    <span style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
      {categorias.map((c, k) => (
        <Chip key={c.rotulo} on={ligadas[k]} onClick={() => onToggle(k)}>
          <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, marginRight: 6, verticalAlign: 'middle',
                         background: `linear-gradient(180deg, rgba(240,84,79,${0.25 + k * 0.12}) 50%, rgba(46,204,132,${0.25 + k * 0.12}) 50%)` }} />
          {c.rotulo}
        </Chip>
      ))}
    </span>
  )
}

function LinhaCategoria({ p, k, rotulo }: { p: NuvensPonto; k: number; rotulo: string }) {
  const v = p.vantagem[k]
  const cor = v === 'bids' ? COR.bids : v === 'asks' ? COR.asks : 'var(--muted)'
  return (
    <tr>
      <td className="sans">{rotulo}</td>
      <td className="r" style={{ color: COR.bids }}>{fmt(p.bids[k], 1)}</td>
      <td className="r" style={{ color: COR.asks }}>{fmt(p.asks[k], 1)}</td>
      <td className="r">{p.razao[k] === null ? '—' : `${fmt(p.razao[k], 2)}x`}</td>
      <td style={{ color: cor }}>{v === 'bids' ? `compra ${fmt(p.forca[k] * 100, 0)}%` : v === 'asks' ? `venda ${fmt(-p.forca[k] * 100, 0)}%` : 'empate'}</td>
      <td className="muted">{p.cobertura[k].length ? p.cobertura[k].map((e) => NOME_EX[e] ?? e).join(' + ') : 'nenhuma completa'}</td>
    </tr>
  )
}

export default function Nuvens() {
  const [exs, setExs] = useState<Record<string, boolean>>({ coinbase: true, binance: true, bybit: true })
  const [ligadas, setLigadas] = useState<boolean[]>([true, true, true, true, true])
  const [mostrarTop, setMostrarTop] = useState(true)
  const exchanges = EXCHANGES.filter((e) => exs[e]).join(',')
  const candles = useCandles('BTCUSDT', '5m', N_CANDLES)
  const dados = candles.data ?? []
  const inicio = dados.length ? dados[0].time : null
  const qOv = useNuvensOverlay(inicio, exchanges, PASSO_S)
  const qTop = useNuvensTop(exchanges)
  const d = qOv.data
  const top = qTop.data
  const ultimo = d?.pontos.length ? d.pontos[d.pontos.length - 1] : null
  const ultimaVela = dados[dados.length - 1]

  const rects = useMemo(() => bandas(d, ligadas), [d, ligadas])
  const levels = useMemo<ChartLevel[]>(() => {
    if (!mostrarTop || !top) return []
    return [
      ...top.bids.map((n) => ({ price: n.preco, label: `B ${fmt(n.qtd, 0)}`, color: COR.bids, dashed: true })),
      ...top.asks.map((n) => ({ price: n.preco, label: `A ${fmt(n.qtd, 0)}`, color: COR.asks, dashed: true })),
    ]
  }, [mostrarTop, top])
  const niveisTop = useMemo(() => {
    if (!top || !top.mid) return []
    const mid = top.mid
    return [...top.asks.map((n) => ({ ...n, lado: 'asks' as const })), ...top.bids.map((n) => ({ ...n, lado: 'bids' as const }))]
      .map((n) => ({ ...n, dist: (n.preco / mid - 1) * 100 }))
      .sort((a, b) => b.preco - a.preco)
  }, [top])
  const aproximados = d ? Object.values(d.fontes).reduce((s, f) => s + f.aproximados, 0) : 0
  const snapshots = d ? Object.values(d.fontes).reduce((s, f) => s + f.snapshots, 0) : 0

  const toggleEx = (e: string) => {
    const novo = { ...exs, [e]: !exs[e] }
    if (Object.values(novo).some(Boolean)) setExs(novo)         // pelo menos uma exchange ligada
  }

  return (
    <>
      <Header titulo="Nuvens do livro" par="BTCUSDT" eyebrow="Order flow"
        subtitulo="Order Book Depth Overlay do TRDR refeito com o coletor próprio: livro de Coinbase, Binance e Bybit somado por categoria de distância (0–1%, 1–2,5%, 2,5–5%, 5–10%, 10–25%) em volta do candle de 5 min — verde embaixo são bids, vermelho em cima são asks, mais opaco é o lado com vantagem; as linhas são os 10 maiores níveis de cada lado" />
      <Page>
        <Estado query={qOv}>
          {!d ? <Empty>sem leitura</Empty> : (
            <>
              <div className="grid" style={{ gridTemplateColumns: 'repeat(4, minmax(0, 1fr))' }}>
                <KPI l="Vantagem a 0–1%" v={ultimo ? (ultimo.vantagem[0] === 'bids' ? 'compra' : ultimo.vantagem[0] === 'asks' ? 'venda' : 'empate') : '—'}
                  color={ultimo?.vantagem[0] === 'bids' ? COR.bids : ultimo?.vantagem[0] === 'asks' ? COR.asks : 'var(--muted)'}
                  sub={ultimo ? `${fmt(ultimo.bids[0], 0)} BTC em bids · ${fmt(ultimo.asks[0], 0)} BTC em asks${ultimo.razao[0] !== null ? ` · ${fmt(ultimo.razao[0], 2)}x` : ''}` : 'sem ponto no período'} />
                <KPI l="Livro inteiro até 25%" v={ultimo ? `${fmt(ultimo.forca_total * 100, 0)}%` : '—'}
                  color={ultimo ? (ultimo.forca_total > 0 ? COR.bids : ultimo.forca_total < 0 ? COR.asks : 'var(--muted)') : 'var(--muted)'}
                  sub={ultimo ? `${fmt(ultimo.total_bids, 0)} BTC bids − ${fmt(ultimo.total_asks, 0)} BTC asks, sobre o total` : null} />
                <KPI l="Último snapshot" v={d.ultimo_ts ? horaUTC(d.ultimo_ts) : '—'}
                  sub={d.ultimo_ts ? `${diaHoraUTC(d.ultimo_ts).slice(0, 10)} · ${snapshots} snapshots em ${d.pontos.length} pontos de ${d.passo_s / 60} min` : 'o coletor ainda não gravou nada'} />
                <KPI l="Fonte" v={`${d.exchanges.length} exchange${d.exchanges.length > 1 ? 's' : ''}`}
                  color={aproximados ? 'var(--amber)' : 'var(--text)'}
                  sub={`${d.exchanges.map((e) => NOME_EX[e] ?? e).join(' + ')}${aproximados ? ` · ${aproximados} de ${snapshots} snapshots anteriores às categorias, aproximados pelas faixas de 0,1% (até 5%)` : ' · categorias medidas do melhor bid/ask'}`} />
              </div>

              {ultimo?.aproximado && (
                <div><span className="alerta-pill">O coletor que está rodando ainda grava só as faixas de 0,1% até 5%: as categorias 5–10% e 10–25% aparecem vazias e os top levels são o centro da maior faixa, não o nível exato. Reinicie o coletor para gravar as categorias e os níveis.</span></div>
              )}

              <Card title="Candles de 5 min com as nuvens" sub={`${N_CANDLES} candles da Bybit · bandas por categoria de distância do mid · B/A nas linhas = BTC no nível`}
                right={<span style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                  {EXCHANGES.map((e) => <Chip key={e} on={!!exs[e]} onClick={() => toggleEx(e)}>{NOME_EX[e]}</Chip>)}
                  <span style={{ width: 8 }} />
                  <Legenda categorias={d.categorias} ligadas={ligadas} onToggle={(k) => setLigadas(ligadas.map((v, i) => (i === k ? !v : v)))} />
                  <span style={{ width: 8 }} />
                  <Chip on={mostrarTop} onClick={() => setMostrarTop(!mostrarTop)}>top levels</Chip>
                </span>}>
                {candles.isPending ? <Loading /> : candles.isError ? <Err e={candles.error} /> : dados.length === 0 ? <Empty>sem candles</Empty> : (
                  <PriceChart candles={dados} rects={rects} levels={levels} height={460} />
                )}
                <p className="sub" style={{ marginBottom: 0 }}>
                  Bandas com {d.pontos.length} pontos{d.pontos.length && ultimaVela ? `, de ${horaUTC(d.pontos[0].ts)} a ${horaUTC(d.pontos[d.pontos.length - 1].ts)}` : ''}; onde não há banda o coletor não estava gravando.
                  As bandas de 5–10% e 10–25% ficam fora da escala do candle: arraste o eixo de preço para vê-las.
                </p>
              </Card>

              <div className="grid" style={{ gridTemplateColumns: 'minmax(360px, 50fr) minmax(0, 50fr)', alignItems: 'start' }}>
                <Card title="Categorias agora" sub={ultimo ? `ponto de ${horaUTC(ultimo.ts)} · BTC por categoria, somando ${ultimo.exchanges.map((e) => NOME_EX[e] ?? e).join(' + ')}` : 'sem ponto'} pad={false}>
                  {!ultimo ? <Empty>sem ponto no período</Empty> : (
                    <table className="table">
                      <thead><tr><th>distância</th><th className="r">bids</th><th className="r">asks</th><th className="r">bids/asks</th><th>vantagem</th><th>livro completo em</th></tr></thead>
                      <tbody>
                        {d.categorias.map((c, k) => <LinhaCategoria key={c.rotulo} p={ultimo} k={k} rotulo={c.rotulo} />)}
                      </tbody>
                    </table>
                  )}
                </Card>

                <Card title="Top levels" sub={top?.ts ? `os 10 maiores níveis de cada lado em ${horaUTC(top.ts)} · mesmo preço a 0,05% vira um nível só${top.aproximado ? ' · aproximados pela faixa de 0,1%' : ''}` : 'sem snapshot'} pad={false}>
                  <Estado query={qTop}>
                    {niveisTop.length === 0 ? <Empty>sem níveis</Empty> : (
                      <table className="table">
                        <thead><tr><th>lado</th><th className="r">preço</th><th className="r">distância</th><th className="r">BTC</th><th>exchanges</th></tr></thead>
                        <tbody>
                          {niveisTop.map((n) => (
                            <tr key={`${n.lado}-${n.preco}`}>
                              <td><Tag color={n.lado === 'bids' ? COR.bids : COR.asks}>{n.lado === 'bids' ? 'bid' : 'ask'}</Tag></td>
                              <td className="r">{fmtPreco(n.preco)}</td>
                              <td className="r" style={{ color: n.dist >= 0 ? COR.asks : COR.bids }}>{n.dist > 0 ? '+' : ''}{fmt(n.dist, 2)}%</td>
                              <td className="r">{fmt(n.qtd, 1)}</td>
                              <td className="muted">{n.exchanges.map((e) => NOME_EX[e] ?? e).join(' + ')}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </Estado>
                </Card>
              </div>

              <Card title="O que cada exchange alcança" sub="profundidade real do livro que a API pública devolve; uma categoria só conta como completa quando o livro chega à borda de cima dela">
                <table className="table">
                  <thead><tr><th>exchange</th><th className="r">snapshots</th><th className="r">último</th><th className="r">alcance bids</th><th className="r">alcance asks</th><th>limite</th></tr></thead>
                  <tbody>
                    {d.exchanges.map((e) => {
                      const f = d.fontes[e]
                      return (
                        <tr key={e}>
                          <td className="sans">{NOME_EX[e] ?? e}</td>
                          <td className="r">{f?.snapshots ?? 0}</td>
                          <td className="r">{f?.ultimo_ts ? horaUTC(f.ultimo_ts) : '—'}</td>
                          <td className="r">{f?.alcance_bids_pct === null || f?.alcance_bids_pct === undefined ? '—' : `${fmt(f.alcance_bids_pct * 100, 2)}%`}</td>
                          <td className="r">{f?.alcance_asks_pct === null || f?.alcance_asks_pct === undefined ? '—' : `${fmt(f.alcance_asks_pct * 100, 2)}%`}</td>
                          <td className="muted" style={{ whiteSpace: 'normal' }}>{d.limitacoes[e]}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </Card>
            </>
          )}
        </Estado>
      </Page>
    </>
  )
}
