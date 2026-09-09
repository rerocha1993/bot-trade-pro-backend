import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { useAlavancagens, useBacktestsBot, useControleBot } from '../api/hooks'
import type { Bot } from '../api/types'
import { Header, Page } from '../components/Layout'
import { Btn, Card, Err, Field, Loading, Seg, Switch } from '../components/ui'
import { hora, pct } from '../lib/format'
import { analisarPlano, perfilSaida } from '../lib/perfil-saida'

const PADRAO: Partial<Bot> = {
  nome: '', ativo: 'BTCUSDT', timeframe: '15m', estilo_trade: 'daytrade', confluencia_tipo: 'conservador', modo_execucao: 'simulador',
  alavancagem: 1, position_mode: 'one-way', margin_mode: 'isolated', subconta: 'principal', tipo_entrada: 'limite', limite_candles_espera: 3,
  delay_execucao: 10, categoria: 'linear', estrategia: 'elliott', exchange: 'bybit', quantidade: 0.001,
  banca: 1000, risco_pct: 0.01, max_alocacao_pct: 0.25, min_quantidade: 0.001, max_quantidade: 0.05, max_trades_dia: 8, max_perda_dia_pct: 0.03,
  prob_sucesso_minima: 0.45, rr_minimo: 0, taxa_historica_minima: 0,
  usar_elliott: true, usar_fibonacci: true, usar_tpo: true, usar_volume_profile: false, usar_vwap: true, usar_orderflow: false, usar_orderblock: true,
  usar_sentimento: true, usar_tendencia_macro: true, usar_api_macro: false, usar_filtro_regime: true, usar_websocket: false,
  usar_trailing_stop: true, ativador_trailing: 0.010, distancia_trailing: 0.007, sl_tipo: 'percentual', sl_variacao_pct: 1.0, saida_estrutural: false,
  usar_saida_escalonada: true, saida_escalonada: '50/30, 75/30, 90/25', mover_stop_para_entrada: true,
  ativo_bot: false,
}

const SWITCHES: [keyof Bot, string, string][] = [
  ['usar_elliott', 'Elliott', 'sempre ligado'], ['usar_fibonacci', 'Fibonacci', ''], ['usar_tpo', 'TPO', 'cesta TradingView'], ['usar_volume_profile', 'Volume Profile', ''],
  ['usar_vwap', 'VWAP', ''], ['usar_orderflow', 'Order Flow', 'delta e imbalance'], ['usar_orderblock', 'Order Block', ''],
  ['usar_sentimento', 'Filtro de sentimento', 'contrário: euforia bloqueia compras'], ['usar_tendencia_macro', 'Alinhamento macro', 'grau superior'],
  ['usar_filtro_regime', 'Filtro de regime', 'bloqueia compressão/serrilhado'], ['usar_api_macro', 'Calendário macro', 'Forex Factory'], ['usar_websocket', 'Websocket', 'trades em tempo real (scalp)'],
  ['saida_estrutural', 'Saída estrutural', 'fecha quando a estrutura vira'],
]

const NUM: (keyof Bot)[] = ['alavancagem', 'limite_candles_espera', 'delay_execucao', 'quantidade', 'banca', 'risco_pct', 'max_alocacao_pct', 'min_quantidade', 'max_quantidade',
  'max_trades_dia', 'max_perda_dia_pct', 'prob_sucesso_minima', 'rr_minimo', 'taxa_historica_minima', 'ativador_trailing', 'distancia_trailing', 'sl_variacao_pct', 'short_base_max', 'folga_stop']

export default function BotForm() {
  const params = useParams()
  const id = params.id ? Number(params.id) : null
  const nav = useNavigate()
  const qc = useQueryClient()
  const existente = useQuery({ queryKey: ['bot', id], enabled: id !== null, queryFn: () => api.get<Bot>(`/bots/${id}`) })
  const gate = useBacktestsBot(id)
  const alav = useAlavancagens()
  const ctl = useControleBot()
  const [f, setF] = useState<Partial<Bot>>(PADRAO)
  const [erro, setErro] = useState<string | null>(null)
  useEffect(() => { if (existente.data) setF({ ...PADRAO, ...existente.data }) }, [existente.data])

  const salvar = useMutation({
    mutationFn: async () => {
      const body: Record<string, unknown> = { ...f }
      for (const k of NUM) if (body[k] !== undefined && body[k] !== null && body[k] !== '') body[k] = Number(body[k])
      delete body.id
      return id === null ? api.post<Bot>('/bots/', undefined, body) : api.put<Bot>(`/bots/${id}`, undefined, body)
    },
    onSuccess: (bot) => { qc.invalidateQueries({ queryKey: ['bots'] }); qc.invalidateQueries({ queryKey: ['bot', bot.id] }); qc.invalidateQueries({ queryKey: ['status-bot', bot.id] }); nav(`/bots/${bot.id}`) },
    onError: (e) => setErro(e instanceof Error ? e.message : String(e)),
  })

  const set = (k: keyof Bot, v: unknown) => setF((s) => ({ ...s, [k]: v }))
  const num = (k: keyof Bot, label: string, step = 'any', span2 = false) => (
    <Field label={label} span2={span2}><input type="number" step={step} value={f[k] === null || f[k] === undefined ? '' : String(f[k])} onChange={(e) => set(k, e.target.value)} /></Field>
  )
  const txt = (k: keyof Bot, label: string, mono = true) => (
    <Field label={label}><input value={String(f[k] ?? '')} onChange={(e) => set(k, e.target.value)} style={mono ? undefined : { fontFamily: 'var(--sans)' }} /></Field>
  )

  const perfil = perfilSaida(f.estilo_trade)
  const plano = analisarPlano(f.saida_escalonada)
  const ativador = Number(f.ativador_trailing ?? 0)
  const distancia = Number(f.distancia_trailing ?? 0)
  const trailingTravaPrejuizo = ativador > 0 && distancia > 0 && ativador <= distancia

  if (id !== null && existente.isPending) return <><Header titulo="Editar robô" /><Page><Loading /></Page></>
  if (id !== null && existente.isError) return <><Header titulo="Editar robô" /><Page><Err e={existente.error} /></Page></>

  return (
    <>
      <Header titulo={id === null ? 'Novo robô' : 'Editar robô'} subtitulo={`${f.nome || 'sem nome'} · ${f.estilo_trade} ${f.timeframe} · ${f.ativo}`} par={f.ativo} actions={
        <div style={{ display: 'flex', gap: 8 }}>
          <Btn kind="ghost" onClick={() => nav(id === null ? '/' : `/bots/${id}`)}>Cancelar</Btn>
          <Btn kind="primary" onClick={() => { setErro(null); salvar.mutate() }} disabled={salvar.isPending || !f.nome}>{salvar.isPending ? 'salvando…' : 'Salvar robô'}</Btn>
        </div>
      } />
      <Page>
        {erro && <div className="err">{erro}</div>}
        {id !== null && gate.data && (
          <div className={gate.data.pode_ativar ? 'info' : 'warn'} style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <span style={{ flex: 1 }}>
              Backtest de validação: {gate.data.motivo}
              {gate.data.em_andamento && ' · rodando agora'}
              {gate.data.backtests[0] && ` · último ${hora(gate.data.backtests[0].criado_em, true)}: ${gate.data.backtests[0].aprovado ? 'aprovado' : 'reprovado'} (${gate.data.backtests[0].trades ?? 0} trades, PF ${gate.data.backtests[0].fator_lucro ?? '—'})`}
            </span>
            <Btn small onClick={() => ctl.backtest.mutate({ id })} disabled={ctl.backtest.isPending || gate.data.em_andamento}>Rodar backtest</Btn>
          </div>
        )}
        <div className="grid" style={{ gridTemplateColumns: 'repeat(2, minmax(340px, 1fr))', alignItems: 'start' }}>
          <Card title="Identificação" pad={false}>
            <div className="form-grid">
              {txt('nome', 'Nome', false)}
              {txt('ativo', 'Par')}
              <Field label="Timeframe"><select value={String(f.timeframe)} onChange={(e) => set('timeframe', e.target.value)}>{['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '1d'].map((t) => <option key={t}>{t}</option>)}</select></Field>
              <div><span className="label">Estilo</span><Seg value={String(f.estilo_trade)} options={['scalping', 'daytrade', 'swing']} onChange={(v) => set('estilo_trade', v)} /></div>
              <div className="span2"><span className="label">Perfil de confluência</span><Seg value={String(f.confluencia_tipo)} options={['conservador', 'turbo']} onChange={(v) => set('confluencia_tipo', v)} /></div>
              <div><span className="label">Estratégia</span><Seg value={String(f.estrategia)} options={['elliott', 'inverse_range']} onChange={(v) => set('estrategia', v)} labels={{ inverse_range: 'inverse (grade)' }} /></div>
              <div><span className="label">Categoria</span><Seg value={String(f.categoria)} options={['linear', 'inverse']} onChange={(v) => set('categoria', v)} labels={{ linear: 'linear (USDT)', inverse: 'inverse (BTC)' }} /></div>
            </div>
          </Card>

          <Card title="Execução" pad={false}>
            <div className="form-grid">
              <div className="span2">
                <span className="label">Modo</span>
                <Seg value={String(f.modo_execucao)} options={['simulador', 'demo', 'testnet', 'real']}
                  onChange={(v) => set('modo_execucao', v)} labels={{ demo: 'demo (conta oficial)' }} />
                {f.modo_execucao === 'demo' && (
                  <div className="mono muted" style={{ fontSize: 10.5, marginTop: 6, lineHeight: 1.5 }}>
                    Demo Trading roda dentro da sua conta oficial da Bybit, com dinheiro fictício e a infraestrutura real.
                    A chave é criada em bybit.com com o modo Demo Trading ligado, e vai nas variáveis terminadas em _DEMO.
                  </div>
                )}
              </div>
              <div><span className="label">Tipo de entrada</span><Seg value={String(f.tipo_entrada)} options={['limite', 'mercado']} onChange={(v) => set('tipo_entrada', v)} labels={{ limite: 'limitada (post-only)', mercado: 'a mercado' }} /></div>
              {num('limite_candles_espera', 'Candles até cancelar a limitada', '1')}
              <Field label="Alavancagem">
                <select value={String(f.alavancagem ?? 1)} onChange={(e) => set('alavancagem', Number(e.target.value))}>
                  {(alav.data?.opcoes ?? [1, 2, 3, 5, 10, 20, 30, 50, 100]).map((a) => <option key={a} value={a}>{a}x</option>)}
                </select>
              </Field>
              {num('delay_execucao', 'Intervalo entre ciclos (s)', '1')}
              <Field label="Modo de posição"><select value={String(f.position_mode)} onChange={(e) => set('position_mode', e.target.value)}><option value="one-way">one-way</option><option value="hedged">hedged</option></select></Field>
              <Field label="Margem"><select value={String(f.margin_mode)} onChange={(e) => set('margin_mode', e.target.value)}><option value="isolated">isolated</option><option value="cross">cross</option></select></Field>
              {txt('subconta', 'Subconta')}
              {num('quantidade', 'Quantidade fixa (fallback se banca = 0)', '0.0001')}
              {(() => {
                const a = Number(f.alavancagem ?? 1)
                const linha = alav.data?.tabela.find((t) => t.alavancagem === a)
                if (!linha || a <= 1) return null
                const cor = a >= 50 ? 'var(--red)' : a >= 20 ? 'var(--amber)' : 'var(--muted)'
                const n = (v: number) => v.toFixed(2).replace('.', ',')
                return (
                  <div className="span2 mono" style={{ fontSize: 11, color: cor, borderLeft: `2px solid ${cor}`, paddingLeft: 8, lineHeight: 1.5 }}>
                    Com {a}x a posição é liquidada se o preço andar {n(linha.distancia_liquidacao_pct)}% contra.
                    O robô recusa a entrada quando o stop passa de {n(linha.stop_maximo_pct)}%, porque a liquidação
                    chegaria antes do stop. A alavancagem não aumenta o tamanho da posição: o tamanho vem do risco por trade.
                  </div>
                )
              })()}
            </div>
          </Card>

          <Card title="Risco" pad={false}>
            <div className="form-grid">
              {num('banca', 'Banca (USDT)', '0.01')}
              {num('risco_pct', 'Risco por trade (fração, 0,01 = 1%)', '0.001')}
              {num('max_alocacao_pct', 'Alocação máxima (fração)', '0.01')}
              {num('max_perda_dia_pct', 'Perda máxima por dia (fração)', '0.005')}
              {num('min_quantidade', 'Quantidade mínima', '0.0001')}
              {num('max_quantidade', 'Quantidade máxima', '0.0001')}
              {num('max_trades_dia', 'Trades por dia', '1')}
              {num('prob_sucesso_minima', 'Probabilidade calibrada mínima', '0.05')}
              {num('rr_minimo', 'Risco:retorno mínimo (0 = padrão)', '0.1')}
              {num('taxa_historica_minima', 'Modo seletivo: acerto histórico mínimo (0 = off)', '0.05')}
            </div>
          </Card>

          <Card title="Indicadores e filtros" pad={false}>
            <div style={{ padding: '6px 14px 14px' }}>
              {SWITCHES.map(([k, l, n]) => (
                <div className="sw-row" key={String(k)}>
                  <span className="t" style={{ color: k === 'usar_elliott' ? 'var(--muted)' : undefined }}>{l}</span>
                  <span className="n">{n}</span>
                  <Switch on={k === 'usar_elliott' ? true : !!f[k]} disabled={k === 'usar_elliott'} onChange={(v) => set(k, v)} />
                </div>
              ))}
            </div>
          </Card>

          <Card title="Stop e trailing" pad={false} right={
            <Btn small kind="ghost" onClick={() => { set('ativador_trailing', perfil.ativador_trailing); set('distancia_trailing', perfil.distancia_trailing) }}>usar perfil {f.estilo_trade}</Btn>
          }>
            <div className="form-grid" style={{ alignItems: 'end' }}>
              <Field label="Tipo de stop"><select value={String(f.sl_tipo)} onChange={(e) => set('sl_tipo', e.target.value)}><option value="percentual">percentual</option><option value="atr">ATR</option><option value="elliott">invalidação de Elliott</option></select></Field>
              {num('sl_variacao_pct', 'Stop (% ou múltiplo de ATR)', '0.1')}
              {num('ativador_trailing', 'Trailing ativa após (fração)', '0.001')}
              {num('distancia_trailing', 'Distância do trailing (fração)', '0.0005')}
              <div className="span2 sw-row" style={{ borderBottom: 0 }}>
                <span className="t">Trailing automático<br /><span className="muted" style={{ fontSize: 11 }}>o stop sobe junto com o preço e nunca desce</span></span>
                <Switch on={!!f.usar_trailing_stop} onChange={(v) => set('usar_trailing_stop', v)} />
              </div>
              <div className="span2 muted" style={{ fontSize: 11 }}>
                {trailingTravaPrejuizo
                  ? <span className="warn-txt">Ativa com {pct(ativador, 2)} de avanço mas cola a {pct(distancia, 2)} do preço: o stop nasceria abaixo da entrada. O ativador tem que ser maior que a distância.</span>
                  : <>Liga depois de {pct(ativador, 2)} a favor e segue a {pct(distancia, 2)} do preço, travando pelo menos {pct(ativador - distancia, 2)} de lucro. Sugerido para {f.estilo_trade}: {pct(perfil.ativador_trailing, 2)} / {pct(perfil.distancia_trailing, 2)}.</>}
              </div>
            </div>
          </Card>

          <Card title="Saída escalonada" pad={false} right={
            <Btn small kind="ghost" onClick={() => set('saida_escalonada', perfil.saida_escalonada)}>usar perfil {f.estilo_trade}</Btn>
          }>
            <div className="form-grid" style={{ alignItems: 'end' }}>
              <div className="span2 sw-row">
                <span className="t">Realizar em pedaços<br /><span className="muted" style={{ fontSize: 11 }}>garante lucro no caminho em vez de tudo ou nada no alvo</span></span>
                <Switch on={!!f.usar_saida_escalonada} onChange={(v) => set('usar_saida_escalonada', v)} />
              </div>
              <div className="span2 sw-row">
                <span className="t">Stop para a entrada na primeira parcial<br /><span className="muted" style={{ fontSize: 11 }}>depois da primeira realização o trade não vira prejuízo</span></span>
                <Switch on={!!f.mover_stop_para_entrada} onChange={(v) => set('mover_stop_para_entrada', v)} />
              </div>
              {txt('saida_escalonada', 'Plano (avanço/fração, em %)')}
              <div className="span2 muted" style={{ fontSize: 11 }}>
                {plano
                  ? <>
                      {plano.map(([av, fr]) => <div key={av}>realiza {pct(fr)} da mão quando o preço andar {pct(av)} do caminho até o alvo</div>)}
                      <div>deixa {pct(1 - plano.reduce((s, [, fr]) => s + fr, 0))} correndo até o alvo (ou até o trailing tirar) — {plano.length + 1} saídas</div>
                    </>
                  : <span className="warn-txt">Plano inválido. Use avanço/fração em %, ex.: 50/30, 75/30, 90/25. As frações precisam somar menos de 100%, para sobrar posição até o alvo.</span>}
                <div style={{ marginTop: 4 }}>Numa mão pequena demais para o mínimo da corretora o plano encolhe sozinho, ou sai tudo no alvo.</div>
              </div>
            </div>
          </Card>

          {f.estrategia === 'inverse_range' && (
            <Card title="Grade inversa" pad={false}>
              <div className="form-grid">
                {num('range_low', 'Fundo do range', '1')}
                {num('range_high', 'Topo do range', '1')}
                {num('short_base_max', 'Short de base máximo (fração)', '0.05')}
                {num('folga_stop', 'Folga acima do topo (fração)', '0.005')}
                <div className="span2 muted" style={{ fontSize: 11 }}>Range proposto e aprovado na tela do robô (rotas /inverse). Estado atual: {String(f.range_status ?? '—')} {f.prob_sucesso_minima !== undefined ? '' : ''}{pct(0) && ''}</div>
              </div>
            </Card>
          )}
        </div>
      </Page>
    </>
  )
}
