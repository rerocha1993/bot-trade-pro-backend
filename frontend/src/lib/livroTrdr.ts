/**
 * A regra do Order Book Depth Overlay do TRDR (as "nuvens"), com as configurações do usuário vistas no TRDR em
 * 21/10/2026: profundidade de 1% (inclusive) a 10%, livro spot, Ratio Minimum Bids/Asks 40, Opacity Cap 100, escala
 * fixa. Cada faixa de distância (1–2,5%, 2,5–5%, 5–10%) é desenhada sozinha, na sua distância do preço: a verde
 * (compra) aparece abaixo quando há pelo menos 40% MAIS compra que venda naquela faixa; a vermelha (venda), acima, no
 * espelho. A cor tem 20 níveis (como no Style do TRDR): 40% a mais = nível 8, o dobro (100%) ou mais = 20.
 *
 * Usada pela tela Nuvens e pelo gráfico da tela Gráfico (só no COINBASE:BTC-USD).
 */
import type { NuvensCategoria, NuvensPonto } from '../api/types'

export const LIVRO_TRDR = { de: 0.01, ate: 0.10, teto: 100, minCompra: 40, minVenda: 40, niveis: 20, alfaMax: 0.85 }
/** verde-água (compra) e vermelho (venda), as cores das velas */
export const RGB_LADO = [[38, 166, 154], [239, 83, 80]] as const

/** quanto um lado passa o outro (em %) → opacidade em 20 degraus; abaixo do mínimo, nada */
export const opacidadeLivro = (aMais: number, minimo: number) => {
  if (aMais < minimo) return 0
  const nivel = Math.max(1, Math.ceil(LIVRO_TRDR.niveis * Math.min(aMais, LIVRO_TRDR.teto) / LIVRO_TRDR.teto))
  return LIVRO_TRDR.alfaMax * nivel / LIVRO_TRDR.niveis
}

/** uma faixa acesa: lado 0 = compra (abaixo do preço), 1 = venda (acima); preços de `lo` a `hi`; `alfa` 0–1 */
export type BandaLivro = { lado: 0 | 1; lo: number; hi: number; alfa: number }

/** As faixas que acendem num ponto do livro (uma vela), já nos preços em volta do mid. */
export function bandasDoPonto(p: NuvensPonto, categorias: NuvensCategoria[]): BandaLivro[] {
  const saida: BandaLivro[] = []
  categorias.forEach((c, k) => {
    if (c.lo < LIVRO_TRDR.de - 1e-9 || c.hi > LIVRO_TRDR.ate + 1e-9) return
    const b = p.bids[k] ?? 0, a = p.asks[k] ?? 0
    if (b <= 0 || a <= 0) return
    const compra = opacidadeLivro(100 * (b / a - 1), LIVRO_TRDR.minCompra)
    if (compra > 0) saida.push({ lado: 0, lo: p.mid * (1 - c.hi), hi: p.mid * (1 - c.lo), alfa: compra })
    const venda = opacidadeLivro(100 * (a / b - 1), LIVRO_TRDR.minVenda)
    if (venda > 0) saida.push({ lado: 1, lo: p.mid * (1 + c.lo), hi: p.mid * (1 + c.hi), alfa: venda })
  })
  return saida
}
