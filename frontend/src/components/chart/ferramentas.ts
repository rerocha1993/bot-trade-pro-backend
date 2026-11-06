/**
 * As ferramentas de desenho (no molde da barra da esquerda da TradingView): a lista de todas e o Fibonacci de retração.
 * As outras ficam em ferramentasLinhas.ts (linhas e canais), ferramentasFormas.ts (medidas, formas e setas) e
 * ferramentasTexto.ts (texto e notas); o formato de uma ferramenta e os ajudantes de canvas, em ferramentasBase.ts.
 *
 * Etapa 1 (05/11/2026): a base, a linha de tendência, a horizontal e o Fibonacci. Etapa 2: as outras linhas, canais,
 * medidas, formas, texto e setas. Etapa 3: a família Fibonacci (ferramentasFibo.ts), pitchforks e Gann
 * (ferramentasGann.ts). Etapa 4: Elliott, padrões e posição comprada/vendida (ferramentasPadroes.ts). Etapa 5: VWAP
 * ancorada, perfis de volume, ciclos, previsão, padrão de barras, ghost feed, projeção, pincel, marca-texto, ícone, tabela
 * e imagem (ferramentasAnalise.ts). Cada ferramenta nova é uma entrada nas listas, com a sua configuração.
 */
import { PADRAO_TV as FIBO_TV, comAlfa, copiar, niveisDe, tracos, type ConfigFibo, type Fibo } from '../../lib/fibo'
import type { Desenho } from '../../lib/desenhos'
import { distSegmento, PERTO_PX, resumoPrecos, tracar, type Ferramenta, type Geo, type Px } from './ferramentasBase'
import { ANALISE, ANOTACOES, CICLOS, LIVRES, PROJECAO } from './ferramentasAnalise'
import { FIBO_FAMILIA } from './ferramentasFibo'
import { MEDIDAS, FORMAS, SETAS } from './ferramentasFormas'
import { GANN } from './ferramentasGann'
import { ELLIOTT, PADROES, POSICOES } from './ferramentasPadroes'
import { CANAIS, LINHAS, setaLinha } from './ferramentasLinhas'
import { TEXTOS } from './ferramentasTexto'

export { GRUPOS, type Ferramenta, type Geo, type GrupoId, type Px, type Campo } from './ferramentasBase'
export { HORIZONTAL_TV, TENDENCIA_TV, type CfgHorizontal, type CfgTendencia } from './ferramentasLinhas'

const comoFibo = (d: Desenho): Fibo => ({ id: d.id, t1: d.pts[0].t, p1: d.pts[0].p, t2: d.pts[1]?.t ?? d.pts[0].t, p2: d.pts[1]?.p ?? d.pts[0].p, cfg: d.cfg as ConfigFibo })

function niveisPx(d: Desenho, px: Px[], g: Geo) {
  const c = d.cfg as ConfigFibo
  const niveis = []
  for (const n of niveisDe(comoFibo(d))) {
    const y = g.y(n.preco)
    if (y !== null) niveis.push({ ...n, y })
  }
  const b = px[1] ?? px[0]
  const esq = c.estenderEsq ? 0 : Math.min(px[0].x, b.x)
  const dir = c.estenderDir ? g.W : Math.max(px[0].x, b.x)
  return { niveis, esq, dir }
}

const fibo: Ferramenta = {
  tipo: 'fibo_retracao', nome: 'Fibonacci de retração', grupo: 'fibonacci', atalho: 'F', pontos: 2,
  icone: 'M2 3 H16 M2 7 H16 M2 11 H16 M2 15 H16 M3 15 L15 3',
  padrao: () => copiar(FIBO_TV),
  linha: {
    ler: (c: ConfigFibo) => ({ cor: c.tendencia.cor, largura: c.larguraNiveis, estilo: c.estiloNiveis }),
    gravar: (c: ConfigFibo, l) => ({ ...c, tendencia: { ...c.tendencia, cor: l.cor }, larguraNiveis: l.largura, estiloNiveis: l.estilo }),
  },
  desenhar(ctx, d, px, g) {
    const c = d.cfg as ConfigFibo
    const { niveis, esq, dir } = niveisPx(d, px, g)
    // fundo: cada faixa entre dois níveis com a cor do nível de cima (o de valor maior), como na TradingView
    if (c.fundo && c.transparencia < 100) {
      const alfa = (100 - c.transparencia) / 100
      for (let i = 1; i < niveis.length; i++) {
        const a = niveis[i - 1], b = niveis[i]
        ctx.fillStyle = comAlfa(b.cor, alfa)
        ctx.fillRect(esq, Math.min(a.y, b.y), dir - esq, Math.abs(b.y - a.y))
      }
    }
    ctx.lineWidth = c.larguraNiveis
    ctx.setLineDash(tracos(c.estiloNiveis, c.larguraNiveis))
    for (const n of niveis) {
      ctx.strokeStyle = n.cor
      const y = Math.round(n.y) + (c.larguraNiveis % 2 ? 0.5 : 0)
      ctx.beginPath(); ctx.moveTo(esq, y); ctx.lineTo(dir, y); ctx.stroke()
    }
    ctx.setLineDash([])
    if (c.tendencia.ligada && px[1]) {
      tracar(ctx, { cor: c.tendencia.cor, largura: c.tendencia.largura, estilo: c.tendencia.estilo })
      ctx.beginPath(); ctx.moveTo(px[0].x, px[0].y); ctx.lineTo(px[1].x, px[1].y); ctx.stroke()
      ctx.setLineDash([])
    }
    if (c.rotulos || c.precos) {
      ctx.font = `${c.fonte}px 'DM Mono', monospace`
      ctx.textBaseline = c.vertical === 'cima' ? 'bottom' : c.vertical === 'baixo' ? 'top' : 'middle'
      const dy = c.vertical === 'cima' ? -2 : c.vertical === 'baixo' ? 2 : 0
      for (const n of niveis) {
        const nome = c.rotuloComo === 'percentual' ? `${+(n.valor * 100).toFixed(1)}%` : String(+n.valor.toFixed(4))
        const texto = (c.rotulos ? nome : '') + (c.precos ? (c.rotulos ? `(${g.formatar(n.preco)})` : g.formatar(n.preco)) : '')
        const w = ctx.measureText(texto).width
        let x: number
        if (c.horizontal === 'centro') x = (esq + dir) / 2 - w / 2
        else if (c.horizontal === 'direita') { x = dir + 4; if (x + w > g.W) x = dir - w - 4 }
        else { x = esq - w - 4; if (x < 0) x = esq + 4 }
        ctx.fillStyle = n.cor
        ctx.textAlign = 'left'
        ctx.fillText(texto, x, n.y + dy)
      }
    }
  },
  acertar(x, y, d, px, g) {
    const c = d.cfg as ConfigFibo
    const { niveis, esq, dir } = niveisPx(d, px, g)
    const dentroX = x >= esq - PERTO_PX && x <= dir + PERTO_PX
    if (dentroX && niveis.some((n) => Math.abs(y - n.y) <= PERTO_PX)) return true
    if (c.tendencia.ligada && px[1] && distSegmento(x, y, px[0].x, px[0].y, px[1].x, px[1].y) <= PERTO_PX) return true
    if (g.selecionado && dentroX && niveis.length > 1) {
      const ys = niveis.map((n) => n.y)
      return y >= Math.min(...ys) && y <= Math.max(...ys)
    }
    return false
  },
  resumo: resumoPrecos,
}

export const FERRAMENTAS: Ferramenta[] = [...LINHAS, ...CANAIS, fibo, ...FIBO_FAMILIA, ...GANN, ...ELLIOTT, ...PADROES, ...POSICOES, ...PROJECAO, ...MEDIDAS, ...ANALISE, ...CICLOS, ...FORMAS, ...LIVRES, ...TEXTOS, ...ANOTACOES, setaLinha, ...SETAS]
export const FERRAMENTA: Record<string, Ferramenta> = Object.fromEntries(FERRAMENTAS.map((f) => [f.tipo, f]))
