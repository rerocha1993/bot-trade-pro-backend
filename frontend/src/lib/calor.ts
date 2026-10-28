/**
 * Cor das paredes do livro (heatmap de liquidez): frio (só acima do normal) → cor do lado → quente (parede muito acima
 * do normal). Usada nas "Paredes de agora" e no heatmap.
 */
import type { CelulaCalor } from '../api/types'

const ESCALA = {
  bids: [[16, 92, 70, 0.30], [46, 204, 132, 0.62], [236, 232, 110, 0.92]],
  asks: [[112, 30, 42, 0.30], [240, 84, 79, 0.62], [255, 196, 92, 0.92]],
} as const
const FRIO = 2, QUENTE = 12

/** 0 no limite de "acima do normal", 1 em 12x ou mais; escala log para 3x e 6x ficarem bem distintos. */
const nivel = (inten: number) => Math.max(0, Math.min(1, Math.log(inten / FRIO) / Math.log(QUENTE / FRIO)))

/** Cor do mapa de calor em números (0–255 e alfa 0–1): frio → cor do lado → quente. */
export function corRGBA(lado: 0 | 1, inten: number): [number, number, number, number] {
  const e = lado === 0 ? ESCALA.bids : ESCALA.asks
  const t = nivel(inten)
  const [a, b, u] = t < 0.5 ? [e[0], e[1], t / 0.5] : [e[1], e[2], (t - 0.5) / 0.5]
  const m = (i: number) => a[i] + (b[i] - a[i]) * u
  return [m(0), m(1), m(2), m(3)]
}

export function corCalor(lado: 0 | 1, inten: number): string {
  const [r, g, b, a] = corRGBA(lado, inten)
  return `rgba(${r.toFixed(0)},${g.toFixed(0)},${b.toFixed(0)},${a.toFixed(3)})`
}

/** Força de uma célula: a maior entre a régua histórica e a das vizinhas. */
export const forca = (c: CelulaCalor) => Math.max(c[4], c[5] ?? 0)
