/**
 * Medidas (faixa de preço, faixa de data, data e preço), formas (retângulo, retângulo girado, caminho, círculo, elipse,
 * polilinha, triângulo, arco, curva, curva dupla) e setas (marcador de seta, seta para cima e para baixo), no molde
 * das ferramentas da TradingView.
 */
import { copiar } from '../../lib/fibo'
import { TEXTO_PADRAO, type Desenho, type Linha, type Texto } from '../../lib/desenhos'
import {
  acesso, caixaComTexto, CAMPO_FUNDO, CAMPO_LINHA, comAlfa, corFundo, dentroPoligono, duracao, fonteDe, fundoPadrao,
  linhaReta, pct, PONTAS, pertoPolilinha, poligono, resumoPrecos, seta, textoNaCaixa, tracar, volumeCurto,
  type Campo, type Ferramenta, type Fundo, type Geo, type Px,
} from './ferramentasBase'

const AZUL = '#2962ff', VERMELHO = '#f23645', VERDE = '#089981'

// ---------------------------------------------------------------- medidas

type CfgMedida = { corAlta: string; corBaixa: string; transparencia: number; volume: boolean }
const MEDIDA_TV: CfgMedida = { corAlta: AZUL, corBaixa: VERMELHO, transparencia: 80, volume: true }
const CAMPOS_MEDIDA: Campo[] = [
  { tipo: 'cor', chave: 'corAlta', nome: 'Cor quando sobe' }, { tipo: 'cor', chave: 'corBaixa', nome: 'Cor quando cai' },
  { tipo: 'numero', chave: 'transparencia', nome: 'Transparência do fundo (%)', min: 0, max: 100, passo: 5 },
  { tipo: 'bool', chave: 'volume', nome: 'Volume da faixa' },
]

function medida(ctx: CanvasRenderingContext2D, d: Desenho, px: Px[], g: Geo, preco: boolean, tempo: boolean) {
  if (px.length < 2) return
  const c = d.cfg as CfgMedida
  const [a, b] = d.pts
  const sobe = preco ? b.p >= a.p : b.t >= a.t
  const cor = sobe ? c.corAlta : c.corBaixa
  const [p0, p1] = px
  ctx.fillStyle = comAlfa(cor, (100 - c.transparencia) / 100)
  ctx.fillRect(Math.min(p0.x, p1.x), Math.min(p0.y, p1.y), Math.abs(p1.x - p0.x), Math.abs(p1.y - p0.y))
  ctx.strokeStyle = cor; ctx.lineWidth = 1; ctx.setLineDash([])
  const mx = (p0.x + p1.x) / 2, my = (p0.y + p1.y) / 2
  if (preco) { linhaReta(ctx, { x: mx, y: p0.y }, { x: mx, y: p1.y }); seta(ctx, { x: mx, y: p1.y }, { x: mx, y: p0.y }, 1) }
  if (tempo) { linhaReta(ctx, { x: p0.x, y: my }, { x: p1.x, y: my }); seta(ctx, { x: p1.x, y: my }, { x: p0.x, y: my }, 1) }
  const linhas: string[] = []
  if (preco) { const dp = b.p - a.p; linhas.push(`${dp >= 0 ? '+' : ''}${g.formatar(dp)} (${a.p ? pct(dp / a.p) : '—'})`) }
  if (tempo) linhas.push(`${Math.round((b.t - a.t) / g.passo)} barras, ${duracao(b.t - a.t)}`)
  if (tempo && c.volume) {
    const v = g.velas(Math.min(a.t, b.t), Math.max(a.t, b.t)).reduce((s, k) => s + k.v, 0)
    linhas.push(`volume ${volumeCurto(v)}`)
  }
  const embaixo = preco ? p1.y >= p0.y : true
  caixaComTexto(ctx, linhas, { x: mx, y: preco ? p1.y + (embaixo ? 8 : -8) : Math.max(p0.y, p1.y) + 8 }, {
    fonte: "12px 'DM Mono', monospace", tamanho: 12, cor: '#ffffff', fundo: cor, ancora: embaixo ? 'cima' : 'baixo', W: g.W, H: g.H,
  })
}
const dentroRet = (x: number, y: number, px: Px[]) => px.length >= 2 && x >= Math.min(px[0].x, px[1].x) - 3 && x <= Math.max(px[0].x, px[1].x) + 3
  && y >= Math.min(px[0].y, px[1].y) - 3 && y <= Math.max(px[0].y, px[1].y) + 3

function ferramentaMedida(tipo: string, nome: string, icone: string, preco: boolean, tempo: boolean): Ferramenta {
  return {
    tipo, nome, grupo: 'medidas', pontos: 2, icone, campos: CAMPOS_MEDIDA,
    padrao: () => copiar(MEDIDA_TV),
    cor: acesso<string>('corAlta'),
    desenhar: (ctx, d, px, g) => medida(ctx, d, px, g, preco, tempo),
    acertar: (x, y, _d, px) => dentroRet(x, y, px),
    resumo: resumoPrecos,
  }
}
const faixaPreco = ferramentaMedida('faixa_preco', 'Faixa de preço', 'M9 2 V16 M6 5 L9 2 L12 5 M6 13 L9 16 L12 13 M3 2 H15 M3 16 H15', true, false)
const faixaData = ferramentaMedida('faixa_data', 'Faixa de data', 'M2 9 H16 M5 6 L2 9 L5 12 M13 6 L16 9 L13 12 M2 3 V15 M16 3 V15', false, true)
const faixaDataPreco = ferramentaMedida('faixa_data_preco', 'Faixa de data e preço', 'M2 2 H16 V16 H2 Z M9 4 V14 M4 9 H14', true, true)

// ---------------------------------------------------------------- formas

type CfgForma = { borda: Linha; fundo: Fundo; texto: Texto; estEsq: boolean; estDir: boolean; meio: boolean }
const FORMA_TV = (cor = AZUL): CfgForma => ({
  borda: { cor, largura: 1, estilo: 'solida' }, fundo: fundoPadrao(cor, 80), texto: { ...TEXTO_PADRAO, v: 'meio' },
  estEsq: false, estDir: false, meio: false,
})
const CAMPOS_FORMA: Campo[] = [CAMPO_LINHA('Borda', 'borda'), CAMPO_FUNDO()]
const formaBase = { linha: acesso<Linha>('borda'), fundo: acesso<string>('fundo.cor'), texto: true, resumo: resumoPrecos }

/** fundo da forma conta como "em cima" quando está ligado ou o desenho está selecionado */
const pegaPorDentro = (c: CfgForma, g: Geo) => (c.fundo.ligado && c.fundo.transparencia < 100) || g.selecionado

const retangulo: Ferramenta = {
  ...formaBase, tipo: 'retangulo', nome: 'Retângulo', grupo: 'formas', atalho: 'Shift+R', pontos: 2,
  campos: [...CAMPOS_FORMA, { tipo: 'bool', chave: 'meio', nome: 'Linha do meio' }, { tipo: 'bool', chave: 'estEsq', nome: 'Estender à esquerda' }, { tipo: 'bool', chave: 'estDir', nome: 'Estender à direita' }],
  icone: 'M2 4 H16 V14 H2 Z',
  padrao: () => FORMA_TV(),
  desenhar(ctx, d, px, g) {
    if (px.length < 2) return
    const c = d.cfg as CfgForma
    const x0 = c.estEsq ? 0 : Math.min(px[0].x, px[1].x), x1 = c.estDir ? g.W : Math.max(px[0].x, px[1].x)
    const y0 = Math.min(px[0].y, px[1].y), y1 = Math.max(px[0].y, px[1].y)
    poligono(ctx, [{ x: x0, y: y0 }, { x: x1, y: y0 }, { x: x1, y: y1 }, { x: x0, y: y1 }], c.fundo, c.borda)
    if (c.meio) { tracar(ctx, { ...c.borda, estilo: 'tracejada' }); linhaReta(ctx, { x: x0, y: (y0 + y1) / 2 }, { x: x1, y: (y0 + y1) / 2 }); ctx.setLineDash([]) }
    textoNaCaixa(ctx, c.texto, x0, y0, x1, y1)
  },
  acertar(x, y, d, px, g) {
    if (px.length < 2) return false
    const c = d.cfg as CfgForma
    const x0 = c.estEsq ? 0 : Math.min(px[0].x, px[1].x), x1 = c.estDir ? g.W : Math.max(px[0].x, px[1].x)
    const y0 = Math.min(px[0].y, px[1].y), y1 = Math.max(px[0].y, px[1].y)
    const cantos = [{ x: x0, y: y0 }, { x: x1, y: y0 }, { x: x1, y: y1 }, { x: x0, y: y1 }]
    return pertoPolilinha(x, y, cantos, true) || (pegaPorDentro(c, g) && x >= x0 && x <= x1 && y >= y0 && y <= y1)
  },
}

/** os 4 cantos do retângulo girado: o lado do ponto 1 ao 2 e a largura até o ponto 3 */
function cantosGirado(px: Px[]): Px[] {
  const [a, b, c] = px
  const dx = b.x - a.x, dy = b.y - a.y, L = Math.hypot(dx, dy) || 1
  const nx = -dy / L, ny = dx / L
  const k = (c.x - a.x) * nx + (c.y - a.y) * ny
  return [a, b, { x: b.x + nx * k, y: b.y + ny * k }, { x: a.x + nx * k, y: a.y + ny * k }]
}
const retanguloGirado: Ferramenta = {
  ...formaBase, tipo: 'retangulo_girado', nome: 'Retângulo girado', grupo: 'formas', pontos: 3, campos: CAMPOS_FORMA, texto: false,
  icone: 'M5 2 L16 7 L13 16 L2 11 Z',
  padrao: () => FORMA_TV(),
  desenhar(ctx, d, px) { if (px.length >= 3) poligono(ctx, cantosGirado(px), (d.cfg as CfgForma).fundo, (d.cfg as CfgForma).borda) },
  acertar(x, y, d, px, g) {
    if (px.length < 3) return false
    const q = cantosGirado(px)
    return pertoPolilinha(x, y, q, true) || (pegaPorDentro(d.cfg as CfgForma, g) && dentroPoligono(x, y, q))
  },
}

const triangulo: Ferramenta = {
  ...formaBase, tipo: 'triangulo', nome: 'Triângulo', grupo: 'formas', pontos: 3, campos: CAMPOS_FORMA, texto: false,
  icone: 'M9 2 L16 15 H2 Z',
  padrao: () => FORMA_TV('#9c27b0'),
  desenhar(ctx, d, px) { if (px.length >= 3) poligono(ctx, px, (d.cfg as CfgForma).fundo, (d.cfg as CfgForma).borda) },
  acertar: (x, y, d, px, g) => px.length >= 3 && (pertoPolilinha(x, y, px, true) || (pegaPorDentro(d.cfg as CfgForma, g) && dentroPoligono(x, y, px))),
}

const circulo: Ferramenta = {
  ...formaBase, tipo: 'circulo', nome: 'Círculo', grupo: 'formas', pontos: 2, campos: CAMPOS_FORMA,
  icone: 'M9 2 a7 7 0 1 0 0.01 0',
  padrao: () => FORMA_TV('#ff9800'),
  desenhar(ctx, d, px) {
    if (px.length < 2) return
    const c = d.cfg as CfgForma, r = Math.hypot(px[1].x - px[0].x, px[1].y - px[0].y)
    ctx.beginPath(); ctx.arc(px[0].x, px[0].y, r, 0, Math.PI * 2)
    if (c.fundo.ligado) { ctx.fillStyle = corFundo(c.fundo); ctx.fill() }
    tracar(ctx, c.borda); ctx.stroke(); ctx.setLineDash([])
    textoNaCaixa(ctx, c.texto, px[0].x - r, px[0].y - r, px[0].x + r, px[0].y + r)
  },
  acertar(x, y, d, px, g) {
    if (px.length < 2) return false
    const r = Math.hypot(px[1].x - px[0].x, px[1].y - px[0].y), dist = Math.hypot(x - px[0].x, y - px[0].y)
    return Math.abs(dist - r) <= 5 || (pegaPorDentro(d.cfg as CfgForma, g) && dist <= r)
  },
}

const elipse: Ferramenta = {
  ...formaBase, tipo: 'elipse', nome: 'Elipse', grupo: 'formas', pontos: 2, campos: CAMPOS_FORMA,
  icone: 'M9 4 a7 5 0 1 0 0.01 0',
  padrao: () => FORMA_TV(VERDE),
  desenhar(ctx, d, px) {
    if (px.length < 2) return
    const c = d.cfg as CfgForma
    const cx = (px[0].x + px[1].x) / 2, cy = (px[0].y + px[1].y) / 2, rx = Math.abs(px[1].x - px[0].x) / 2, ry = Math.abs(px[1].y - px[0].y) / 2
    ctx.beginPath(); ctx.ellipse(cx, cy, Math.max(rx, 0.5), Math.max(ry, 0.5), 0, 0, Math.PI * 2)
    if (c.fundo.ligado) { ctx.fillStyle = corFundo(c.fundo); ctx.fill() }
    tracar(ctx, c.borda); ctx.stroke(); ctx.setLineDash([])
    textoNaCaixa(ctx, c.texto, px[0].x, px[0].y, px[1].x, px[1].y)
  },
  acertar(x, y, d, px, g) {
    if (px.length < 2) return false
    const cx = (px[0].x + px[1].x) / 2, cy = (px[0].y + px[1].y) / 2, rx = Math.max(Math.abs(px[1].x - px[0].x) / 2, 1), ry = Math.max(Math.abs(px[1].y - px[0].y) / 2, 1)
    const k = Math.hypot((x - cx) / rx, (y - cy) / ry)
    return Math.abs(k - 1) * Math.min(rx, ry) <= 5 || (pegaPorDentro(d.cfg as CfgForma, g) && k <= 1)
  },
}

const polilinha: Ferramenta = {
  ...formaBase, tipo: 'polilinha', nome: 'Polilinha', grupo: 'formas', pontos: 0, campos: CAMPOS_FORMA, texto: false,
  icone: 'M2 14 L6 4 L11 11 L16 3 L14 16 Z',
  padrao: () => FORMA_TV('#00bcd4'),
  desenhar(ctx, d, px) { poligono(ctx, px, (d.cfg as CfgForma).fundo, (d.cfg as CfgForma).borda, px.length > 2) },
  acertar: (x, y, d, px, g) => pertoPolilinha(x, y, px, true) || (px.length > 2 && pegaPorDentro(d.cfg as CfgForma, g) && dentroPoligono(x, y, px)),
}

type CfgCaminho = { linha: Linha; pontaEsq: 'normal' | 'seta'; pontaDir: 'normal' | 'seta' }
const caminho: Ferramenta = {
  tipo: 'caminho', nome: 'Caminho', grupo: 'formas', pontos: 0, campos: [CAMPO_LINHA(), ...PONTAS],
  icone: 'M2 15 L7 6 L11 12 L16 3 M12 3 H16 V7',
  padrao: () => ({ linha: { cor: AZUL, largura: 2, estilo: 'solida' }, pontaEsq: 'normal', pontaDir: 'seta' } as CfgCaminho),
  linha: acesso<Linha>('linha'),
  desenhar(ctx, d, px) {
    const c = d.cfg as CfgCaminho
    poligono(ctx, px, null, c.linha, false)
    tracar(ctx, c.linha)
    const n = px.length
    if (n >= 2 && c.pontaDir === 'seta') seta(ctx, px[n - 1], px[n - 2], c.linha.largura)
    if (n >= 2 && c.pontaEsq === 'seta') seta(ctx, px[0], px[1], c.linha.largura)
    ctx.setLineDash([])
  },
  acertar: (x, y, _d, px) => pertoPolilinha(x, y, px),
  resumo: (d) => `${d.pts.length} pontos`,
}

// curvas: a quadrática passa pelo ponto 3 (o controle fica a 2× do meio); a dupla é uma cúbica em S
function amostrar(f: (u: number) => Px, n = 32): Px[] { return Array.from({ length: n + 1 }, (_, i) => f(i / n)) }
const quad = (a: Px, c: Px, b: Px) => (u: number): Px => ({ x: (1 - u) ** 2 * a.x + 2 * (1 - u) * u * c.x + u * u * b.x, y: (1 - u) ** 2 * a.y + 2 * (1 - u) * u * c.y + u * u * b.y })
const cub = (a: Px, c1: Px, c2: Px, b: Px) => (u: number): Px => ({
  x: (1 - u) ** 3 * a.x + 3 * (1 - u) ** 2 * u * c1.x + 3 * (1 - u) * u * u * c2.x + u ** 3 * b.x,
  y: (1 - u) ** 3 * a.y + 3 * (1 - u) ** 2 * u * c1.y + 3 * (1 - u) * u * u * c2.y + u ** 3 * b.y,
})
const controlePor = (a: Px, b: Px, p: Px): Px => ({ x: 2 * p.x - (a.x + b.x) / 2, y: 2 * p.y - (a.y + b.y) / 2 })
function pontosCurva(tipo: string, px: Px[]): Px[] {
  if (px.length < 3) return px
  const [a, b, p] = px
  if (tipo === 'curva_dupla') {
    const m = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
    return amostrar(cub(a, p, { x: 2 * m.x - p.x, y: 2 * m.y - p.y }, b))
  }
  return amostrar(quad(a, controlePor(a, b, p), b))
}

const arco: Ferramenta = {
  ...formaBase, tipo: 'arco', nome: 'Arco', grupo: 'formas', pontos: 3, campos: CAMPOS_FORMA, texto: false,
  icone: 'M2 14 Q9 -2 16 14 Z',
  padrao: () => FORMA_TV('#e91e63'),
  desenhar(ctx, d, px) { if (px.length >= 3) poligono(ctx, pontosCurva('arco', px), (d.cfg as CfgForma).fundo, (d.cfg as CfgForma).borda) },
  acertar(x, y, d, px, g) {
    if (px.length < 3) return false
    const q = pontosCurva('arco', px)
    return pertoPolilinha(x, y, q, true) || (pegaPorDentro(d.cfg as CfgForma, g) && dentroPoligono(x, y, q))
  },
}

function ferramentaCurva(tipo: string, nome: string, icone: string): Ferramenta {
  return {
    tipo, nome, grupo: 'formas', pontos: 3, campos: [CAMPO_LINHA(), ...PONTAS], icone,
    padrao: () => ({ linha: { cor: AZUL, largura: 2, estilo: 'solida' }, pontaEsq: 'normal', pontaDir: 'normal' } as CfgCaminho),
    linha: acesso<Linha>('linha'),
    desenhar(ctx, d, px) {
      const c = d.cfg as CfgCaminho
      const q = px.length >= 3 ? pontosCurva(tipo, px) : px
      poligono(ctx, q, null, c.linha, false)
      tracar(ctx, c.linha)
      if (q.length >= 2 && c.pontaDir === 'seta') seta(ctx, q[q.length - 1], q[q.length - 2], c.linha.largura)
      if (q.length >= 2 && c.pontaEsq === 'seta') seta(ctx, q[0], q[1], c.linha.largura)
      ctx.setLineDash([])
    },
    acertar: (x, y, _d, px) => pertoPolilinha(x, y, px.length >= 3 ? pontosCurva(tipo, px) : px),
    resumo: resumoPrecos,
  }
}
const curva = ferramentaCurva('curva', 'Curva', 'M2 15 Q9 -3 16 15')
const curvaDupla = ferramentaCurva('curva_dupla', 'Curva dupla', 'M2 14 C6 0 12 18 16 4')

// ---------------------------------------------------------------- setas

type CfgMarca = { cor: string; texto: Texto }
const MARCA_TV = (cor: string): CfgMarca => ({ cor, texto: { ...TEXTO_PADRAO, texto: '', cor, h: 'centro', v: 'baixo' } })

/** marcador de seta: corpo grosso do ponto 1 (cauda) ao 2 (ponta) */
function setaGrossa(a: Px, b: Px): Px[] {
  const dx = b.x - a.x, dy = b.y - a.y, L = Math.hypot(dx, dy) || 1
  const ux = dx / L, uy = dy / L, nx = -uy, ny = ux
  const cab = Math.min(26, L * 0.5), meia = 6, asa = 13
  const base = { x: b.x - ux * cab, y: b.y - uy * cab }
  return [
    { x: a.x + nx * meia, y: a.y + ny * meia }, { x: base.x + nx * meia, y: base.y + ny * meia }, { x: base.x + nx * asa, y: base.y + ny * asa },
    b, { x: base.x - nx * asa, y: base.y - ny * asa }, { x: base.x - nx * meia, y: base.y - ny * meia }, { x: a.x - nx * meia, y: a.y - ny * meia },
  ]
}
const marcadorSeta: Ferramenta = {
  tipo: 'marcador_seta', nome: 'Marcador de seta', grupo: 'setas', pontos: 2, texto: true,
  campos: [{ tipo: 'cor', chave: 'cor', nome: 'Cor' }],
  icone: 'M2 12 L11 5 L10 2 L16 3 L15 9 L13 7 L4 14 Z',
  padrao: () => ({ ...MARCA_TV('#ff9800'), texto: { ...TEXTO_PADRAO, cor: '#ff9800', v: 'meio' } }),
  cor: acesso<string>('cor'),
  desenhar(ctx, d, px) {
    if (px.length < 2) return
    const c = d.cfg as CfgMarca
    poligono(ctx, setaGrossa(px[0], px[1]), { ligado: true, cor: c.cor, transparencia: 0 }, null)
    const t = c.texto
    if (t.texto.trim()) {
      ctx.font = fonteDe(t); ctx.fillStyle = t.cor; ctx.textBaseline = 'middle'
      const esquerda = px[0].x <= px[1].x
      ctx.textAlign = esquerda ? 'right' : 'left'
      ctx.fillText(t.texto, px[0].x + (esquerda ? -8 : 8), px[0].y)
    }
  },
  acertar: (x, y, _d, px) => px.length >= 2 && dentroPoligono(x, y, setaGrossa(px[0], px[1])),
  resumo: resumoPrecos,
}

function marcaSeta(tipo: string, nome: string, icone: string, paraCima: boolean): Ferramenta {
  const forma = (p: Px): Px[] => {
    const s = paraCima ? 1 : -1, y0 = p.y + s * 2
    return [{ x: p.x, y: y0 }, { x: p.x + 9, y: y0 + s * 11 }, { x: p.x + 4, y: y0 + s * 11 }, { x: p.x + 4, y: y0 + s * 22 },
      { x: p.x - 4, y: y0 + s * 22 }, { x: p.x - 4, y: y0 + s * 11 }, { x: p.x - 9, y: y0 + s * 11 }]
  }
  return {
    tipo, nome, grupo: 'setas', pontos: 1, texto: true, icone,
    campos: [{ tipo: 'cor', chave: 'cor', nome: 'Cor' }],
    padrao: () => MARCA_TV(paraCima ? VERDE : VERMELHO),
    cor: acesso<string>('cor'),
    desenhar(ctx, d, px) {
      const c = d.cfg as CfgMarca
      poligono(ctx, forma(px[0]), { ligado: true, cor: c.cor, transparencia: 0 }, null)
      const t = c.texto
      if (t.texto.trim()) {
        ctx.font = fonteDe(t); ctx.fillStyle = t.cor; ctx.textAlign = 'center'
        ctx.textBaseline = paraCima ? 'top' : 'bottom'
        ctx.fillText(t.texto, px[0].x, px[0].y + (paraCima ? 28 : -28))
      }
    },
    acertar: (x, y, _d, px) => dentroPoligono(x, y, forma(px[0])),
    resumo: (d, f) => f(d.pts[0].p),
  }
}
const setaCima = marcaSeta('seta_cima', 'Seta para cima', 'M9 2 L15 9 H11 V16 H7 V9 H3 Z', true)
const setaBaixo = marcaSeta('seta_baixo', 'Seta para baixo', 'M9 16 L15 9 H11 V2 H7 V9 H3 Z', false)

export const MEDIDAS: Ferramenta[] = [faixaPreco, faixaData, faixaDataPreco]
export const FORMAS: Ferramenta[] = [retangulo, retanguloGirado, caminho, circulo, elipse, polilinha, triangulo, arco, curva, curvaDupla]
export const SETAS: Ferramenta[] = [marcadorSeta, setaCima, setaBaixo]
