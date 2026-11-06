/**
 * O que toda ferramenta de desenho usa: o formato de uma ferramenta (pontos, padrão da TradingView, desenho, acerto,
 * campos da aba Estilo) e os ajudantes de canvas (linha, seta, texto, caixa, fundo, distância até segmento e polígono).
 * As ferramentas em si ficam em ferramentasLinhas.ts, ferramentasFormas.ts, ferramentasTexto.ts e ferramentas.ts
 * (que também tem a lista de todas).
 */
import { tracos, type EstiloLinha } from '../../lib/fibo'
import type { Cfg, Desenho, Linha, Texto } from '../../lib/desenhos'

export type Px = { x: number; y: number }
export type VelaG = { t: number; o: number; h: number; l: number; c: number; v: number }
export type Geo = {
  W: number; H: number
  /** preço com as casas da moeda */
  formatar: (p: number) => string
  y: (p: number) => number | null
  x: (t: number) => number | null
  /** segundos por vela */
  passo: number
  /** desenho selecionado (ou sendo desenhado): mostra o que só aparece na seleção */
  selecionado: boolean
  /** as velas carregadas entre dois instantes (inclusive) */
  velas: (t1: number, t2: number) => VelaG[]
}

export type GrupoId = 'linhas' | 'canais' | 'fibonacci' | 'medidas' | 'formas' | 'texto' | 'setas'
export const GRUPOS: { id: GrupoId; nome: string }[] = [
  { id: 'linhas', nome: 'Linhas' }, { id: 'canais', nome: 'Canais' }, { id: 'fibonacci', nome: 'Fibonacci' },
  { id: 'medidas', nome: 'Medidas' }, { id: 'formas', nome: 'Formas' }, { id: 'texto', nome: 'Texto e notas' }, { id: 'setas', nome: 'Setas' },
]

/** um campo da aba Estilo; `chave` aceita caminho com ponto ('stats.preco') */
export type Campo =
  | { tipo: 'linha'; chave: string; nome: string }
  | { tipo: 'cor'; chave: string; nome: string }
  | { tipo: 'fundo'; chave: string; nome: string }
  | { tipo: 'bool'; chave: string; nome: string }
  | { tipo: 'escolha'; chave: string; nome: string; opcoes: [string, string][] }
  | { tipo: 'numero'; chave: string; nome: string; min?: number; max?: number; passo?: number }
  | { tipo: 'secao'; nome: string }

type Acesso<T> = { ler: (c: Cfg) => T; gravar: (c: Cfg, v: T) => Cfg }

export interface Ferramenta {
  tipo: string
  nome: string
  grupo: GrupoId
  /** atalho da TradingView: letra com Alt ('T' = Alt+T; 'Shift+R' = Alt+Shift+R) */
  atalho?: string
  /** desenho do ícone: caminho SVG num quadrado de 18 */
  icone: string
  /** quantos cliques para desenhar; 0 = quantos quiser (termina com duplo clique ou Enter) */
  pontos: number
  padrao: () => Cfg
  /** a cor, a espessura e o estilo que a barra flutuante muda */
  linha?: Acesso<Linha>
  /** só a cor (ferramentas de texto, marcas) */
  cor?: Acesso<string>
  /** a cor do fundo, na barra flutuante */
  fundo?: Acesso<string>
  /** campos da aba Estilo (o Fibonacci tem a aba própria) */
  campos?: Campo[]
  /** tem aba Texto (cfg.texto) */
  texto?: boolean
  /** abre a aba Texto logo depois de desenhar */
  pedeTexto?: boolean
  /** só o preço importa (linha horizontal) / só o tempo (linha vertical, regressão) */
  soPreco?: boolean
  soTempo?: boolean
  /** preso à tela, não ao gráfico: os pontos são frações da largura e da altura */
  tela?: boolean
  desenhar: (ctx: CanvasRenderingContext2D, d: Desenho, px: Px[], g: Geo) => void
  acertar: (x: number, y: number, d: Desenho, px: Px[], g: Geo) => boolean
  /** onde ficam as alças (por padrão, nos pontos) */
  alcas?: (d: Desenho, px: Px[], g: Geo) => Px[]
  /** rótulos que ficam sempre nas escalas */
  rotulosPreco?: (d: Desenho) => { preco: number; cor: string }[]
  rotulosTempo?: (d: Desenho) => { t: number; cor: string }[]
  /** uma linha para a lista de objetos */
  resumo: (d: Desenho, formatar: (p: number) => string) => string
}

/** distância (px) até a linha que ainda conta como em cima dela */
export const PERTO_PX = 5

export type Fundo = { ligado: boolean; cor: string; transparencia: number }
export const fundoPadrao = (cor: string, transparencia = 80): Fundo => ({ ligado: true, cor, transparencia })

// ---------------------------------------------------------------- acesso a campos

export function lerCampo(c: Cfg, chave: string): unknown {
  return chave.split('.').reduce<Cfg>((o, k) => (o == null ? undefined : o[k]), c)
}
export function gravarCampo(c: Cfg, chave: string, v: unknown): Cfg {
  const [k, ...resto] = chave.split('.')
  return { ...c, [k]: resto.length ? gravarCampo(c?.[k] ?? {}, resto.join('.'), v) : v }
}
export const acesso = <T,>(chave: string): Acesso<T> => ({ ler: (c) => lerCampo(c, chave) as T, gravar: (c, v) => gravarCampo(c, chave, v) })

// ---------------------------------------------------------------- canvas

export function comAlfa(cor: string, alfa: number): string {
  const m = /^#([0-9a-f]{6})$/i.exec(cor)
  if (!m) return cor
  const n = parseInt(m[1], 16)
  return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${alfa})`
}
export const corFundo = (f: Fundo) => comAlfa(f.cor, (100 - f.transparencia) / 100)

export function tracar(ctx: CanvasRenderingContext2D, l: Linha) {
  ctx.strokeStyle = l.cor
  ctx.lineWidth = l.largura
  ctx.setLineDash(tracos(l.estilo as EstiloLinha, l.largura))
}

export function linhaReta(ctx: CanvasRenderingContext2D, a: Px, b: Px) {
  ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke()
}

export function poligono(ctx: CanvasRenderingContext2D, pts: Px[], fundo: Fundo | null, borda: Linha | null, fechar = true) {
  if (pts.length < 2) return
  ctx.beginPath()
  ctx.moveTo(pts[0].x, pts[0].y)
  for (const p of pts.slice(1)) ctx.lineTo(p.x, p.y)
  if (fechar) ctx.closePath()
  if (fundo?.ligado && fundo.transparencia < 100) { ctx.fillStyle = corFundo(fundo); ctx.fill() }
  if (borda) { tracar(ctx, borda); ctx.stroke(); ctx.setLineDash([]) }
}

export function distSegmento(px: number, py: number, ax: number, ay: number, bx: number, by: number): number {
  const dx = bx - ax, dy = by - ay
  const l2 = dx * dx + dy * dy
  const t = l2 ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / l2)) : 0
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy))
}
export const pertoSegmento = (x: number, y: number, a: Px, b: Px) => distSegmento(x, y, a.x, a.y, b.x, b.y) <= PERTO_PX
export function pertoPolilinha(x: number, y: number, pts: Px[], fechar = false): boolean {
  for (let i = 1; i < pts.length; i++) if (pertoSegmento(x, y, pts[i - 1], pts[i])) return true
  return fechar && pts.length > 2 && pertoSegmento(x, y, pts[pts.length - 1], pts[0])
}
export function dentroPoligono(x: number, y: number, pts: Px[]): boolean {
  let dentro = false
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const a = pts[i], b = pts[j]
    if ((a.y > y) !== (b.y > y) && x < ((b.x - a.x) * (y - a.y)) / (b.y - a.y) + a.x) dentro = !dentro
  }
  return dentro
}

/** o segmento a→b esticado para além de a e/ou de b até sair da tela */
export function estender(a: Px, b: Px, antes: boolean, depois: boolean, W: number, H: number): [Px, Px] {
  const dx = b.x - a.x, dy = b.y - a.y
  const L = Math.hypot(dx, dy)
  if (!L) return [a, b]
  const k = (W + H) * 4 / L
  return [antes ? { x: a.x - dx * k, y: a.y - dy * k } : a, depois ? { x: b.x + dx * k, y: b.y + dy * k } : b]
}

export function seta(ctx: CanvasRenderingContext2D, ponta: Px, de: Px, largura: number) {
  const ang = Math.atan2(ponta.y - de.y, ponta.x - de.x)
  const tam = 8 + largura * 2
  ctx.setLineDash([])
  ctx.beginPath()
  ctx.moveTo(ponta.x - tam * Math.cos(ang - Math.PI / 7), ponta.y - tam * Math.sin(ang - Math.PI / 7))
  ctx.lineTo(ponta.x, ponta.y)
  ctx.lineTo(ponta.x - tam * Math.cos(ang + Math.PI / 7), ponta.y - tam * Math.sin(ang + Math.PI / 7))
  ctx.stroke()
}

export const fonteDe = (t: Texto) => `${t.italico ? 'italic ' : ''}${t.negrito ? 'bold ' : ''}${t.tamanho}px 'DM Sans', sans-serif`

/** texto ao longo do segmento a→b (girado como a linha), na ponta, no meio ou na outra ponta, em cima ou embaixo */
export function textoNaLinha(ctx: CanvasRenderingContext2D, t: Texto | undefined, a: Px, b: Px) {
  if (!t || !t.texto.trim()) return
  const [e, d] = a.x <= b.x ? [a, b] : [b, a]           // da esquerda para a direita: nunca de cabeça para baixo
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

/** texto num retângulo (formas): alinhado dentro dele */
export function textoNaCaixa(ctx: CanvasRenderingContext2D, t: Texto | undefined, x0: number, y0: number, x1: number, y1: number) {
  if (!t || !t.texto.trim()) return
  const [l, r] = [Math.min(x0, x1), Math.max(x0, x1)], [c, b] = [Math.min(y0, y1), Math.max(y0, y1)]
  ctx.save()
  ctx.font = fonteDe(t); ctx.fillStyle = t.cor
  ctx.textAlign = t.h === 'esquerda' ? 'left' : t.h === 'direita' ? 'right' : 'center'
  ctx.textBaseline = 'middle'
  const linhas = t.texto.split('\n'), alt = t.tamanho * 1.25, total = alt * linhas.length
  const x = t.h === 'esquerda' ? l + 6 : t.h === 'direita' ? r - 6 : (l + r) / 2
  const yIni = t.v === 'cima' ? c + 6 + alt / 2 : t.v === 'baixo' ? b - 6 - total + alt / 2 : (c + b) / 2 - total / 2 + alt / 2
  linhas.forEach((s, i) => ctx.fillText(s, x, yIni + i * alt))
  ctx.restore()
}

export type Caixa = { x: number; y: number; w: number; h: number }
/** as caixas de texto desenhadas por último, por desenho: o acerto do mouse usa as mesmas medidas */
export const CAIXAS = new Map<string, Caixa[]>()
export const dentroCaixas = (id: string, x: number, y: number) =>
  (CAIXAS.get(id) ?? []).some((c) => x >= c.x - 2 && x <= c.x + c.w + 2 && y >= c.y - 2 && y <= c.y + c.h + 2)

/**
 * Caixa de texto com fundo e borda opcionais, ancorada num ponto (o canto ou o meio que `ancora` disser).
 * Devolve a caixa desenhada (para o acerto do mouse).
 */
export function caixaComTexto(ctx: CanvasRenderingContext2D, linhas: string[], ponto: Px, opc: {
  fonte: string; tamanho: number; cor: string; fundo?: string | null; borda?: string | null; pad?: number
  ancora?: 'centro' | 'baixo' | 'cima' | 'esquerda' | 'direita' | 'cima-esq'; raio?: number; W?: number; H?: number
}): Caixa {
  ctx.save()
  ctx.font = opc.fonte
  const pad = opc.pad ?? 6, alt = opc.tamanho * 1.3
  const w = Math.max(...linhas.map((s) => ctx.measureText(s).width), 4) + pad * 2
  const h = alt * linhas.length + pad * 2 - (alt - opc.tamanho)
  const a = opc.ancora ?? 'centro'
  let x = a === 'esquerda' ? ponto.x : a === 'direita' ? ponto.x - w : a === 'cima-esq' ? ponto.x : ponto.x - w / 2
  let y = a === 'baixo' ? ponto.y - h : a === 'cima' || a === 'cima-esq' ? ponto.y : ponto.y - h / 2
  if (opc.W) x = Math.max(2, Math.min(opc.W - w - 2, x))
  if (opc.H) y = Math.max(2, Math.min(opc.H - h - 2, y))          // a caixa nunca sai da tela
  ctx.setLineDash([])
  ctx.beginPath(); ctx.roundRect(x, y, w, h, opc.raio ?? 4)
  if (opc.fundo) { ctx.fillStyle = opc.fundo; ctx.fill() }
  if (opc.borda) { ctx.strokeStyle = opc.borda; ctx.lineWidth = 1; ctx.stroke() }
  ctx.fillStyle = opc.cor; ctx.textAlign = 'left'; ctx.textBaseline = 'middle'
  linhas.forEach((s, i) => ctx.fillText(s, x + pad, y + pad + opc.tamanho / 2 + i * alt))
  ctx.restore()
  return { x, y, w, h }
}

/** largura e altura que caixaComTexto vai ocupar, sem desenhar */
export function medirCaixa(ctx: CanvasRenderingContext2D, linhas: string[], fonte: string, tamanho: number, pad = 6) {
  ctx.save(); ctx.font = fonte
  const w = Math.max(...linhas.map((s) => ctx.measureText(s).width), 4) + pad * 2
  ctx.restore()
  const alt = tamanho * 1.3
  return { w, h: alt * linhas.length + pad * 2 - (alt - tamanho) }
}

/** caixa escura com linhas de texto (estatísticas, medidas) */
export function caixaTexto(ctx: CanvasRenderingContext2D, linhas: string[], x: number, y: number, ancora: 'esquerda' | 'centro' | 'direita', W: number, cor = '#e8ecf2') {
  return caixaComTexto(ctx, linhas, { x, y }, {
    fonte: "11.5px 'DM Mono', monospace", tamanho: 11.5, cor, fundo: 'rgba(19,23,34,0.92)', borda: 'rgba(255,255,255,0.12)', W,
    ancora: ancora === 'esquerda' ? 'cima-esq' : ancora === 'direita' ? 'direita' : 'cima',
  })
}

export function duracao(seg: number): string {
  const s = Math.abs(seg)
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60)
  return [d && `${d}d`, h && `${h}h`, m && `${m}m`].filter(Boolean).join(' ') || '0m'
}
export const pct = (v: number) => `${v >= 0 ? '+' : ''}${(v * 100).toFixed(2).replace('.', ',')}%`
export function volumeCurto(v: number): string {
  const a = Math.abs(v)
  return a >= 1e9 ? `${(v / 1e9).toFixed(2)}B` : a >= 1e6 ? `${(v / 1e6).toFixed(2)}M` : a >= 1e3 ? `${(v / 1e3).toFixed(2)}K` : v.toFixed(a >= 10 ? 0 : 2)
}

/** campos que muitas ferramentas repetem */
export const CAMPO_LINHA = (nome = 'Linha', chave = 'linha'): Campo => ({ tipo: 'linha', chave, nome })
export const CAMPO_FUNDO = (nome = 'Fundo', chave = 'fundo'): Campo => ({ tipo: 'fundo', chave, nome })
export const ESTENDER: Campo[] = [{ tipo: 'bool', chave: 'estEsq', nome: 'Estender antes do ponto 1' }, { tipo: 'bool', chave: 'estDir', nome: 'Estender depois do ponto 2' }]
export const PONTAS: Campo[] = [
  { tipo: 'escolha', chave: 'pontaEsq', nome: 'Ponta 1', opcoes: [['normal', 'Normal'], ['seta', 'Seta']] },
  { tipo: 'escolha', chave: 'pontaDir', nome: 'Ponta 2', opcoes: [['normal', 'Normal'], ['seta', 'Seta']] },
]
export const resumoPrecos = (d: Desenho, f: (p: number) => string) => d.pts.map((p) => f(p.p)).join(' → ')
export const resumoTexto = (d: Desenho) => {
  const t = (d.cfg?.texto?.texto ?? '').replace(/\s+/g, ' ').trim()
  return t.length > 28 ? t.slice(0, 27) + '…' : t
}
