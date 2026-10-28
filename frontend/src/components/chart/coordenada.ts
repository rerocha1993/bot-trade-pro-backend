/**
 * Posição x de um índice de vela que pode ser fracionário (um bloco de 5 min num gráfico de 15 min cai entre duas
 * velas). `timeScale().logicalToCoordinate` da lightweight-charts 4.2 devolve 0 para índice não inteiro, o que
 * achatava no canto esquerdo tudo o que não começava exatamente numa vela; aqui a parte fracionária anda pela
 * largura da vela.
 */
import type { IChartApi, Logical } from 'lightweight-charts'

export function xDoIndice(chart: IChartApi, indice: number, barSpacing?: number): number | null {
  const ts = chart.timeScale()
  const base = Math.floor(indice)
  const x = ts.logicalToCoordinate(base as Logical)
  if (x === null) return null
  // options() copia o objeto de opções inteiro: quem desenha muitas colunas passa a largura já lida
  return x + (indice - base) * (barSpacing ?? ts.options().barSpacing)
}
