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
  id: string; tipo: 'mapa' | 'proximidade' | 'absorcao' | 'presos'; ts: number; chave: string; titulo: string; texto: string; preco: number
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

/** Mapa de calor do livro (GET /api/nuvens/calor): só as células com ordens acima do normal da distância. */
/** intensidade = contra o histórico na mesma distância; local = contra as faixas vizinhas no mesmo instante */
export type CelulaCalor = [baixo: number, alto: number, lado: 0 | 1, btc: number, intensidade: number, local?: number]
export interface NuvensCalor {
  inicio: number; fim: number; passo_s: number; grade_usd: number | null; fator_min: number; btc_min: number
  exchanges: string[]; base: Record<string, number>
  colunas: { ts: number; mid: number; celulas: CelulaCalor[] }[]
  limitacoes: Record<string, string>
}

/** Presos no footprint (GET /api/fluxo/presos): confirmado null = ainda sem as velas seguintes. */
export interface EventoPresos { ts: number; lado: 'compradores' | 'vendedores'; preco: number; btc: number; vezes: number; confirmado: boolean | null }
export interface FluxoPresos {
  inicio: number; fim: number; passo_s: number; exchanges: string[]; abandono_pct: number
  velas_com_footprint: number; primeira_vela: number | null; eventos: EventoPresos[]
}

/** Absorção (GET /api/fluxo/absorcao): parede no livro + agressão alavancada contra ela + preço travado. */
export interface EventoAbsorcao {
  ts: number; ate_ts: number; tipo: 'venda' | 'compra'; baixo: number; alto: number; intensidade: number
  parede_btc: number; delta_btc: number; delta_z: number; oi_var_pct: number; fechamento: number
}
export interface PressaoLivro { ts: number; tipo: 'venda' | 'compra'; baixo: number; alto: number; forca: number; btc: number }
export interface FluxoAbsorcao {
  inicio: number; fim: number; passo_s: number; eventos: EventoAbsorcao[]; pressao: PressaoLivro[]
  velas_com_livro_e_negocios: number; desde: number | null
  criterio: { parede_vezes: number; parede_btc: number; agressao_percentil: number; encostou_pct: number; pressao_vezes: number; oi: string }
}

/** Footprint (GET /api/fluxo/footprint): por vela, [preço da linha, compra, venda] agredidos a mercado. */
export interface VelaFootprint {
  ts: number; abertura: number; maxima: number; minima: number; fechamento: number
  compra: number; venda: number; delta: number; poc: number | null
  linhas: [preco: number, compra: number, venda: number][]
  presos: EventoPresos[]
}
export interface FluxoFootprint { passo_s: number; linha_usd: number; exchanges: string[]; velas: VelaFootprint[] }

/** Robôs em simulação (GET /api/robos e /api/robos/trades). */
export interface PosicaoRobo {
  status: 'pendente' | 'aberta' | 'fechada' | 'expirada'; lado: 'compra' | 'venda'; fatias: [number, number][]
  stop: number; stop_atual: number; alvo: number | null; medio: number | null; tomou_1r: boolean
  criado_s: number; valido_ate_s: number; motivo: string
}
export interface Robo {
  robo: string; nome: string; banca: number; trades: number; ganhos: number; resultado_r: number; media_r: number | null
  posicao: PosicaoRobo | null
}
export interface RobosStatus {
  ativo: boolean; ciclos: number; ultimo_erro: string | null; velas5: number; simulacao: boolean
  risco_pct: number; banca_inicial: number; robos: Robo[]
}
export interface TradeRobo {
  robo: string; lado: 'compra' | 'venda'; criado_s: number; entrada_s: number; saida_s: number; medio: number; stop: number
  alvo: number | null; saida: string; tomou_1r: boolean; resultado_r: number; resultado_usdt: number; banca: number; motivo: string
}

/** Liquidações dos perpétuos (GET /api/fluxo/liquidacoes): long = quem estava comprado e foi fechado a mercado. */
export interface VelaLiquidacoes { ts: number; long_usd: number; short_usd: number; long_btc: number; short_btc: number; n: number }
export interface FluxoLiquidacoes { inicio: number; fim: number; passo_s: number; exchanges: string[]; desde: number | null; velas: VelaLiquidacoes[] }

/** Funding (GET /api/mercado/funding): [ts_ms, taxa] por corretora e [ts_ms, taxa média, n corretoras]. */
export interface FundingAgregado {
  por_exchange: Record<string, [number, number][]>; media: [number, number, number][]; falhas: Record<string, string>
}

/** Livro dos perpétuos até 0,1% do preço (GET /api/nuvens/perp), somado entre Binance, Bybit e OKX. */
export interface LivroPerp {
  inicio: number; fim: number; passo_s: number; faixa_pct: number; exchanges: string[]
  velas: { ts: number; exchanges: string[]; bids: number; asks: number }[]
}
