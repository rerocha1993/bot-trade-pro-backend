/**
 * As ferramentas de desenho (no molde da barra da esquerda da TradingView). Cada uma diz quantos pontos precisa, a
 * configuração padrão da TradingView, como se desenha no canvas e quando o mouse está em cima dela. Quem cuida do mouse
 * é o GraficoTV e quem junta tudo no gráfico é a desenhosPrimitiva; a janela de configuração de cada uma fica em
 * DesenhoConfig.
 *
 * Etapa 1 (05/11/2026): a base, com linha de tendência, linha horizontal e Fibonacci de retração. As outras entram
 * aqui nas próximas etapas, cada uma com a sua entrada nesta lista.
 */
import { PADRAO_TV as FIBO_TV, comAlfa, copiar, niveisDe, tracos, type ConfigFibo, type Fibo } from '../../lib/fibo'
import { TEXTO_PADRAO, type Cfg, type Desenho, type Linha, type Texto } from '../../lib/desenhos'

export type Px = { x: number; y: number }
export type Geo = {
  W: number; H: number
  /** preço com as casas da moeda */
  formatar: (p: number) => string
  y: (p: number) => number | null
  /** segundos por vela */
  passo: number
  /** desenho selecionado (ou sendo desenhado): mostra o que só aparece na seleção */
  selecionado: boolean
}

export type GrupoId = 'linhas' | 'fibonacci'
export const GRUPOS: { id: GrupoId; nome: string }[] = [{ id: 'linhas', nome: 'Linhas' }, { id: 'fibonacci', nome: 'Fibonacci' }]

export interface Ferramenta {
  tipo: string
  nome: string
  grupo: GrupoId
  /** atalho da TradingView (Alt + letra) */
  atalho?: string
  /** desenho do ícone: caminho SVG num quadrado de 18 */
  icone: string
  /** quantos cliques para desenhar */
  pontos: number
  padrao: () => Cfg
  /** a cor, a espessura e o estilo que a barra flutuante muda */
  linha: { ler: (c: Cfg) => Linha; gravar: (c: Cfg, l: Linha) => Cfg }
  /** tem aba Texto */
  texto?: boolean
  /** só o preço importa (a aba Coordenadas não pede a barra) */
  soPreco?: boolean
  desenhar: (ctx: CanvasRenderingContext2D, d: Desenho, px: Px[], g: Geo) => void
  acertar: (x: number, y: number, d: Desenho, px: Px[], g: Geo) => boolean
  /** rótulos que ficam sempre na escala de preço (a linha horizontal) */
  rotulosPreco?: (d: Desenho) => { preco: number; cor: string }[]
  /** uma linha para a lista de objetos */
  resumo: (d: Desenho, formatar: (p: number) => string) => string
}

/** distância (px) até a linha que ainda conta como em cima dela */
export const PERTO_PX = 5

// ---------------------------------------------------------------- ajudantes de desenho

export function tracar(ctx: CanvasRenderingContext2D, l: Linha) {
  ctx.strokeStyle = l.cor
  ctx.lineWidth = l.largura
  ctx.setLineDash(tracos(l.estilo, l.largura))
}

export function distSegmento(px: number, py: number, ax: number, ay: number, bx: number, by: number): number {
  const dx = bx - ax, dy = by - ay
  const l2 = dx * dx + dy * dy
  const t = l2 ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / l2)) : 0
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy))
}

/** o segmento a→b esticado para além de a e/ou de b até sair da tela */
function estender(a: Px, b: Px, antes: boolean, depois: boolean, W: number, H: number): [Px, Px] {
  const dx = b.x - a.x, dy = b.y - a.y
  const L = Math.hypot(dx, dy)
  if (!L) return [a, b]
  const k = (W + H) * 4 / L
  return [antes ? { x: a.x - dx * k, y: a.y - dy * k } : a, depois ? { x: b.x + dx * k, y: b.y + dy * k } : b]
}

function seta(ctx: CanvasRenderingContext2D, ponta: Px, de: Px, largura: number) {
  const ang = Math.atan2(ponta.y - de.y, ponta.x - de.x)
  const tam = 8 + largura * 2
  ctx.setLineDash([])
  ctx.beginPath()
  ctx.moveTo(ponta.x - tam * Math.cos(ang - Math.PI / 7), ponta.y - tam * Math.sin(ang - Math.PI / 7))
  ctx.lineTo(ponta.x, ponta.y)
  ctx.lineTo(ponta.x - tam * Math.cos(ang + Math.PI / 7), ponta.y - tam * Math.sin(ang + Math.PI / 7))
  ctx.stroke()
}

const fonteDe = (t: Texto) => `${t.italico ? 'italic ' : ''}${t.negrito ? 'bold ' : ''}${t.tamanho}px 'DM Sans', sans-serif`

/** texto ao longo do segmento a→b (girado como a linha), na ponta, no meio ou na outra ponta, em cima ou embaixo */
function textoNaLinha(ctx: CanvasRenderingContext2D, t: Texto, a: Px, b: Px) {
  if (!t.texto.trim()) return
  // da esquerda para a direita, para o texto nunca ficar de cabeça para baixo
  const [e, d] = a.x <= b.x ? [a, b] : [b, a]
  const ang = Math.atan2(d.y - e.y, d.x - e.x)
  const L = Math.hypot(d.x - e.x, d.y - e.y)
  ctx.save()
  ctx.font = fonteDe(t)
  ctx.fillStyle = t.cor
  ctx.translate(e.x, e.y)
  ctx.rotate(ang)
  const linhas = t.texto.split('\n')
  const alt = t.tamanho * 1.25
  const x = t.h === 'esquerda' ? 4 : t.h === 'direita' ? L - 4 : L / 2
  ctx.textAlign = t.h === 'esquerda' ? 'left' : t.h === 'direita' ? 'right' : 'center'
  ctx.textBaseline = 'middle'
  const total = alt * linhas.length
  const y0 = t.v === 'cima' ? -total - 2 + alt / 2 : t.v === 'baixo' ? 4 + alt / 2 : -total / 2 + alt / 2
  linhas.forEach((s, i) => ctx.fillText(s, x, y0 + i * alt))
  ctx.restore()
}

/** caixa escura com linhas de texto (estatísticas, rótulos) */
export function caixaTexto(ctx: CanvasRenderingContext2D, linhas: string[], x: number, y: number, ancora: 'esquerda' | 'centro' | 'direita', W: number, cor = '#e8ecf2') {
  ctx.save()
  ctx.font = "11.5px 'DM Mono', monospace"
  const alt = 16, pad = 6
  const larg = Math.max(...linhas.map((s) => ctx.measureText(s).width)) + pad * 2
  let x0 = ancora === 'esquerda' ? x : ancora === 'direita' ? x - larg : x - larg / 2
  x0 = Math.max(2, Math.min(W - larg - 2, x0))
  const h = alt * linhas.length + pad
  ctx.fillStyle = 'rgba(19,23,34,0.92)'
  ctx.strokeStyle = 'rgba(255,255,255,0.12)'
  ctx.lineWidth = 1
  ctx.setLineDash([])
  ctx.beginPath(); ctx.roundRect(x0, y, larg, h, 4); ctx.fill(); ctx.stroke()
  ctx.fillStyle = cor
  ctx.textBaseline = 'middle'
  ctx.textAlign = 'left'
  linhas.forEach((s, i) => ctx.fillText(s, x0 + pad, y + pad / 2 + alt * i + alt / 2))
  ctx.restore()
}

export function duracao(seg: number): string {
  const s = Math.abs(seg)
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60)
  return [d && `${d}d`, h && `${h}h`, m && `${m}m`].filter(Boolean).join(' ') || '0m'
}

const pct = (v: number) => `${v >= 0 ? '+' : ''}${(v * 100).toFixed(2).replace('.', ',')}%`

// ---------------------------------------------------------------- linha de tendência

export type CfgTendencia = {
  linha: Linha
  estEsq: boolean; estDir: boolean
  pontaEsq: 'normal' | 'seta'; pontaDir: 'normal' | 'seta'
  meio: boolean
  precos: boolean
  stats: { preco: boolean; pct: boolean; barras: boolean; tempo: boolean; distancia: boolean; angulo: boolean }
  statsPos: 'esquerda' | 'centro' | 'direita'
  statsSempre: boolean
  texto: Texto
}
export const TENDENCIA_TV: CfgTendencia = {
  linha: { cor: '#2962ff', largura: 2, estilo: 'solida' },
  estEsq: false, estDir: false, pontaEsq: 'normal', pontaDir: 'normal', meio: false, precos: false,
  stats: { preco: true, pct: true, barras: true, tempo: true, distancia: false, angulo: false },
  statsPos: 'direita', statsSempre: false,
  texto: { ...TEXTO_PADRAO },
}

function estatisticas(d: Desenho, px: Px[], g: Geo, s: CfgTendencia['stats']): string[] {
  const [a, b] = d.pts
  const out: string[] = []
  const dp = b.p - a.p
  if (s.preco || s.pct) out.push([s.preco && `${dp >= 0 ? '+' : ''}${g.formatar(dp)}`, s.pct && a.p && `(${pct(dp / a.p)})`].filter(Boolean).join(' '))
  if (s.barras || s.tempo) {
    const barras = Math.round((b.t - a.t) / g.passo)
    out.push([s.barras && `${barras} barras`, s.tempo && duracao(b.t - a.t)].filter(Boolean).join(', '))
  }
  if (s.distancia) out.push(`distância ${Math.round(Math.hypot(px[1].x - px[0].x, px[1].y - px[0].y))} px`)
  if (s.angulo) out.push(`${Math.round(Math.atan2(px[0].y - px[1].y, px[1].x - px[0].x) * 180 / Math.PI)}°`)
  return out.filter(Boolean)
}

const tendencia: Ferramenta = {
  tipo: 'linha_tendencia', nome: 'Linha de tendência', grupo: 'linhas', atalho: 'T', pontos: 2, texto: true,
  icone: 'M3 15 L15 3 M3 15 m-1.5 0 a1.5 1.5 0 1 0 3 0 a1.5 1.5 0 1 0 -3 0 M15 3 m-1.5 0 a1.5 1.5 0 1 0 3 0 a1.5 1.5 0 1 0 -3 0',
  padrao: () => copiar(TENDENCIA_TV),
  linha: { ler: (c: CfgTendencia) => c.linha, gravar: (c: CfgTendencia, l) => ({ ...c, linha: l }) },
  desenhar(ctx, d, px, g) {
    const c = d.cfg as CfgTendencia
    const [a, b] = px
    const [e1, e2] = estender(a, b, c.estEsq, c.estDir, g.W, g.H)
    tracar(ctx, c.linha)
    ctx.beginPath(); ctx.moveTo(e1.x, e1.y); ctx.lineTo(e2.x, e2.y); ctx.stroke()
    if (c.pontaEsq === 'seta' && !c.estEsq) seta(ctx, a, b, c.linha.largura)
    if (c.pontaDir === 'seta' && !c.estDir) seta(ctx, b, a, c.linha.largura)
    ctx.setLineDash([])
    if (c.meio) {
      ctx.beginPath(); ctx.arc((a.x + b.x) / 2, (a.y + b.y) / 2, 3, 0, Math.PI * 2); ctx.fillStyle = c.linha.cor; ctx.fill()
    }
    if (c.precos) {
      ctx.font = "11px 'DM Mono', monospace"; ctx.fillStyle = c.linha.cor; ctx.textBaseline = 'bottom'; ctx.textAlign = 'center'
      d.pts.forEach((p, i) => ctx.fillText(g.formatar(p.p), px[i].x, px[i].y - 8))
    }
    textoNaLinha(ctx, c.texto, a, b)
    if ((c.statsSempre || g.selecionado) && Object.values(c.stats).some(Boolean)) {
      const linhas = estatisticas(d, px, g, c.stats)
      if (linhas.length) {
        const ref = c.statsPos === 'esquerda' ? (a.x <= b.x ? a : b) : c.statsPos === 'direita' ? (a.x <= b.x ? b : a) : { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
        caixaTexto(ctx, linhas, ref.x + (c.statsPos === 'centro' ? 0 : c.statsPos === 'direita' ? 10 : -10), ref.y + 10, c.statsPos === 'direita' ? 'esquerda' : c.statsPos === 'esquerda' ? 'direita' : 'centro', g.W)
      }
    }
  },
  acertar(x, y, d, px, g) {
    const c = d.cfg as CfgTendencia
    const [e1, e2] = estender(px[0], px[1], c.estEsq, c.estDir, g.W, g.H)
    return distSegmento(x, y, e1.x, e1.y, e2.x, e2.y) <= PERTO_PX
  },
  resumo: (d, f) => `${f(d.pts[0].p)} → ${f(d.pts[1]?.p ?? d.pts[0].p)}`,
}

// ---------------------------------------------------------------- linha horizontal

export type CfgHorizontal = { linha: Linha; rotuloPreco: boolean; texto: Texto }
export const HORIZONTAL_TV: CfgHorizontal = {
  linha: { cor: '#2962ff', largura: 1, estilo: 'solida' }, rotuloPreco: true,
  texto: { ...TEXTO_PADRAO, h: 'direita' },
}

const horizontal: Ferramenta = {
  tipo: 'linha_horizontal', nome: 'Linha horizontal', grupo: 'linhas', atalho: 'H', pontos: 1, texto: true, soPreco: true,
  icone: 'M1 9 H17 M9 9 m-1.5 0 a1.5 1.5 0 1 0 3 0 a1.5 1.5 0 1 0 -3 0',
  padrao: () => copiar(HORIZONTAL_TV),
  linha: { ler: (c: CfgHorizontal) => c.linha, gravar: (c: CfgHorizontal, l) => ({ ...c, linha: l }) },
  desenhar(ctx, d, px, g) {
    const c = d.cfg as CfgHorizontal
    const y = Math.round(px[0].y) + (c.linha.largura % 2 ? 0.5 : 0)
    tracar(ctx, c.linha)
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(g.W, y); ctx.stroke()
    ctx.setLineDash([])
    textoNaLinha(ctx, c.texto, { x: 0, y }, { x: g.W, y })
  },
  acertar: (_x, y, _d, px) => Math.abs(y - px[0].y) <= PERTO_PX,
  rotulosPreco: (d) => ((d.cfg as CfgHorizontal).rotuloPreco ? [{ preco: d.pts[0].p, cor: (d.cfg as CfgHorizontal).linha.cor }] : []),
  resumo: (d, f) => f(d.pts[0].p),
}

// ---------------------------------------------------------------- Fibonacci de retração

const comoFibo = (d: Desenho): Fibo => ({ id: d.id, t1: d.pts[0].t, p1: d.pts[0].p, t2: d.pts[1]?.t ?? d.pts[0].t, p2: d.pts[1]?.p ?? d.pts[0].p, cfg: d.cfg as ConfigFibo })

function niveisPx(d: Desenho, px: Px[], g: Geo) {
  const c = d.cfg as ConfigFibo
  const niveis = []
  for (const n of niveisDe(comoFibo(d))) {
    const y = g.y(n.preco)
    if (y !== null) niveis.push({ ...n, y })
  }
  const esq = c.estenderEsq ? 0 : Math.min(px[0].x, px[1].x)
  const dir = c.estenderDir ? g.W : Math.max(px[0].x, px[1].x)
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
    if (c.tendencia.ligada) {
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
    if (c.tendencia.ligada && distSegmento(x, y, px[0].x, px[0].y, px[1].x, px[1].y) <= PERTO_PX) return true
    if (g.selecionado && dentroX && niveis.length > 1) {
      const ys = niveis.map((n) => n.y)
      return y >= Math.min(...ys) && y <= Math.max(...ys)
    }
    return false
  },
  resumo: (d, f) => `${f(d.pts[0].p)} → ${f(d.pts[1]?.p ?? d.pts[0].p)}`,
}

export const FERRAMENTAS: Ferramenta[] = [tendencia, horizontal, fibo]
export const FERRAMENTA: Record<string, Ferramenta> = Object.fromEntries(FERRAMENTAS.map((f) => [f.tipo, f]))
