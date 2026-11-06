/**
 * Ondas de Elliott (impulso, correção, triângulo, combinação dupla e tripla), padrões (XABCD, Cypher, ABCD, triângulo,
 * ombro-cabeça-ombro, três drives) e posição comprada/vendida, no molde das ferramentas da TradingView.
 *
 * Elliott: os rótulos seguem o grau escolhido (ciclo I, primário ①, intermediário (1), menor 1, minuto (i), minueto i).
 * No impulso, "Conferir as regras" avisa no gráfico quando a contagem quebra uma regra: a onda 2 passa do início da 1,
 * a 3 é a mais curta, ou a 4 entra no território da 1. É só a geometria dos pontos marcados, não uma previsão.
 *
 * Posição: um clique na entrada; nasce com stop a 1% e alvo a 2% (arraste as alças). Mostra risco e retorno, a
 * quantidade pelo risco da conta e, com as velas que vieram depois, se bateu primeiro o alvo ou o stop.
 */
import type { Desenho, Linha } from '../../lib/desenhos'
import {
  acesso, caixaComTexto, comAlfa, dentroPoligono, estender, linhaReta, pct, pertoPolilinha, pertoSegmento, poligono, tracar,
  type Campo, type Ferramenta, type Fundo, type Geo, type Px,
} from './ferramentasBase'

const AZUL = '#2962ff', VERDE = '#089981', VERMELHO = '#f23645'
const fmtNum = (v: number, casas = 2) => v.toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas })

/** rótulo num ponto: em cima se o ponto é topo (mais alto que os vizinhos), embaixo se é fundo */
function rotuloNoPonto(ctx: CanvasRenderingContext2D, texto: string, px: Px[], i: number, cor: string, tam = 12, negrito = true) {
  if (!texto) return
  const p = px[i], ant = px[i - 1], prox = px[i + 1]
  const viz = [ant, prox].filter(Boolean) as Px[]
  const topo = viz.length ? viz.every((v) => p.y <= v.y) : true
  ctx.font = `${negrito ? 'bold ' : ''}${tam}px 'DM Sans', sans-serif`
  ctx.fillStyle = cor; ctx.textAlign = 'center'; ctx.textBaseline = topo ? 'bottom' : 'top'
  ctx.fillText(texto, p.x, p.y + (topo ? -6 : 6))
}
const linhaPorPontos = (ctx: CanvasRenderingContext2D, px: Px[]) => { ctx.beginPath(); px.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y))); ctx.stroke() }

// ---------------------------------------------------------------- Elliott

const GRAUS: [string, string][] = [['ciclo', 'Ciclo (I, II…)'], ['primario', 'Primário (①…)'], ['intermediario', 'Intermediário ((1)…)'], ['menor', 'Menor (1…)'], ['minuto', 'Minuto ((i)…)'], ['minueto', 'Minueto (i…)']]
const ROMANOS = ['I', 'II', 'III', 'IV', 'V']
const CIRCULADOS = ['①', '②', '③', '④', '⑤']
const LETRAS_CIRC: Record<string, string> = { A: 'Ⓐ', B: 'Ⓑ', C: 'Ⓒ', D: 'Ⓓ', E: 'Ⓔ', W: 'Ⓦ', X: 'Ⓧ', Y: 'Ⓨ', Z: 'Ⓩ' }
/** o rótulo de uma onda ('1'..'5' ou letra) no grau escolhido */
function rotuloOnda(onda: string, grau: string): string {
  const n = Number(onda)
  const num = Number.isFinite(n)
  switch (grau) {
    case 'ciclo': return num ? ROMANOS[n - 1] : onda
    case 'primario': return num ? CIRCULADOS[n - 1] : LETRAS_CIRC[onda] ?? onda
    case 'intermediario': return `(${onda})`
    case 'menor': return onda
    case 'minuto': return num ? `(${ROMANOS[n - 1].toLowerCase()})` : `(${onda.toLowerCase()})`
    case 'minueto': return num ? ROMANOS[n - 1].toLowerCase() : onda.toLowerCase()
    default: return onda
  }
}

type CfgElliott = { linha: Linha; grau: string; corRotulo: string; tamanho: number; regras: boolean }
const CAMPOS_ELLIOTT: Campo[] = [
  { tipo: 'linha', chave: 'linha', nome: 'Linha' },
  { tipo: 'escolha', chave: 'grau', nome: 'Grau', opcoes: GRAUS },
  { tipo: 'cor', chave: 'corRotulo', nome: 'Cor dos rótulos' },
  { tipo: 'numero', chave: 'tamanho', nome: 'Tamanho dos rótulos', min: 9, max: 28 },
]

/** as 3 regras do impulso (para cima ou para baixo); devolve os avisos e o ponto onde mostrar cada um */
function regrasImpulso(d: Desenho): { i: number; texto: string }[] {
  if (d.pts.length < 6) return []
  const p = d.pts.map((x) => x.p)
  const s = p[1] >= p[0] ? 1 : -1
  const out: { i: number; texto: string }[] = []
  if (s * (p[2] - p[0]) <= 0) out.push({ i: 2, texto: 'onda 2 passou do início da 1' })
  const o1 = Math.abs(p[1] - p[0]), o3 = Math.abs(p[3] - p[2]), o5 = Math.abs(p[5] - p[4])
  if (o3 < o1 && o3 < o5) out.push({ i: 3, texto: 'onda 3 é a mais curta' })
  if (s * (p[4] - p[1]) <= 0) out.push({ i: 4, texto: 'onda 4 entrou no território da 1' })
  return out
}

function ferramentaElliott(tipo: string, nome: string, ondas: string[], icone: string, regras = false): Ferramenta {
  return {
    tipo, nome, grupo: 'elliott', pontos: ondas.length + 1, icone,
    campos: regras ? [...CAMPOS_ELLIOTT, { tipo: 'bool', chave: 'regras', nome: 'Conferir as regras do impulso' }] : CAMPOS_ELLIOTT,
    padrao: (): CfgElliott => ({ linha: { cor: AZUL, largura: 2, estilo: 'solida' }, grau: 'intermediario', corRotulo: AZUL, tamanho: 13, regras }),
    linha: acesso<Linha>('linha'),
    cor: acesso<string>('corRotulo'),
    desenhar(ctx, d, px, g) {
      const c = d.cfg as CfgElliott
      tracar(ctx, c.linha); linhaPorPontos(ctx, px); ctx.setLineDash([])
      ondas.forEach((o, k) => { if (px[k + 1]) rotuloNoPonto(ctx, rotuloOnda(o, c.grau), px, k + 1, c.corRotulo, c.tamanho) })
      if (regras && c.regras && px.length >= 6) {
        for (const r of regrasImpulso(d)) {
          caixaComTexto(ctx, [`⚠ ${r.texto}`], { x: px[r.i].x + 8, y: px[r.i].y }, {
            fonte: "11px 'DM Sans', sans-serif", tamanho: 11, cor: '#ffffff', fundo: 'rgba(242,54,69,0.85)', ancora: 'esquerda', W: g.W, H: g.H,
          })
        }
      }
    },
    acertar: (x, y, _d, px) => pertoPolilinha(x, y, px),
    resumo: (d) => ondas.slice(0, Math.max(0, d.pts.length - 1)).map((o) => rotuloOnda(o, (d.cfg as CfgElliott).grau)).join(' '),
  }
}
const impulso = ferramentaElliott('elliott_impulso', 'Onda de impulso (12345)', ['1', '2', '3', '4', '5'], 'M1 15 L5 9 L7 12 L12 3 L14 7 L17 1', true)
const correcao = ferramentaElliott('elliott_correcao', 'Onda de correção (ABC)', ['A', 'B', 'C'], 'M1 3 L7 12 L11 7 L17 16')
const trianguloE = ferramentaElliott('elliott_triangulo', 'Onda de triângulo (ABCDE)', ['A', 'B', 'C', 'D', 'E'], 'M1 2 L5 15 L8 5 L11 13 L14 7 L17 11')
const dupla = ferramentaElliott('elliott_dupla', 'Combinação dupla (WXY)', ['W', 'X', 'Y'], 'M1 3 L7 11 L11 6 L17 15')
const tripla = ferramentaElliott('elliott_tripla', 'Combinação tripla (WXYXZ)', ['W', 'X', 'Y', 'X', 'Z'], 'M1 2 L4 9 L7 6 L10 12 L13 9 L17 16')

// ---------------------------------------------------------------- padrões

type CfgPadrao = { linha: Linha; fundo: Fundo; corTexto: string; razoes: boolean }
const PADRAO_TV = (cor = AZUL): CfgPadrao => ({ linha: { cor, largura: 2, estilo: 'solida' }, fundo: { ligado: true, cor, transparencia: 85 }, corTexto: '#ffffff', razoes: true })
const CAMPOS_PADRAO: Campo[] = [
  { tipo: 'linha', chave: 'linha', nome: 'Linha' }, { tipo: 'fundo', chave: 'fundo', nome: 'Fundo' },
  { tipo: 'cor', chave: 'corTexto', nome: 'Cor dos rótulos' }, { tipo: 'bool', chave: 'razoes', nome: 'Razões de Fibonacci' },
]
const razao = (d: Desenho, a: number, b: number, c: number, e: number) => {
  const den = Math.abs(d.pts[b].p - d.pts[a].p)
  return den ? Math.abs(d.pts[e].p - d.pts[c].p) / den : 0
}
/** linha tracejada entre dois pontos com a razão no meio */
function linhaRazao(ctx: CanvasRenderingContext2D, a: Px, b: Px, valor: number, c: CfgPadrao) {
  tracar(ctx, { cor: c.linha.cor, largura: 1, estilo: 'tracejada' }); linhaReta(ctx, a, b); ctx.setLineDash([])
  caixaComTexto(ctx, [fmtNum(valor, 3)], { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }, {
    fonte: "11px 'DM Mono', monospace", tamanho: 11, cor: c.corTexto, fundo: comAlfa(c.linha.cor, 0.85),
  })
}

function ferramentaPadrao(tipo: string, nome: string, rotulos: string[], icone: string, extra: (ctx: CanvasRenderingContext2D, d: Desenho, px: Px[], c: CfgPadrao, g: Geo) => void, triangulos: number[][] = []): Ferramenta {
  return {
    tipo, nome, grupo: 'padroes', pontos: rotulos.length, icone, campos: CAMPOS_PADRAO,
    padrao: () => PADRAO_TV(),
    linha: acesso<Linha>('linha'), fundo: acesso<string>('fundo.cor'),
    desenhar(ctx, d, px, g) {
      const c = d.cfg as CfgPadrao
      for (const tri of triangulos) if (tri.every((i) => px[i])) poligono(ctx, tri.map((i) => px[i]), c.fundo, null)
      tracar(ctx, c.linha); linhaPorPontos(ctx, px); ctx.setLineDash([])
      extra(ctx, d, px, c, g)
      rotulos.forEach((r, i) => { if (px[i]) rotuloNoPonto(ctx, r, px, i, c.linha.cor, 12) })
    },
    acertar(x, y, d, px, g) {
      if (pertoPolilinha(x, y, px)) return true
      const c = d.cfg as CfgPadrao
      return g.selecionado && c.fundo.ligado && triangulos.some((tri) => tri.every((i) => px[i]) && dentroPoligono(x, y, tri.map((i) => px[i])))
    },
    resumo: (d) => `${d.pts.length} pontos`,
  }
}

const xabcd = ferramentaPadrao('padrao_xabcd', 'Padrão XABCD', ['X', 'A', 'B', 'C', 'D'], 'M1 14 L5 3 L8 10 L12 5 L17 15 M1 14 L8 10 M8 10 L17 15',
  (ctx, d, px, c) => {
    if (!c.razoes) return
    if (px[2]) linhaRazao(ctx, px[0], px[2], razao(d, 0, 1, 1, 2), c)               // AB / XA
    if (px[3]) linhaRazao(ctx, px[1], px[3], razao(d, 1, 2, 2, 3), c)               // BC / AB
    if (px[4]) { linhaRazao(ctx, px[2], px[4], razao(d, 2, 3, 3, 4), c); linhaRazao(ctx, px[0], px[4], razao(d, 0, 1, 1, 4), c) }   // CD / BC, AD / XA
  }, [[0, 1, 2], [2, 3, 4]])

const cypher = ferramentaPadrao('padrao_cypher', 'Padrão Cypher', ['X', 'A', 'B', 'C', 'D'], 'M1 15 L5 4 L8 10 L12 1 L17 12 M1 15 L8 10 L17 12',
  (ctx, d, px, c) => {
    if (!c.razoes) return
    if (px[2]) linhaRazao(ctx, px[0], px[2], razao(d, 0, 1, 1, 2), c)               // AB / XA
    if (px[3]) linhaRazao(ctx, px[0], px[3], razao(d, 0, 1, 0, 3), c)               // XC / XA (extensão)
    if (px[4]) linhaRazao(ctx, px[2], px[4], razao(d, 0, 3, 3, 4), c)               // CD / XC
  }, [[0, 1, 2], [2, 3, 4]])

const abcd = ferramentaPadrao('padrao_abcd', 'Padrão ABCD', ['A', 'B', 'C', 'D'], 'M1 15 L6 4 L10 10 L17 1',
  (ctx, d, px, c) => {
    if (!c.razoes) return
    if (px[2]) linhaRazao(ctx, px[0], px[2], razao(d, 0, 1, 1, 2), c)               // BC / AB
    if (px[3]) linhaRazao(ctx, px[1], px[3], razao(d, 1, 2, 2, 3), c)               // CD / BC
  })

const trianguloPadrao = ferramentaPadrao('padrao_triangulo', 'Padrão de triângulo', ['A', 'B', 'C', 'D'], 'M1 2 L6 15 L10 5 L14 12 M1 2 L17 9 M6 15 L17 9',
  (ctx, _d, px, c, g) => {
    if (px.length < 4) return
    // as duas bordas do triângulo, esticadas até se cruzarem
    tracar(ctx, { ...c.linha, largura: 1, estilo: 'tracejada' })
    const [a1, a2] = estender(px[0], px[2], false, true, g.W, g.H), [b1, b2] = estender(px[1], px[3], false, true, g.W, g.H)
    linhaReta(ctx, a1, a2); linhaReta(ctx, b1, b2); ctx.setLineDash([])
  }, [[0, 1, 2], [1, 2, 3]])

const oco = ferramentaPadrao('padrao_oco', 'Ombro-cabeça-ombro', ['', 'Ombro esquerdo', '', 'Cabeça', '', 'Ombro direito', ''], 'M1 15 L4 8 L6 11 L9 2 L12 11 L14 8 L17 15 M1 11 H17',
  (ctx, _d, px, c, g) => {
    if (px.length < 5) return
    // a linha do pescoço passa pelos dois fundos entre os ombros e a cabeça
    tracar(ctx, { ...c.linha, estilo: 'tracejada' })
    const [e1, e2] = estender(px[2], px[4], true, true, g.W, g.H)
    linhaReta(ctx, e1, e2); ctx.setLineDash([])
  }, [[0, 1, 2], [2, 3, 4], [4, 5, 6]])

const tresDrives = ferramentaPadrao('padrao_tres_drives', 'Padrão de três drives', ['', '1', 'A', '2', 'B', '3', ''], 'M1 16 L4 10 L6 12 L9 6 L11 8 L14 2 L17 6',
  (ctx, d, px, c) => {
    if (!c.razoes) return
    if (px[3]) linhaRazao(ctx, px[1], px[3], razao(d, 0, 1, 2, 3), c)               // drive 2 / drive 1
    if (px[5]) linhaRazao(ctx, px[3], px[5], razao(d, 2, 3, 4, 5), c)               // drive 3 / drive 2
  })

// ---------------------------------------------------------------- posição comprada / vendida

type CfgPosicao = { corAlvo: string; corStop: string; transparencia: number; conta: number; riscoPct: number; resultado: boolean; sempre: boolean }
const CAMPOS_POSICAO: Campo[] = [
  { tipo: 'cor', chave: 'corAlvo', nome: 'Cor do alvo' }, { tipo: 'cor', chave: 'corStop', nome: 'Cor do stop' },
  { tipo: 'numero', chave: 'transparencia', nome: 'Transparência (%)', min: 0, max: 100, passo: 5 },
  { tipo: 'secao', nome: 'Tamanho' },
  { tipo: 'numero', chave: 'conta', nome: 'Conta (USD)', min: 0, passo: 100 },
  { tipo: 'numero', chave: 'riscoPct', nome: 'Risco por operação (%)', min: 0.01, max: 100, passo: 0.1 },
  { tipo: 'bool', chave: 'resultado', nome: 'Mostrar o que aconteceu depois (alvo ou stop)' },
  { tipo: 'bool', chave: 'sempre', nome: 'Mostrar os números sempre (não só selecionada)' },
]

/** pontos: entrada, alvo e stop; o fim da caixa no tempo vem do alvo */
function geoPosicao(px: Px[]) {
  const [e, a, s] = px
  return { x0: e.x, x1: Math.max(a.x, e.x + 10), ye: e.y, ya: a.y, ys: s.y }
}

/** com as velas depois da entrada: o que veio primeiro, alvo ou stop (na mesma vela conta o stop, por cautela) */
function desfecho(d: Desenho, g: Geo, comprada: boolean) {
  const [e, a, s] = d.pts
  const velas = g.velas(e.t + 1, Math.max(a.t, e.t))
  for (const k of velas) {
    const bateuStop = comprada ? k.l <= s.p : k.h >= s.p
    const bateuAlvo = comprada ? k.h >= a.p : k.l <= a.p
    if (bateuStop) return { t: k.t, preco: s.p, quem: 'stop' as const }
    if (bateuAlvo) return { t: k.t, preco: a.p, quem: 'alvo' as const }
  }
  const ult = velas[velas.length - 1]
  return ult ? { t: ult.t, preco: ult.c, quem: 'aberta' as const } : null
}

function ferramentaPosicao(tipo: string, nome: string, comprada: boolean, icone: string): Ferramenta {
  return {
    tipo, nome, grupo: 'medidas', pontos: 1, icone, campos: CAMPOS_POSICAO,
    criar: (pt, passo) => {
      const s = comprada ? 1 : -1
      return [pt, { t: pt.t + passo * 30, p: pt.p * (1 + s * 0.02) }, { t: pt.t + passo * 30, p: pt.p * (1 - s * 0.01) }]
    },
    padrao: (): CfgPosicao => ({ corAlvo: VERDE, corStop: VERMELHO, transparencia: 80, conta: 1000, riscoPct: 1, resultado: true, sempre: false }),
    cor: acesso<string>('corAlvo'),
    alcas: (_d, px) => {
      if (px.length < 3) return px
      const G = geoPosicao(px)
      return [px[0], { x: G.x1, y: G.ya }, { x: G.x1, y: G.ys }]
    },
    desenhar(ctx, d, px, g) {
      if (px.length < 3) return
      const c = d.cfg as CfgPosicao, G = geoPosicao(px)
      const [e, a, s] = d.pts
      const al = (100 - c.transparencia) / 100
      ctx.fillStyle = comAlfa(c.corAlvo, al); ctx.fillRect(G.x0, Math.min(G.ye, G.ya), G.x1 - G.x0, Math.abs(G.ya - G.ye))
      ctx.fillStyle = comAlfa(c.corStop, al); ctx.fillRect(G.x0, Math.min(G.ye, G.ys), G.x1 - G.x0, Math.abs(G.ys - G.ye))
      tracar(ctx, { cor: '#787b86', largura: 1, estilo: 'solida' }); linhaReta(ctx, { x: G.x0, y: G.ye }, { x: G.x1, y: G.ye }); ctx.setLineDash([])
      const risco = Math.abs(e.p - s.p), ganho = Math.abs(a.p - e.p)
      const rr = risco ? ganho / risco : 0
      const qtd = risco ? (c.conta * c.riscoPct / 100) / risco : 0
      // o que aconteceu depois: linha da entrada até o preço onde bateu (ou o último fechamento)
      let fim: ReturnType<typeof desfecho> = null
      if (c.resultado) {
        fim = desfecho(d, g, comprada)
        const xf = fim ? g.x(fim.t) : null, yf = fim ? g.y(fim.preco) : null
        if (fim && xf !== null && yf !== null) {
          tracar(ctx, { cor: fim.quem === 'stop' ? c.corStop : fim.quem === 'alvo' ? c.corAlvo : '#e8ecf2', largura: 1, estilo: 'tracejada' })
          linhaReta(ctx, { x: G.x0, y: G.ye }, { x: xf, y: yf }); ctx.setLineDash([])
        }
      }
      if (!(c.sempre || g.selecionado)) return
      const s1 = comprada ? 1 : -1
      const fonte = { fonte: "11.5px 'DM Mono', monospace", tamanho: 11.5, cor: '#ffffff', W: g.W, H: g.H }
      caixaComTexto(ctx, [`Alvo ${g.formatar(a.p)} (${pct(s1 * (a.p - e.p) / e.p)}) · +${fmtNum(qtd * ganho)} USD`], { x: (G.x0 + G.x1) / 2, y: G.ya + (G.ya < G.ye ? -4 : 4) }, { ...fonte, fundo: c.corAlvo, ancora: G.ya < G.ye ? 'baixo' : 'cima' })
      caixaComTexto(ctx, [`Stop ${g.formatar(s.p)} (${pct(s1 * (s.p - e.p) / e.p)}) · −${fmtNum(qtd * risco)} USD`], { x: (G.x0 + G.x1) / 2, y: G.ys + (G.ys > G.ye ? 4 : -4) }, { ...fonte, fundo: c.corStop, ancora: G.ys > G.ye ? 'cima' : 'baixo' })
      const linhas = [`${comprada ? 'Comprado' : 'Vendido'} em ${g.formatar(e.p)}`, `Risco/retorno ${fmtNum(rr)} · qtd ${fmtNum(qtd, qtd < 1 ? 4 : 2)}`]
      if (fim) linhas.push(fim.quem === 'alvo' ? 'bateu o alvo primeiro' : fim.quem === 'stop' ? 'bateu o stop primeiro' : `aberta: ${pct(s1 * (fim.preco - e.p) / e.p)} agora`)
      // o resumo fica à direita da caixa, para não cobrir a alça da entrada
      caixaComTexto(ctx, linhas, { x: G.x1 + 10, y: G.ye }, { ...fonte, fundo: 'rgba(19,23,34,0.92)', borda: 'rgba(255,255,255,0.15)', ancora: 'esquerda' })
    },
    acertar(x, y, _d, px) {
      if (px.length < 3) return false
      const G = geoPosicao(px)
      const y0 = Math.min(G.ya, G.ys, G.ye), y1 = Math.max(G.ya, G.ys, G.ye)
      return x >= G.x0 - 3 && x <= G.x1 + 3 && y >= y0 - 3 && y <= y1 + 3 || pertoSegmento(x, y, { x: G.x0, y: G.ye }, { x: G.x1, y: G.ye })
    },
    resumo: (d, f) => `${f(d.pts[0].p)} · alvo ${f(d.pts[1]?.p ?? d.pts[0].p)} · stop ${f(d.pts[2]?.p ?? d.pts[0].p)}`,
  }
}
const comprada = ferramentaPosicao('posicao_comprada', 'Posição comprada', true, 'M2 2 H16 V9 H2 Z M2 9 H16 V15 H2 Z')
const vendida = ferramentaPosicao('posicao_vendida', 'Posição vendida', false, 'M2 3 H16 V9 H2 Z M2 9 H16 V16 H2 Z M5 6 L13 6')

export const ELLIOTT: Ferramenta[] = [impulso, correcao, trianguloE, dupla, tripla]
export const PADROES: Ferramenta[] = [xabcd, cypher, abcd, trianguloPadrao, oco, tresDrives]
export const POSICOES: Ferramenta[] = [comprada, vendida]
