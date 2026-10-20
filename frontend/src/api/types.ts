/** Tipos das respostas da API do conselho (campos opcionais quando o backend pode omitir). */

export interface Candle { time: number; open: number; high: number; low: number; close: number; volume?: number }

/** Estado do conselho (GET /api/mercado/status). */
export interface StatusConselho {
  avisos: ServicoAvisos; telegram: boolean; coletor_idade_s: Record<string, number | null>
}

/** Níveis de um perfil de TPO (dia, sessão ou composto). */
export interface NiveisPerfil { inicio: number; poc: number; val: number; vah: number; minima: number; maxima: number; blocos: number }

/** Conselho de avisos (GET /api/avisos/mapa e /api/avisos/ultimos): só informação, sem %, stop ou alvo. */
export interface NivelMapa {
  chave: string; grupo: string; rotulo: string; preco: number; distancia_pct: number; dia_ms: number | null
}
export type NiveisMapa = Omit<NiveisPerfil, 'blocos'>
export interface ServicoAvisos {
  ativo: boolean; intervalo_s: number; ciclos: number; ultimo_erro: string | null; candles: number; telegram: boolean; arquivo: string
}
export interface MapaDoDia {
  ts: number; preco: number; posicao: string; p: number | null; dias_no_composto: number
  composto: NiveisMapa | null; ontem: NiveisMapa | null
  sessoes_ontem: Record<string, NiveisMapa>; sessoes_hoje: Record<string, NiveisMapa>
  aberturas: Record<string, number | null>; pivo_virgem: Record<string, number | null>
  naked_pocs: { preco: number; dia_ms: number }[]; niveis: NivelMapa[]
  ressalva: string; servico: ServicoAvisos
}
export interface Aviso {
  id: string; tipo: 'mapa' | 'proximidade'; ts: number; chave: string; titulo: string; texto: string; preco: number
  nivel: NivelMapa | null; ressalva: string
}
export interface AvisosUltimos { avisos: Aviso[]; servico: ServicoAvisos }

/** Nuvens do TRDR (GET /api/nuvens/overlay e /top): livro agregado por categoria de distância do melhor bid/ask. */
export interface NuvensCategoria { lo: number; hi: number; rotulo: string }
export interface NuvensPonto {
  ts: number; mid: number; bids: number[]; asks: number[]; razao: (number | null)[]; forca: number[]
  vantagem: ('bids' | 'asks' | null)[]; cobertura: string[][]; exchanges: string[]; aproximado: boolean
  total_bids: number; total_asks: number; forca_total: number
}
export interface NuvensFonte {
  snapshots: number; primeiro_ts: number | null; ultimo_ts: number | null
  alcance_bids_pct: number | null; alcance_asks_pct: number | null; aproximados: number
}
export interface NuvensOverlay {
  inicio: number; fim: number; exchanges: string[]; passo_s: number; categorias: NuvensCategoria[]; pontos: NuvensPonto[]
  fontes: Record<string, NuvensFonte>; ultimo_ts: number | null; limitacoes: Record<string, string>
}
export interface NuvensNivel { preco: number; qtd: number; exchanges: string[] }
export interface NuvensTop {
  ts: number | null; mid: number | null; bids: NuvensNivel[]; asks: NuvensNivel[]; exchanges: string[]; aproximado: boolean
  exchanges_pedidas: string[]
}
