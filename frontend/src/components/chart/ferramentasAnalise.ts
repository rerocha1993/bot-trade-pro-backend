/**
 * Etapa 5 das ferramentas da TradingView: as que usam as velas (VWAP ancorada, perfil de volume de faixa fixa e
 * ancorado, previsão, padrão de barras, ghost feed), os ciclos (linhas cíclicas, ciclos de tempo, senoide), a projeção,
 * o desenho à mão livre (pincel e marca-texto) e o que é mais de anotação (ícone, tabela, imagem, nota ancorada).
 */
import { TEXTO_PADRAO, type Desenho, type Linha, type Texto } from '../../lib/desenhos'
import {
  acesso, CAIXAS, caixaComTexto, comAlfa, dentroCaixas, dentroPoligono, duracao, fonteDe, linhaReta, pct, PERTO_PX,
  pertoPolilinha, pertoSegmento, poligono, seta, tracar, type Campo, type Ferramenta, type Fundo, type Geo, type Px, type VelaG,
} from './ferramentasBase'

const AZUL = '#2962ff', VERDE = '#089981', VERMELHO = '#f23645', LARANJA = '#ff9800'
const fmtNum = (v: number, casas = 2) => v.toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas })
const FIM = 1e12

// ---------------------------------------------------------------- VWAP ancorada

type CfgVwap = { linha: Linha; fonte: 'hlc3' | 'hl2' | 'close' | 'ohlc4'; b1: boolean; b2: boolean; b3: boolean; linhaBandas: Linha; fundo: Fundo }
const precoFonte = (k: VelaG, f: CfgVwap['fonte']) => (f === 'close' ? k.c : f === 'hl2' ? (k.h + k.l) / 2 : f === 'ohlc4' ? (k.o + k.h + k.l + k.c) / 4 : (k.h + k.l + k.c) / 3)

/** VWAP da âncora em diante e o desvio padrão ponderado pelo volume (para as bandas) */
function serieVwap(c: CfgVwap, velas: VelaG[]) {
  let pv = 0, v = 0, p2v = 0
  return velas.map((k) => {
    const p = precoFonte(k, c.fonte)
    pv += p * k.v; v += k.v; p2v += p * p * k.v
    const m = v ? pv / v : p
    return { t: k.t, m, sd: v ? Math.sqrt(Math.max(0, p2v / v - m * m)) : 0 }
  })
}
const vwap: Ferramenta = {
  tipo: 'vwap_ancorada', nome: 'VWAP ancorada', grupo: 'volume', pontos: 1, soTempo: true,
  campos: [
    { tipo: 'linha', chave: 'linha', nome: 'VWAP' },
    { tipo: 'escolha', chave: 'fonte', nome: 'Preço', opcoes: [['hlc3', '(máx+mín+fech)/3'], ['hl2', '(máx+mín)/2'], ['ohlc4', '(abe+máx+mín+fech)/4'], ['close', 'Fechamento']] },
    { tipo: 'secao', nome: 'Bandas de desvio padrão' },
    { tipo: 'bool', chave: 'b1', nome: '±1' }, { tipo: 'bool', chave: 'b2', nome: '±2' }, { tipo: 'bool', chave: 'b3', nome: '±3' },
    { tipo: 'linha', chave: 'linhaBandas', nome: 'Linha das bandas' }, { tipo: 'fundo', chave: 'fundo', nome: 'Fundo entre as bandas' },
  ],
  icone: 'M2 14 Q6 4 9 9 T16 4 M2 16 V2',
  padrao: (): CfgVwap => ({
    linha: { cor: AZUL, largura: 2, estilo: 'solida' }, fonte: 'hlc3', b1: true, b2: false, b3: false,
    linhaBandas: { cor: VERDE, largura: 1, estilo: 'solida' }, fundo: { ligado: true, cor: VERDE, transparencia: 92 },
  }),
  linha: acesso<Linha>('linha'),
  desenhar(ctx, d, px, g) {
    const c = d.cfg as CfgVwap
    const S = serieVwap(c, g.velas(d.pts[0].t, FIM))
    const pt = (t: number, p: number) => { const x = g.x(t), y = g.y(p); return x === null || y === null ? null : { x, y } }
    const curva = (k: number) => S.map((s) => pt(s.t, s.m + k * s.sd)).filter((p): p is Px => p !== null)
    const bandas = [c.b1 && 1, c.b2 && 2, c.b3 && 3].filter(Boolean) as number[]
    const maior = Math.max(0, ...bandas)
    if (maior && c.fundo.ligado) poligono(ctx, [...curva(maior), ...curva(-maior).reverse()], c.fundo, null)
    for (const k of bandas) for (const s of [1, -1]) poligono(ctx, curva(k * s), null, c.linhaBandas, false)
    poligono(ctx, curva(0), null, c.linha, false)
    // a âncora: uma marca na vela
    ctx.fillStyle = c.linha.cor; ctx.beginPath(); ctx.arc(px[0].x, px[0].y, 3, 0, Math.PI * 2); ctx.fill()
    const ult = S[S.length - 1]
    if (ult) {
      const p = pt(ult.t, ult.m)
      if (p) caixaComTexto(ctx, [`VWAP ${g.formatar(ult.m)}`], { x: p.x + 6, y: p.y }, { fonte: "11px 'DM Mono', monospace", tamanho: 11, cor: '#ffffff', fundo: c.linha.cor, ancora: 'esquerda', W: g.W, H: g.H })
    }
  },
  acertar(x, y, d, _px, g) {
    const S = serieVwap(d.cfg as CfgVwap, g.velas(d.pts[0].t, FIM))
    const pts = S.map((s) => ({ x: g.x(s.t), y: g.y(s.m) })).filter((p): p is Px => p.x !== null && p.y !== null)
    return pertoPolilinha(x, y, pts)
  },
  alcas(d, px, g) {
    const k = g.velas(d.pts[0].t, FIM)[0]
    const y = k ? g.y(precoFonte(k, (d.cfg as CfgVwap).fonte)) : null
    return [{ x: px[0].x, y: y ?? px[0].y }]
  },
  resumo: (d) => `desde ${new Date(d.pts[0].t * 1000).toISOString().slice(0, 16).replace('T', ' ')} UTC`,
}

// ---------------------------------------------------------------- perfil de volume

type CfgPerfil = {
  linhas: number; largura: number; lado: 'esquerda' | 'direita'; corCompra: string; corVenda: string; transparencia: number
  poc: Linha; va: boolean; vaPct: number; linhaVa: Linha; caixa: boolean
}
const CAMPOS_PERFIL: Campo[] = [
  { tipo: 'numero', chave: 'linhas', nome: 'Número de linhas', min: 6, max: 200 },
  { tipo: 'numero', chave: 'largura', nome: 'Largura do histograma (% da faixa)', min: 5, max: 100, passo: 5 },
  { tipo: 'escolha', chave: 'lado', nome: 'Lado', opcoes: [['esquerda', 'Esquerda'], ['direita', 'Direita']] },
  { tipo: 'cor', chave: 'corCompra', nome: 'Volume de alta' }, { tipo: 'cor', chave: 'corVenda', nome: 'Volume de baixa' },
  { tipo: 'numero', chave: 'transparencia', nome: 'Transparência (%)', min: 0, max: 100, passo: 5 },
  { tipo: 'linha', chave: 'poc', nome: 'POC' },
  { tipo: 'bool', chave: 'va', nome: 'Área de valor (VAH e VAL)' }, { tipo: 'numero', chave: 'vaPct', nome: 'Área de valor (%)', min: 10, max: 99 },
  { tipo: 'linha', chave: 'linhaVa', nome: 'Linha de VAH e VAL' }, { tipo: 'bool', chave: 'caixa', nome: 'Fundo da faixa' },
]
const PERFIL_TV = (): CfgPerfil => ({
  linhas: 24, largura: 30, lado: 'esquerda', corCompra: '#26a69a', corVenda: '#ef5350', transparencia: 35,
  poc: { cor: VERMELHO, largura: 2, estilo: 'solida' }, va: true, vaPct: 70, linhaVa: { cor: AZUL, largura: 1, estilo: 'tracejada' }, caixa: true,
})

/** o volume de cada vela espalhado por igual na faixa de preço dela; vela de alta soma compra, de baixa soma venda */
function calcularPerfil(velas: VelaG[], n: number, vaPct: number) {
  if (!velas.length) return null
  const lo = Math.min(...velas.map((k) => k.l)), hi = Math.max(...velas.map((k) => k.h))
  const passo = (hi - lo) / n || 1
  const linhas = Array.from({ length: n }, () => ({ alta: 0, baixa: 0 }))
  for (const k of velas) {
    const a = Math.max(0, Math.min(n - 1, Math.floor((k.l - lo) / passo))), b = Math.max(0, Math.min(n - 1, Math.floor((k.h - lo) / passo)))
    const por = k.v / (b - a + 1)
    for (let r = a; r <= b; r++) { if (k.c >= k.o) linhas[r].alta += por; else linhas[r].baixa += por }
  }
  const tot = linhas.map((l) => l.alta + l.baixa)
  const poc = tot.indexOf(Math.max(...tot))
  const soma = tot.reduce((s, v) => s + v, 0)
  let de = poc, ate = poc, dentro = tot[poc]
  while (dentro < soma * vaPct / 100 && (de > 0 || ate < n - 1)) {
    const baixo = de > 0 ? tot[de - 1] : -1, cima = ate < n - 1 ? tot[ate + 1] : -1
    if (cima >= baixo) { ate++; dentro += tot[ate] } else { de--; dentro += tot[de] }
  }
  return { lo, passo, linhas, tot, poc, val: lo + de * passo, vah: lo + (ate + 1) * passo, pocPreco: lo + (poc + 0.5) * passo, max: Math.max(...tot) }
}

function desenharPerfil(ctx: CanvasRenderingContext2D, c: CfgPerfil, t1: number, t2: number, g: Geo) {
  const P = calcularPerfil(g.velas(Math.min(t1, t2), Math.max(t1, t2)), Math.max(6, Math.round(c.linhas)), c.vaPct)
  const xa = g.x(Math.min(t1, t2)), xb = g.x(Math.max(t1, t2))
  if (!P || xa === null || xb === null) return null
  const largura = Math.max(xb - xa, 20) * c.largura / 100
  const yTopo = g.y(P.lo + P.passo * P.linhas.length), yBase = g.y(P.lo)
  if (yTopo === null || yBase === null) return null
  if (c.caixa) { ctx.fillStyle = 'rgba(41,98,255,0.06)'; ctx.fillRect(xa, yTopo, xb - xa, yBase - yTopo) }
  const al = (100 - c.transparencia) / 100
  P.linhas.forEach((l, r) => {
    const y0 = g.y(P.lo + r * P.passo), y1 = g.y(P.lo + (r + 1) * P.passo)
    if (y0 === null || y1 === null) return
    const h = Math.max(1, Math.abs(y0 - y1) - 1), top = Math.min(y0, y1)
    const wA = (l.alta / P.max) * largura, wB = (l.baixa / P.max) * largura
    const dir = c.lado === 'direita' ? -1 : 1, x0 = c.lado === 'direita' ? xb : xa
    const dentroVa = c.va && P.lo + r * P.passo >= P.val - 1e-9 && P.lo + (r + 1) * P.passo <= P.vah + 1e-9
    const a2 = dentroVa ? al : al * 0.5
    ctx.fillStyle = comAlfa(c.corCompra, a2); ctx.fillRect(dir > 0 ? x0 : x0 - wA, top, wA, h)
    ctx.fillStyle = comAlfa(c.corVenda, a2); ctx.fillRect(dir > 0 ? x0 + wA : x0 - wA - wB, top, wB, h)
  })
  const linhaH = (p: number, l: Linha) => { const y = g.y(p); if (y !== null) { tracar(ctx, l); linhaReta(ctx, { x: xa, y }, { x: xb, y }) } }
  linhaH(P.pocPreco, c.poc)
  if (c.va) { linhaH(P.vah, c.linhaVa); linhaH(P.val, c.linhaVa) }
  ctx.setLineDash([])
  const rot = (texto: string, p: number, cor: string) => { const y = g.y(p); if (y !== null) { ctx.font = "10.5px 'DM Mono', monospace"; ctx.fillStyle = cor; ctx.textAlign = 'left'; ctx.textBaseline = 'bottom'; ctx.fillText(texto, xb + 4, y) } }
  rot(`POC ${g.formatar(P.pocPreco)}`, P.pocPreco, c.poc.cor)
  if (c.va) { rot(`VAH ${g.formatar(P.vah)}`, P.vah, c.linhaVa.cor); rot(`VAL ${g.formatar(P.val)}`, P.val, c.linhaVa.cor) }
  return { xa, xb, yTopo, yBase }
}

const perfilFixo: Ferramenta = {
  tipo: 'perfil_volume_fixo', nome: 'Perfil de volume de faixa fixa', grupo: 'volume', pontos: 2, soTempo: true, campos: CAMPOS_PERFIL,
  icone: 'M2 2 V16 M2 4 H8 M2 7 H12 M2 10 H16 M2 13 H9 M16 2 V16',
  padrao: PERFIL_TV,
  linha: acesso<Linha>('poc'),
  desenhar(ctx, d, _px, g) { if (d.pts.length >= 2) desenharPerfil(ctx, d.cfg as CfgPerfil, d.pts[0].t, d.pts[1].t, g) },
  acertar(x, y, d, _px, g) {
    if (d.pts.length < 2) return false
    const xa = g.x(Math.min(d.pts[0].t, d.pts[1].t)), xb = g.x(Math.max(d.pts[0].t, d.pts[1].t))
    const P = calcularPerfil(g.velas(Math.min(d.pts[0].t, d.pts[1].t), Math.max(d.pts[0].t, d.pts[1].t)), 6, 70)
    if (xa === null || xb === null || !P) return false
    const yT = g.y(P.lo + P.passo * 6), yB = g.y(P.lo)
    return yT !== null && yB !== null && x >= xa - 3 && x <= xb + 3 && y >= yT - 3 && y <= yB + 3
  },
  alcas(d, px, g) {
    if (d.pts.length < 2) return px
    const P = calcularPerfil(g.velas(Math.min(d.pts[0].t, d.pts[1].t), Math.max(d.pts[0].t, d.pts[1].t)), 6, 70)
    const y = P ? g.y(P.lo + P.passo * 6) : null
    return px.map((p) => ({ x: p.x, y: y ?? p.y }))
  },
  resumo: (d) => duracao(Math.abs((d.pts[1]?.t ?? d.pts[0].t) - d.pts[0].t)),
}

const perfilAncorado: Ferramenta = {
  ...perfilFixo, tipo: 'perfil_volume_ancorado', nome: 'Perfil de volume ancorado', pontos: 1,
  icone: 'M2 2 V16 M2 4 H8 M2 7 H12 M2 10 H16 M2 13 H9',
  desenhar(ctx, d, _px, g) { const v = g.velas(d.pts[0].t, FIM); if (v.length) desenharPerfil(ctx, d.cfg as CfgPerfil, d.pts[0].t, v[v.length - 1].t, g) },
  acertar(x, y, d, _px, g) {
    const v = g.velas(d.pts[0].t, FIM)
    if (!v.length) return false
    return perfilFixo.acertar(x, y, { ...d, pts: [d.pts[0], { t: v[v.length - 1].t, p: 0 }] }, [], g)
  },
  alcas(d, px, g) {
    const v = g.velas(d.pts[0].t, FIM)
    const P = calcularPerfil(v, 6, 70)
    const y = P ? g.y(P.lo + P.passo * 6) : null
    return [{ x: px[0].x, y: y ?? px[0].y }]
  },
  resumo: (d) => `desde ${new Date(d.pts[0].t * 1000).toISOString().slice(0, 16).replace('T', ' ')} UTC`,
}

// ---------------------------------------------------------------- ciclos

type CfgCiclo = { linha: Linha; fundo: Fundo }
const CAMPOS_CICLO: Campo[] = [{ tipo: 'linha', chave: 'linha', nome: 'Linha' }]

/** os instantes t1 + k·Δ que caem na tela (para frente e para trás) */
function instantesCiclo(d: Desenho, g: Geo, maxK = 300): number[] {
  const [a, b] = d.pts
  const delta = (b?.t ?? a.t) - a.t
  if (!delta) return [a.t]
  const out: number[] = []
  for (let k = -maxK; k <= maxK; k++) {
    const t = a.t + k * delta
    const x = g.x(t)
    if (x !== null && x >= -50 && x <= g.W + 50) out.push(t)
  }
  return out
}

const linhasCiclicas: Ferramenta = {
  tipo: 'linhas_ciclicas', nome: 'Linhas cíclicas', grupo: 'ciclos', pontos: 2, soTempo: true, campos: CAMPOS_CICLO,
  icone: 'M3 2 V16 M7 2 V16 M11 2 V16 M15 2 V16',
  padrao: (): CfgCiclo => ({ linha: { cor: AZUL, largura: 1, estilo: 'solida' }, fundo: { ligado: false, cor: AZUL, transparencia: 90 } }),
  linha: acesso<Linha>('linha'),
  desenhar(ctx, d, _px, g) {
    const c = d.cfg as CfgCiclo
    tracar(ctx, c.linha)
    for (const t of instantesCiclo(d, g)) { const x = g.x(t); if (x !== null) linhaReta(ctx, { x, y: 0 }, { x, y: g.H }) }
    ctx.setLineDash([])
  },
  acertar: (x, _y, d, _px, g) => instantesCiclo(d, g).some((t) => { const xx = g.x(t); return xx !== null && Math.abs(xx - x) <= PERTO_PX }),
  resumo: (d) => `a cada ${duracao(Math.abs((d.pts[1]?.t ?? d.pts[0].t) - d.pts[0].t))}`,
}

const ciclosTempo: Ferramenta = {
  tipo: 'ciclos_tempo', nome: 'Ciclos de tempo', grupo: 'ciclos', pontos: 2,
  campos: [...CAMPOS_CICLO, { tipo: 'fundo', chave: 'fundo', nome: 'Fundo' }],
  icone: 'M1 14 A4 4 0 0 1 9 14 A4 4 0 0 1 17 14 M1 14 H17',
  padrao: (): CfgCiclo => ({ linha: { cor: '#9c27b0', largura: 1, estilo: 'solida' }, fundo: { ligado: true, cor: '#9c27b0', transparencia: 90 } }),
  linha: acesso<Linha>('linha'),
  desenhar(ctx, d, px, g) {
    if (px.length < 2) return
    const c = d.cfg as CfgCiclo
    const base = px[0].y, ry = Math.max(Math.abs(px[1].y - px[0].y), 4), sobe = px[1].y <= px[0].y
    const ts = instantesCiclo(d, g)
    for (let i = 1; i < ts.length; i++) {
      const x0 = g.x(ts[i - 1]), x1 = g.x(ts[i])
      if (x0 === null || x1 === null) continue
      ctx.beginPath(); ctx.ellipse((x0 + x1) / 2, base, Math.abs(x1 - x0) / 2, ry, 0, Math.PI, 0, !sobe)
      if (c.fundo.ligado) { ctx.fillStyle = comAlfa(c.fundo.cor, (100 - c.fundo.transparencia) / 100); ctx.fill() }
      tracar(ctx, c.linha); ctx.stroke(); ctx.setLineDash([])
    }
  },
  acertar(x, y, d, px, g) {
    if (px.length < 2) return false
    const base = px[0].y, ry = Math.max(Math.abs(px[1].y - px[0].y), 4)
    const ts = instantesCiclo(d, g)
    for (let i = 1; i < ts.length; i++) {
      const x0 = g.x(ts[i - 1]), x1 = g.x(ts[i])
      if (x0 === null || x1 === null || x < Math.min(x0, x1) || x > Math.max(x0, x1)) continue
      const rx = Math.abs(x1 - x0) / 2, cx = (x0 + x1) / 2
      const yArco = base - Math.sign(base - px[1].y || 1) * ry * Math.sqrt(Math.max(0, 1 - ((x - cx) / rx) ** 2))
      if (Math.abs(y - yArco) <= PERTO_PX || Math.abs(y - base) <= PERTO_PX) return true
    }
    return false
  },
  resumo: (d) => `a cada ${duracao(Math.abs((d.pts[1]?.t ?? d.pts[0].t) - d.pts[0].t))}`,
}

/** senoide: no ponto 1 está uma crista e no ponto 2 o vale seguinte (meio período) */
function pontosSenoide(px: Px[], W: number): Px[] {
  const [a, b] = px
  const meioPeriodo = b.x - a.x || 1, centro = (a.y + b.y) / 2, amp = (a.y - b.y) / 2
  const out: Px[] = []
  for (let x = -10; x <= W + 10; x += 3) out.push({ x, y: centro + amp * Math.cos(Math.PI * (x - a.x) / meioPeriodo) })
  return out
}
const senoide: Ferramenta = {
  tipo: 'senoide', nome: 'Linha senoidal', grupo: 'ciclos', pontos: 2, campos: CAMPOS_CICLO,
  icone: 'M1 9 Q4 1 7 9 T13 9 T19 9',
  padrao: (): CfgCiclo => ({ linha: { cor: LARANJA, largura: 1, estilo: 'solida' }, fundo: { ligado: false, cor: LARANJA, transparencia: 90 } }),
  linha: acesso<Linha>('linha'),
  desenhar(ctx, d, px, g) { if (px.length >= 2) poligono(ctx, pontosSenoide(px, g.W), null, (d.cfg as CfgCiclo).linha, false) },
  acertar: (x, y, _d, px, g) => px.length >= 2 && pertoPolilinha(x, y, pontosSenoide(px, g.W)),
  resumo: (d) => `período ${duracao(2 * Math.abs((d.pts[1]?.t ?? d.pts[0].t) - d.pts[0].t))}`,
}

// ---------------------------------------------------------------- previsão

type CfgPrevisao = { linha: Linha; corAcerto: string; corErro: string }
const previsao: Ferramenta = {
  tipo: 'previsao', nome: 'Previsão', grupo: 'medidas', pontos: 2,
  campos: [{ tipo: 'linha', chave: 'linha', nome: 'Linha' }, { tipo: 'cor', chave: 'corAcerto', nome: 'Cor quando acerta' }, { tipo: 'cor', chave: 'corErro', nome: 'Cor quando erra' }],
  icone: 'M2 14 L9 8 M9 8 L16 3 M12 3 H16 V7 M2 16 H16',
  padrao: (): CfgPrevisao => ({ linha: { cor: AZUL, largura: 2, estilo: 'tracejada' }, corAcerto: VERDE, corErro: VERMELHO }),
  linha: acesso<Linha>('linha'),
  desenhar(ctx, d, px, g) {
    if (px.length < 2) return
    const c = d.cfg as CfgPrevisao, [a, b] = d.pts
    tracar(ctx, c.linha); linhaReta(ctx, px[0], px[1]); ctx.setLineDash([]); seta(ctx, px[1], px[0], c.linha.largura)
    const sobe = b.p >= a.p
    const linhas = [`Previsão ${pct((b.p - a.p) / a.p)} em ${Math.round((b.t - a.t) / g.passo)} barras (${duracao(b.t - a.t)})`]
    const velas = g.velas(a.t + 1, b.t)
    const ult = g.velas(a.t + 1, FIM).at(-1)
    let cor = c.linha.cor
    if (velas.length && ult && ult.t >= b.t) {
      const bateu = velas.some((k) => (sobe ? k.h >= b.p : k.l <= b.p))
      cor = bateu ? c.corAcerto : c.corErro
      linhas.push(bateu ? 'acertou: o preço chegou lá no prazo' : `errou: no prazo fechou em ${pct((velas[velas.length - 1].c - a.p) / a.p)}`)
    } else if (velas.length) linhas.push(`em andamento: ${pct((velas[velas.length - 1].c - a.p) / a.p)} até agora`)
    caixaComTexto(ctx, linhas, { x: px[1].x, y: px[1].y + (sobe ? -8 : 8) }, { fonte: "11.5px 'DM Mono', monospace", tamanho: 11.5, cor: '#ffffff', fundo: cor, ancora: sobe ? 'baixo' : 'cima', W: g.W, H: g.H })
  },
  acertar: (x, y, _d, px) => px.length >= 2 && pertoSegmento(x, y, px[0], px[1]),
  resumo: (d, f) => `${f(d.pts[0].p)} → ${f(d.pts[1]?.p ?? d.pts[0].p)}`,
}

// ---------------------------------------------------------------- padrão de barras e ghost feed

type CfgBarras = { modo: 'velas' | 'linha' | 'oc'; espelhar: boolean; inverter: boolean; cor: string; transparencia: number }
/** cópia das velas da faixa (pontos 1 e 2) colada no ponto 3: a 1ª abertura vai no preço do ponto 3 */
function velasCopiadas(d: Desenho, g: Geo) {
  if (d.pts.length < 3) return []
  const [a, b, k] = d.pts
  const c = d.cfg as CfgBarras
  let v = g.velas(Math.min(a.t, b.t), Math.max(a.t, b.t))
  if (!v.length) return []
  if (c.espelhar) v = [...v].reverse().map((x) => ({ ...x, o: x.c, c: x.o }))
  const base = v[0].o, s = c.inverter ? -1 : 1
  const tr = (p: number) => k.p + s * (p - base)
  return v.map((x, i) => {
    const o = tr(x.o), cc = tr(x.c), h = tr(c.inverter ? x.l : x.h), l = tr(c.inverter ? x.h : x.l)
    return { t: k.t + i * g.passo, o, h, l, c: cc }
  })
}
const padraoBarras: Ferramenta = {
  tipo: 'padrao_barras', nome: 'Padrão de barras', grupo: 'medidas', pontos: 3,
  campos: [
    { tipo: 'escolha', chave: 'modo', nome: 'Desenho', opcoes: [['velas', 'Velas'], ['linha', 'Linha do fechamento'], ['oc', 'Abertura e fechamento']] },
    { tipo: 'bool', chave: 'espelhar', nome: 'Espelhar (de trás para frente)' }, { tipo: 'bool', chave: 'inverter', nome: 'Inverter (de cabeça para baixo)' },
    { tipo: 'cor', chave: 'cor', nome: 'Cor' }, { tipo: 'numero', chave: 'transparencia', nome: 'Transparência (%)', min: 0, max: 100, passo: 5 },
  ],
  icone: 'M3 5 V13 M6 3 V11 M9 6 V14 M12 4 V9 M15 7 V15',
  padrao: (): CfgBarras => ({ modo: 'velas', espelhar: false, inverter: false, cor: AZUL, transparencia: 30 }),
  cor: acesso<string>('cor'),
  desenhar(ctx, d, px, g) {
    const c = d.cfg as CfgBarras
    if (px.length >= 2) {
      // a faixa copiada: colchete fino sobre as velas de origem
      ctx.strokeStyle = comAlfa(c.cor, 0.6); ctx.lineWidth = 1; ctx.setLineDash([3, 3])
      linhaReta(ctx, { x: px[0].x, y: px[0].y }, { x: px[1].x, y: px[0].y }); ctx.setLineDash([])
    }
    const v = velasCopiadas(d, g)
    const al = (100 - c.transparencia) / 100
    const meia = Math.max(1, (g.x(g.passo * 1 + (v[0]?.t ?? 0)) ?? 0) - (g.x(v[0]?.t ?? 0) ?? 0)) * 0.35
    const pts: Px[] = []
    for (const k of v) {
      const x = g.x(k.t), yo = g.y(k.o), yc = g.y(k.c), yh = g.y(k.h), yl = g.y(k.l)
      if (x === null || yo === null || yc === null || yh === null || yl === null) continue
      pts.push({ x, y: yc })
      if (c.modo === 'linha') continue
      ctx.fillStyle = comAlfa(c.cor, k.c >= k.o ? al : al * 0.55); ctx.strokeStyle = comAlfa(c.cor, al)
      if (c.modo === 'velas') { ctx.lineWidth = 1; linhaReta(ctx, { x, y: yh }, { x, y: yl }) }
      ctx.fillRect(x - meia, Math.min(yo, yc), meia * 2, Math.max(1, Math.abs(yc - yo)))
    }
    if (c.modo === 'linha') poligono(ctx, pts, null, { cor: comAlfa(c.cor, al), largura: 2, estilo: 'solida' }, false)
  },
  acertar(x, y, d, px, g) {
    const v = velasCopiadas(d, g)
    if (!v.length) return px.length >= 2 && pertoSegmento(x, y, px[0], { x: px[1].x, y: px[0].y })
    const xs = v.map((k) => g.x(k.t)).filter((q): q is number => q !== null)
    const ys = v.flatMap((k) => [g.y(k.h), g.y(k.l)]).filter((q): q is number => q !== null)
    return x >= Math.min(...xs) - 4 && x <= Math.max(...xs) + 4 && y >= Math.min(...ys) - 4 && y <= Math.max(...ys) + 4
  },
  resumo: (d) => `${Math.round(Math.abs((d.pts[1]?.t ?? d.pts[0].t) - d.pts[0].t) / 60)} min copiados`,
}

type CfgFantasma = { corAlta: string; corBaixa: string; transparencia: number }
/** velas fantasma pelo caminho marcado: cada trecho vira velas de um tempo gráfico, com um pavio pequeno */
function velasFantasma(d: Desenho, g: Geo) {
  const out: { t: number; o: number; h: number; l: number; c: number }[] = []
  for (let i = 1; i < d.pts.length; i++) {
    const a = d.pts[i - 1], b = d.pts[i]
    const n = Math.max(1, Math.round(Math.abs(b.t - a.t) / g.passo))
    let ant = a.p
    for (let j = 1; j <= n; j++) {
      const c = a.p + (b.p - a.p) * j / n
      const pav = Math.abs(c - ant) * 0.35 + Math.abs(b.p - a.p) / n * 0.1
      out.push({ t: a.t + (b.t - a.t) * j / n, o: ant, c, h: Math.max(ant, c) + pav, l: Math.min(ant, c) - pav })
      ant = c
    }
  }
  return out
}
const ghost: Ferramenta = {
  tipo: 'ghost_feed', nome: 'Ghost feed (velas fantasma)', grupo: 'medidas', pontos: 0,
  campos: [{ tipo: 'cor', chave: 'corAlta', nome: 'Vela de alta' }, { tipo: 'cor', chave: 'corBaixa', nome: 'Vela de baixa' }, { tipo: 'numero', chave: 'transparencia', nome: 'Transparência (%)', min: 0, max: 100, passo: 5 }],
  icone: 'M3 6 V14 M3 8 H5 V12 H3 M8 3 V11 M8 5 H10 V9 H8 M13 7 V15 M13 9 H15 V13 H13',
  padrao: (): CfgFantasma => ({ corAlta: '#26a69a', corBaixa: '#ef5350', transparencia: 45 }),
  cor: acesso<string>('corAlta'),
  desenhar(ctx, d, px, g) {
    const c = d.cfg as CfgFantasma, al = (100 - c.transparencia) / 100
    tracar(ctx, { cor: 'rgba(120,123,134,0.6)', largura: 1, estilo: 'pontilhada' })
    ctx.beginPath(); px.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y))); ctx.stroke(); ctx.setLineDash([])
    for (const k of velasFantasma(d, g)) {
      const x = g.x(k.t), yo = g.y(k.o), yc = g.y(k.c), yh = g.y(k.h), yl = g.y(k.l)
      if (x === null || yo === null || yc === null || yh === null || yl === null) continue
      const cor = comAlfa(k.c >= k.o ? c.corAlta : c.corBaixa, al)
      ctx.strokeStyle = cor; ctx.fillStyle = cor; ctx.lineWidth = 1
      linhaReta(ctx, { x, y: yh }, { x, y: yl })
      ctx.fillRect(x - 2.5, Math.min(yo, yc), 5, Math.max(1, Math.abs(yc - yo)))
    }
  },
  acertar: (x, y, _d, px) => pertoPolilinha(x, y, px),
  resumo: (d) => `${d.pts.length} pontos`,
}

// ---------------------------------------------------------------- projeção

type CfgProjecao = { linha: Linha; fundo: Fundo }
/** projeção: a perna AB e a BC, com o arco de A até C em volta de B e quanto BC vale de AB */
const projecao: Ferramenta = {
  tipo: 'projecao', nome: 'Projeção', grupo: 'medidas', pontos: 3,
  campos: [{ tipo: 'linha', chave: 'linha', nome: 'Linha' }, { tipo: 'fundo', chave: 'fundo', nome: 'Fundo' }],
  icone: 'M2 15 L9 3 L16 12 M2 15 A9 9 0 0 1 16 12',
  padrao: (): CfgProjecao => ({ linha: { cor: AZUL, largura: 1, estilo: 'solida' }, fundo: { ligado: true, cor: AZUL, transparencia: 88 } }),
  linha: acesso<Linha>('linha'), fundo: acesso<string>('fundo.cor'),
  desenhar(ctx, d, px, g) {
    const c = d.cfg as CfgProjecao
    if (px.length < 3) { if (px.length === 2) { tracar(ctx, c.linha); linhaReta(ctx, px[0], px[1]); ctx.setLineDash([]) } return }
    const [a, b, k] = px
    poligono(ctx, [a, b, k], c.fundo, null)
    tracar(ctx, c.linha); linhaReta(ctx, a, b); linhaReta(ctx, b, k)
    const r = Math.hypot(a.x - b.x, a.y - b.y)
    const angA = Math.atan2(a.y - b.y, a.x - b.x), angC = Math.atan2(k.y - b.y, k.x - b.x)
    ctx.setLineDash([4, 4]); ctx.beginPath(); ctx.arc(b.x, b.y, r, angA, angC, (angC - angA + 2 * Math.PI) % (2 * Math.PI) > Math.PI); ctx.stroke(); ctx.setLineDash([])
    const [pa, pb, pc] = d.pts
    const rel = Math.abs(pb.p - pa.p) ? Math.abs(pc.p - pb.p) / Math.abs(pb.p - pa.p) : 0
    caixaComTexto(ctx, [`${fmtNum(rel * 100, 1)}% de AB`, `${pct((pc.p - pb.p) / pb.p)} · ${Math.round((pc.t - pb.t) / g.passo)} barras`], { x: k.x + 8, y: k.y }, {
      fonte: "11.5px 'DM Mono', monospace", tamanho: 11.5, cor: '#ffffff', fundo: c.linha.cor, ancora: 'esquerda', W: g.W, H: g.H,
    })
  },
  acertar: (x, y, _d, px) => px.length >= 3 && (pertoSegmento(x, y, px[0], px[1]) || pertoSegmento(x, y, px[1], px[2]) || dentroPoligono(x, y, px)),
  resumo: (d) => `${d.pts.length} pontos`,
}

// ---------------------------------------------------------------- pincel e marca-texto

type CfgPincel = { linha: Linha; fundo: Fundo; alfa: number }
function tracoLivre(ctx: CanvasRenderingContext2D, px: Px[]) {
  if (px.length < 2) return
  ctx.beginPath(); ctx.moveTo(px[0].x, px[0].y)
  for (let i = 1; i < px.length - 1; i++) { const m = { x: (px[i].x + px[i + 1].x) / 2, y: (px[i].y + px[i + 1].y) / 2 }; ctx.quadraticCurveTo(px[i].x, px[i].y, m.x, m.y) }
  ctx.lineTo(px[px.length - 1].x, px[px.length - 1].y)
}
function ferramentaPincel(tipo: string, nome: string, icone: string, padrao: () => CfgPincel): Ferramenta {
  return {
    tipo, nome, grupo: 'formas', pontos: 0, arrastar: true, icone,
    campos: [{ tipo: 'linha', chave: 'linha', nome: 'Traço' }, { tipo: 'numero', chave: 'alfa', nome: 'Opacidade do traço (%)', min: 5, max: 100, passo: 5 }, { tipo: 'fundo', chave: 'fundo', nome: 'Preencher a forma' }],
    padrao, linha: acesso<Linha>('linha'),
    desenhar(ctx, d, px) {
      const c = d.cfg as CfgPincel
      if (c.fundo.ligado && px.length > 2) { tracoLivre(ctx, px); ctx.closePath(); ctx.fillStyle = comAlfa(c.fundo.cor, (100 - c.fundo.transparencia) / 100); ctx.fill() }
      ctx.save(); ctx.globalAlpha = c.alfa / 100; ctx.lineCap = 'round'; ctx.lineJoin = 'round'
      tracar(ctx, c.linha); tracoLivre(ctx, px); ctx.stroke(); ctx.restore()
    },
    acertar: (x, y, d, px) => {
      const larg = (d.cfg as CfgPincel).linha.largura
      for (let i = 1; i < px.length; i++) if (pertoSegmento(x, y, px[i - 1], px[i]) || (larg > 6 && Math.hypot(x - px[i].x, y - px[i].y) <= larg / 2)) return true
      return false
    },
    alcas: (_d, px) => (px.length ? [px[0], px[px.length - 1]] : px),
    resumo: (d) => `${d.pts.length} pontos`,
  }
}
const pincel = ferramentaPincel('pincel', 'Pincel', 'M3 15 C5 9 8 13 10 8 S14 4 16 3', () => ({ linha: { cor: AZUL, largura: 2, estilo: 'solida' }, fundo: { ligado: false, cor: AZUL, transparencia: 85 }, alfa: 100 }))
const marcaTexto = ferramentaPincel('marca_texto', 'Marca-texto', 'M2 12 L12 2 L16 6 L6 16 Z M2 16 H8', () => ({ linha: { cor: '#ffeb3b', largura: 14, estilo: 'solida' }, fundo: { ligado: false, cor: '#ffeb3b', transparencia: 85 }, alfa: 35 }))

// ---------------------------------------------------------------- ícone, tabela, imagem, nota ancorada

const SIMBOLOS = ['⭐', '🔥', '🚀', '⚠️', '✅', '❌', '💰', '📈', '📉', '🐂', '🐻', '💎', '⚡', '🎯', '🔔', '❓', '❗', '👍', '👎', '😀', '😱', '🤔', '👀', '📌', '🏁', '⛔', '🟢', '🔴', '🔵', '⬆️', '⬇️', '➡️']
type CfgIcone = { simbolo: string; tamanho: number }
const icone: Ferramenta = {
  tipo: 'icone', nome: 'Ícone / emoji', grupo: 'texto', pontos: 1, pedeConfig: true,
  campos: [{ tipo: 'escolha', chave: 'simbolo', nome: 'Ícone', opcoes: SIMBOLOS.map((s) => [s, s]) }, { tipo: 'numero', chave: 'tamanho', nome: 'Tamanho', min: 10, max: 120 }],
  icone: 'M9 2 L11 7 H16 L12 10 L14 16 L9 12 L4 16 L6 10 L2 7 H7 Z',
  padrao: (): CfgIcone => ({ simbolo: '⭐', tamanho: 28 }),
  desenhar(ctx, d, px) {
    const c = d.cfg as CfgIcone, p = px[0]
    ctx.font = `${c.tamanho}px 'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', sans-serif`
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = '#ffffff'
    ctx.fillText(c.simbolo, p.x, p.y)
    CAIXAS.set(d.id, [{ x: p.x - c.tamanho / 2, y: p.y - c.tamanho / 2, w: c.tamanho, h: c.tamanho }])
  },
  acertar: (x, y, d) => dentroCaixas(d.id, x, y),
  resumo: (d) => (d.cfg as CfgIcone).simbolo,
}

type CfgTabela = { texto: Texto; fundo: string; borda: string; cabecalho: boolean; corCabecalho: string }
const tabela: Ferramenta = {
  tipo: 'tabela', nome: 'Tabela', grupo: 'texto', pontos: 1, texto: true, pedeTexto: true,
  campos: [{ tipo: 'cor', chave: 'fundo', nome: 'Fundo' }, { tipo: 'cor', chave: 'borda', nome: 'Grade' }, { tipo: 'bool', chave: 'cabecalho', nome: 'Primeira linha é o cabeçalho' }, { tipo: 'cor', chave: 'corCabecalho', nome: 'Fundo do cabeçalho' }],
  icone: 'M2 3 H16 V15 H2 Z M2 7 H16 M2 11 H16 M7 3 V15 M12 3 V15',
  padrao: (): CfgTabela => ({
    texto: { ...TEXTO_PADRAO, texto: 'Nível | Preço\nAlvo | \nStop | ', cor: '#e8ecf2', tamanho: 13, h: 'esquerda', v: 'meio' },
    fundo: '#131722', borda: '#5d606b', cabecalho: true, corCabecalho: '#2a2e39',
  }),
  cor: acesso<string>('texto.cor'),
  desenhar(ctx, d, px) {
    const c = d.cfg as CfgTabela, p = px[0]
    // uma linha por linha de texto; colunas separadas por "|"
    const linhas = c.texto.texto.split('\n').map((l) => l.split('|').map((x) => x.trim()))
    const ncol = Math.max(1, ...linhas.map((l) => l.length))
    ctx.font = fonteDe(c.texto)
    const pad = 6, alt = c.texto.tamanho * 1.6
    const larg = Array.from({ length: ncol }, (_, j) => Math.max(30, ...linhas.map((l) => ctx.measureText(l[j] ?? '').width)) + pad * 2)
    const W = larg.reduce((s, v) => s + v, 0), H = alt * linhas.length
    ctx.fillStyle = c.fundo; ctx.fillRect(p.x, p.y, W, H)
    if (c.cabecalho && linhas.length) { ctx.fillStyle = c.corCabecalho; ctx.fillRect(p.x, p.y, W, alt) }
    ctx.strokeStyle = c.borda; ctx.lineWidth = 1; ctx.setLineDash([])
    ctx.strokeRect(p.x + 0.5, p.y + 0.5, W, H)
    for (let i = 1; i < linhas.length; i++) linhaReta(ctx, { x: p.x, y: p.y + i * alt + 0.5 }, { x: p.x + W, y: p.y + i * alt + 0.5 })
    let xc = p.x
    for (let j = 0; j < ncol - 1; j++) { xc += larg[j]; linhaReta(ctx, { x: xc + 0.5, y: p.y }, { x: xc + 0.5, y: p.y + H }) }
    ctx.fillStyle = c.texto.cor; ctx.textBaseline = 'middle'; ctx.textAlign = 'left'
    linhas.forEach((l, i) => {
      let x = p.x
      for (let j = 0; j < ncol; j++) {
        ctx.font = (c.cabecalho && i === 0 ? 'bold ' : '') + fonteDe(c.texto)
        ctx.fillText(l[j] ?? '', x + pad, p.y + i * alt + alt / 2)
        x += larg[j]
      }
    })
    CAIXAS.set(d.id, [{ x: p.x, y: p.y, w: W, h: H }])
  },
  acertar: (x, y, d) => dentroCaixas(d.id, x, y),
  resumo: (d) => (d.cfg as CfgTabela).texto.texto.split('\n')[0].slice(0, 28),
}

type CfgImagem = { src: string; opacidade: number; borda: boolean }
const IMAGENS = new Map<string, HTMLImageElement>()
function imagemPronta(src: string, redesenhar: () => void): HTMLImageElement | null {
  if (!src) return null
  let im = IMAGENS.get(src)
  if (!im) { im = new Image(); im.onload = () => redesenhar(); im.src = src; IMAGENS.set(src, im) }
  return im.complete && im.naturalWidth ? im : null
}
const imagem: Ferramenta = {
  tipo: 'imagem', nome: 'Imagem', grupo: 'texto', pontos: 2, pedeConfig: true,
  campos: [{ tipo: 'imagem', chave: 'src', nome: 'Imagem' }, { tipo: 'numero', chave: 'opacidade', nome: 'Opacidade (%)', min: 5, max: 100, passo: 5 }, { tipo: 'bool', chave: 'borda', nome: 'Borda' }],
  icone: 'M2 3 H16 V15 H2 Z M2 12 L7 7 L11 11 L13 9 L16 12 M12 6 h0.5',
  padrao: (): CfgImagem => ({ src: '', opacidade: 100, borda: false }),
  desenhar(ctx, d, px, g) {
    if (px.length < 2) return
    const c = d.cfg as CfgImagem
    const x = Math.min(px[0].x, px[1].x), y = Math.min(px[0].y, px[1].y), w = Math.abs(px[1].x - px[0].x), h = Math.abs(px[1].y - px[0].y)
    const im = imagemPronta(c.src, g.redesenhar)
    if (im) { ctx.save(); ctx.globalAlpha = c.opacidade / 100; ctx.drawImage(im, x, y, w, h); ctx.restore() }
    else {
      ctx.fillStyle = 'rgba(41,98,255,0.08)'; ctx.fillRect(x, y, w, h)
      ctx.font = "12px 'DM Sans', sans-serif"; ctx.fillStyle = '#8b95a5'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
      ctx.fillText(c.src ? 'carregando a imagem…' : 'duplo clique para escolher a imagem', x + w / 2, y + h / 2)
    }
    if (c.borda || !im) { ctx.strokeStyle = 'rgba(139,149,165,0.6)'; ctx.lineWidth = 1; ctx.setLineDash(im ? [] : [4, 4]); ctx.strokeRect(x, y, w, h); ctx.setLineDash([]) }
  },
  acertar: (x, y, _d, px) => px.length >= 2 && x >= Math.min(px[0].x, px[1].x) && x <= Math.max(px[0].x, px[1].x) && y >= Math.min(px[0].y, px[1].y) && y <= Math.max(px[0].y, px[1].y),
  resumo: (d) => ((d.cfg as CfgImagem).src ? 'imagem' : 'sem imagem'),
}

export const ANALISE: Ferramenta[] = [vwap, perfilFixo, perfilAncorado]
export const CICLOS: Ferramenta[] = [linhasCiclicas, ciclosTempo, senoide]
export const PROJECAO: Ferramenta[] = [previsao, padraoBarras, ghost, projecao]
export const LIVRES: Ferramenta[] = [pincel, marcaTexto]
export const ANOTACOES: Ferramenta[] = [icone, tabela, imagem]
