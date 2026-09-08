import type { CSSProperties, ReactNode } from 'react'
import { erroTexto } from '../api/client'

export function Card({ title, sub, right, children, style, pad = true }: {
  title?: ReactNode; sub?: ReactNode; right?: ReactNode; children: ReactNode; style?: CSSProperties; pad?: boolean
}) {
  return (
    <div className="card" style={style}>
      {title !== undefined && (
        <div className="card-h">
          <span>{title}</span>
          {sub && <span className="sub">{sub}</span>}
          {right && <span style={{ marginLeft: 'auto' }}>{right}</span>}
        </div>
      )}
      {pad ? <div className="card-b">{children}</div> : children}
    </div>
  )
}

export function KPI({ v, l, color }: { v: ReactNode; l: ReactNode; color?: string }) {
  return (
    <div className="kpi">
      <div className="v" style={{ color: color || 'var(--text)' }}>{v}</div>
      <div className="l">{l}</div>
    </div>
  )
}

export function Tag({ children, color }: { children: ReactNode; color?: string }) {
  const st = color ? { borderColor: color + '55', background: color + '1a', color } : undefined
  return <span className="tag" style={st}>{children}</span>
}

export function ModoTag({ modo }: { modo: string | null | undefined }) {
  const c = modo === 'real' ? 'var(--red)' : modo === 'testnet' ? 'var(--amber)' : undefined
  return <Tag color={c}>{modo || 'simulador'}</Tag>
}

export function Chip({ on, onClick, children }: { on: boolean; onClick?: () => void; children: ReactNode }) {
  return <button type="button" className={'chip' + (on ? ' on' : '')} onClick={onClick}>{children}</button>
}

export function Seg<T extends string>({ value, options, onChange, labels }: {
  value: T; options: readonly T[]; onChange: (v: T) => void; labels?: Partial<Record<T, string>>
}) {
  return (
    <div className="seg">
      {options.map((o) => (
        <button key={o} type="button" className={o === value ? 'on' : ''} onClick={() => onChange(o)}>{labels?.[o] ?? o}</button>
      ))}
    </div>
  )
}

export function Switch({ on, onChange, disabled }: { on: boolean; onChange?: (v: boolean) => void; disabled?: boolean }) {
  return (
    <button type="button" className={'switch' + (on ? ' on' : '')} disabled={disabled} onClick={() => onChange?.(!on)} aria-pressed={on}>
      <span className="knob" />
    </button>
  )
}

export function Field({ label, children, span2 }: { label: ReactNode; children: ReactNode; span2?: boolean }) {
  return (
    <label style={{ display: 'block' }} className={span2 ? 'span2' : undefined}>
      <span className="label">{label}</span>
      {children}
    </label>
  )
}

export function KV({ k, v, src, color }: { k: ReactNode; v: ReactNode; src?: ReactNode; color?: string }) {
  return (
    <div className="kv">
      <span className="k">{k}</span>
      <span className="v" style={{ color }}>{v}</span>
      {src && <span className="src">{src}</span>}
    </div>
  )
}

export function ProbBar({ bull, bear }: { bull: number; bear: number }) {
  const und = Math.max(0, 1 - bull - bear)
  return (
    <>
      <div className="probbar" style={{ margin: '12px 0 6px' }}>
        <span style={{ width: `${bull * 100}%`, background: 'var(--green)' }} />
        <span style={{ width: `${bear * 100}%`, background: 'var(--red)' }} />
        <span style={{ width: `${und * 100}%`, background: 'var(--dim)' }} />
      </div>
      <div className="mono muted" style={{ fontSize: 11 }}>
        <span className="green">Bull {Math.round(bull * 100)}%</span> · <span className="red">Bear {Math.round(bear * 100)}%</span>
        {und > 0.005 && <> · Indefinido {Math.round(und * 100)}%</>}
      </div>
    </>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>
}

export function Loading({ children = 'carregando…' }: { children?: ReactNode }) {
  return <div className="empty mono">{children}</div>
}

export function Err({ e }: { e: unknown }) {
  return <div className="err">{erroTexto(e)}</div>
}

export function Estado({ query, children }: { query: { isPending: boolean; isError: boolean; error: unknown }; children: ReactNode }) {
  if (query.isPending) return <Loading />
  if (query.isError) return <Err e={query.error} />
  return <>{children}</>
}

export function Btn({ kind, children, onClick, disabled, title, small }: {
  kind?: 'primary' | 'danger' | 'ghost' | 'ok'; children: ReactNode; onClick?: () => void; disabled?: boolean; title?: string; small?: boolean
}) {
  return (
    <button type="button" className={'btn' + (kind ? ' ' + kind : '')} onClick={onClick} disabled={disabled} title={title}
      style={small ? { padding: '4px 9px', fontSize: 11 } : undefined}>
      {children}
    </button>
  )
}
