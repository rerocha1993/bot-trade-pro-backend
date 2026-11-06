/**
 * Pitchforks (Andrews, Schiff, Schiff modificado e interno) e Gann (caixa, quadrado fixo, quadrado e leque), no molde
 * das ferramentas da TradingView.
 *
 * Pitchfork: 3 cliques (A, B, C). A mediana sai da origem e passa pelo meio de BC; as outras linhas são paralelas a
 * ela, saindo de BC nos níveis (1 = em B e em C). A origem muda com o estilo: Andrews = A; Schiff = A no tempo e no
 * meio do preço de A e B; Schiff modificado e interno = meio de A e B no tempo e no preço.
 */
import type { Linha } from '../../lib/desenhos'
import {
  acesso, comAlfa, linhaReta, PERTO_PX, pertoSegmento, resumoPrecos, tracar,
  type Campo, type Ferramenta, type Geo, type Px,
} from './ferramentasBase'
import {
  baseNiveis, CAMPOS_NIVEIS, ligadosEmOrdem, nivelTraco, niveisPadrao, raioAte, rotulo, rotuloNivel, type CfgNiveis, type NivelF,
} from './ferramentasFibo'

const CINZA = '#787b86'
const alfa = (c: { transparencia: number }) => (100 - c.transparencia) / 100

// ---------------------------------------------------------------- pitchforks

type Estilo = 'andrews' | 'schiff' | 'schiff_mod' | 'interno'
function origem(estilo: Estilo, px: Px[]): Px {
  const [a, b] = px
  if (estilo === 'schiff') return { x: a.x, y: (a.y + b.y) / 2 }
  if (estilo === 'schiff_mod' || estilo === 'interno') return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
  return a
}

function linhasForquilha(estilo: Estilo, c: CfgNiveis, px: Px[], g: Geo) {
  const [, b, k] = px
  const o = origem(estilo, px)
  const m = { x: (b.x + k.x) / 2, y: (b.y + k.y) / 2 }
  const dir = { x: m.x - o.x, y: m.y - o.y }
  const mediana = { a: o, fim: raioAte(o, dir, g.W, g.H) }
  const lados: { valor: number; cor: string; a: Px; fim: Px }[][] = [[], []]
  for (const n of ligadosEmOrdem(c.niveis)) {
    if (n.valor === 0) continue
    ;[k, b].forEach((lado, i) => {
      const p = { x: m.x + (lado.x - m.x) * n.valor, y: m.y + (lado.y - m.y) * n.valor }
      lados[i].push({ ...n, a: p, fim: raioAte(p, dir, g.W, g.H) })
    })
  }
  return { o, m, mediana, lados }
}

function ferramentaForquilha(tipo: string, nome: string, estilo: Estilo, icone: string): Ferramenta {
  return {
    tipo, nome, grupo: 'gann', pontos: 3, icone,
    campos: [{ tipo: 'linha', chave: 'linha', nome: 'Mediana' } as Campo, ...CAMPOS_NIVEIS({ tendencia: false, precos: false })],
    padrao: () => baseNiveis(niveisPadrao([0.5, 1], [0.25, 0.382, 0.618, 0.75, 1.5, 1.75, 2]), {
      tendencia: false, precos: false, linha: { cor: '#f23645', largura: 1, estilo: 'solida' }, transparencia: 85,
    }),
    linha: acesso<Linha>('linha'),
    desenhar(ctx, d, px, g) {
      const c = d.cfg as CfgNiveis
      if (px.length < 3) { if (px.length === 2) { tracar(ctx, c.linha); linhaReta(ctx, px[0], px[1]) } return }
      const F = linhasForquilha(estilo, c, px, g)
      if (c.fundo) for (const L of F.lados) for (let i = 0; i < L.length; i++) {
        const ant = i ? L[i - 1] : { a: F.m, fim: F.mediana.fim }
        ctx.fillStyle = comAlfa(L[i].cor, alfa(c))
        ctx.beginPath(); ctx.moveTo(ant.a.x, ant.a.y); ctx.lineTo(ant.fim.x, ant.fim.y); ctx.lineTo(L[i].fim.x, L[i].fim.y); ctx.lineTo(L[i].a.x, L[i].a.y); ctx.closePath(); ctx.fill()
      }
      for (const L of F.lados) for (const n of L) { nivelTraco(ctx, c, n.cor); linhaReta(ctx, n.a, n.fim) }
      tracar(ctx, c.linha); linhaReta(ctx, F.mediana.a, F.mediana.fim)
      tracar(ctx, { cor: CINZA, largura: 1, estilo: 'solida' }); linhaReta(ctx, px[1], px[2])
      if (estilo !== 'andrews') { tracar(ctx, { cor: CINZA, largura: 1, estilo: 'tracejada' }); linhaReta(ctx, px[0], px[1]) }
      ctx.setLineDash([])
      if (c.rotulos) for (const L of F.lados) for (const n of L) rotulo(ctx, rotuloNivel(n.valor), n.a.x + 4, n.a.y, n.cor)
    },
    acertar(x, y, d, px, g) {
      if (px.length < 3) return false
      const F = linhasForquilha(estilo, d.cfg as CfgNiveis, px, g)
      return pertoSegmento(x, y, F.mediana.a, F.mediana.fim) || pertoSegmento(x, y, px[1], px[2]) || F.lados.some((L) => L.some((n) => pertoSegmento(x, y, n.a, n.fim)))
    },
    resumo: resumoPrecos,
  }
}

const forquilha = ferramentaForquilha('pitchfork', 'Pitchfork (Andrews)', 'andrews', 'M2 16 L10 6 M6 3 L14 9 M6 3 L16 1 M14 9 L18 6 M10 6 L17 3')
const schiff = ferramentaForquilha('pitchfork_schiff', 'Pitchfork de Schiff', 'schiff', 'M2 12 L10 6 M6 3 L14 9 M6 3 L16 1 M14 9 L18 6 M2 16 V8')
const schiffMod = ferramentaForquilha('pitchfork_schiff_mod', 'Pitchfork de Schiff modificado', 'schiff_mod', 'M4 11 L10 6 M6 3 L14 9 M6 3 L16 1 M14 9 L18 6 M2 16 L6 6')
const interno = ferramentaForquilha('pitchfork_interno', 'Pitchfork interno', 'interno', 'M4 10 L10 6 M6 3 L14 9 M2 16 L6 3 M8 5 L15 3 M12 8 L17 7')

// ---------------------------------------------------------------- caixa de Gann

type CfgGannCaixa = {
  niveisPreco: NivelF[]; niveisTempo: NivelF[]; largura: number; estilo: Linha['estilo']
  fundo: boolean; transparencia: number; rotulos: boolean; angulos: boolean; linhaAngulos: Linha
}
const NIVEIS_GANN = [0, 0.25, 0.382, 0.5, 0.618, 0.75, 1]
const caixaRet = (px: Px[]) => ({ x0: px[0].x, y0: px[0].y, x1: px[1].x, y1: px[1].y })

const gannCaixa: Ferramenta = {
  tipo: 'gann_caixa', nome: 'Caixa de Gann', grupo: 'gann', pontos: 2,
  campos: [
    { tipo: 'numero', chave: 'largura', nome: 'Espessura dos níveis', min: 1, max: 4 },
    { tipo: 'escolha', chave: 'estilo', nome: 'Estilo dos níveis', opcoes: [['solida', 'Sólida'], ['tracejada', 'Tracejada'], ['pontilhada', 'Pontilhada']] },
    { tipo: 'niveis', chave: 'niveisPreco', nome: 'Níveis de preço' }, { tipo: 'niveis', chave: 'niveisTempo', nome: 'Níveis de tempo' },
    { tipo: 'bool', chave: 'fundo', nome: 'Fundo' }, { tipo: 'numero', chave: 'transparencia', nome: 'Transparência do fundo (%)', min: 0, max: 100, passo: 5 },
    { tipo: 'bool', chave: 'rotulos', nome: 'Rótulos' }, { tipo: 'bool', chave: 'angulos', nome: 'Ângulos (diagonais)' }, { tipo: 'linha', chave: 'linhaAngulos', nome: 'Linha dos ângulos' },
  ],
  icone: 'M2 2 H16 V16 H2 Z M2 9 H16 M9 2 V16 M2 16 L16 2',
  padrao: (): CfgGannCaixa => ({
    niveisPreco: niveisPadrao(NIVEIS_GANN), niveisTempo: niveisPadrao(NIVEIS_GANN), largura: 1, estilo: 'solida',
    fundo: true, transparencia: 90, rotulos: true, angulos: false, linhaAngulos: { cor: CINZA, largura: 1, estilo: 'solida' },
  }),
  linha: acesso<Linha>('linhaAngulos'),
  desenhar(ctx, d, px) {
    if (px.length < 2) return
    const c = d.cfg as CfgGannCaixa, { x0, y0, x1, y1 } = caixaRet(px)
    const preco = ligadosEmOrdem(c.niveisPreco), tempo = ligadosEmOrdem(c.niveisTempo)
    const traco = { largura: c.largura, estilo: c.estilo }
    if (c.fundo) {
      for (let i = 1; i < preco.length; i++) { ctx.fillStyle = comAlfa(preco[i].cor, alfa(c)); const ya = y0 + (y1 - y0) * preco[i - 1].valor, yb = y0 + (y1 - y0) * preco[i].valor; ctx.fillRect(Math.min(x0, x1), Math.min(ya, yb), Math.abs(x1 - x0), Math.abs(yb - ya)) }
      for (let i = 1; i < tempo.length; i++) { ctx.fillStyle = comAlfa(tempo[i].cor, alfa(c) * 0.6); const xa = x0 + (x1 - x0) * tempo[i - 1].valor, xb = x0 + (x1 - x0) * tempo[i].valor; ctx.fillRect(Math.min(xa, xb), Math.min(y0, y1), Math.abs(xb - xa), Math.abs(y1 - y0)) }
    }
    for (const n of preco) { const y = y0 + (y1 - y0) * n.valor; tracar(ctx, { cor: n.cor, ...traco }); linhaReta(ctx, { x: x0, y }, { x: x1, y }) }
    for (const n of tempo) { const x = x0 + (x1 - x0) * n.valor; tracar(ctx, { cor: n.cor, ...traco }); linhaReta(ctx, { x, y: y0 }, { x, y: y1 }) }
    if (c.angulos) { tracar(ctx, c.linhaAngulos); linhaReta(ctx, { x: x0, y: y0 }, { x: x1, y: y1 }); linhaReta(ctx, { x: x0, y: y1 }, { x: x1, y: y0 }) }
    ctx.setLineDash([])
    if (c.rotulos) {
      const esq = Math.min(x0, x1), topo = Math.min(y0, y1)
      for (const n of preco) rotulo(ctx, rotuloNivel(n.valor), esq - 4, y0 + (y1 - y0) * n.valor, n.cor, 'right')
      for (const n of tempo) rotulo(ctx, rotuloNivel(n.valor), x0 + (x1 - x0) * n.valor, topo - 4, n.cor, 'center', 'bottom')
    }
  },
  acertar(x, y, d, px) {
    if (px.length < 2) return false
    const c = d.cfg as CfgGannCaixa, { x0, y0, x1, y1 } = caixaRet(px)
    const dentroX = x >= Math.min(x0, x1) - 5 && x <= Math.max(x0, x1) + 5, dentroY = y >= Math.min(y0, y1) - 5 && y <= Math.max(y0, y1) + 5
    return (dentroX && ligadosEmOrdem(c.niveisPreco).some((n) => Math.abs(y - (y0 + (y1 - y0) * n.valor)) <= PERTO_PX))
      || (dentroY && ligadosEmOrdem(c.niveisTempo).some((n) => Math.abs(x - (x0 + (x1 - x0) * n.valor)) <= PERTO_PX))
      || (c.angulos && (pertoSegmento(x, y, { x: x0, y: y0 }, { x: x1, y: y1 }) || pertoSegmento(x, y, { x: x0, y: y1 }, { x: x1, y: y0 })))
  },
  resumo: resumoPrecos,
}

// ---------------------------------------------------------------- quadrado de Gann (e o fixo)

type CfgGannQuadrado = {
  niveis: NivelF[]; largura: number; estilo: Linha['estilo']; fundo: boolean; transparencia: number; rotulos: boolean
  leques: boolean; arcos: boolean; linhaLeque: Linha; linhaArco: Linha
}
/** razões tempo × preço dos raios do leque de Gann, do mais deitado ao mais em pé */
const RAZOES: [string, number, number][] = [['1x8', 8, 1], ['1x4', 4, 1], ['1x3', 3, 1], ['1x2', 2, 1], ['1x1', 1, 1], ['2x1', 1, 2], ['3x1', 1, 3], ['4x1', 1, 4], ['8x1', 1, 8]]

/** o quadrado fixo força o mesmo tamanho em pixels nos dois lados */
function cantoOposto(px: Px[], fixo: boolean): Px {
  const [a, b] = px
  if (!fixo) return b
  const s = Math.max(Math.abs(b.x - a.x), Math.abs(b.y - a.y))
  return { x: a.x + Math.sign(b.x - a.x || 1) * s, y: a.y + Math.sign(b.y - a.y || 1) * s }
}

function ferramentaQuadrado(tipo: string, nome: string, fixo: boolean, icone: string): Ferramenta {
  return {
    tipo, nome, grupo: 'gann', pontos: 2, icone,
    campos: [
      ...CAMPOS_NIVEIS({ tendencia: false, precos: false }),
      { tipo: 'bool', chave: 'leques', nome: 'Leques' }, { tipo: 'linha', chave: 'linhaLeque', nome: 'Linha dos leques' },
      { tipo: 'bool', chave: 'arcos', nome: 'Arcos' }, { tipo: 'linha', chave: 'linhaArco', nome: 'Linha dos arcos' },
    ],
    padrao: (): CfgGannQuadrado => ({
      niveis: niveisPadrao(NIVEIS_GANN), largura: 1, estilo: 'solida', fundo: true, transparencia: 92, rotulos: true,
      leques: true, arcos: true, linhaLeque: { cor: '#2962ff', largura: 1, estilo: 'solida' }, linhaArco: { cor: '#ff9800', largura: 1, estilo: 'solida' },
    }),
    linha: acesso<Linha>('linhaLeque'),
    alcas: (_d, px) => (px.length >= 2 ? [px[0], cantoOposto(px, fixo)] : px),
    desenhar(ctx, d, px) {
      if (px.length < 2) return
      const c = d.cfg as CfgGannQuadrado, a = px[0], b = cantoOposto(px, fixo)
      const dx = b.x - a.x, dy = b.y - a.y
      const lista = ligadosEmOrdem(c.niveis)
      ctx.save()
      ctx.beginPath(); ctx.rect(Math.min(a.x, b.x) - 1, Math.min(a.y, b.y) - 1, Math.abs(dx) + 2, Math.abs(dy) + 2); ctx.clip()
      if (c.fundo) for (let i = 1; i < lista.length; i++) {
        ctx.fillStyle = comAlfa(lista[i].cor, alfa(c))
        const ya = a.y + dy * lista[i - 1].valor, yb = a.y + dy * lista[i].valor
        ctx.fillRect(Math.min(a.x, b.x), Math.min(ya, yb), Math.abs(dx), Math.abs(yb - ya))
      }
      for (const n of lista) {
        tracar(ctx, { cor: n.cor, largura: c.largura, estilo: c.estilo })
        linhaReta(ctx, { x: a.x, y: a.y + dy * n.valor }, { x: b.x, y: a.y + dy * n.valor })
        linhaReta(ctx, { x: a.x + dx * n.valor, y: a.y }, { x: a.x + dx * n.valor, y: b.y })
      }
      if (c.leques) {
        tracar(ctx, c.linhaLeque)
        // cada razão tempo×preço até a borda do quadrado: 1x1 vai ao canto oposto, 1x8 quase deitada, 8x1 quase em pé
        for (const [, t, p] of RAZOES) { const s = Math.max(t, p); linhaReta(ctx, a, { x: a.x + (dx * t) / s, y: a.y + (dy * p) / s }) }
      }
      if (c.arcos) {
        tracar(ctx, c.linhaArco)
        for (const n of lista) if (n.valor > 0) { ctx.beginPath(); ctx.ellipse(a.x, a.y, Math.abs(dx) * n.valor, Math.abs(dy) * n.valor, 0, 0, Math.PI * 2); ctx.stroke() }
      }
      ctx.setLineDash([])
      ctx.restore()
      if (c.rotulos) for (const n of lista) rotulo(ctx, rotuloNivel(n.valor), Math.min(a.x, b.x) - 4, a.y + dy * n.valor, n.cor, 'right')
    },
    acertar(x, y, d, px) {
      if (px.length < 2) return false
      const a = px[0], b = cantoOposto(px, fixo)
      return x >= Math.min(a.x, b.x) - 3 && x <= Math.max(a.x, b.x) + 3 && y >= Math.min(a.y, b.y) - 3 && y <= Math.max(a.y, b.y) + 3
        && (ligadosEmOrdem((d.cfg as CfgGannQuadrado).niveis).some((n) => Math.abs(y - (a.y + (b.y - a.y) * n.valor)) <= PERTO_PX || Math.abs(x - (a.x + (b.x - a.x) * n.valor)) <= PERTO_PX))
    },
    resumo: resumoPrecos,
  }
}
const quadradoFixo = ferramentaQuadrado('gann_quadrado_fixo', 'Quadrado de Gann fixo', true, 'M2 2 H16 V16 H2 Z M2 16 L16 2 M2 16 L16 9 M2 16 L9 2')
const quadrado = ferramentaQuadrado('gann_quadrado', 'Quadrado de Gann', false, 'M2 4 H16 V14 H2 Z M2 14 L16 4 M2 14 A14 10 0 0 1 16 4')

// ---------------------------------------------------------------- leque de Gann

type CfgGannLeque = { angulos: NivelF[]; largura: number; estilo: Linha['estilo']; fundo: boolean; transparencia: number; rotulos: boolean }
/** o valor do nível é a razão preço/tempo em relação ao 1x1 (o ponto 2): 2 = 2x1 (mais em pé), 0,5 = 1x2 */
const nomeAngulo = (v: number) => (v >= 1 ? `${+v.toFixed(2)}x1` : `1x${+(1 / v).toFixed(2)}`)
function raiosGann(c: CfgGannLeque, px: Px[], g: Geo) {
  const [a, b] = px
  const dx = b.x - a.x, dy = b.y - a.y
  return ligadosEmOrdem(c.angulos).filter((n) => n.valor > 0).map((n) => {
    const dir = { x: dx, y: dy * n.valor }
    const k = n.valor > 1 ? 1 / n.valor : 1
    return { ...n, fim: raioAte(a, dir, g.W, g.H), rot: { x: a.x + dir.x * k, y: a.y + dir.y * k } }
  })
}
const gannLeque: Ferramenta = {
  tipo: 'gann_leque', nome: 'Leque de Gann', grupo: 'gann', pontos: 2,
  campos: [
    { tipo: 'numero', chave: 'largura', nome: 'Espessura', min: 1, max: 4 },
    { tipo: 'escolha', chave: 'estilo', nome: 'Estilo', opcoes: [['solida', 'Sólida'], ['tracejada', 'Tracejada'], ['pontilhada', 'Pontilhada']] },
    { tipo: 'niveis', chave: 'angulos', nome: 'Ângulos (preço/tempo; 1 = 1x1)' },
    { tipo: 'bool', chave: 'fundo', nome: 'Fundo' }, { tipo: 'numero', chave: 'transparencia', nome: 'Transparência do fundo (%)', min: 0, max: 100, passo: 5 },
    { tipo: 'bool', chave: 'rotulos', nome: 'Rótulos' },
  ],
  icone: 'M2 16 L16 2 M2 16 L16 9 M2 16 L9 2 M2 16 L16 13 M2 16 L13 2',
  padrao: (): CfgGannLeque => ({
    angulos: [8, 4, 3, 2, 1, 1 / 2, 1 / 3, 1 / 4, 1 / 8].map((valor, i) => ({ valor, ligado: true, cor: ['#f23645', '#ff9800', '#4caf50', '#089981', '#2962ff', '#089981', '#4caf50', '#ff9800', '#f23645'][i] })),
    largura: 1, estilo: 'solida', fundo: true, transparencia: 90, rotulos: true,
  }),
  linha: { ler: (c: CfgGannLeque) => ({ cor: c.angulos[4]?.cor ?? '#2962ff', largura: c.largura, estilo: c.estilo }), gravar: (c: CfgGannLeque, l) => ({ ...c, largura: l.largura, estilo: l.estilo }) },
  desenhar(ctx, d, px, g) {
    if (px.length < 2) return
    const c = d.cfg as CfgGannLeque
    const R = raiosGann(c, px, g)
    if (c.fundo) for (let i = 1; i < R.length; i++) {
      ctx.fillStyle = comAlfa(R[i].cor, alfa(c))
      ctx.beginPath(); ctx.moveTo(px[0].x, px[0].y); ctx.lineTo(R[i - 1].fim.x, R[i - 1].fim.y); ctx.lineTo(R[i].fim.x, R[i].fim.y); ctx.closePath(); ctx.fill()
    }
    for (const r of R) { tracar(ctx, { cor: r.cor, largura: c.largura, estilo: c.estilo }); linhaReta(ctx, px[0], r.fim) }
    ctx.setLineDash([])
    if (c.rotulos) for (const r of R) rotulo(ctx, nomeAngulo(r.valor), r.rot.x + 4, r.rot.y, r.cor)
  },
  acertar: (x, y, d, px, g) => px.length >= 2 && raiosGann(d.cfg as CfgGannLeque, px, g).some((r) => pertoSegmento(x, y, px[0], r.fim)),
  resumo: resumoPrecos,
}

export const GANN: Ferramenta[] = [forquilha, schiff, schiffMod, interno, gannCaixa, quadradoFixo, quadrado, gannLeque]
