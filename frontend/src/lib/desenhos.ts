/**
 * Desenhos da tela Gráfico (as ferramentas da TradingView): o formato de cada desenho, a visibilidade por tempo
 * gráfico, os modelos ("Salvar como padrão") e onde tudo fica guardado.
 *
 * Os desenhos ficam no SERVIDOR (api/routes/desenhos_routes.py), um arquivo por moeda, para aparecerem igual no PC e
 * no celular; uma cópia fica no navegador para o caso de o servidor não responder. Os Fibonacci antigos, que ficavam
 * só no navegador (lib/fibo.ts), sobem para o servidor na primeira vez que a moeda abre.
 *
 * Os pontos guardam o instante (s) e o preço, não o índice da vela: o desenho continua no lugar ao trocar o tempo.
 */
import { api } from '../api/client'
import { copiar, guardarFibos, lerFibos, type EstiloLinha } from './fibo'

export type Ponto = { t: number; p: number }
export type Linha = { cor: string; largura: number; estilo: EstiloLinha }
export type Texto = {
  texto: string; cor: string; tamanho: number; negrito: boolean; italico: boolean
  h: 'esquerda' | 'centro' | 'direita'; v: 'cima' | 'meio' | 'baixo'
}
export type Faixa = { ligado: boolean; de: number; ate: number }
/** em que tempos gráficos o desenho aparece (a aba Visibilidade da TradingView) */
export type Visibilidade = { minutos: Faixa; horas: Faixa; dias: Faixa; semanas: boolean; meses: boolean }
// a configuração é de cada ferramenta (components/chart/ferramentas.ts); aqui ela só passa
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Cfg = any
export type Desenho = { id: string; tipo: string; pts: Ponto[]; cfg: Cfg; vis: Visibilidade; travado?: boolean; oculto?: boolean }

export const VIS_PADRAO: Visibilidade = {
  minutos: { ligado: true, de: 1, ate: 59 }, horas: { ligado: true, de: 1, ate: 24 }, dias: { ligado: true, de: 1, ate: 366 },
  semanas: true, meses: true,
}
export const TEXTO_PADRAO: Texto = { texto: '', cor: '#2962ff', tamanho: 14, negrito: false, italico: false, h: 'centro', v: 'cima' }

/** o desenho aparece neste tempo gráfico ('1m', '4h', '1d')? */
export function visivelNoTempo(v: Visibilidade, tempo: string): boolean {
  const m = /^(\d+)([mhd])$/.exec(tempo)
  if (!m) return true
  const n = Number(m[1])
  const f = m[2] === 'm' ? v.minutos : m[2] === 'h' ? v.horas : v.dias
  return f.ligado && n >= f.de && n <= f.ate
}

export const novoId = () => Math.random().toString(36).slice(2, 10)

// ---------------------------------------------------------------- modelos ("Salvar como padrão")

const CHAVE_MODELOS = 'grafico.desenhos.modelos.v1'
const CHAVE_PADRAO_FIBO_ANTIGO = 'grafico.fibo.padrao.v1'
let modelos: Record<string, Cfg> = {}
try { modelos = JSON.parse(localStorage.getItem(CHAVE_MODELOS) || '{}') } catch { /* sem armazenamento */ }

function guardarModelosLocal() { try { localStorage.setItem(CHAVE_MODELOS, JSON.stringify(modelos)) } catch { /* sem armazenamento */ } }

/** busca os modelos do servidor uma vez (e sobe o padrão antigo do Fibonacci, se houver) */
let carregouModelos = false
export async function carregarModelos(): Promise<void> {
  if (carregouModelos) return
  carregouModelos = true
  try {
    const r = await api.get<{ modelos: Record<string, Cfg> }>('/api/desenhos/modelos')
    modelos = { ...r.modelos }
    let antigo: string | null = null
    try { antigo = localStorage.getItem(CHAVE_PADRAO_FIBO_ANTIGO) } catch { /* nada */ }
    if (antigo && !modelos.fibo_retracao) {
      modelos.fibo_retracao = JSON.parse(antigo)
      await api.put('/api/desenhos/modelos', undefined, { modelos })
      try { localStorage.removeItem(CHAVE_PADRAO_FIBO_ANTIGO) } catch { /* nada */ }
    }
    guardarModelosLocal()
  } catch { carregouModelos = false }
}

/** a configuração salva como padrão da ferramenta, por cima da padrão da TradingView */
export function modeloDe(tipo: string, padraoTv: Cfg): Cfg {
  const m = modelos[tipo]
  return m ? mesclar(copiar(padraoTv), m) : copiar(padraoTv)
}
export function temModelo(tipo: string): boolean { return !!modelos[tipo] }
export async function guardarModelo(tipo: string, cfg: Cfg | null): Promise<boolean> {
  if (cfg) modelos[tipo] = copiar(cfg); else delete modelos[tipo]
  guardarModelosLocal()
  try { await api.put('/api/desenhos/modelos', undefined, { modelos }); return true } catch { return false }
}

/** junta o guardado por cima do padrão: campos novos de versões futuras ficam com o valor padrão */
export function mesclar(base: Cfg, por: Cfg): Cfg {
  if (!por || typeof por !== 'object' || Array.isArray(por) || !base || typeof base !== 'object' || Array.isArray(base)) return por ?? base
  const r: Cfg = { ...base }
  for (const [k, v] of Object.entries(por)) r[k] = k in base ? mesclar(base[k], v) : v
  return r
}

// ---------------------------------------------------------------- desenhos de cada moeda

const CHAVE_CACHE = 'grafico.desenhos.v2'

function lerCache(simbolo: string): Desenho[] | null {
  try { return (JSON.parse(localStorage.getItem(CHAVE_CACHE) || '{}') as Record<string, Desenho[]>)[simbolo] ?? null } catch { return null }
}
export function guardarCache(simbolo: string, lista: Desenho[]) {
  try {
    const tudo = JSON.parse(localStorage.getItem(CHAVE_CACHE) || '{}') as Record<string, Desenho[]>
    if (lista.length) tudo[simbolo] = lista; else delete tudo[simbolo]
    localStorage.setItem(CHAVE_CACHE, JSON.stringify(tudo))
  } catch { /* sem armazenamento */ }
}

/** os Fibonacci antigos (só do navegador) no formato novo */
function fibosAntigos(simbolo: string): Desenho[] {
  return lerFibos(simbolo).map((f) => ({ id: f.id, tipo: 'fibo_retracao', pts: [{ t: f.t1, p: f.p1 }, { t: f.t2, p: f.p2 }], cfg: f.cfg, vis: copiar(VIS_PADRAO) }))
}

export function normalizar(d: Desenho): Desenho {
  return { ...d, pts: d.pts ?? [], cfg: d.cfg ?? {}, vis: mesclar(copiar(VIS_PADRAO), d.vis ?? {}) }
}

export type Carga = { lista: Desenho[]; doServidor: boolean }

export async function carregarDesenhos(simbolo: string): Promise<Carga> {
  try {
    const r = await api.get<{ desenhos: Desenho[] }>('/api/desenhos', { simbolo })
    let lista = r.desenhos ?? []
    const antigos = fibosAntigos(simbolo)
    if (antigos.length) {
      const ids = new Set(lista.map((d) => d.id))
      lista = [...lista, ...antigos.filter((d) => !ids.has(d.id))]
      await gravarDesenhos(simbolo, lista)
      guardarFibos(simbolo, [])                        // já subiram: não voltam a ser importados
    }
    lista = lista.map(normalizar)
    guardarCache(simbolo, lista)
    return { lista, doServidor: true }
  } catch {
    return { lista: (lerCache(simbolo) ?? fibosAntigos(simbolo)).map(normalizar), doServidor: false }
  }
}

export async function gravarDesenhos(simbolo: string, lista: Desenho[], manterVivo = false): Promise<void> {
  if (manterVivo) {
    // saindo da página: o fetch com keepalive termina mesmo com a aba fechando
    await fetch(`/api/desenhos?simbolo=${encodeURIComponent(simbolo)}`, {
      method: 'PUT', keepalive: true, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ desenhos: lista }),
    })
    return
  }
  await api.put('/api/desenhos', { simbolo }, { desenhos: lista })
}
