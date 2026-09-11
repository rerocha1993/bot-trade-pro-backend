/** Tipos das respostas da API (campos opcionais quando o backend pode omitir). */

export interface Bot {
  id: number
  nome: string
  ativo: string
  timeframe: string
  estilo_trade: string
  modo_execucao: string
  alavancagem: number
  quantidade: number
  exchange: string
  usar_elliott: boolean
  usar_fibonacci: boolean
  usar_tpo: boolean
  usar_orderflow: boolean
  usar_vwap: boolean
  usar_volume_profile: boolean
  usar_orderblock: boolean
  usar_trailing_stop: boolean
  sl_tipo: string
  sl_variacao_pct: number
  ativo_bot: boolean
  usar_api_macro: boolean
  position_mode: string
  margin_mode: string
  subconta: string
  banca: number | string
  risco_pct: number
  max_alocacao_pct: number
  min_quantidade: number | null
  max_quantidade: number | null
  confluencia_tipo: string
  ativador_trailing: number
  distancia_trailing: number
  trailing_manual: boolean
  usar_saida_escalonada: boolean
  saida_escalonada: string
  mover_stop_para_entrada: boolean
  // motor de fluxo (scalp): decide por barra de volume, nao por candle de 1m
  usar_motor_fluxo?: boolean
  barra_tipo?: string
  barra_tamanho?: number
  barra_segundos_alvo?: number
  usar_sentimento: boolean
  usar_tendencia_macro: boolean
  max_trades_dia: number
  max_perda_dia_pct: number
  delay_execucao: number
  usar_filtro_regime: boolean
  prob_sucesso_minima: number
  tipo_entrada: string
  limite_candles_espera: number
  usar_websocket: boolean
  taxa_historica_minima: number
  rr_minimo: number
  estrategia: string
  categoria: string
  range_low: number | null
  range_high: number | null
  range_status: string | null
  short_base_max: number
  folga_stop: number
  saida_estrutural: boolean
  [k: string]: unknown
}

export interface BotStatusItem {
  id: number
  nome: string
  ativo: boolean
  rodando: boolean
  ativo_nome: string
  timeframe: string
  modo_execucao: string
  estilo_trade: string
  confluencia_tipo: string
  ultimo_status: string | null
  ultima_execucao: string | null
  ultima_decisao: DecisaoResumo | null
  pnl_dia: number | null
}

export interface DecisaoResumo {
  acao?: string
  motivo?: string
  fase_onda?: string
  cenario?: string
  probabilidade?: number
  tp?: number
  sl?: number
  votos?: string | string[]
}

export interface EstadoExecutor {
  modo: string
  par: string
  timeframe: string
  ciclos: number
  erros: number
  ultima_decisao: DecisaoResumo | null
  ultimo_ciclo: string | null
  posicao: unknown
  pnl_dia: number
  trades_dia: number
  dia: string
  inicio: string
  rodando: boolean
  thread_viva: boolean
  ordem_pendente: Record<string, unknown> | null
  fluxo?: EstadoFluxo | null
}

/** Motor de fluxo do scalp: a regua da barra, o ritmo que ela esta rendendo e o que segurou a ultima leitura. */
export interface EstadoFluxo {
  motor: string
  barras: { tipo: string; tamanho: number; calibrado: boolean; barras: number; negocios_vistos: number; lacunas: number; segundos_alvo: number; ritmo_s: number | null }
  barras_avaliadas: number
  ultima_barra: Record<string, number> | null
  ultimo_motivo: string
  contexto: { direcao: string; motivo: string; vies_contexto: string; vies_macro: string; idade_s: number; niveis: { preco: number; fonte: string; tipo: string }[] } | null
}

export interface Posicao {
  id: number
  bot_id: number
  par: string
  modo_execucao: string
  direcao: 'buy' | 'sell'
  quantidade: number
  preco_entrada: number
  sl: number | null
  tp: number | null
  sl_inicial: number | null
  trailing_ativo: boolean
  quantidade_inicial: number | null
  saidas_feitas: string | null
  pnl_parcial: number | null
  status: 'aberta' | 'fechada'
  preco_saida: number | null
  pnl: number | null
  taxas: number | null
  motivo_entrada: string | null
  motivo_saida: string | null
  fase_onda: string | null
  cenario: string | null
  aberto_em: string
  fechado_em: string | null
}

export interface Decisao {
  id: number
  bot_id: number
  par: string
  timeframe: string
  candle_ts: number | null
  preco: number
  acao: 'buy' | 'sell' | 'hold'
  fase_onda: string | null
  cenario: string | null
  probabilidade: number | null
  tendencia_macro: string | null
  votos: string | null
  tp: number | null
  sl: number | null
  sentimento: number | null
  motivo: string | null
  detalhes?: Record<string, unknown> | string | null
  criado_em: string
}

export interface StatusBot {
  bot: Bot
  rodando: boolean
  estado: EstadoExecutor | null
  posicao: Posicao | null
  ultima_decisao: Decisao | null
}

export interface PosicoesResp {
  resumo: { total: number; ganhos: number; perdas: number; taxa_acerto: number | null; pnl_total: number; fator_lucro: number | null }
  posicoes: Posicao[]
}

export interface LogExecucao {
  id: number
  bot_id: number
  data_execucao: string
  preco: number | null
  acao: string | null
  motivo: string | null
  resultado: number | null
  erro: string | null
  tipo_operacao: string | null
  direcao: string | null
}

export interface Onda {
  rotulo: string
  inicio: number
  fim: number
  ts_inicio: number
  ts_fim: number
  confirmado?: boolean
  data_inicio?: string
  data_fim?: string
}

export interface Cenario {
  id: string
  nome: string
  padrao: string
  vies: 'bull' | 'bear'
  fase: string
  direcao_trade: string
  horizonte: string
  score: number
  probabilidade: number
  prob_sucesso?: number | null
  invalidacao: number | null
  alvos: number[]
  ondas: Onda[]
  completo: boolean
  motivo: string
}

export interface Pivot {
  idx: number
  ts: number
  preco: number
  tipo: 'H' | 'L'
  confirmado: boolean
  data?: string
}

export interface AnaliseGrau {
  preco?: number
  timeframe?: string
  fase: string
  direcao: string
  consenso: string
  tendencia?: string
  prob_bull: number
  prob_bear: number
  prob_indefinido?: number
  primario: Cenario | null
  alternativos: Cenario[]
  cenarios: Cenario[]
  pivots?: Pivot[]
  regime?: { regime?: string; [k: string]: unknown }
  erro?: string
}

export interface Alinhamento {
  direcao: string
  direcao_operacional: string
  fase: string
  alinhado: boolean
  contra_tendencia: boolean
  bloqueado: boolean
  vies_contexto: string
  vies_macro: string
  vies_mestre: string | null
  vies_trader?: string | null
  estado_superciclo?: string | null
  fator_tamanho?: number
  tendencia_macro: string
  motivo: string
}

export interface MultiGrau {
  perfil: string
  timeframes: { operacional: string; contexto: string; macro: string }
  graus: { operacional: AnaliseGrau; contexto: AnaliseGrau; macro: AnaliseGrau }
  alinhamento: Alinhamento
}

export interface Sentimento {
  score: number
  zona: string
  vies_contrario: string
  componentes: Record<string, number>
  fear_greed: { valor: number; classificacao: string } | null
  funding: number | null
  long_short_ratio: number | null
  open_interest: { oi_var: number; preco_var: number } | null
  bloqueia_compra: boolean
  bloqueia_venda: boolean
  timestamp: number
}

export interface Candle { time: number; open: number; high: number; low: number; close: number; volume?: number }

export interface NiveisResp {
  preco: number
  tpo: { POC: number; VAH: number; VAL: number; shape?: string; HVN?: number[]; LVN?: number[]; perfil?: PerfilLinha[]; range?: [number, number] }
  volume_profile: { POC?: number; VAH?: number; VAL?: number; perfil?: PerfilLinha[]; [k: string]: unknown }
  vwap: { vwap: number; banda_sup?: number | null; banda_inf?: number | null; stddev?: number; [k: string]: unknown } | null
  order_blocks: { bullish?: OrderBlock[]; bearish?: OrderBlock[]; erro?: string }
}

export interface PerfilLinha { lo: number; hi: number; valor: number }

export interface OrderBlock {
  preco: number
  zona?: [number, number]
  timestamp?: number
  index?: number
  forca?: number
  topo?: number
  fundo?: number
  tipo?: string
  mitigado?: boolean
  [k: string]: unknown
}

export interface PontoInstitucional {
  id: number
  preco: number | string
  data_identificacao: string | null
  tipo: string
  motivo: string | null
  ativo: boolean
  testado: boolean
  rompido: boolean
  data_testado: string | null
  data_rompido: string | null
  par: string
  exchange: string
  relevancia: number | null
  extra: string | null
}

export interface Backtest {
  id: number
  bot_id: number | null
  par: string
  timeframe: string
  estilo_trade: string | null
  confluencia_tipo: string | null
  fonte: string
  dias: number | null
  data_inicio: string | null
  data_fim: string | null
  candles: number | null
  trades: number | null
  taxa_acerto: number | null
  retorno_pct: number | null
  fator_lucro: number | null
  drawdown_max_pct: number | null
  r_medio: number | null
  aprovado: boolean
  motivo: string | null
  status: string
  criado_em: string
}

export interface BacktestsBot { bot_id: number; em_andamento: boolean; pode_ativar: boolean; motivo: string; backtests: Backtest[] }

export interface HipoteseViva {
  chave?: string
  nome: string
  vies: 'bull' | 'bear'
  fase: string
  probabilidade_madura: number
  nascimento?: string
  idade_passos?: number
  testes?: number
  alvos_batidos?: number
  invalidacao?: number | null
  alvos?: number[]
  status?: string
}

export interface Superciclo {
  estado: string
  direcao?: string
  leitura?: string
  fase_ciclo?: string
  ath?: number
  topo?: number
  fundo_perna?: number
  minimo?: number
  extensao_log?: number
  extensao_vs_ciclo_anterior?: number | null
  meses_desde_fundo?: number
  meses_desde_topo?: number
  recuo_log?: number
  retracao_log_minimo?: number | null
  retracao_log_preco?: number | null
  recuperacao_log?: number
  queda_pct?: number
  queda_desde_ath_pct?: number
  criterios_terminal?: Record<string, boolean>
}

export interface Trader {
  par: string
  ts: number
  data: string
  preco: number
  direcao: 'buy' | 'sell' | 'hold'
  prob_bull: number
  prob_bear: number
  superciclo: Superciclo
  subordinado: { direcao: string; prob_bull: number; prob_bear: number }
  n_vivas: number
  primaria: HipoteseViva | null
  vivas: HipoteseViva[]
  ciclo: { prob_bull: number; prob_bear: number; direcao: string; primaria: string | null; exaurido: { bull: boolean; bear: boolean } }
  ciclos_fechados?: { topo: number; ts_topo: number; fundo: number; ts_fundo: number; fundo_anterior: number; ts_fundo_anterior: number }[]
  ultimo_candle?: number
  erro?: string
}

export interface GrauMestre {
  timeframe?: string
  desde?: string
  fase: string
  direcao?: string
  prob_bull?: number
  prob_bear?: number
  primario?: Cenario | null
  cenarios: Cenario[]
  pivots: Pivot[]
  erro?: string
  regime?: unknown
}

export interface Trava {
  id?: number
  grau: string
  timeframe?: string
  cenario?: Cenario
  vies: string
  fase: string
  invalidacao: number | null
  alvos: number[]
  travada_em?: string
  preco_na_trava?: number
  status?: string
  motivo?: string
}

export interface Mestre {
  par: string
  inicio: string
  fim: string
  preco: number
  graus: Record<string, GrauMestre>
  trava: Trava | null
  trader?: Trader
}

export interface Dial {
  preco: number
  barreira: { preco: number; fontes: string[]; peso?: number } | null
  suporte: { preco: number; fontes: string[]; peso?: number } | null
  exaustao: { score: number; confluencias: number; componentes?: Record<string, number | null> }
  elliott: Record<string, unknown>
  superciclo?: Superciclo
  impulso_de_alta: boolean
  recomendacao: string
  niveis: { preco: number; fonte: string; peso: number }[]
  erro?: string
}

export interface StatusGeral {
  bots: Record<string, EstadoExecutor>
  servicos: { market_data: Record<string, unknown>; telegram: boolean }
}

export interface LinhaAlavancagem {
  alavancagem: number
  distancia_liquidacao_pct: number
  stop_maximo_pct: number
}

export interface OpcoesAlavancagem {
  opcoes: number[]
  margem: string
  margem_manutencao: number
  folga: number
  tabela: LinhaAlavancagem[]
}

export interface ZonaPlano {
  preco: number
  peso: number
  fontes: string[]
  distancia_pct: number
}

export interface Plano {
  par: string
  ts: number
  preco: number
  estado: string
  modo: string
  modo_descricao: string
  direcao_grau_maior: 'buy' | 'sell' | 'hold'
  risco_permitido: number
  teto_hedge: number
  pode_comprar: boolean
  pode_vender: boolean
  graus: Record<string, Record<string, unknown>>
  barreira: { preco: number; peso: number; fontes: string[] } | null
  suporte: { preco: number; peso: number; fontes: string[] } | null
  zonas_compra: ZonaPlano[]
  zonas_venda: ZonaPlano[]
  exaustao: { score: number; confluencias: number; confirmada: boolean; componentes?: Record<string, number> }
  superciclo: Superciclo
  leituras: { fonte: string; vies: string; forca: number; acao: string; motivo: string; erro?: string | null }[]
  niveis: { preco: number; fonte: string; peso: number; tipo: string; rotulo?: string }[]
  motivo: string
  erro?: string
}

/** Máquina de rompimento do modo inverse (core/inverse_rompimento.py). */
export interface RompimentoInverse {
  estado: string
  descricao: string
  contagem: number
  nivel_rompido: number | null
  alvo: number | null
  fonte_alvo: string | null
  stop: number | null
  candles_espera: number
  reteste: { contratos: number; preco_entrada: number; fracao: number } | null
  ultimo_evento: string | null
  pnl_reteste_btc: number | null
}

export interface GradeInverseResumo {
  low: number
  high: number
  fracao_aberta: number
  contratos: number
  btc_realizado: number
  pnl_aberto_btc: number
  ciclos: number
}

export interface InverseEstado {
  range: { low: number | null; high: number | null; status: string | null; motivo: string | null }
  estado: { grade: GradeInverseResumo | null; posicao: unknown; rompimento?: RompimentoInverse } | null
  ultima_decisao: { acao: string; motivo: string } | null
}

export interface PropostaRange {
  preco: number
  proposta: { valido: boolean; low?: number; high?: number; motivo: string } | null
  elliott_primario: { nome?: string; fase?: string; vies?: string; alvos?: number[]; invalidacao?: number } | null
}

/** Jogo do range (GET /api/range/contexto) */
export interface NiveisPerfil { inicio: number; poc: number; val: number; vah: number; minima: number; maxima: number; blocos: number }
export interface PerfilDia extends NiveisPerfil { sessoes: Record<string, NiveisPerfil> }
export interface PlanoRange {
  lado: number; jogada: string; niveis: number[]; stop: number; alvo1: number; alvo2: number; rr: number; motivo: string
}
export interface RangeContexto {
  par: string
  preco: number
  ate_ms: number | null
  range: { val: number; poc: number; vah: number; minima: number; maxima: number; largura_pct: number | null; pocs_diarios: number[]; dias: number; valido: boolean } | null
  perfis: PerfilDia[]
  hoje: PerfilDia | null
  naked_pocs: { preco: number; dia_ms: number }[]
  toques: { val: number | null; vah: number | null }
  aceitacao: number
  long_short: { atual: number | null; mediana_30d: number | null; presos_no_val: boolean | null; presos_no_vah: boolean | null } | null
  plano: PlanoRange | null
  barrado: PlanoRange | null
  motivo: string
}

/** Mesa de posições (GET /posicoes/abertas) */
export interface PosicaoAberta {
  id: number
  bot_id: number
  bot: string
  estrategia: string | null
  modo: string
  par: string
  timeframe: string | null
  direcao: string
  quantidade: number
  quantidade_inicial: number
  preco_entrada: number
  preco: number | null
  sl: number | null
  sl_inicial: number | null
  tp: number | null
  pnl_aberto: number | null
  pnl_parcial: number
  pnl_total: number | null
  r_corrido: number | null
  zero_a_zero: boolean
  aberto_em: string | null
  motivo_entrada: string | null
  cenario: string | null
  rodando: boolean
  escada: { pendentes: number; executadas?: number | null; de?: number | null; preco?: number } | null
}
