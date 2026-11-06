/**
 * Texto e notas da barra da TradingView: texto, texto ancorado (preso à tela), nota, nota de preço, alfinete, balão,
 * comentário, etiqueta de preço, placa e bandeira. As que têm texto abrem a aba Texto logo depois de desenhar.
 * As caixas desenhadas ficam em CAIXAS, para o clique acertar exatamente o que se vê.
 */
import { TEXTO_PADRAO, type Desenho, type Linha, type Texto } from '../../lib/desenhos'
import {
  acesso, CAIXAS, caixaComTexto, CAMPO_FUNDO, CAMPO_LINHA, corFundo, dentroCaixas, fonteDe, fundoPadrao, linhaReta,
  medirCaixa, pertoSegmento, resumoTexto, tracar, type Caixa, type Campo, type Ferramenta, type Fundo, type Px,
} from './ferramentasBase'

const CLARO = '#e8ecf2', AZUL = '#2962ff'
const TEXTO_TV = (texto = 'Texto', cor = CLARO): Texto => ({ ...TEXTO_PADRAO, texto, cor, tamanho: 14, h: 'esquerda', v: 'meio' })

type CfgCaixa = { texto: Texto; fundo: Fundo; borda: { ligado: boolean; cor: string } }
const CAMPOS_CAIXA: Campo[] = [CAMPO_FUNDO(), { tipo: 'bool', chave: 'borda.ligado', nome: 'Borda' }, { tipo: 'cor', chave: 'borda.cor', nome: 'Cor da borda' }]

const guardar = (d: Desenho, cx: Caixa | Caixa[]) => CAIXAS.set(d.id, Array.isArray(cx) ? cx : [cx])
const linhasDe = (t: Texto) => (t.texto || ' ').split('\n')

function caixaDoTexto(ctx: CanvasRenderingContext2D, c: CfgCaixa, p: Px, ancora: Parameters<typeof caixaComTexto>[3]['ancora'], W: number, raio = 4) {
  return caixaComTexto(ctx, linhasDe(c.texto), p, {
    fonte: fonteDe(c.texto), tamanho: c.texto.tamanho, cor: c.texto.cor, ancora, W, raio,
    fundo: c.fundo.ligado && c.fundo.transparencia < 100 ? corFundo(c.fundo) : null, borda: c.borda.ligado ? c.borda.cor : null,
  })
}

const baseTexto = {
  texto: true, pedeTexto: true, cor: acesso<string>('texto.cor'),
  acertar: (x: number, y: number, d: Desenho) => dentroCaixas(d.id, x, y),
  resumo: resumoTexto,
}

const texto: Ferramenta = {
  ...baseTexto, tipo: 'texto', nome: 'Texto', grupo: 'texto', pontos: 1, campos: CAMPOS_CAIXA,
  icone: 'M3 3 H15 M9 3 V16 M6 16 H12',
  padrao: (): CfgCaixa => ({ texto: TEXTO_TV(), fundo: { ...fundoPadrao(AZUL, 85), ligado: false }, borda: { ligado: false, cor: AZUL } }),
  fundo: acesso<string>('fundo.cor'),
  desenhar(ctx, d, px, g) { guardar(d, caixaDoTexto(ctx, d.cfg as CfgCaixa, px[0], 'esquerda', g.W)) },
}

const textoAncorado: Ferramenta = {
  ...texto, tipo: 'texto_ancorado', nome: 'Texto ancorado (preso à tela)', tela: true,
  icone: 'M3 3 H15 M9 3 V13 M6 13 H12 M2 16 H16',
}

type CfgNota = { cor: string; texto: Texto; sempre: boolean }
const CAMPOS_NOTA: Campo[] = [{ tipo: 'cor', chave: 'cor', nome: 'Cor do marcador' }, { tipo: 'bool', chave: 'sempre', nome: 'Mostrar o texto sempre (não só selecionada)' }]

const nota: Ferramenta = {
  ...baseTexto, tipo: 'nota', nome: 'Nota', grupo: 'texto', pontos: 1, campos: CAMPOS_NOTA,
  icone: 'M3 2 H15 V12 L11 16 H3 Z M11 16 V12 H15',
  padrao: (): CfgNota => ({ cor: '#ff9800', texto: TEXTO_TV('Nota'), sempre: false }),
  cor: acesso<string>('cor'),
  desenhar(ctx, d, px, g) {
    const c = d.cfg as CfgNota, p = px[0]
    ctx.fillStyle = c.cor
    ctx.beginPath(); ctx.roundRect(p.x - 7, p.y - 7, 14, 14, 3); ctx.fill()
    ctx.strokeStyle = '#131722'; ctx.lineWidth = 1.2; ctx.beginPath(); ctx.moveTo(p.x - 3, p.y - 2); ctx.lineTo(p.x + 3, p.y - 2); ctx.moveTo(p.x - 3, p.y + 1.5); ctx.lineTo(p.x + 2, p.y + 1.5); ctx.stroke()
    const cx: Caixa[] = [{ x: p.x - 8, y: p.y - 8, w: 16, h: 16 }]
    if (c.sempre || g.selecionado) {
      cx.push(caixaComTexto(ctx, linhasDe(c.texto), { x: p.x + 12, y: p.y }, {
        fonte: fonteDe(c.texto), tamanho: c.texto.tamanho, cor: c.texto.cor, fundo: 'rgba(19,23,34,0.95)', borda: c.cor, ancora: 'esquerda', W: g.W, H: g.H,
      }))
    }
    guardar(d, cx)
  },
}

const alfinete: Ferramenta = {
  ...nota, tipo: 'alfinete', nome: 'Alfinete',
  icone: 'M9 16 L5 8 a4 4 0 1 1 8 0 Z',
  padrao: (): CfgNota => ({ cor: '#f23645', texto: TEXTO_TV('Alfinete'), sempre: false }),
  desenhar(ctx, d, px, g) {
    const c = d.cfg as CfgNota, p = px[0]
    ctx.fillStyle = c.cor
    ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x - 7, p.y - 14); ctx.arc(p.x, p.y - 17, 7.6, Math.PI * 0.85, Math.PI * 0.15); ctx.closePath(); ctx.fill()
    ctx.fillStyle = '#ffffff'; ctx.beginPath(); ctx.arc(p.x, p.y - 17, 2.8, 0, Math.PI * 2); ctx.fill()
    const cx: Caixa[] = [{ x: p.x - 8, y: p.y - 26, w: 16, h: 26 }]
    if (c.sempre || g.selecionado) {
      cx.push(caixaComTexto(ctx, linhasDe(c.texto), { x: p.x, y: p.y - 30 }, {
        fonte: fonteDe(c.texto), tamanho: c.texto.tamanho, cor: c.texto.cor, fundo: 'rgba(19,23,34,0.95)', borda: c.cor, ancora: 'baixo', W: g.W, H: g.H,
      }))
    }
    guardar(d, cx)
  },
}

type CfgNotaPreco = { linha: Linha; texto: Texto }
const notaPreco: Ferramenta = {
  tipo: 'nota_preco', nome: 'Nota de preço', grupo: 'texto', pontos: 2, texto: true, campos: [CAMPO_LINHA()],
  icone: 'M3 15 L10 6 M10 3 H16 V9 H10 Z',
  padrao: (): CfgNotaPreco => ({ linha: { cor: AZUL, largura: 1, estilo: 'solida' }, texto: TEXTO_TV('', CLARO) }),
  linha: acesso<Linha>('linha'),
  desenhar(ctx, d, px, g) {
    if (px.length < 2) return
    const c = d.cfg as CfgNotaPreco
    tracar(ctx, c.linha); linhaReta(ctx, px[0], px[1]); ctx.setLineDash([])
    ctx.fillStyle = c.linha.cor; ctx.beginPath(); ctx.arc(px[0].x, px[0].y, 3, 0, Math.PI * 2); ctx.fill()
    const linhas = [g.formatar(d.pts[0].p), ...(c.texto.texto.trim() ? c.texto.texto.split('\n') : [])]
    guardar(d, caixaComTexto(ctx, linhas, px[1], {
      fonte: "12px 'DM Mono', monospace", tamanho: 12, cor: '#ffffff', fundo: c.linha.cor, ancora: px[1].y < px[0].y ? 'baixo' : 'cima', W: g.W, H: g.H,
    }))
  },
  acertar: (x, y, d, px) => dentroCaixas(d.id, x, y) || (px.length >= 2 && pertoSegmento(x, y, px[0], px[1])),
  resumo: (d, f) => f(d.pts[0].p),
}

const balao: Ferramenta = {
  ...baseTexto, tipo: 'balao', nome: 'Balão', grupo: 'texto', pontos: 2, campos: CAMPOS_CAIXA,
  icone: 'M6 2 H16 V10 H11 L3 16 L8 10 H6 Z',
  padrao: (): CfgCaixa => ({ texto: TEXTO_TV('Balão'), fundo: fundoPadrao(AZUL, 20), borda: { ligado: false, cor: AZUL } }),
  fundo: acesso<string>('fundo.cor'),
  desenhar(ctx, d, px, g) {
    if (px.length < 2) return
    const c = d.cfg as CfgCaixa
    const cx = caixaDoTexto(ctx, { ...c, fundo: { ...c.fundo, transparencia: 100 }, borda: { ...c.borda, ligado: false } }, px[1], 'centro', g.W)
    // o rabicho do balão até o ponto 1, por baixo da caixa
    const centro = { x: cx.x + cx.w / 2, y: cx.y + cx.h / 2 }, larg = Math.min(14, cx.w / 3)
    const ang = Math.atan2(px[0].y - centro.y, px[0].x - centro.x), nx = -Math.sin(ang), ny = Math.cos(ang)
    ctx.fillStyle = c.fundo.ligado ? corFundo(c.fundo) : 'rgba(41,98,255,0.8)'
    ctx.beginPath(); ctx.moveTo(centro.x + nx * larg, centro.y + ny * larg); ctx.lineTo(px[0].x, px[0].y); ctx.lineTo(centro.x - nx * larg, centro.y - ny * larg); ctx.closePath(); ctx.fill()
    guardar(d, [caixaDoTexto(ctx, c, px[1], 'centro', g.W)])
  },
  acertar: (x, y, d, px) => dentroCaixas(d.id, x, y) || (px.length >= 2 && pertoSegmento(x, y, px[0], px[1])),
}

const comentario: Ferramenta = {
  ...baseTexto, tipo: 'comentario', nome: 'Comentário', grupo: 'texto', pontos: 1, campos: CAMPOS_CAIXA,
  icone: 'M2 3 H16 V12 H8 L4 16 V12 H2 Z',
  padrao: (): CfgCaixa => ({ texto: TEXTO_TV('Comentário'), fundo: fundoPadrao('#2a2e39', 0), borda: { ligado: true, cor: '#5d606b' } }),
  fundo: acesso<string>('fundo.cor'),
  desenhar(ctx, d, px, g) {
    const c = d.cfg as CfgCaixa, p = px[0]
    // a caixa fica em cima do ponto, com a ponta embaixo à esquerda
    const { h } = medirCaixa(ctx, linhasDe(c.texto), fonteDe(c.texto), c.texto.tamanho)
    const fim = caixaDoTexto(ctx, c, { x: p.x - 10, y: p.y - 12 - h }, 'cima-esq', g.W, 10)
    ctx.fillStyle = c.fundo.ligado ? corFundo(c.fundo) : '#2a2e39'
    ctx.beginPath(); ctx.moveTo(fim.x + 8, fim.y + fim.h - 1); ctx.lineTo(p.x, p.y); ctx.lineTo(fim.x + 22, fim.y + fim.h - 1); ctx.closePath(); ctx.fill()
    guardar(d, [fim, { x: p.x - 4, y: fim.y + fim.h, w: 24, h: p.y - fim.y - fim.h + 2 }])
  },
}

type CfgEtiqueta = { cor: string; corTexto: string }
const etiquetaPreco: Ferramenta = {
  tipo: 'etiqueta_preco', nome: 'Etiqueta de preço', grupo: 'texto', pontos: 1,
  campos: [{ tipo: 'cor', chave: 'cor', nome: 'Cor do fundo' }, { tipo: 'cor', chave: 'corTexto', nome: 'Cor do texto' }],
  icone: 'M2 9 L6 4 H16 V14 H6 Z',
  padrao: (): CfgEtiqueta => ({ cor: AZUL, corTexto: '#ffffff' }),
  cor: acesso<string>('cor'),
  desenhar(ctx, d, px, g) {
    const c = d.cfg as CfgEtiqueta, p = px[0]
    const cx = caixaComTexto(ctx, [g.formatar(d.pts[0].p)], { x: p.x + 10, y: p.y - 12 }, {
      fonte: "12px 'DM Mono', monospace", tamanho: 12, cor: c.corTexto, fundo: c.cor, ancora: 'baixo', W: g.W, H: g.H,
    })
    ctx.fillStyle = c.cor
    ctx.beginPath(); ctx.moveTo(cx.x + 4, cx.y + cx.h - 1); ctx.lineTo(p.x, p.y); ctx.lineTo(cx.x + 16, cx.y + cx.h - 1); ctx.closePath(); ctx.fill()
    guardar(d, [cx, { x: p.x - 3, y: cx.y + cx.h, w: 20, h: p.y - cx.y - cx.h + 2 }])
  },
  acertar: (x, y, d) => dentroCaixas(d.id, x, y),
  resumo: (d, f) => f(d.pts[0].p),
}

type CfgPlaca = { cor: string; texto: Texto }
const placa: Ferramenta = {
  ...baseTexto, tipo: 'placa', nome: 'Placa', grupo: 'texto', pontos: 1,
  campos: [{ tipo: 'cor', chave: 'cor', nome: 'Cor da placa' }],
  icone: 'M9 16 V8 M3 2 H15 V8 H3 Z',
  padrao: (): CfgPlaca => ({ cor: '#9c27b0', texto: TEXTO_TV('Placa', '#ffffff') }),
  cor: acesso<string>('cor'),
  desenhar(ctx, d, px, g) {
    const c = d.cfg as CfgPlaca, p = px[0]
    ctx.strokeStyle = c.cor; ctx.lineWidth = 2; ctx.setLineDash([])
    linhaReta(ctx, p, { x: p.x, y: p.y - 40 })
    ctx.fillStyle = c.cor; ctx.beginPath(); ctx.arc(p.x, p.y, 3, 0, Math.PI * 2); ctx.fill()
    const cx = caixaComTexto(ctx, linhasDe(c.texto), { x: p.x, y: p.y - 40 }, {
      fonte: fonteDe(c.texto), tamanho: c.texto.tamanho, cor: c.texto.cor, fundo: c.cor, ancora: 'baixo', W: g.W, H: g.H, raio: 10,
    })
    guardar(d, [cx, { x: p.x - 4, y: p.y - 40, w: 8, h: 42 }])
  },
}

const bandeira: Ferramenta = {
  tipo: 'bandeira', nome: 'Bandeira', grupo: 'texto', pontos: 1,
  campos: [{ tipo: 'cor', chave: 'cor', nome: 'Cor' }],
  icone: 'M4 17 V2 M4 3 H15 L12 7 L15 11 H4',
  padrao: () => ({ cor: '#f23645' }),
  cor: acesso<string>('cor'),
  desenhar(ctx, d, px) {
    const cor = (d.cfg as { cor: string }).cor, p = px[0]
    ctx.strokeStyle = cor; ctx.lineWidth = 2; ctx.setLineDash([])
    linhaReta(ctx, p, { x: p.x, y: p.y - 26 })
    ctx.fillStyle = cor
    ctx.beginPath(); ctx.moveTo(p.x, p.y - 26); ctx.lineTo(p.x + 18, p.y - 26); ctx.lineTo(p.x + 13, p.y - 20); ctx.lineTo(p.x + 18, p.y - 14); ctx.lineTo(p.x, p.y - 14); ctx.closePath(); ctx.fill()
    guardar(d, { x: p.x - 3, y: p.y - 27, w: 22, h: 28 })
  },
  acertar: (x, y, d) => dentroCaixas(d.id, x, y),
  resumo: (d, f) => f(d.pts[0].p),
}

const notaAncorada: Ferramenta = { ...nota, tipo: 'nota_ancorada', nome: 'Nota ancorada (presa à tela)', tela: true, icone: 'M3 2 H15 V12 L11 16 H3 Z M11 16 V12 H15 M2 17 H16' }

export const TEXTOS: Ferramenta[] = [texto, textoAncorado, nota, notaAncorada, notaPreco, alfinete, balao, comentario, etiquetaPreco, placa, bandeira]
