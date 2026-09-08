/** Formatação pt-BR compacta usada no painel: milhar com espaço, decimal com vírgula. */
export function fmt(n: number | null | undefined, dec = 0): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  const [int, frac] = Math.abs(n).toFixed(dec).split('.')
  const i = int.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
  return (n < 0 ? '−' : '') + i + (frac ? ',' + frac : '')
}

export function fmtSigned(n: number | null | undefined, dec = 2): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  return (n > 0 ? '+' : '') + fmt(n, dec)
}

export function pct(n: number | null | undefined, dec = 0): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  return fmt(n * 100, dec) + '%'
}

export function pctSigned(n: number | null | undefined, dec = 1): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  return (n > 0 ? '+' : '') + fmt(n * 100, dec) + '%'
}

/** preço: sem decimais acima de 1000, 2 abaixo, 4 abaixo de 1 */
export function preco(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  return fmt(n, n >= 1000 ? 0 : n >= 1 ? 2 : 4)
}

export function hora(ts: string | number | null | undefined, comData = false): string {
  if (!ts) return '—'
  const d = typeof ts === 'number' ? new Date(ts) : new Date(ts.endsWith('Z') || ts.includes('+') ? ts : ts + 'Z')
  if (Number.isNaN(d.getTime())) return '—'
  const p = (x: number) => String(x).padStart(2, '0')
  const h = `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
  return comData ? `${p(d.getDate())}/${p(d.getMonth() + 1)} ${h.slice(0, 5)}` : h
}

export function data(ts: number | string | null | undefined): string {
  if (!ts) return '—'
  const d = typeof ts === 'number' ? new Date(ts) : new Date(ts)
  if (Number.isNaN(d.getTime())) return '—'
  const p = (x: number) => String(x).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

export const corAcao = (a: string | null | undefined) =>
  a === 'buy' || a === 'COMPRA' ? 'var(--green)' : a === 'sell' || a === 'VENDA' ? 'var(--red)' : 'var(--muted)'

export const rotuloAcao = (a: string | null | undefined) =>
  a === 'buy' ? 'COMPRA' : a === 'sell' ? 'VENDA' : a === 'hold' ? 'AGUARDAR' : (a || '—').toUpperCase()

export const corVies = (v: string | null | undefined) =>
  v === 'bull' || v === 'buy' || v === 'alta' ? 'var(--green)' : v === 'bear' || v === 'sell' || v === 'baixa' ? 'var(--red)' : 'var(--muted)'

export const rotuloVies = (v: string | null | undefined) =>
  v === 'bull' || v === 'buy' ? 'alta' : v === 'bear' || v === 'sell' ? 'baixa' : v === 'neutro' || v === 'hold' ? 'neutro' : (v || '—')

export const corPnl = (n: number | null | undefined) => (n === null || n === undefined ? 'var(--muted)' : n >= 0 ? 'var(--green)' : 'var(--red)')
