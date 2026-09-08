import { useQuery } from '@tanstack/react-query'
import { useEffect, useState, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { api } from '../api/client'
import type { StatusGeral } from '../api/types'
import { fmt, pctSigned } from '../lib/format'

const NAV = [
  ['/', 'Dashboard'], ['/trader', 'Mesa do trader'], ['/mercado', 'Mercado'], ['/pontos', 'Pontos institucionais'],
  ['/sentimento', 'Sentimento'], ['/historico', 'Histórico'], ['/bots/novo', 'Novo robô'],
] as const

interface DiagBybit { modo: string; publico?: string; privado?: string; saldo_usdt?: unknown; [k: string]: unknown }

export function useStatusGeral() {
  return useQuery({ queryKey: ['status'], queryFn: () => api.get<StatusGeral>('/status/'), refetchInterval: 10_000 })
}

export function usePreco(par = 'BTCUSDT') {
  return useQuery({
    queryKey: ['preco', par],
    queryFn: async () => {
      const r = await api.get<{ candles: number[][] }>('/status/mercado/candles', { par, timeframe: '1d', limite: 2 })
      const c = r.candles
      const ultimo = c[c.length - 1], anterior = c[c.length - 2]
      return { preco: ultimo[4], var24h: anterior ? ultimo[4] / anterior[4] - 1 : 0 }
    },
    refetchInterval: 15_000,
  })
}

export function Sidebar() {
  const status = useStatusGeral()
  const bybit = useQuery({ queryKey: ['bybit', 'simulador'], queryFn: () => api.get<DiagBybit>('/status/bybit', { modo: 'simulador' }), refetchInterval: 60_000, retry: 0 })
  const conta = useQuery({ queryKey: ['bybit', 'testnet'], queryFn: () => api.get<DiagBybit>('/status/bybit', { modo: 'testnet' }), refetchInterval: 120_000, retry: 0 })
  const md = status.data?.servicos?.market_data as { cesta?: string; membros?: string[]; falhas?: Record<string, unknown> } | undefined
  const totExch = md?.membros?.length
  const okExch = totExch !== undefined ? totExch - Object.keys(md?.falhas ?? {}).length : undefined
  const dados = bybit.isError ? 'falha' : bybit.data ? (bybit.data.publico === 'ok' ? 'ok' : 'falha') : '…'
  const contaTxt = conta.isError ? 'falha' : conta.data ? (conta.data.privado === 'ok' ? 'ok' : String(conta.data.privado || '').startsWith('erro') ? 'chave inválida' : 'sem chave') : '…'
  const cor = (v: string) => (v === 'ok' ? 'var(--green)' : v === '…' || v === '—' ? 'var(--muted)' : v === 'sem chave' ? 'var(--muted)' : 'var(--amber)')
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-arc" />
        <span>
          <span className="brand-name">Bot Trade</span>
          <span className="brand-sub">PRO</span>
        </span>
      </div>
      <nav className="nav">
        {NAV.map(([to, label]) => (
          <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => (isActive ? 'on' : '')}>{label}</NavLink>
        ))}
      </nav>
      <div className="saude">
        <span className="eyebrow" style={{ fontSize: 10, letterSpacing: '0.16em' }}>Saúde</span>
        {[['Bybit dados', dados], ['Bybit conta', contaTxt], ['Cesta exchanges', okExch !== undefined && totExch ? `${okExch}/${totExch}` : '—'],
          ['Telegram', status.data ? (status.data.servicos.telegram ? 'ok' : 'off') : '…']].map(([l, v]) => (
          <div className="saude-row" key={l}>
            <span className="dot" style={{ background: cor(v) }} />
            <span className="lab">{l}</span>
            <span className="val" style={{ color: cor(v) }}>{v}</span>
          </div>
        ))}
      </div>
    </aside>
  )
}

export function Header({ titulo, subtitulo, actions, par = 'BTCUSDT' }: { titulo: ReactNode; subtitulo?: ReactNode; actions?: ReactNode; par?: string }) {
  const [hora, setHora] = useState('')
  useEffect(() => {
    const t = () => { const d = new Date(), p = (n: number) => String(n).padStart(2, '0'); setHora(`${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`) }
    t(); const id = setInterval(t, 1000); return () => clearInterval(id)
  }, [])
  const preco = usePreco(par)
  return (
    <header className="header">
      <div style={{ minWidth: 0 }}>
        <h1>{titulo}</h1>
        {subtitulo && <p>{subtitulo}</p>}
      </div>
      <div className="header-right">
        {actions}
        <div className="mono" style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 13 }}>{par} · <span style={{ color: (preco.data?.var24h ?? 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>{preco.data ? fmt(preco.data.preco) : '…'}</span>
            {preco.data && <span className="muted" style={{ fontSize: 11 }}> {pctSigned(preco.data.var24h)}</span>}</div>
          <div className="muted" style={{ fontSize: 11 }}>{hora}</div>
        </div>
      </div>
    </header>
  )
}

export function Page({ children }: { children: ReactNode }) {
  return <div className="page">{children}</div>
}
