/**
 * Fibonacci de retração desenhado à mão no gráfico, com as mesmas opções da ferramenta "Fib Retracement" da
 * TradingView (níveis, cores, linha de tendência, fundo, estender, inverter, preços, rótulos, escala log).
 *
 * Ponto 1 = onde começou o movimento, ponto 2 = onde terminou: o nível 0 fica no ponto 2 e o 1 no ponto 1, como na
 * TradingView (puxar de um fundo a um topo põe o 0 no topo e as retrações para baixo). "Inverter" troca as pontas.
 *
 * Os pontos guardam o instante (s) e não o índice da vela, para o desenho continuar no lugar ao trocar o tempo gráfico.
 */
export type EstiloLinha = 'solida' | 'tracejada' | 'pontilhada'
export type NivelFibo = { valor: number; cor: string; ligado: boolean }
export type ConfigFibo = {
  tendencia: { ligada: boolean; cor: string; largura: number; estilo: EstiloLinha }
  niveis: NivelFibo[]
  larguraNiveis: number
  estiloNiveis: EstiloLinha
  umaCor: boolean
  corUnica: string
  fundo: boolean
  /** 0 a 100, como na TradingView: 100 = fundo invisível */
  transparencia: number
  estenderEsq: boolean
  estenderDir: boolean
  inverter: boolean
  precos: boolean
  rotulos: boolean
  rotuloComo: 'valor' | 'percentual'
  horizontal: 'esquerda' | 'centro' | 'direita'
  vertical: 'cima' | 'meio' | 'baixo'
  fonte: number
  log: boolean
}
export type Fibo = { id: string; t1: number; p1: number; t2: number; p2: number; cfg: ConfigFibo }

const CINZA = '#787b86'
/** os níveis e as cores da TradingView; os desligados aparecem na configuração para ligar */
const NIVEIS_TV: [number, string, boolean][] = [
  [0, CINZA, true], [0.236, '#f23645', true], [0.382, '#ff9800', true], [0.5, '#4caf50', true],
  [0.618, '#089981', true], [0.786, '#00bcd4', true], [1, CINZA, true], [1.618, '#2962ff', true],
  [2.618, '#f23645', true], [3.618, '#9c27b0', true], [4.236, '#e91e63', true],
  [1.272, '#ff9800', false], [1.414, '#f23645', false], [2, '#089981', false], [2.272, '#ff9800', false],
  [2.414, '#4caf50', false], [3, '#00bcd4', false], [3.272, CINZA, false], [3.414, '#2962ff', false],
  [4, '#f23645', false], [4.272, '#9c27b0', false], [4.414, '#e91e63', false], [4.618, '#ff9800', false],
  [4.764, '#089981', false],
]

export const PADRAO_TV: ConfigFibo = {
  tendencia: { ligada: true, cor: CINZA, largura: 1, estilo: 'tracejada' },
  niveis: NIVEIS_TV.map(([valor, cor, ligado]) => ({ valor, cor, ligado })),
  larguraNiveis: 1,
  estiloNiveis: 'solida',
  umaCor: false,
  corUnica: '#2962ff',
  fundo: true,
  transparencia: 80,
  estenderEsq: false,
  estenderDir: false,
  inverter: false,
  precos: true,
  rotulos: true,
  rotuloComo: 'valor',
  horizontal: 'esquerda',
  vertical: 'meio',
  fonte: 12,
  log: false,
}

const CHAVE_DESENHOS = 'grafico.fibos.v1'
const CHAVE_PADRAO = 'grafico.fibo.padrao.v1'

export const copiar = <T,>(x: T): T => JSON.parse(JSON.stringify(x)) as T

/** a configuração guardada como padrão ("Modelo › Salvar como padrão"), ou a da TradingView */
export function padraoFibo(): ConfigFibo {
  try {
    const s = localStorage.getItem(CHAVE_PADRAO)
    if (s) return { ...copiar(PADRAO_TV), ...JSON.parse(s) }
  } catch { /* modo privado ou guardado estragado */ }
  return copiar(PADRAO_TV)
}
export function guardarPadrao(cfg: ConfigFibo | null) {
  try { if (cfg) localStorage.setItem(CHAVE_PADRAO, JSON.stringify(cfg)); else localStorage.removeItem(CHAVE_PADRAO) } catch { /* sem armazenamento */ }
}

/** os desenhos ficam por moeda, como na TradingView */
export function lerFibos(simbolo: string): Fibo[] {
  try {
    const tudo = JSON.parse(localStorage.getItem(CHAVE_DESENHOS) || '{}') as Record<string, Fibo[]>
    return (tudo[simbolo] ?? []).map((f) => ({ ...f, cfg: { ...copiar(PADRAO_TV), ...f.cfg } }))
  } catch { return [] }
}
export function guardarFibos(simbolo: string, fibos: Fibo[]) {
  try {
    const tudo = JSON.parse(localStorage.getItem(CHAVE_DESENHOS) || '{}') as Record<string, Fibo[]>
    if (fibos.length) tudo[simbolo] = fibos; else delete tudo[simbolo]
    localStorage.setItem(CHAVE_DESENHOS, JSON.stringify(tudo))
  } catch { /* sem armazenamento: os desenhos valem só até recarregar */ }
}

/** preço do nível `v`: 0 no ponto 2, 1 no ponto 1 (ou o contrário com "inverter"); em log, a conta é no logaritmo */
export function precoDoNivel(f: Fibo, v: number): number {
  const [a, b] = f.cfg.inverter ? [f.p2, f.p1] : [f.p1, f.p2]
  if (f.cfg.log && a > 0 && b > 0) return Math.exp(Math.log(b) + (Math.log(a) - Math.log(b)) * v)
  return b + (a - b) * v
}

/** os níveis ligados, do valor menor para o maior, com o preço e a cor de cada um */
export function niveisDe(f: Fibo): { valor: number; preco: number; cor: string }[] {
  return f.cfg.niveis.filter((n) => n.ligado && Number.isFinite(n.valor))
    .sort((x, y) => x.valor - y.valor)
    .map((n) => ({ valor: n.valor, preco: precoDoNivel(f, n.valor), cor: f.cfg.umaCor ? f.cfg.corUnica : n.cor }))
}

export const tracos = (e: EstiloLinha, largura: number): number[] =>
  e === 'tracejada' ? [5 * largura, 4 * largura] : e === 'pontilhada' ? [largura, 3 * largura] : []

/** cor #rrggbb com opacidade (0 a 1) */
export function comAlfa(cor: string, alfa: number): string {
  const m = /^#([0-9a-f]{6})$/i.exec(cor)
  if (!m) return cor
  const n = parseInt(m[1], 16)
  return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${alfa})`
}

export const novoId = () => Math.random().toString(36).slice(2, 10)
