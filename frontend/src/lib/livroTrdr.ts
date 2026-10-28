/**
 * A regra do Order Book Depth Overlay do TRDR (as "nuvens"), com as configurações do usuário vistas no TRDR em
 * 21/10/2026: profundidade de 1% (inclusive) a 10%, livro spot, Ratio Minimum Bids/Asks 40, Opacity Cap 100, escala
 * fixa. Cada faixa de distância (1–2,5%, 2,5–5%, 5–10%) é desenhada sozinha, na sua distância do preço.
 *
 * O "ratio" do TRDR vai de 0 a 100 (a doc divide a cor em 20 caixas de 5 pontos e fala em "ratio acima de 90"): é o
 * quanto um lado domina o total da faixa, 100 × |compra − venda| ÷ (compra + venda). 0 = empate; 40 = um lado com 70%
 * do livro da faixa (2,3 contra 1); 100 = só um lado. A verde (compra) aparece abaixo do preço quando a compra domina
 * com ratio ≥ 40; a vermelha (venda), acima, no espelho. A cor tem 20 níveis: ratio 40 = nível 8, 100 = nível 20.
 *
 * (Até 28/10/2026 o ratio era lido como "um lado X% maior que o outro", e 40 virava 1,4 contra 1: a nuvem acendia em
 * 45% das faixas em 7 dias de livro da Coinbase, contra 15% com a leitura de 0 a 100.)
 *
 * Usada pela tela Nuvens e pelo gráfico da tela Gráfico (só no COINBASE:BTC-USD).
 */
import type { NuvensCategoria, NuvensPonto } from '../api/types'

export const LIVRO_TRDR = { de: 0.01, ate: 0.10, minCompra: 40, minVenda: 40, niveis: 20, alfaMax: 0.85 }
/** verde-água (compra) e vermelho (venda), as cores das velas */
export const RGB_LADO = [[38, 166, 154], [239, 83, 80]] as const

/** folga para o ponto flutuante: um ratio de exatamente 40 pode sair 39,99999999999999 e não acender */
const FOLGA = 1e-9

/** ratio do TRDR, de 0 (empate) a 100 (só um lado) */
export const ratioLivro = (compra: number, venda: number) =>
  compra + venda > 0 ? (100 * Math.abs(compra - venda)) / (compra + venda) : 0

/** ratio (0–100) → opacidade em 20 degraus; abaixo do mínimo, nada */
export const opacidadeLivro = (ratio: number, minimo: number) => {
  if (ratio < minimo - FOLGA) return 0
  const nivel = Math.max(1, Math.ceil((LIVRO_TRDR.niveis * Math.min(ratio, 100)) / 100 - FOLGA))
  return (LIVRO_TRDR.alfaMax * nivel) / LIVRO_TRDR.niveis
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
    const r = ratioLivro(b, a)
    if (b > a) {
      const alfa = opacidadeLivro(r, LIVRO_TRDR.minCompra)
      if (alfa > 0) saida.push({ lado: 0, lo: p.mid * (1 - c.hi), hi: p.mid * (1 - c.lo), alfa })
    } else if (a > b) {
      const alfa = opacidadeLivro(r, LIVRO_TRDR.minVenda)
      if (alfa > 0) saida.push({ lado: 1, lo: p.mid * (1 + c.lo), hi: p.mid * (1 + c.hi), alfa })
    }
  })
  return saida
}
