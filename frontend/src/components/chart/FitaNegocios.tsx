/**
 * Fita de negócios grandes ao vivo, como a coluna da esquerda do aggr.trade: este navegador ouve os websockets públicos
 * da Coinbase, da Binance (à vista e perpétuo) e da Bybit e lista cada agressão acima do mínimo; verde = compra a
 * mercado, vermelho = venda. Uma ordem a mercado que varre vários preços chega em pedaços: os pedaços da mesma ordem
 * (Coinbase: taker_order_id; as outras: mesmo instante e mesmo lado) viram uma linha só. Começa vazia e enche enquanto a
 * aba estiver aberta: o servidor só guarda os negócios por minuto, não um por um.
 */
import { useEffect, useRef, useState } from 'react'
import { fmt } from '../../lib/format'

/** um pedaço de negócio: [ms, preço, BTC, o agressor comprou?, chave da ordem] */
type Pedaco = [number, number, number, boolean, string]
type Fonte = { nome: string; titulo: string; url: string; inscricao?: object; ping?: object; ler: (m: any) => Pedaco[] }   // eslint-disable-line @typescript-eslint/no-explicit-any
type Linha = { id: number; ms: number; ex: string; preco: number; usd: number; compra: boolean }

const binance = (m: any): Pedaco[] => (m.e === 'aggTrade' ? [[m.T, +m.p, +m.q, !m.m, `${m.T}${m.m}`]] : [])   // eslint-disable-line @typescript-eslint/no-explicit-any
const FONTES: Fonte[] = [
  { nome: 'CB', titulo: 'Coinbase à vista (BTC-USD)', url: 'wss://ws-feed.exchange.coinbase.com',
    inscricao: { type: 'subscribe', product_ids: ['BTC-USD'], channels: ['matches'] },
    // `side` é o lado da ordem parada: parada vendendo = agressor comprando
    ler: (m) => (m.type === 'match' ? [[Date.parse(m.time), +m.price, +m.size, m.side === 'sell', String(m.taker_order_id)]] : []) },
  { nome: 'BN', titulo: 'Binance à vista (BTCUSDT)', url: 'wss://stream.binance.com:9443/ws/btcusdt@aggTrade', ler: binance },
  { nome: 'BN-P', titulo: 'Binance perpétuo (BTCUSDT)', url: 'wss://fstream.binance.com/ws/btcusdt@aggTrade', ler: binance },
  { nome: 'BY', titulo: 'Bybit perpétuo (BTCUSDT)', url: 'wss://stream.bybit.com/v5/public/linear',
    inscricao: { op: 'subscribe', args: ['publicTrade.BTCUSDT'] }, ping: { op: 'ping' },
    ler: (m) => (String(m.topic ?? '').startsWith('publicTrade')
      ? (m.data ?? []).map((d: any): Pedaco => [d.T, +d.p, +d.v, d.S === 'Buy', `${d.T}${d.S}`]) : []) },   // eslint-disable-line @typescript-eslint/no-explicit-any
]
const MINIMOS = [50_000, 100_000, 250_000, 500_000, 1_000_000]
const MAX_LINHAS = 80
const JUNTA_MS = 300

const curto = (v: number) => (v >= 1e6 ? `${fmt(v / 1e6, 2)}M` : `${fmt(v / 1e3, 0)}k`)
const hora = (ms: number) => new Date(ms).toLocaleTimeString('pt-BR', { hour12: false })

export default function FitaNegocios() {
  const [minimo, setMinimo] = useState(100_000)
  const [linhas, setLinhas] = useState<Linha[]>([])
  const [vivas, setVivas] = useState<Record<string, boolean>>({})
  const min = useRef(minimo)
  min.current = minimo

  useEffect(() => {
    let parar = false, proximoId = 0
    // pedaços esperando a ordem terminar, por fonte e chave
    const abertos = new Map<string, { ex: string; ms: number; btc: number; usd: number; compra: boolean; visto: number }>()
    const conexoes: WebSocket[] = []
    const timers: number[] = []

    const descarregar = () => {
      const agora = Date.now(), novas: Linha[] = []
      for (const [k, o] of abertos) {
        if (agora - o.visto < JUNTA_MS) continue
        abertos.delete(k)
        if (o.usd >= min.current) novas.push({ id: proximoId++, ms: o.ms, ex: o.ex, preco: o.usd / o.btc, usd: o.usd, compra: o.compra })
      }
      if (novas.length) setLinhas((l) => [...novas.sort((a, b) => b.ms - a.ms), ...l].slice(0, MAX_LINHAS))
    }
    timers.push(window.setInterval(descarregar, 150))

    const abrir = (f: Fonte, espera: number) => {
      if (parar) return
      const ws = new WebSocket(f.url)
      conexoes.push(ws)
      let ping = 0
      ws.onopen = () => {
        setVivas((v) => ({ ...v, [f.nome]: true }))
        if (f.inscricao) ws.send(JSON.stringify(f.inscricao))
        if (f.ping) ping = window.setInterval(() => ws.readyState === WebSocket.OPEN && ws.send(JSON.stringify(f.ping)), 20_000)
      }
      ws.onmessage = (e) => {
        let m
        try { m = JSON.parse(e.data) } catch { return }
        for (const [ms, preco, btc, compra, chave] of f.ler(m)) {
          if (!(btc > 0 && preco > 0)) continue
          const k = `${f.nome}:${chave}`
          const o = abertos.get(k) ?? { ex: f.nome, ms, btc: 0, usd: 0, compra, visto: 0 }
          o.btc += btc; o.usd += btc * preco; o.visto = Date.now()
          abertos.set(k, o)
        }
      }
      ws.onclose = () => {
        window.clearInterval(ping)
        setVivas((v) => ({ ...v, [f.nome]: false }))
        if (!parar) timers.push(window.setTimeout(() => abrir(f, Math.min(60_000, espera * 2)), espera))
      }
      ws.onerror = () => ws.close()
    }
    for (const f of FONTES) abrir(f, 2000)
    return () => {
      parar = true
      for (const t of timers) { window.clearInterval(t); window.clearTimeout(t) }
      for (const ws of conexoes) ws.close()
    }
  }, [])

  return (
    <div className="card aggr-fita">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', fontSize: 12 }}>
        <b style={{ color: '#e8ecf2' }}>Negócios grandes</b>
        <select className="gselect" value={minimo} onChange={(e) => setMinimo(+e.target.value)} aria-label="Tamanho mínimo">
          {MINIMOS.map((m) => <option key={m} value={m}>≥ ${curto(m)}</option>)}
        </select>
      </div>
      <div className="muted" style={{ fontSize: 11, margin: '4px 0 6px' }}>
        {FONTES.map((f) => (
          <span key={f.nome} title={f.titulo} style={{ marginRight: 8 }}>
            <span style={{ color: vivas[f.nome] ? '#2ecc84' : '#f0544f' }}>●</span> {f.nome}
          </span>
        ))}
        <div>ao vivo deste navegador · começa vazia</div>
      </div>
      <div className="aggr-fita-lista">
        {linhas.map((l) => {
          const forca = Math.min(1, 0.25 + Math.log10(l.usd / minimo + 1) / 1.5)
          const cor = l.compra ? `rgba(46,204,132,${forca})` : `rgba(240,84,79,${forca})`
          return (
            <div key={l.id} className="aggr-fita-linha mono" style={{ background: cor, fontWeight: l.usd >= 1e6 ? 700 : 400 }}>
              <span>{l.ex}</span><span>{fmt(l.preco, 1)}</span><span>${curto(l.usd)}</span><span className="muted">{hora(l.ms)}</span>
            </div>
          )
        })}
        {!linhas.length && <div className="muted" style={{ fontSize: 12, padding: 8 }}>esperando o primeiro negócio de ${curto(minimo)} ou mais…</div>}
      </div>
    </div>
  )
}
