/**
 * A família Fibonacci da barra da TradingView (o Fibonacci de retração fica em ferramentas.ts): extensão baseada em
 * tendência, canal, zonas de tempo, leque de velocidade e resistência, tempo baseado em tendência, círculos, espiral,
 * arcos de velocidade e resistência, cunha e pitchfan. Os níveis de cada uma se editam na aba Estilo (campo 'niveis').
 */
import type { Linha } from '../../lib/desenhos'
import {
  acesso, comAlfa, distSegmento, estender, linhaReta, PERTO_PX, pertoSegmento, resumoPrecos, tracar,
  type Campo, type Ferramenta, type Geo, type Px,
} from './ferramentasBase'

export type NivelF = { valor: number; cor: string; ligado: boolean }

const CINZA = '#787b86'
/** as cores da TradingView por nível; o que não está aqui segue a paleta */
const COR_NIVEL: Record<string, string> = {
  '0': CINZA, '0.236': '#f23645', '0.25': '#f23645', '0.382': '#ff9800', '0.5': '#4caf50', '0.618': '#089981', '0.75': '#00bcd4',
  '0.786': '#00bcd4', '1': CINZA, '1.272': '#ff9800', '1.382': '#f23645', '1.414': '#f23645', '1.618': '#2962ff', '2': '#089981',
  '2.382': '#4caf50', '2.618': '#f23645', '3': '#00bcd4', '3.618': '#9c27b0', '4.236': '#e91e63',
}
const PALETA = ['#f23645', '#ff9800', '#4caf50', '#089981', '#00bcd4', '#2962ff', '#9c27b0', '#e91e63', CINZA]

/** níveis da TradingView: os valores ligados e os que aparecem desligados na configuração */
export function niveisPadrao(ligados: number[], desligados: number[] = []): NivelF[] {
  return [...ligados.map((v) => [v, true] as const), ...desligados.map((v) => [v, false] as const)]
    .map(([valor, ligado], i) => ({ valor, ligado, cor: COR_NIVEL[String(valor)] ?? PALETA[i % PALETA.length] }))
}
export const ligadosEmOrdem = (n: NivelF[]) => n.filter((x) => x.ligado && Number.isFinite(x.valor)).sort((a, b) => a.valor - b.valor)
export const rotuloNivel = (v: number) => String(+v.toFixed(4))

/** a configuração comum: linha de tendência, linha dos níveis, fundo e rótulos */
export type CfgNiveis = {
  niveis: NivelF[]; linha: Linha; tendencia: boolean; largura: number; estilo: Linha['estilo']
  fundo: boolean; transparencia: number; rotulos: boolean; precos: boolean; estEsq: boolean; estDir: boolean
}
export const baseNiveis = (niveis: NivelF[], extra: Partial<CfgNiveis> = {}): CfgNiveis => ({
  niveis, linha: { cor: CINZA, largura: 1, estilo: 'tracejada' }, tendencia: true, largura: 1, estilo: 'solida',
  fundo: true, transparencia: 85, rotulos: true, precos: true, estEsq: false, estDir: false, ...extra,
})
export const CAMPOS_NIVEIS = (opc: { tendencia?: boolean; precos?: boolean; estender?: boolean; chaveNiveis?: string; nomeNiveis?: string } = {}): Campo[] => [
  ...(opc.tendencia === false ? [] : [{ tipo: 'bool', chave: 'tendencia', nome: 'Linha de tendência' } as Campo, { tipo: 'linha', chave: 'linha', nome: 'Linha de tendência' } as Campo]),
  { tipo: 'numero', chave: 'largura', nome: 'Espessura dos níveis', min: 1, max: 4 },
  { tipo: 'escolha', chave: 'estilo', nome: 'Estilo dos níveis', opcoes: [['solida', 'Sólida'], ['tracejada', 'Tracejada'], ['pontilhada', 'Pontilhada']] },
  { tipo: 'niveis', chave: opc.chaveNiveis ?? 'niveis', nome: opc.nomeNiveis ?? 'Níveis' },
  { tipo: 'bool', chave: 'fundo', nome: 'Fundo' }, { tipo: 'numero', chave: 'transparencia', nome: 'Transparência do fundo (%)', min: 0, max: 100, passo: 5 },
  { tipo: 'bool', chave: 'rotulos', nome: 'Rótulos dos níveis' },
  ...(opc.precos === false ? [] : [{ tipo: 'bool', chave: 'precos', nome: 'Preços' } as Campo]),
  ...(opc.estender ? [{ tipo: 'bool', chave: 'estEsq', nome: 'Estender à esquerda' } as Campo, { tipo: 'bool', chave: 'estDir', nome: 'Estender à direita' } as Campo] : []),
]

// ---------------------------------------------------------------- ajudantes

const alfa = (c: CfgNiveis) => (100 - c.transparencia) / 100
export function nivelTraco(ctx: CanvasRenderingContext2D, c: CfgNiveis, cor: string) { tracar(ctx, { cor, largura: c.largura, estilo: c.estilo }) }
export function tendenciaTracejada(ctx: CanvasRenderingContext2D, c: CfgNiveis, pts: Px[]) {
  if (!c.tendencia || pts.length < 2) return
  tracar(ctx, c.linha)
  ctx.beginPath(); ctx.moveTo(pts[0].x, pts[0].y); for (const p of pts.slice(1)) ctx.lineTo(p.x, p.y); ctx.stroke()
  ctx.setLineDash([])
}
export function rotulo(ctx: CanvasRenderingContext2D, texto: string, x: number, y: number, cor: string, alinhar: CanvasTextAlign = 'left', base: CanvasTextBaseline = 'middle') {
  ctx.font = "11px 'DM Mono', monospace"; ctx.fillStyle = cor; ctx.textAlign = alinhar; ctx.textBaseline = base
  ctx.fillText(texto, x, y)
}
/** semirreta de a na direção d, até sair da tela */
export function raioAte(a: Px, d: Px, W: number, H: number): Px {
  const L = Math.hypot(d.x, d.y) || 1
  const k = (W + H) * 4 / L
  return { x: a.x + d.x * k, y: a.y + d.y * k }
}
export const pertoTendencia = (x: number, y: number, c: CfgNiveis, pts: Px[]) => {
  if (!c.tendencia) return false
  for (let i = 1; i < pts.length; i++) if (pertoSegmento(x, y, pts[i - 1], pts[i])) return true
  return false
}

// ---------------------------------------------------------------- níveis horizontais (extensão baseada em tendência)

/** linhas horizontais de preço entre x0 e x1, com fundo entre elas e rótulo "1.618 (81.234,50)" */
function niveisHorizontais(ctx: CanvasRenderingContext2D, c: CfgNiveis, lista: { valor: number; cor: string; preco: number }[], x0: number, x1: number, g: Geo) {
  const esq = c.estEsq ? 0 : x0, dir = c.estDir ? g.W : x1
  const ys = lista.map((n) => ({ ...n, y: g.y(n.preco) })).filter((n): n is typeof n & { y: number } => n.y !== null)
  if (c.fundo) for (let i = 1; i < ys.length; i++) { ctx.fillStyle = comAlfa(ys[i].cor, alfa(c)); ctx.fillRect(esq, Math.min(ys[i - 1].y, ys[i].y), dir - esq, Math.abs(ys[i].y - ys[i - 1].y)) }
  for (const n of ys) { nivelTraco(ctx, c, n.cor); linhaReta(ctx, { x: esq, y: n.y }, { x: dir, y: n.y }) }
  ctx.setLineDash([])
  if (c.rotulos || c.precos) for (const n of ys) {
    const t = `${c.rotulos ? rotuloNivel(n.valor) : ''}${c.precos ? `${c.rotulos ? ' (' : ''}${g.formatar(n.preco)}${c.rotulos ? ')' : ''}` : ''}`
    rotulo(ctx, t, Math.max(esq - 4, 4), n.y, n.cor, esq - 4 > 40 ? 'right' : 'left', 'bottom')
  }
  return { ys, esq, dir }
}

const extensao: Ferramenta = {
  tipo: 'fibo_extensao', nome: 'Extensão de Fibonacci baseada em tendência', grupo: 'fibonacci', pontos: 3,
  campos: CAMPOS_NIVEIS({ estender: true }),
  icone: 'M2 15 L7 6 L11 11 M2 3 H16 M2 7 H16 M10 15 H16',
  padrao: () => baseNiveis(niveisPadrao([0, 0.236, 0.382, 0.5, 0.618, 0.786, 1, 1.618, 2.618, 3.618, 4.236], [1.272, 1.414, 2, 3, 4])),
  linha: acesso<Linha>('linha'),
  desenhar(ctx, d, px, g) {
    const c = d.cfg as CfgNiveis
    tendenciaTracejada(ctx, c, px)
    if (d.pts.length < 3) return
    const [a, b, k] = d.pts
    const lista = ligadosEmOrdem(c.niveis).map((n) => ({ ...n, preco: k.p + (b.p - a.p) * n.valor }))
    niveisHorizontais(ctx, c, lista, Math.min(px[1].x, px[2].x), Math.max(px[2].x, px[1].x) + Math.abs(px[2].x - px[1].x), g)
  },
  acertar(x, y, d, px, g) {
    const c = d.cfg as CfgNiveis
    if (pertoTendencia(x, y, c, px)) return true
    if (d.pts.length < 3) return false
    const [a, b, k] = d.pts
    const x0 = c.estEsq ? 0 : Math.min(px[1].x, px[2].x), x1 = c.estDir ? g.W : Math.max(px[2].x, px[1].x) + Math.abs(px[2].x - px[1].x)
    return x >= x0 - 5 && x <= x1 + 5 && ligadosEmOrdem(c.niveis).some((n) => { const yy = g.y(k.p + (b.p - a.p) * n.valor); return yy !== null && Math.abs(yy - y) <= PERTO_PX })
  },
  resumo: resumoPrecos,
}

// ---------------------------------------------------------------- canal de Fibonacci

function linhasCanal(c: CfgNiveis, px: Px[], g: Geo) {
  const [a, b, k] = px
  const yNa = b.x === a.x ? a.y : a.y + ((b.y - a.y) * (k.x - a.x)) / (b.x - a.x)
  const dy = k.y - yNa
  return ligadosEmOrdem(c.niveis).map((n) => {
    const [e1, e2] = estender({ x: a.x, y: a.y + dy * n.valor }, { x: b.x, y: b.y + dy * n.valor }, c.estEsq, c.estDir, g.W, g.H)
    return { ...n, a: e1, b: e2 }
  })
}
const canal: Ferramenta = {
  tipo: 'fibo_canal', nome: 'Canal de Fibonacci', grupo: 'fibonacci', pontos: 3, campos: CAMPOS_NIVEIS({ tendencia: false, precos: false, estender: true }),
  icone: 'M2 12 L12 2 M4 15 L14 5 M6 17 L16 7',
  padrao: () => baseNiveis(niveisPadrao([0, 0.236, 0.382, 0.5, 0.618, 0.786, 1, 1.618, 2.618, 3.618, 4.236]), { tendencia: false, precos: false }),
  linha: { ler: (c: CfgNiveis) => ({ cor: c.niveis[0]?.cor ?? CINZA, largura: c.largura, estilo: c.estilo }), gravar: (c: CfgNiveis, l) => ({ ...c, largura: l.largura, estilo: l.estilo }) },
  desenhar(ctx, d, px, g) {
    const c = d.cfg as CfgNiveis
    if (px.length < 3) { if (px.length === 2) { tracar(ctx, { cor: CINZA, largura: 1, estilo: 'solida' }); linhaReta(ctx, px[0], px[1]) } return }
    const L = linhasCanal(c, px, g)
    if (c.fundo) for (let i = 1; i < L.length; i++) {
      ctx.fillStyle = comAlfa(L[i].cor, alfa(c))
      ctx.beginPath(); ctx.moveTo(L[i - 1].a.x, L[i - 1].a.y); ctx.lineTo(L[i - 1].b.x, L[i - 1].b.y); ctx.lineTo(L[i].b.x, L[i].b.y); ctx.lineTo(L[i].a.x, L[i].a.y); ctx.closePath(); ctx.fill()
    }
    for (const n of L) { nivelTraco(ctx, c, n.cor); linhaReta(ctx, n.a, n.b) }
    ctx.setLineDash([])
    if (c.rotulos) for (const n of L) rotulo(ctx, rotuloNivel(n.valor), n.a.x - 4, n.a.y, n.cor, 'right')
  },
  acertar: (x, y, d, px, g) => px.length >= 3 && linhasCanal(d.cfg as CfgNiveis, px, g).some((n) => pertoSegmento(x, y, n.a, n.b)),
  resumo: resumoPrecos,
}

// ---------------------------------------------------------------- tempo: zonas e tempo baseado em tendência

function verticais(ctx: CanvasRenderingContext2D, c: CfgNiveis, lista: { valor: number; cor: string; t: number }[], g: Geo) {
  const xs = lista.map((n) => ({ ...n, x: g.x(n.t) })).filter((n): n is typeof n & { x: number } => n.x !== null)
  if (c.fundo) for (let i = 1; i < xs.length; i++) { ctx.fillStyle = comAlfa(xs[i].cor, alfa(c) * 0.6); ctx.fillRect(xs[i - 1].x, 0, xs[i].x - xs[i - 1].x, g.H) }
  for (const n of xs) { nivelTraco(ctx, c, n.cor); linhaReta(ctx, { x: n.x, y: 0 }, { x: n.x, y: g.H }) }
  ctx.setLineDash([])
  if (c.rotulos) for (const n of xs) rotulo(ctx, rotuloNivel(n.valor), n.x + 3, g.H - 6, n.cor, 'left', 'bottom')
  return xs
}

const ZONAS = [0, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377]
const zonasTempo: Ferramenta = {
  tipo: 'fibo_zonas_tempo', nome: 'Zonas de tempo de Fibonacci', grupo: 'fibonacci', pontos: 2, soTempo: true,
  campos: CAMPOS_NIVEIS({ precos: false }).filter((c) => !('chave' in c) || c.chave !== 'fundo' && c.chave !== 'transparencia'),
  icone: 'M2 2 V16 M4 2 V16 M7 2 V16 M12 2 V16 M2 16 L12 4',
  padrao: () => baseNiveis(niveisPadrao(ZONAS.slice(0, 11), ZONAS.slice(11)).map((n) => ({ ...n, cor: '#2962ff' })), { fundo: false, precos: false }),
  linha: acesso<Linha>('linha'),
  desenhar(ctx, d, px, g) {
    const c = d.cfg as CfgNiveis
    if (px.length >= 2) tendenciaTracejada(ctx, c, px)
    const [a, b] = d.pts
    const passo = (b?.t ?? a.t) - a.t
    verticais(ctx, c, ligadosEmOrdem(c.niveis).map((n) => ({ ...n, t: a.t + passo * n.valor })), g)
  },
  acertar(x, y, d, px, g) {
    const c = d.cfg as CfgNiveis
    if (pertoTendencia(x, y, c, px)) return true
    const [a, b] = d.pts
    return ligadosEmOrdem(c.niveis).some((n) => { const xx = g.x(a.t + ((b?.t ?? a.t) - a.t) * n.valor); return xx !== null && Math.abs(xx - x) <= PERTO_PX })
  },
  resumo: (d) => `${d.pts.length} pontos`,
}

const tempoTendencia: Ferramenta = {
  tipo: 'fibo_tempo_tendencia', nome: 'Tempo de Fibonacci baseado em tendência', grupo: 'fibonacci', pontos: 3, soTempo: true,
  campos: CAMPOS_NIVEIS({ precos: false }),
  icone: 'M2 15 L6 5 L9 12 M11 2 V16 M14 2 V16 M16 2 V16',
  padrao: () => baseNiveis(niveisPadrao([0, 0.382, 0.5, 0.618, 1, 1.382, 1.618, 2, 2.382, 2.618, 3, 3.618, 4.236]), { precos: false }),
  linha: acesso<Linha>('linha'),
  desenhar(ctx, d, px, g) {
    const c = d.cfg as CfgNiveis
    tendenciaTracejada(ctx, c, px)
    if (d.pts.length < 3) return
    const [a, b, k] = d.pts
    verticais(ctx, c, ligadosEmOrdem(c.niveis).map((n) => ({ ...n, t: k.t + (b.t - a.t) * n.valor })), g)
  },
  acertar(x, y, d, px, g) {
    const c = d.cfg as CfgNiveis
    if (pertoTendencia(x, y, c, px)) return true
    if (d.pts.length < 3) return false
    const [a, b, k] = d.pts
    return ligadosEmOrdem(c.niveis).some((n) => { const xx = g.x(k.t + (b.t - a.t) * n.valor); return xx !== null && Math.abs(xx - x) <= PERTO_PX })
  },
  resumo: (d) => `${d.pts.length} pontos`,
}

// ---------------------------------------------------------------- leque de velocidade e resistência

type CfgLeque = CfgNiveis & { niveisTempo: NivelF[]; grade: boolean }
function raiosLeque(c: CfgLeque, px: Px[], g: Geo) {
  const [a, b] = px
  const preco = ligadosEmOrdem(c.niveis).map((n) => ({ ...n, fim: raioAte(a, { x: b.x - a.x, y: (b.y - a.y) * n.valor }, g.W, g.H) }))
  const tempo = ligadosEmOrdem(c.niveisTempo).map((n) => ({ ...n, fim: raioAte(a, { x: (b.x - a.x) * n.valor, y: b.y - a.y }, g.W, g.H) }))
  return { preco, tempo }
}
const leque: Ferramenta = {
  tipo: 'fibo_leque', nome: 'Leque de velocidade e resistência', grupo: 'fibonacci', pontos: 2,
  campos: [...CAMPOS_NIVEIS({ tendencia: false, precos: false, nomeNiveis: 'Níveis de preço' }), { tipo: 'niveis', chave: 'niveisTempo', nome: 'Níveis de tempo' }, { tipo: 'bool', chave: 'grade', nome: 'Grade' }],
  icone: 'M2 16 L16 2 M2 16 L16 7 M2 16 L16 12 M2 16 L7 2 M2 16 L12 2',
  padrao: (): CfgLeque => ({
    ...baseNiveis(niveisPadrao([0, 0.25, 0.382, 0.5, 0.618, 0.75, 1]), { tendencia: false, precos: false, transparencia: 90 }),
    niveisTempo: niveisPadrao([0, 0.25, 0.382, 0.5, 0.618, 0.75, 1]), grade: true,
  }),
  linha: { ler: (c: CfgLeque) => ({ cor: c.niveis[0]?.cor ?? CINZA, largura: c.largura, estilo: c.estilo }), gravar: (c: CfgLeque, l) => ({ ...c, largura: l.largura, estilo: l.estilo }) },
  desenhar(ctx, d, px, g) {
    if (px.length < 2) return
    const c = d.cfg as CfgLeque, [a, b] = px
    const R = raiosLeque(c, px, g)
    if (c.grade) {
      ctx.strokeStyle = 'rgba(120,123,134,0.35)'; ctx.lineWidth = 1; ctx.setLineDash([])
      for (const n of ligadosEmOrdem(c.niveis)) { const y = a.y + (b.y - a.y) * n.valor; linhaReta(ctx, { x: a.x, y }, { x: b.x, y }) }
      for (const n of ligadosEmOrdem(c.niveisTempo)) { const x = a.x + (b.x - a.x) * n.valor; linhaReta(ctx, { x, y: a.y }, { x, y: b.y }) }
    }
    if (c.fundo) for (let i = 1; i < R.preco.length; i++) {
      ctx.fillStyle = comAlfa(R.preco[i].cor, alfa(c))
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(R.preco[i - 1].fim.x, R.preco[i - 1].fim.y); ctx.lineTo(R.preco[i].fim.x, R.preco[i].fim.y); ctx.closePath(); ctx.fill()
    }
    for (const n of [...R.preco, ...R.tempo]) { nivelTraco(ctx, c, n.cor); linhaReta(ctx, a, n.fim) }
    ctx.setLineDash([])
    if (c.rotulos) {
      for (const n of ligadosEmOrdem(c.niveis)) rotulo(ctx, rotuloNivel(n.valor), b.x + 4, a.y + (b.y - a.y) * n.valor, n.cor)
      for (const n of ligadosEmOrdem(c.niveisTempo)) rotulo(ctx, rotuloNivel(n.valor), a.x + (b.x - a.x) * n.valor, b.y + (b.y > a.y ? 12 : -12), n.cor, 'center')
    }
  },
  acertar(x, y, d, px, g) {
    if (px.length < 2) return false
    const R = raiosLeque(d.cfg as CfgLeque, px, g)
    return [...R.preco, ...R.tempo].some((n) => pertoSegmento(x, y, px[0], n.fim))
  },
  resumo: resumoPrecos,
}

// ---------------------------------------------------------------- círculos, arcos, espiral, cunha

const raioPx = (px: Px[]) => Math.hypot(px[1].x - px[0].x, px[1].y - px[0].y)

const circulos: Ferramenta = {
  tipo: 'fibo_circulos', nome: 'Círculos de Fibonacci', grupo: 'fibonacci', pontos: 2, campos: CAMPOS_NIVEIS({ precos: false }),
  icone: 'M9 9 m-7 0 a7 7 0 1 0 14 0 a7 7 0 1 0 -14 0 M9 9 m-4 0 a4 4 0 1 0 8 0 a4 4 0 1 0 -8 0',
  padrao: () => baseNiveis(niveisPadrao([0.236, 0.382, 0.5, 0.618, 0.786, 1, 1.618, 2.618, 3.618, 4.236]), { precos: false }),
  linha: acesso<Linha>('linha'),
  desenhar(ctx, d, px) {
    if (px.length < 2) return
    const c = d.cfg as CfgNiveis, r = raioPx(px), [o] = px
    const lista = ligadosEmOrdem(c.niveis)
    if (c.fundo) for (let i = lista.length - 1; i >= 0; i--) {
      ctx.fillStyle = comAlfa(lista[i].cor, alfa(c))
      ctx.beginPath(); ctx.arc(o.x, o.y, r * lista[i].valor, 0, Math.PI * 2)
      if (i > 0) ctx.arc(o.x, o.y, r * lista[i - 1].valor, 0, Math.PI * 2, true)
      ctx.fill()
    }
    for (const n of lista) { nivelTraco(ctx, c, n.cor); ctx.beginPath(); ctx.arc(o.x, o.y, r * n.valor, 0, Math.PI * 2); ctx.stroke() }
    ctx.setLineDash([])
    tendenciaTracejada(ctx, c, px)
    if (c.rotulos) for (const n of lista) rotulo(ctx, rotuloNivel(n.valor), o.x + r * n.valor + 3, o.y - 6, n.cor)
  },
  acertar(x, y, d, px) {
    if (px.length < 2) return false
    const r = raioPx(px), dist = Math.hypot(x - px[0].x, y - px[0].y)
    return ligadosEmOrdem((d.cfg as CfgNiveis).niveis).some((n) => Math.abs(dist - r * n.valor) <= PERTO_PX) || pertoTendencia(x, y, d.cfg as CfgNiveis, px)
  },
  resumo: resumoPrecos,
}

type CfgArcos = CfgNiveis & { inteiros: boolean }
const arcos: Ferramenta = {
  tipo: 'fibo_arcos', nome: 'Arcos de velocidade e resistência', grupo: 'fibonacci', pontos: 2,
  campos: [...CAMPOS_NIVEIS({ precos: false }), { tipo: 'bool', chave: 'inteiros', nome: 'Círculos inteiros' }],
  icone: 'M2 16 L14 4 M16 16 A12 12 0 0 0 4 4 M16 16 A7 7 0 0 0 9 9',
  padrao: (): CfgArcos => ({ ...baseNiveis(niveisPadrao([0.236, 0.382, 0.5, 0.618, 0.786, 1], [1.618, 2.618, 3.618, 4.236]), { precos: false }), inteiros: false }),
  linha: acesso<Linha>('linha'),
  desenhar(ctx, d, px) {
    if (px.length < 2) return
    const c = d.cfg as CfgArcos, r = raioPx(px), [o, b] = px
    // meia-volta virada para o ponto 2, como a TradingView
    const ang = Math.atan2(b.y - o.y, b.x - o.x)
    const [ini, fim] = c.inteiros ? [0, Math.PI * 2] : [ang - Math.PI / 2, ang + Math.PI / 2]
    const lista = ligadosEmOrdem(c.niveis)
    if (c.fundo) for (let i = lista.length - 1; i >= 0; i--) {
      ctx.fillStyle = comAlfa(lista[i].cor, alfa(c))
      ctx.beginPath(); ctx.arc(o.x, o.y, r * lista[i].valor, ini, fim)
      if (i > 0) ctx.arc(o.x, o.y, r * lista[i - 1].valor, fim, ini, true); else ctx.lineTo(o.x, o.y)
      ctx.closePath(); ctx.fill()
    }
    for (const n of lista) { nivelTraco(ctx, c, n.cor); ctx.beginPath(); ctx.arc(o.x, o.y, r * n.valor, ini, fim); ctx.stroke() }
    ctx.setLineDash([])
    tendenciaTracejada(ctx, c, px)
    if (c.rotulos) for (const n of lista) rotulo(ctx, rotuloNivel(n.valor), o.x + Math.cos(ang) * r * n.valor + 3, o.y + Math.sin(ang) * r * n.valor - 6, n.cor)
  },
  acertar(x, y, d, px) {
    if (px.length < 2) return false
    const c = d.cfg as CfgArcos, r = raioPx(px), dist = Math.hypot(x - px[0].x, y - px[0].y)
    const ang = Math.atan2(px[1].y - px[0].y, px[1].x - px[0].x), angP = Math.atan2(y - px[0].y, x - px[0].x)
    const dentroAng = c.inteiros || Math.abs(Math.atan2(Math.sin(angP - ang), Math.cos(angP - ang))) <= Math.PI / 2
    return (dentroAng && ligadosEmOrdem(c.niveis).some((n) => Math.abs(dist - r * n.valor) <= PERTO_PX)) || pertoTendencia(x, y, c, px)
  },
  resumo: resumoPrecos,
}

type CfgEspiral = { linha: Linha; antihorario: boolean }
const PHI = (1 + Math.sqrt(5)) / 2
function pontosEspiral(c: CfgEspiral, px: Px[], g: Geo): Px[] {
  const [o, b] = px
  const r0 = raioPx(px), a0 = Math.atan2(b.y - o.y, b.x - o.x), s = c.antihorario ? -1 : 1
  const k = Math.log(PHI) / (Math.PI / 2)                     // cresce φ a cada quarto de volta
  const out: Px[] = []
  const limite = (g.W + g.H) * 2
  for (let th = -8 * Math.PI; th <= 6 * Math.PI; th += Math.PI / 48) {
    const r = r0 * Math.exp(k * th)
    if (r > limite) break
    if (r < 0.5) continue
    out.push({ x: o.x + r * Math.cos(a0 + s * th), y: o.y + r * Math.sin(a0 + s * th) })
  }
  return out
}
const espiral: Ferramenta = {
  tipo: 'fibo_espiral', nome: 'Espiral de Fibonacci', grupo: 'fibonacci', pontos: 2,
  campos: [{ tipo: 'linha', chave: 'linha', nome: 'Linha' }, { tipo: 'bool', chave: 'antihorario', nome: 'Sentido anti-horário' }],
  icone: 'M9 9 m0 -1 a1 1 0 1 1 -1 1 a3 3 0 0 1 3 -3 a5 5 0 0 1 5 5 a8 8 0 0 1 -8 8',
  padrao: (): CfgEspiral => ({ linha: { cor: '#f23645', largura: 1, estilo: 'solida' }, antihorario: false }),
  linha: acesso<Linha>('linha'),
  desenhar(ctx, d, px, g) {
    if (px.length < 2) return
    const c = d.cfg as CfgEspiral
    const pts = pontosEspiral(c, px, g)
    tracar(ctx, c.linha)
    ctx.beginPath(); pts.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y))); ctx.stroke()
    tracar(ctx, { ...c.linha, estilo: 'tracejada' }); linhaReta(ctx, px[0], px[1]); ctx.setLineDash([])
  },
  acertar(x, y, d, px, g) {
    if (px.length < 2) return false
    const pts = pontosEspiral(d.cfg as CfgEspiral, px, g)
    for (let i = 1; i < pts.length; i++) if (distSegmento(x, y, pts[i - 1].x, pts[i - 1].y, pts[i].x, pts[i].y) <= PERTO_PX) return true
    return pertoSegmento(x, y, px[0], px[1])
  },
  resumo: resumoPrecos,
}

/** cunha: arcos com centro no ponto 1, entre as direções dos pontos 2 e 3, no raio do ponto 2 */
const cunha: Ferramenta = {
  tipo: 'fibo_cunha', nome: 'Cunha de Fibonacci', grupo: 'fibonacci', pontos: 3, campos: CAMPOS_NIVEIS({ precos: false, tendencia: false }),
  icone: 'M2 16 L16 4 M2 16 L16 14 M14 5 A13 13 0 0 1 14 14 M9 8 A8 8 0 0 1 9 14',
  padrao: () => baseNiveis(niveisPadrao([0.236, 0.382, 0.5, 0.618, 0.786, 1]), { precos: false, tendencia: false }),
  linha: { ler: (c: CfgNiveis) => ({ cor: c.niveis.at(-1)?.cor ?? CINZA, largura: c.largura, estilo: c.estilo }), gravar: (c: CfgNiveis, l) => ({ ...c, largura: l.largura, estilo: l.estilo }) },
  desenhar(ctx, d, px) {
    const c = d.cfg as CfgNiveis
    if (px.length < 3) { if (px.length === 2) { tracar(ctx, { cor: CINZA, largura: 1, estilo: 'solida' }); linhaReta(ctx, px[0], px[1]) } return }
    const [o, b, k] = px, r = raioPx(px)
    const a1 = Math.atan2(b.y - o.y, b.x - o.x)
    let a2 = Math.atan2(k.y - o.y, k.x - o.x)
    let delta = a2 - a1
    while (delta > Math.PI) delta -= 2 * Math.PI
    while (delta < -Math.PI) delta += 2 * Math.PI
    a2 = a1 + delta
    const anti = delta < 0
    const lista = ligadosEmOrdem(c.niveis)
    if (c.fundo) for (let i = lista.length - 1; i >= 0; i--) {
      ctx.fillStyle = comAlfa(lista[i].cor, alfa(c))
      ctx.beginPath(); ctx.arc(o.x, o.y, r * lista[i].valor, a1, a2, anti)
      if (i > 0) ctx.arc(o.x, o.y, r * lista[i - 1].valor, a2, a1, !anti); else ctx.lineTo(o.x, o.y)
      ctx.closePath(); ctx.fill()
    }
    for (const n of lista) { nivelTraco(ctx, c, n.cor); ctx.beginPath(); ctx.arc(o.x, o.y, r * n.valor, a1, a2, anti); ctx.stroke() }
    tracar(ctx, { cor: CINZA, largura: 1, estilo: 'solida' })
    const rm = r * Math.max(1, ...lista.map((n) => n.valor))
    linhaReta(ctx, o, { x: o.x + Math.cos(a1) * rm, y: o.y + Math.sin(a1) * rm }); linhaReta(ctx, o, { x: o.x + Math.cos(a2) * rm, y: o.y + Math.sin(a2) * rm })
    ctx.setLineDash([])
    if (c.rotulos) for (const n of lista) rotulo(ctx, rotuloNivel(n.valor), o.x + Math.cos(a1) * r * n.valor + 3, o.y + Math.sin(a1) * r * n.valor, n.cor)
  },
  acertar(x, y, d, px) {
    if (px.length < 3) return false
    const [o] = px, r = raioPx(px), dist = Math.hypot(x - o.x, y - o.y)
    const a1 = Math.atan2(px[1].y - o.y, px[1].x - o.x), a2 = Math.atan2(px[2].y - o.y, px[2].x - o.x), ap = Math.atan2(y - o.y, x - o.x)
    const norm = (v: number) => Math.atan2(Math.sin(v), Math.cos(v))
    const d12 = norm(a2 - a1), d1p = norm(ap - a1)
    const dentro = d12 >= 0 ? d1p >= 0 && d1p <= d12 : d1p <= 0 && d1p >= d12
    return (dentro && ligadosEmOrdem((d.cfg as CfgNiveis).niveis).some((n) => Math.abs(dist - r * n.valor) <= PERTO_PX)) || pertoSegmento(x, y, o, px[1]) || pertoSegmento(x, y, o, px[2])
  },
  resumo: resumoPrecos,
}

// ---------------------------------------------------------------- pitchfan

function raiosPitchfan(c: CfgNiveis, px: Px[], g: Geo) {
  const [a, b, k] = px
  const m = { x: (b.x + k.x) / 2, y: (b.y + k.y) / 2 }
  const lista = ligadosEmOrdem(c.niveis)
  const raios: { valor: number; cor: string; fim: Px }[] = [{ valor: 0, cor: c.linha.cor, fim: raioAte(a, { x: m.x - a.x, y: m.y - a.y }, g.W, g.H) }]
  for (const n of lista) {
    if (n.valor === 0) continue
    for (const lado of [k, b]) {
      const p = { x: m.x + (lado.x - m.x) * n.valor, y: m.y + (lado.y - m.y) * n.valor }
      raios.push({ ...n, fim: raioAte(a, { x: p.x - a.x, y: p.y - a.y }, g.W, g.H) })
    }
  }
  return raios
}
const pitchfan: Ferramenta = {
  tipo: 'pitchfan', nome: 'Pitchfan', grupo: 'fibonacci', pontos: 3, campos: CAMPOS_NIVEIS({ precos: false, tendencia: false }),
  icone: 'M2 16 L16 2 M2 16 L16 9 M2 16 L9 2 M12 3 L16 8',
  padrao: () => baseNiveis(niveisPadrao([0.25, 0.382, 0.5, 0.618, 0.75, 1]), { precos: false, tendencia: false, linha: { cor: '#f23645', largura: 1, estilo: 'solida' } }),
  linha: acesso<Linha>('linha'),
  desenhar(ctx, d, px, g) {
    const c = d.cfg as CfgNiveis
    if (px.length < 3) { if (px.length === 2) { tracar(ctx, c.linha); linhaReta(ctx, px[0], px[1]) } return }
    const R = raiosPitchfan(c, px, g)
    if (c.fundo) {
      // fundo entre raios vizinhos dos dois lados (cada nível com o anterior)
      const lados = [R.filter((_, i) => i > 0 && i % 2 === 1), R.filter((_, i) => i > 0 && i % 2 === 0)]
      for (const L of lados) for (let i = 0; i < L.length; i++) {
        const ant = i ? L[i - 1].fim : R[0].fim
        ctx.fillStyle = comAlfa(L[i].cor, alfa(c))
        ctx.beginPath(); ctx.moveTo(px[0].x, px[0].y); ctx.lineTo(ant.x, ant.y); ctx.lineTo(L[i].fim.x, L[i].fim.y); ctx.closePath(); ctx.fill()
      }
    }
    for (const r of R) { nivelTraco(ctx, c, r.cor); linhaReta(ctx, px[0], r.fim) }
    tracar(ctx, { cor: CINZA, largura: 1, estilo: 'solida' }); linhaReta(ctx, px[1], px[2])
    ctx.setLineDash([])
  },
  acertar: (x, y, d, px, g) => px.length >= 3 && (raiosPitchfan(d.cfg as CfgNiveis, px, g).some((r) => pertoSegmento(x, y, px[0], r.fim)) || pertoSegmento(x, y, px[1], px[2])),
  resumo: resumoPrecos,
}

export const FIBO_FAMILIA: Ferramenta[] = [extensao, canal, zonasTempo, leque, tempoTendencia, circulos, espiral, arcos, cunha, pitchfan]
