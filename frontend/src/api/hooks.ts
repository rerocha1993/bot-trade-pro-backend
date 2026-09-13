import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type {
  Backtest, BacktestsBot, BotStatusItem, Decisao, Dial, LogExecucao, Mestre, MultiGrau, NiveisResp, PontoInstitucional,
  OpcoesAlavancagem, Plano, PosicoesResp, PosicaoAberta, RangeContexto, Sentimento, StatusBot, Trader, InverseEstado, PropostaRange,
  TradeirosBacktestResp, TradeirosPlanoResp } from './types'
import { candlesDaApi } from './adapters'

export const useBots = () => useQuery({ queryKey: ['bots'], queryFn: () => api.get<BotStatusItem[]>('/bot-control/'), refetchInterval: 5_000 })

export const useStatusBot = (id: number | null) => useQuery({
  queryKey: ['status-bot', id], enabled: id !== null, refetchInterval: 5_000,
  queryFn: () => api.get<StatusBot>(`/status/bots/${id}`),
})

/**
 * Busca de TODOS os robôs sem deixar um com erro esvaziar os outros. Com Promise.all, o 500 do robô 10 rejeitava
 * a busca inteira e a visão geral mostrava "sem posição" e "ciclo 0" para todos — inclusive o robô que estava
 * comprado. Só falha se nenhum robô responder.
 */
async function porRobo<T>(ids: number[], buscar: (id: number) => Promise<T>): Promise<T[]> {
  const r = await Promise.allSettled(ids.map(buscar))
  const ok = r.filter((x): x is PromiseFulfilledResult<Awaited<T>> => x.status === 'fulfilled').map((x) => x.value)
  if (!ok.length && r.length) throw (r[0] as PromiseRejectedResult).reason
  return ok
}

export const useDetalhes = (ids: number[]) => useQuery({
  queryKey: ['bots-detalhe', ids], enabled: ids.length > 0, refetchInterval: 5_000,
  queryFn: () => porRobo(ids, (id) => api.get<StatusBot>(`/status/bots/${id}`)),
})

export const useFechadas = (ids: number[], limite = 300) => useQuery({
  queryKey: ['fechadas', ids, limite], enabled: ids.length > 0, refetchInterval: 30_000,
  queryFn: () => porRobo(ids, (id) => api.get<PosicoesResp>(`/status/bots/${id}/posicoes`, { status: 'fechada', limite })),
})

export const usePosicoes = (id: number | null, limite = 30) => useQuery({
  queryKey: ['posicoes', id, limite], enabled: id !== null, refetchInterval: 15_000,
  queryFn: () => api.get<PosicoesResp>(`/status/bots/${id}/posicoes`, { limite }),
})

export const useLogs = (ids: number[], limite = 8) => useQuery({
  queryKey: ['logs', ids, limite], enabled: ids.length > 0, refetchInterval: 15_000,
  queryFn: () => porRobo(ids, (id) => api.get<LogExecucao[]>(`/bot-control/${id}/historico`, { limite })),
})

export const useDecisoes = (id: number | null, limite = 30) => useQuery({
  queryKey: ['decisoes', id, limite], enabled: id !== null, refetchInterval: 15_000,
  queryFn: () => api.get<Decisao[]>(`/status/bots/${id}/decisoes`, { limite, detalhes: true }),
})

export const useMultigrau = (par: string, estilo: string, timeframe: string, perfil: string, enabled = true) => useQuery({
  queryKey: ['multigrau', par, estilo, timeframe, perfil], enabled, refetchInterval: 60_000, staleTime: 30_000,
  queryFn: () => api.get<MultiGrau>('/api/elliott/multigrau', { par, estilo, timeframe, perfil }),
})

export const useCandles = (par: string, timeframe: string, limite = 300, composto = false) => useQuery({
  queryKey: ['candles', par, timeframe, limite, composto], refetchInterval: 30_000,
  queryFn: async () => candlesDaApi((await api.get<{ candles: number[][] }>('/status/mercado/candles', { par, timeframe, limite, composto })).candles),
})

export const useHistorico = (par: string, timeframe: '1d' | '1w', limite = 6000, enabled = true) => useQuery({
  queryKey: ['historico', par, timeframe, limite], enabled, staleTime: 10 * 60_000,
  queryFn: async () => candlesDaApi((await api.get<{ candles: number[][] }>('/status/mercado/historico', { par, timeframe, limite })).candles),
})

export const useNiveis = (par: string, timeframe: string, enabled = true) => useQuery({
  queryKey: ['niveis', par, timeframe], enabled, refetchInterval: 60_000, staleTime: 30_000,
  queryFn: () => api.get<NiveisResp>('/status/mercado/niveis', { par, timeframe, limite: 300 }),
})

export const useAlavancagens = () => useQuery({
  queryKey: ['alavancagens'], staleTime: Infinity,
  queryFn: () => api.get<OpcoesAlavancagem>('/bots/opcoes/alavancagem'),
})

export const useSentimento = (par = 'BTCUSDT') => useQuery({
  queryKey: ['sentimento', par], refetchInterval: 60_000, queryFn: () => api.get<Sentimento>('/status/sentimento', { par }),
})

export const useTrader = (par = 'BTCUSDT') => useQuery({
  queryKey: ['trader', par], refetchInterval: 60_000, queryFn: () => api.get<Trader>('/api/elliott/trader', { par }),
})

export const usePlano = (par = 'BTCUSDT') => useQuery({
  queryKey: ['plano', par], refetchInterval: 60_000, staleTime: 30_000,
  queryFn: () => api.get<Plano>('/api/elliott/plano', { par }),
})

export const useMestre = (par = 'BTCUSDT') => useQuery({
  queryKey: ['mestre', par], refetchInterval: 5 * 60_000, staleTime: 60_000, queryFn: () => api.get<Mestre>('/api/elliott/mestre', { par }),
})

export const useDial = (par = 'BTCUSDT') => useQuery({
  queryKey: ['dial', par], refetchInterval: 5 * 60_000, staleTime: 60_000, queryFn: () => api.get<Dial>('/inverse/dial', { par }),
})

export const usePontos = (par: string, preco: number | undefined, faixa: number) => useQuery({
  queryKey: ['pontos', par, faixa, preco ? Math.round(preco) : null], enabled: !!preco, refetchInterval: 60_000,
  queryFn: () => api.get<PontoInstitucional[]>('/pontos-institucionais', { par, preco_atual: preco, faixa_pct: faixa }),
})

export const useBacktests = (par?: string) => useQuery({
  queryKey: ['backtests', par ?? ''], refetchInterval: 20_000, queryFn: () => api.get<Backtest[]>('/backtest/', { par, limite: 100 }),
})

export const useBacktestsBot = (id: number | null) => useQuery({
  queryKey: ['backtests-bot', id], enabled: id !== null, refetchInterval: 15_000, queryFn: () => api.get<BacktestsBot>(`/backtest/bots/${id}`),
})

/** Ativar / parar bot com tratamento do gate de backtest (409). */
export function useControleBot() {
  const qc = useQueryClient()
  const invalidar = () => { qc.invalidateQueries({ queryKey: ['bots'] }); qc.invalidateQueries({ queryKey: ['bots-detalhe'] }); qc.invalidateQueries({ queryKey: ['status-bot'] }) }
  const ativar = useMutation({ mutationFn: ({ id, forcar }: { id: number; forcar?: boolean }) => api.post(`/bot-control/${id}/ativar`, { forcar: !!forcar }), onSuccess: invalidar })
  const parar = useMutation({ mutationFn: (id: number) => api.post(`/bot-control/${id}/desativar`), onSuccess: invalidar })
  const trailing = useMutation({ mutationFn: ({ id, on }: { id: number; on: boolean }) => api.post(`/bots/${id}/${on ? 'ativar_trailing' : 'desativar_trailing'}`), onSuccess: invalidar })
  const backtest = useMutation({ mutationFn: ({ id, dias }: { id: number; dias?: number }) => api.post(`/backtest/bots/${id}`, { dias }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['backtests'] }); qc.invalidateQueries({ queryKey: ['backtests-bot'] }) } })
  return { ativar, parar, trailing, backtest }
}

export const useInverseEstado = (id: number | null) => useQuery({
  queryKey: ['inverse-estado', id], enabled: id !== null, refetchInterval: 30_000,
  queryFn: () => api.get<InverseEstado>(`/inverse/${id}/estado`),
})

/** A proposta roda a contagem mestre no diário: é cara, então fica em cache por minutos. */
export const usePropostaRange = (id: number | null) => useQuery({
  queryKey: ['inverse-proposta', id], enabled: id !== null, staleTime: 5 * 60_000, refetchInterval: 15 * 60_000,
  queryFn: () => api.get<PropostaRange>(`/inverse/${id}/range/proposta`),
})

/** Aprovar / cancelar o range. A API recusa com os motivos; `forcar` só vence avisos, nunca bloqueios. */
export function useRangeInverse() {
  const qc = useQueryClient()
  const invalidar = () => {
    qc.invalidateQueries({ queryKey: ['inverse-estado'] })
    qc.invalidateQueries({ queryKey: ['status-bot'] })
    qc.invalidateQueries({ queryKey: ['bots-detalhe'] })
  }
  const aprovar = useMutation({
    mutationFn: ({ id, low, high, forcar }: { id: number; low: number; high: number; forcar?: boolean }) =>
      api.post(`/inverse/${id}/range/aprovar`, { low, high, forcar: !!forcar }),
    onSuccess: invalidar,
  })
  const cancelar = useMutation({
    mutationFn: ({ id, forcar }: { id: number; forcar?: boolean }) => api.post(`/inverse/${id}/range/cancelar`, { forcar: !!forcar }),
    onSuccess: invalidar,
  })
  return { aprovar, cancelar }
}

/** Portal Tradeiros: sem data = ao vivo (o backend refaz a cada 5 min); com data = replay daquele dia. */
export const useTradeirosPlano = (data: string | null) => useQuery({
  queryKey: ['tradeiros-plano', data], refetchInterval: data ? false : 60_000,
  queryFn: () => api.get<TradeirosPlanoResp>('/api/tradeiros/plano', data ? { data } : {}),
})

export const useTradeirosBacktest = () => useQuery({
  queryKey: ['tradeiros-backtest'], refetchInterval: 300_000,
  queryFn: () => api.get<TradeirosBacktestResp>('/api/tradeiros/backtest'),
})

export const useRangeContexto = (par = 'BTCUSDT') => useQuery({
  queryKey: ['range-contexto', par], refetchInterval: 60_000,
  queryFn: () => api.get<RangeContexto>('/api/range/contexto', { par }),
})

export const usePosicoesAbertas = () => useQuery({
  queryKey: ['posicoes-abertas'], refetchInterval: 10_000,
  queryFn: () => api.get<PosicaoAberta[]>('/posicoes/abertas'),
})
