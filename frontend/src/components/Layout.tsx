import { useQuery } from '@tanstack/react-query'
import { useEffect, useState, type ReactNode } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { api } from '../api/client'
import type { StatusConselho } from '../api/types'
import { fmt, pctSigned } from '../lib/format'

const NAV = [['/', 'Mapa e avisos'], ['/nuvens', 'Nuvens'], ['/robos', 'Robôs']] as const

/** Coletor parado há mais de 5 min = buraco no histórico das nuvens. */
const COLETOR_ATRASO_S = 300

export function useStatusConselho() {
  return useQuery({ queryKey: ['status'], queryFn: () => api.get<StatusConselho>('/api/mercado/status'), refetchInterval: 30_000 })
}

export function usePreco(par = 'BTCUSDT') {
  return useQuery({
    queryKey: ['preco', par],
    queryFn: async () => {
      const r = await api.get<{ candles: number[][] }>('/api/mercado/candles', { par, timeframe: '1d', limite: 2 })
      const c = r.candles
      const ultimo = c[c.length - 1], anterior = c[c.length - 2]
      return { preco: ultimo[4], var24h: anterior ? ultimo[4] / anterior[4] - 1 : 0 }
    },
    refetchInterval: 15_000,
  })
}

function useRelogio() {
  const [hora, setHora] = useState('')
  useEffect(() => {
    const t = () => { const d = new Date(), p = (n: number) => String(n).padStart(2, '0'); setHora(`${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`) }
    t(); const id = setInterval(t, 1000); return () => clearInterval(id)
  }, [])
  return hora
}

/** Saúde do conselho: vira o ponto do topo (detalhe ao passar o mouse) e a faixa de alerta quando algo falha. */
function useSaude() {
  const status = useStatusConselho()
  const preco = usePreco('BTCUSDT')
  const s = status.data
  const dados = preco.isError ? 'falha' : preco.data ? 'ok' : '…'
  const avisos = s ? (s.avisos.ativo ? 'ok' : 'off') : '…'
  const idades = s ? Object.values(s.coletor_idade_s) : []
  const atrasado = idades.some((v) => v === null || v > COLETOR_ATRASO_S)
  const coletor = !s ? '…' : atrasado ? 'parado' : 'ok'
  const linhas: [string, string][] = [['Bybit dados', dados], ['Serviço de avisos', avisos], ['Coletor do livro', coletor],
    ['Telegram', s ? (s.telegram ? 'ok' : 'off') : '…']]
  const problemas: string[] = []
  if (dados === 'falha') problemas.push('dados públicos da Bybit indisponíveis')
  if (coletor === 'parado') problemas.push('coletor do livro parado · abra o coletor_livro.bat')
  if (status.isError) problemas.push('API do conselho sem resposta')
  return { linhas, problemas }
}

const corSaude = (v: string) => (v === 'ok' ? 'var(--acc)' : v === '…' || v === '—' || v === 'off' ? 'var(--muted)' : 'var(--amber)')

export function TopBar() {
  const hora = useRelogio()
  const preco = usePreco('BTCUSDT')
  const { linhas, problemas } = useSaude()
  const fuso = -new Date().getTimezoneOffset() / 60
  const corDot = problemas.length ? 'var(--amber)' : 'var(--acc)'
  return (
    <>
      <header className="topbar">
        <Link to="/" className="logo">
          <span className="logo-txt">Conselho<span>BTC</span></span>
          <span className="logo-ring" />
        </Link>
        <nav className="navpill">
          {NAV.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => (isActive ? 'on' : '')}>{label}</NavLink>
          ))}
        </nav>
        <div className="topbar-right">
          <div className="topbar-preco">
            <div className="p">BTCUSDT <span style={{ color: (preco.data?.var24h ?? 0) >= 0 ? 'var(--acc)' : 'var(--red)' }}>{preco.data ? fmt(preco.data.preco) : '…'}</span></div>
            <div className="h">{hora} · UTC{fuso >= 0 ? '+' : '−'}{Math.abs(fuso)}</div>
          </div>
          <div className="saude">
            <span className="saude-dot" style={{ background: corDot, boxShadow: `0 0 12px ${corDot}` }} aria-label="saúde das conexões" />
            <div className="saude-pop">
              <span className="eyebrow">Saúde das conexões</span>
              {linhas.map(([l, v]) => (
                <div className="saude-row" key={l}>
                  <span className="dot" style={{ width: 6, height: 6, flex: '0 0 6px', background: corSaude(v) }} />
                  <span className="lab">{l}</span>
                  <span className="val" style={{ color: corSaude(v) }}>{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </header>
      {problemas.length > 0 && (
        <div className="alerta-wrap"><div className="alerta-pill">{problemas.join(' · ')}</div></div>
      )}
    </>
  )
}

/**
 * Topo da página: sobrelinha (contexto curto, em maiúsculas), título grande e ações.
 * `subtitulo` vira a linha de apoio embaixo do título; a sobrelinha é `eyebrow` ou o par.
 */
export function Header({ titulo, subtitulo, actions, par, eyebrow }: {
  titulo: ReactNode; subtitulo?: ReactNode; actions?: ReactNode; par?: string; eyebrow?: ReactNode
}) {
  const preco = usePreco(par || 'BTCUSDT')
  const outroPar = par && par !== 'BTCUSDT'
  return (
    <div className="pagehead">
      <div style={{ minWidth: 0 }}>
        <div className="eb">{eyebrow ?? par ?? 'BTCUSDT'}</div>
        <h1>{titulo}</h1>
        {subtitulo && <p className="sub">{subtitulo}</p>}
      </div>
      <div className="acoes">
        {outroPar && preco.data && (
          <span className="mono" style={{ fontSize: 13 }}>{par} <span style={{ color: preco.data.var24h >= 0 ? 'var(--acc)' : 'var(--red)' }}>{fmt(preco.data.preco)}</span>
            <span className="muted" style={{ fontSize: 11 }}> {pctSigned(preco.data.var24h)}</span></span>
        )}
        {actions}
      </div>
    </div>
  )
}

export function Page({ children }: { children: ReactNode }) {
  return <div className="page">{children}</div>
}
