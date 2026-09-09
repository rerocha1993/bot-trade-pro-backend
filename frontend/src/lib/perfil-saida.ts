/**
 * Perfil de saída por estilo — espelho de core/perfil_saida.py.
 *
 * O trailing precisa ficar fora do ruído do timeframe: o pavio de um candle de 4h é umas quinze vezes o de um
 * candle de 1m, então a distância acompanha o estilo. E o ativador é sempre maior que a distância, senão o
 * trailing liga com o stop abaixo da entrada e trava prejuízo.
 */
export interface PerfilSaida {
  ativador_trailing: number
  distancia_trailing: number
  saida_escalonada: string
}

export const PERFIS: Record<string, PerfilSaida> = {
  scalping: { ativador_trailing: 0.004, distancia_trailing: 0.003, saida_escalonada: '50/40, 80/30' },
  daytrade: { ativador_trailing: 0.010, distancia_trailing: 0.007, saida_escalonada: '50/30, 75/30, 90/25' },
  swing: { ativador_trailing: 0.030, distancia_trailing: 0.020, saida_escalonada: '50/25, 75/25, 90/25' },
}

export function perfilSaida(estilo?: string | null): PerfilSaida {
  return PERFIS[(estilo ?? '').trim().toLowerCase()] ?? PERFIS.daytrade
}

/** Lê '50/30, 75/30' como pares [avanço, fração] em fração de 1. Devolve null quando o texto não é um plano. */
export function analisarPlano(texto?: string | null): [number, number][] | null {
  if (!texto || !texto.trim()) return null
  const fatias: [number, number][] = []
  for (const parte of texto.replace(/;/g, ',').split(',')) {
    const t = parte.trim()
    if (!t) continue
    const [a, f] = t.split('/')
    const avanco = Number(a) / 100
    const fracao = Number(f) / 100
    if (!Number.isFinite(avanco) || !Number.isFinite(fracao)) return null
    if (!(avanco > 0 && avanco <= 1) || !(fracao > 0 && fracao < 1)) return null
    fatias.push([avanco, fracao])
  }
  if (!fatias.length) return null
  if (fatias.reduce((s, [, f]) => s + f, 0) >= 1) return null
  if (new Set(fatias.map(([a]) => a)).size !== fatias.length) return null
  return fatias.sort((x, y) => x[0] - y[0])
}
