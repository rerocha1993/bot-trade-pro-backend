/**
 * Linhas e canais da barra da TradingView: linha de tendência e as variações dela (raio, linha de informação, linha
 * estendida, ângulo de tendência, seta), linha e raio horizontal, linha vertical, cruz, canal paralelo, canal de
 * regressão, topo/fundo plano e canal disjunto.
 */
import { copiar } from '../../lib/fibo'
import { TEXTO_PADRAO, type Desenho, type Linha, type Texto } from '../../lib/desenhos'
import {
  acesso, caixaTexto, CAMPO_FUNDO, CAMPO_LINHA, corFundo, dentroPoligono, duracao, ESTENDER, estender, fundoPadrao,
  linhaReta, pct, PONTAS, pertoSegmento, poligono, resumoPrecos, seta, textoNaLinha, tracar,
  type Campo, type Ferramenta, type Fundo, type Geo, type Px,
} from './ferramentasBase'

const AZUL = '#2962ff'

// ---------------------------------------------------------------- linha de tendência e variações

export type CfgTendencia = {
  linha: Linha
  estEsq: boolean; estDir: boolean
  pontaEsq: 'normal' | 'seta'; pontaDir: 'normal' | 'seta'
  meio: boolean
  precos: boolean
  /** arco e valor do ângulo no ponto 1 (ângulo de tendência) */
  arco: boolean
  stats: { preco: boolean; pct: boolean; barras: boolean; tempo: boolean; distancia: boolean; angulo: boolean }
  statsPos: 'esquerda' | 'centro' | 'direita'
  statsSempre: boolean
  texto: Texto
}
export const TENDENCIA_TV: CfgTendencia = {
  linha: { cor: AZUL, largura: 2, estilo: 'solida' },
  estEsq: false, estDir: false, pontaEsq: 'normal', pontaDir: 'normal', meio: false, precos: false, arco: false,
  stats: { preco: true, pct: true, barras: true, tempo: true, distancia: false, angulo: false },
  statsPos: 'direita', statsSempre: false,
  texto: { ...TEXTO_PADRAO },
}

const angulo = (a: Px, b: Px) => Math.round(Math.atan2(a.y - b.y, b.x - a.x) * 180 / Math.PI)

function estatisticas(d: Desenho, px: Px[], g: Geo, s: CfgTendencia['stats']): string[] {
  const [a, b] = d.pts
  const out: string[] = []
  const dp = b.p - a.p
  if (s.preco || s.pct) out.push([s.preco && `${dp >= 0 ? '+' : ''}${g.formatar(dp)}`, s.pct && a.p && `(${pct(dp / a.p)})`].filter(Boolean).join(' '))
  if (s.barras || s.tempo) out.push([s.barras && `${Math.round((b.t - a.t) / g.passo)} barras`, s.tempo && duracao(b.t - a.t)].filter(Boolean).join(', '))
  if (s.distancia) out.push(`distância ${Math.round(Math.hypot(px[1].x - px[0].x, px[1].y - px[0].y))} px`)
  if (s.angulo) out.push(`${angulo(px[0], px[1])}°`)
  return out.filter(Boolean)
}

const CAMPOS_TENDENCIA: Campo[] = [
  CAMPO_LINHA(), ...ESTENDER, ...PONTAS,
  { tipo: 'bool', chave: 'meio', nome: 'Ponto do meio' }, { tipo: 'bool', chave: 'precos', nome: 'Rótulos de preço' },
  { tipo: 'bool', chave: 'arco', nome: 'Arco do ângulo' },
  { tipo: 'secao', nome: 'Estatísticas' },
  { tipo: 'bool', chave: 'stats.preco', nome: 'Variação do preço' }, { tipo: 'bool', chave: 'stats.pct', nome: 'Variação %' },
  { tipo: 'bool', chave: 'stats.barras', nome: 'Barras' }, { tipo: 'bool', chave: 'stats.tempo', nome: 'Tempo' },
  { tipo: 'bool', chave: 'stats.distancia', nome: 'Distância' }, { tipo: 'bool', chave: 'stats.angulo', nome: 'Ângulo' },
  { tipo: 'escolha', chave: 'statsPos', nome: 'Posição', opcoes: [['esquerda', 'Esquerda'], ['centro', 'Centro'], ['direita', 'Direita']] },
  { tipo: 'bool', chave: 'statsSempre', nome: 'Sempre mostrar (não só selecionada)' },
]

export function desenharTendencia(ctx: CanvasRenderingContext2D, c: CfgTendencia, d: Desenho, px: Px[], g: Geo) {
  const [a, b] = px
  const [e1, e2] = estender(a, b, c.estEsq, c.estDir, g.W, g.H)
  tracar(ctx, c.linha)
  linhaReta(ctx, e1, e2)
  if (c.pontaEsq === 'seta' && !c.estEsq) seta(ctx, a, b, c.linha.largura)
  if (c.pontaDir === 'seta' && !c.estDir) seta(ctx, b, a, c.linha.largura)
  ctx.setLineDash([])
  if (c.meio) { ctx.beginPath(); ctx.arc((a.x + b.x) / 2, (a.y + b.y) / 2, 3, 0, Math.PI * 2); ctx.fillStyle = c.linha.cor; ctx.fill() }
  if (c.arco) {
    const ang = Math.atan2(b.y - a.y, b.x - a.x)
    ctx.strokeStyle = c.linha.cor; ctx.lineWidth = 1; ctx.setLineDash([3, 3])
    linhaReta(ctx, a, { x: a.x + 60, y: a.y })
    ctx.setLineDash([])
    ctx.beginPath(); ctx.arc(a.x, a.y, 36, Math.min(0, ang), Math.max(0, ang)); ctx.stroke()
    ctx.font = "11px 'DM Mono', monospace"; ctx.fillStyle = c.linha.cor; ctx.textBaseline = 'middle'; ctx.textAlign = 'left'
    ctx.fillText(`${angulo(a, b)}°`, a.x + 42, a.y + (ang < 0 ? -10 : 10))
  }
  if (c.precos) {
    ctx.font = "11px 'DM Mono', monospace"; ctx.fillStyle = c.linha.cor; ctx.textBaseline = 'bottom'; ctx.textAlign = 'center'
    d.pts.forEach((p, i) => ctx.fillText(g.formatar(p.p), px[i].x, px[i].y - 8))
  }
  textoNaLinha(ctx, c.texto, a, b)
  if ((c.statsSempre || g.selecionado) && Object.values(c.stats).some(Boolean)) {
    const linhas = estatisticas(d, px, g, c.stats)
    if (linhas.length) {
      const esq = a.x <= b.x ? a : b, dir = a.x <= b.x ? b : a
      const ref = c.statsPos === 'esquerda' ? esq : c.statsPos === 'direita' ? dir : { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
      const dx = c.statsPos === 'centro' ? 0 : c.statsPos === 'direita' ? 10 : -10
      caixaTexto(ctx, linhas, ref.x + dx, ref.y + 10, c.statsPos === 'direita' ? 'esquerda' : c.statsPos === 'esquerda' ? 'direita' : 'centro', g.W)
    }
  }
}

function familiaTendencia(tipo: string, nome: string, icone: string, extra: Partial<CfgTendencia>, opc: { atalho?: string; grupo?: Ferramenta['grupo'] } = {}): Ferramenta {
  return {
    tipo, nome, grupo: opc.grupo ?? 'linhas', atalho: opc.atalho, pontos: 2, texto: true, icone, campos: CAMPOS_TENDENCIA,
    padrao: () => ({ ...copiar(TENDENCIA_TV), ...copiar(extra) }),
    linha: acesso<Linha>('linha'),
    desenhar: (ctx, d, px, g) => desenharTendencia(ctx, d.cfg as CfgTendencia, d, px, g),
    acertar(x, y, d, px, g) {
      const c = d.cfg as CfgTendencia
      const [e1, e2] = estender(px[0], px[1], c.estEsq, c.estDir, g.W, g.H)
      return pertoSegmento(x, y, e1, e2)
    },
    resumo: resumoPrecos,
  }
}

const PONTA = 'm-1.5 0 a1.5 1.5 0 1 0 3 0 a1.5 1.5 0 1 0 -3 0'
export const tendencia = familiaTendencia('linha_tendencia', 'Linha de tendência', `M3 15 L15 3 M3 15 ${PONTA} M15 3 ${PONTA}`, {}, { atalho: 'T' })
const raio = familiaTendencia('raio', 'Raio', `M3 15 L17 1 M3 15 ${PONTA} M10 8 ${PONTA}`, { estDir: true })
const informacao = familiaTendencia('linha_informacao', 'Linha de informação', `M3 15 L13 5 M3 15 ${PONTA} M13 5 ${PONTA} M11 13 H17 M11 16 H15`,
  { statsSempre: true, stats: { preco: true, pct: true, barras: true, tempo: true, distancia: false, angulo: true } })
const estendida = familiaTendencia('linha_estendida', 'Linha estendida', `M1 17 L17 1 M6 12 ${PONTA} M12 6 ${PONTA}`, { estEsq: true, estDir: true })
const anguloTendencia = familiaTendencia('angulo_tendencia', 'Ângulo de tendência', `M3 15 L15 5 M3 15 H16 M9 15 A6 6 0 0 0 8 11`,
  { arco: true, stats: { ...TENDENCIA_TV.stats, angulo: true } })
export const setaLinha = familiaTendencia('seta', 'Seta', 'M3 15 L15 3 M9 3 H15 V9', { pontaDir: 'seta' }, { grupo: 'setas' })

// ---------------------------------------------------------------- horizontal, raio horizontal, vertical, cruz

export type CfgHorizontal = { linha: Linha; rotuloPreco: boolean; rotuloTempo?: boolean; texto: Texto }
export const HORIZONTAL_TV: CfgHorizontal = {
  linha: { cor: AZUL, largura: 1, estilo: 'solida' }, rotuloPreco: true, rotuloTempo: true, texto: { ...TEXTO_PADRAO, h: 'direita' },
}
const CAMPOS_HORIZONTAL: Campo[] = [CAMPO_LINHA(), { tipo: 'bool', chave: 'rotuloPreco', nome: 'Rótulo do preço na escala' }]
const CAMPOS_VERTICAL: Campo[] = [CAMPO_LINHA(), { tipo: 'bool', chave: 'rotuloTempo', nome: 'Rótulo da data na escala' }]
const CAMPOS_CRUZ: Campo[] = [...CAMPOS_HORIZONTAL, { tipo: 'bool', chave: 'rotuloTempo', nome: 'Rótulo da data na escala' }]

const meioPx = (v: number, largura: number) => Math.round(v) + (largura % 2 ? 0.5 : 0)
const rotulosPreco = (d: Desenho) => ((d.cfg as CfgHorizontal).rotuloPreco ? [{ preco: d.pts[0].p, cor: (d.cfg as CfgHorizontal).linha.cor }] : [])
const rotulosTempo = (d: Desenho) => ((d.cfg as CfgHorizontal).rotuloTempo ? [{ t: d.pts[0].t, cor: (d.cfg as CfgHorizontal).linha.cor }] : [])

export const horizontal: Ferramenta = {
  tipo: 'linha_horizontal', nome: 'Linha horizontal', grupo: 'linhas', atalho: 'H', pontos: 1, texto: true, soPreco: true, campos: CAMPOS_HORIZONTAL,
  icone: `M1 9 H17 M9 9 ${PONTA}`,
  padrao: () => copiar(HORIZONTAL_TV),
  linha: acesso<Linha>('linha'),
  desenhar(ctx, d, px, g) {
    const c = d.cfg as CfgHorizontal
    const y = meioPx(px[0].y, c.linha.largura)
    tracar(ctx, c.linha); linhaReta(ctx, { x: 0, y }, { x: g.W, y }); ctx.setLineDash([])
    textoNaLinha(ctx, c.texto, { x: 0, y }, { x: g.W, y })
  },
  acertar: (_x, y, _d, px) => Math.abs(y - px[0].y) <= 5,
  rotulosPreco,
  resumo: (d, f) => f(d.pts[0].p),
}

const raioHorizontal: Ferramenta = {
  ...horizontal, tipo: 'raio_horizontal', nome: 'Raio horizontal', atalho: 'J', soPreco: false,
  icone: `M5 9 H17 M5 9 ${PONTA}`,
  desenhar(ctx, d, px, g) {
    const c = d.cfg as CfgHorizontal
    const y = meioPx(px[0].y, c.linha.largura)
    tracar(ctx, c.linha); linhaReta(ctx, { x: px[0].x, y }, { x: g.W, y }); ctx.setLineDash([])
    textoNaLinha(ctx, c.texto, { x: px[0].x, y }, { x: g.W, y })
  },
  acertar: (x, y, _d, px) => x >= px[0].x - 5 && Math.abs(y - px[0].y) <= 5,
}

const vertical: Ferramenta = {
  tipo: 'linha_vertical', nome: 'Linha vertical', grupo: 'linhas', atalho: 'V', pontos: 1, texto: true, soTempo: true, campos: CAMPOS_VERTICAL,
  icone: `M9 1 V17 M9 9 ${PONTA}`,
  padrao: () => ({ ...copiar(HORIZONTAL_TV), rotuloPreco: false, texto: { ...TEXTO_PADRAO, h: 'direita' } }),
  linha: acesso<Linha>('linha'),
  desenhar(ctx, d, px, g) {
    const c = d.cfg as CfgHorizontal
    const x = meioPx(px[0].x, c.linha.largura)
    tracar(ctx, c.linha); linhaReta(ctx, { x, y: 0 }, { x, y: g.H }); ctx.setLineDash([])
    textoNaLinha(ctx, c.texto, { x, y: g.H }, { x, y: 0 })
  },
  acertar: (x, _y, _d, px) => Math.abs(x - px[0].x) <= 5,
  alcas: (_d, px, g) => [{ x: px[0].x, y: Math.min(Math.max(px[0].y, 10), g.H - 10) }],
  rotulosTempo,
  resumo: (d) => new Date(d.pts[0].t * 1000).toISOString().slice(0, 16).replace('T', ' ') + ' UTC',
}

const cruz: Ferramenta = {
  tipo: 'cruz', nome: 'Linha cruzada', grupo: 'linhas', atalho: 'C', pontos: 1, campos: CAMPOS_CRUZ,
  icone: `M9 1 V17 M1 9 H17`,
  padrao: () => ({ ...copiar(HORIZONTAL_TV), texto: { ...TEXTO_PADRAO } }),
  linha: acesso<Linha>('linha'),
  desenhar(ctx, d, px, g) {
    const c = d.cfg as CfgHorizontal
    const x = meioPx(px[0].x, c.linha.largura), y = meioPx(px[0].y, c.linha.largura)
    tracar(ctx, c.linha); linhaReta(ctx, { x, y: 0 }, { x, y: g.H }); linhaReta(ctx, { x: 0, y }, { x: g.W, y }); ctx.setLineDash([])
  },
  acertar: (x, y, _d, px) => Math.abs(x - px[0].x) <= 5 || Math.abs(y - px[0].y) <= 5,
  rotulosPreco, rotulosTempo,
  resumo: (d, f) => f(d.pts[0].p),
}

// ---------------------------------------------------------------- canais

type CfgCanal = { linha: Linha; fundo: Fundo; meio: boolean; linhaMeio: Linha; estEsq: boolean; estDir: boolean }
const CANAL_TV: CfgCanal = {
  linha: { cor: AZUL, largura: 2, estilo: 'solida' }, fundo: fundoPadrao(AZUL, 80),
  meio: true, linhaMeio: { cor: AZUL, largura: 1, estilo: 'tracejada' }, estEsq: false, estDir: false,
}
const CAMPOS_CANAL: Campo[] = [CAMPO_LINHA(), CAMPO_FUNDO(), { tipo: 'bool', chave: 'meio', nome: 'Linha do meio' }, CAMPO_LINHA('Linha do meio', 'linhaMeio'), ...ESTENDER]

/** a 2ª linha do canal paralelo: a 1ª deslocada na vertical até passar pelo ponto 3 */
function linhaParalela(px: Px[]): [Px, Px] {
  const [a, b, c] = px
  const yNaLinha = b.x === a.x ? a.y : a.y + ((b.y - a.y) * (c.x - a.x)) / (b.x - a.x)
  const dy = c.y - yNaLinha
  return [{ x: a.x, y: a.y + dy }, { x: b.x, y: b.y + dy }]
}

function desenharCanal(ctx: CanvasRenderingContext2D, c: CfgCanal, l1: [Px, Px], l2: [Px, Px], g: Geo, meio = c.meio) {
  poligono(ctx, [l1[0], l1[1], l2[1], l2[0]], c.fundo, null)
  tracar(ctx, c.linha)
  for (const [a, b] of [l1, l2]) { const [e1, e2] = estender(a, b, c.estEsq, c.estDir, g.W, g.H); linhaReta(ctx, e1, e2) }
  if (meio) {
    tracar(ctx, c.linhaMeio)
    const [e1, e2] = estender({ x: (l1[0].x + l2[0].x) / 2, y: (l1[0].y + l2[0].y) / 2 }, { x: (l1[1].x + l2[1].x) / 2, y: (l1[1].y + l2[1].y) / 2 }, c.estEsq, c.estDir, g.W, g.H)
    linhaReta(ctx, e1, e2)
  }
  ctx.setLineDash([])
}
function acertarCanal(x: number, y: number, c: CfgCanal, l1: [Px, Px], l2: [Px, Px], g: Geo) {
  for (const [a, b] of [l1, l2]) { const [e1, e2] = estender(a, b, c.estEsq, c.estDir, g.W, g.H); if (pertoSegmento(x, y, e1, e2)) return true }
  return g.selecionado && dentroPoligono(x, y, [l1[0], l1[1], l2[1], l2[0]])
}

const canalParalelo: Ferramenta = {
  tipo: 'canal_paralelo', nome: 'Canal paralelo', grupo: 'canais', pontos: 3, campos: CAMPOS_CANAL,
  icone: 'M2 12 L12 2 M6 16 L16 6 M4 14 L14 4',
  padrao: () => copiar(CANAL_TV),
  linha: acesso<Linha>('linha'), fundo: acesso<string>('fundo.cor'),
  desenhar(ctx, d, px, g) {
    if (px.length < 3) return
    desenharCanal(ctx, d.cfg as CfgCanal, [px[0], px[1]], linhaParalela(px), g)
  },
  acertar: (x, y, d, px, g) => px.length >= 3 && acertarCanal(x, y, d.cfg as CfgCanal, [px[0], px[1]], linhaParalela(px), g),
  resumo: resumoPrecos,
}

const topoFundoPlano: Ferramenta = {
  tipo: 'topo_fundo_plano', nome: 'Topo/fundo plano', grupo: 'canais', pontos: 3, campos: CAMPOS_CANAL.filter((c) => !('chave' in c) || !c.chave.startsWith('linhaMeio') && c.chave !== 'meio'),
  icone: 'M2 14 L16 4 M2 16 H16',
  padrao: () => ({ ...copiar(CANAL_TV), meio: false }),
  linha: acesso<Linha>('linha'), fundo: acesso<string>('fundo.cor'),
  desenhar(ctx, d, px, g) {
    if (px.length < 3) return
    const yh = px[2].y
    desenharCanal(ctx, d.cfg as CfgCanal, [px[0], px[1]], [{ x: px[0].x, y: yh }, { x: px[1].x, y: yh }], g, false)
  },
  acertar: (x, y, d, px, g) => px.length >= 3 && acertarCanal(x, y, d.cfg as CfgCanal, [px[0], px[1]], [{ x: px[0].x, y: px[2].y }, { x: px[1].x, y: px[2].y }], g),
  alcas: (_d, px) => px.length >= 3 ? [px[0], px[1], { x: px[1].x, y: px[2].y }] : px,
  resumo: resumoPrecos,
}

/** o canal disjunto: a 2ª linha nasce no ponto 3 com a inclinação espelhada da 1ª */
const linhaDisjunta = (px: Px[]): [Px, Px] => [{ x: px[0].x, y: px[2].y }, { x: px[1].x, y: px[2].y - (px[1].y - px[0].y) }]
const canalDisjunto: Ferramenta = {
  tipo: 'canal_disjunto', nome: 'Canal disjunto', grupo: 'canais', pontos: 3, campos: CAMPOS_CANAL,
  icone: 'M2 8 L16 2 M2 10 L16 16',
  padrao: () => ({ ...copiar(CANAL_TV), meio: false }),
  linha: acesso<Linha>('linha'), fundo: acesso<string>('fundo.cor'),
  desenhar(ctx, d, px, g) { if (px.length >= 3) desenharCanal(ctx, d.cfg as CfgCanal, [px[0], px[1]], linhaDisjunta(px), g) },
  acertar: (x, y, d, px, g) => px.length >= 3 && acertarCanal(x, y, d.cfg as CfgCanal, [px[0], px[1]], linhaDisjunta(px), g),
  alcas: (_d, px) => px.length >= 3 ? [px[0], px[1], linhaDisjunta(px)[0]] : px,
  resumo: resumoPrecos,
}

// ---------------------------------------------------------------- canal de regressão

type CfgRegressao = { base: Linha; cima: Linha; baixo: Linha; desvio: number; fundo: Fundo; estDir: boolean; pearson: boolean }
const REGRESSAO_TV: CfgRegressao = {
  base: { cor: '#f23645', largura: 1, estilo: 'tracejada' }, cima: { cor: AZUL, largura: 1, estilo: 'solida' }, baixo: { cor: AZUL, largura: 1, estilo: 'solida' },
  desvio: 2, fundo: fundoPadrao(AZUL, 85), estDir: false, pearson: true,
}

/** regressão linear do fechamento pelas velas entre os dois instantes: reta, desvio padrão dos resíduos e r de Pearson */
function regressao(d: Desenho, g: Geo) {
  const [t1, t2] = [Math.min(d.pts[0].t, d.pts[1]?.t ?? d.pts[0].t), Math.max(d.pts[0].t, d.pts[1]?.t ?? d.pts[0].t)]
  const v = g.velas(t1, t2)
  const n = v.length
  if (n < 2) return null
  let sx = 0, sy = 0, sxx = 0, sxy = 0, syy = 0
  v.forEach((k, i) => { sx += i; sy += k.c; sxx += i * i; sxy += i * k.c; syy += k.c * k.c })
  const b = (n * sxy - sx * sy) / (n * sxx - sx * sx), a = (sy - b * sx) / n
  const sd = Math.sqrt(v.reduce((s, k, i) => s + (k.c - (a + b * i)) ** 2, 0) / n)
  const r = (n * sxy - sx * sy) / Math.sqrt((n * sxx - sx * sx) * (n * syy - sy * sy) || 1)
  return { t1: v[0].t, t2: v[n - 1].t, p1: a, p2: a + b * (n - 1), sd, r }
}

function linhasRegressao(d: Desenho, g: Geo) {
  const c = d.cfg as CfgRegressao
  const R = regressao(d, g)
  if (!R) return null
  const x1 = g.x(R.t1), x2 = g.x(R.t2)
  if (x1 === null || x2 === null) return null
  const ponto = (x: number, p: number) => { const y = g.y(p); return y === null ? null : { x, y } }
  const lin = (k: number) => {
    const a = ponto(x1, R.p1 + k * c.desvio * R.sd), b = ponto(x2, R.p2 + k * c.desvio * R.sd)
    if (!a || !b) return null
    const [e1, e2] = estender(a, b, false, c.estDir, g.W, g.H)
    return [e1, e2] as [Px, Px]
  }
  const base = lin(0), cima = lin(1), baixo = lin(-1)
  return base && cima && baixo ? { base, cima, baixo, r: R.r } : null
}

const canalRegressao: Ferramenta = {
  tipo: 'canal_regressao', nome: 'Canal de regressão', grupo: 'canais', pontos: 2, soTempo: true,
  campos: [CAMPO_LINHA('Linha base', 'base'), CAMPO_LINHA('Linha de cima', 'cima'), CAMPO_LINHA('Linha de baixo', 'baixo'),
    { tipo: 'numero', chave: 'desvio', nome: 'Desvios padrão', min: 0.1, max: 10, passo: 0.1 }, CAMPO_FUNDO(),
    { tipo: 'bool', chave: 'estDir', nome: 'Estender à direita' }, { tipo: 'bool', chave: 'pearson', nome: 'Mostrar o r de Pearson' }],
  icone: 'M2 13 L16 5 M2 9 L16 1 M2 17 L16 9',
  padrao: () => copiar(REGRESSAO_TV),
  linha: acesso<Linha>('base'), fundo: acesso<string>('fundo.cor'),
  desenhar(ctx, d, px, g) {
    const c = d.cfg as CfgRegressao
    const L = linhasRegressao(d, g)
    if (!L) { tracar(ctx, c.base); if (px[1]) linhaReta(ctx, px[0], px[1]); ctx.setLineDash([]); return }
    if (c.fundo.ligado) { ctx.fillStyle = corFundo(c.fundo); ctx.beginPath(); for (const p of [L.cima[0], L.cima[1], L.baixo[1], L.baixo[0]]) ctx.lineTo(p.x, p.y); ctx.closePath(); ctx.fill() }
    for (const [l, k] of [[c.cima, L.cima], [c.baixo, L.baixo], [c.base, L.base]] as const) { tracar(ctx, l); linhaReta(ctx, k[0], k[1]) }
    ctx.setLineDash([])
    if (c.pearson) {
      ctx.font = "11px 'DM Mono', monospace"; ctx.fillStyle = c.base.cor; ctx.textAlign = 'left'; ctx.textBaseline = 'top'
      ctx.fillText(`r ${L.r.toFixed(3).replace('.', ',')}`, L.baixo[0].x, L.baixo[0].y + 4)
    }
  },
  acertar(x, y, d, _px, g) {
    const L = linhasRegressao(d, g)
    if (!L) return false
    if ([L.base, L.cima, L.baixo].some(([a, b]) => pertoSegmento(x, y, a, b))) return true
    return g.selecionado && dentroPoligono(x, y, [L.cima[0], L.cima[1], L.baixo[1], L.baixo[0]])
  },
  alcas(d, px, g) { const L = linhasRegressao(d, g); return L ? [L.base[0], L.base[1]] : px },
  resumo: (d) => `${duracao(Math.abs((d.pts[1]?.t ?? d.pts[0].t) - d.pts[0].t))}`,
}

export const LINHAS: Ferramenta[] = [tendencia, raio, informacao, estendida, anguloTendencia, horizontal, raioHorizontal, vertical, cruz]
export const CANAIS: Ferramenta[] = [canalParalelo, canalRegressao, topoFundoPlano, canalDisjunto]
