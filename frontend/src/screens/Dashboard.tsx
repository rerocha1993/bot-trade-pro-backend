import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../api/client'
import { useBots, useControleBot, useDetalhes, useFechadas, useLogs } from '../api/hooks'
import type { LogExecucao, Posicao, StatusBot } from '../api/types'
import { Header, Page, usePreco } from '../components/Layout'
import { Btn, Card, Empty, Err, KPI, Loading, ModoTag } from '../components/ui'
import { corAcao, corPnl, fmt, fmtSigned, hora, pct, preco, rotuloAcao } from '../lib/format'

type QuedaRede = { kind: 'rede'; id: string; inicio: string; fim: string; inicioMs: number; ciclos: number; robos: Set<string>; timeouts: number }
type Alerta = QuedaRede | (LogExecucao & { nome: string; kind: 'log' })

/**
 * Erro de REDE, não do robô. A ccxt usa a URL como mensagem ("bybit GET https://..."), com ou sem o nome da
 * exceção na frente (NetworkError, RequestTimeout, ExchangeNotAvailable).
 */
export function ehErroDeRede(erro: string | null | undefined): boolean {
  if (!erro) return false
  return /^(NetworkError|RequestTimeout|ExchangeNotAvailable|DDoSProtection)\b/.test(erro) || /^bybit (GET|POST) https?:\/\//.test(erro)
}

function pnlAberto(p: Posicao | null, precoAtual: number | undefined): number | null {
  if (!p || !precoAtual) return null
  return (p.direcao === 'buy' ? precoAtual - p.preco_entrada : p.preco_entrada - precoAtual) * p.quantidade
}

function drawdown(pnls: number[]): number {
  let acc = 0, pico = 0, dd = 0
  for (const p of pnls) { acc += p; pico = Math.max(pico, acc); dd = Math.max(dd, pico - acc) }
  return dd
}

/** Pontos da curva do resultado acumulado de um robô (posições fechadas), já na escala 0–100 do SVG. */
function curva(pnls: number[]): string | null {
  if (pnls.length < 2) return null
  const acc: number[] = [0]
  for (const p of pnls) acc.push(acc[acc.length - 1] + p)
  const mn = Math.min(...acc), mx = Math.max(...acc), faixa = mx - mn || 1
  return acc.map((v, i) => `${((i / (acc.length - 1)) * 100).toFixed(1)},${(92 - ((v - mn) / faixa) * 84).toFixed(1)}`).join(' ')
}

function Stat({ rotulo, valor, cor, linha, mono }: { rotulo: string; valor: string; cor: string; linha: string; mono?: boolean }) {
  return (
    <div style={{ minWidth: 0 }}>
      <div className="muted" style={{ fontSize: 11 }}>{rotulo}</div>
      <div className={mono ? 'mono' : undefined} style={{ fontSize: 15, fontWeight: 500, color: cor }}>{valor}</div>
      <div className="mono" style={{ fontSize: 12, color: 'var(--muted-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={linha}>{linha}</div>
    </div>
  )
}

export default function Dashboard() {
  const bots = useBots()
  const ids = useMemo(() => (bots.data ?? []).map((b) => b.id), [bots.data])
  const detalhes = useDetalhes(ids)
  const fechadas = useFechadas(ids)
  const logs = useLogs(ids, 40)
  const precoQ = usePreco()
  const ctl = useControleBot()
  const [erroCtl, setErroCtl] = useState<{ id: number; msg: string; gate: boolean } | null>(null)

  const porId = useMemo(() => new Map((detalhes.data ?? []).map((d) => [d.bot.id, d])), [detalhes.data])
  const todasFechadas = useMemo(() => {
    const l = (fechadas.data ?? []).flatMap((r) => r.posicoes).filter((p) => p.status === 'fechada' && p.pnl !== null)
    return l.sort((a, b) => (a.fechado_em || '').localeCompare(b.fechado_em || ''))
  }, [fechadas.data])
  const curvaPorBot = useMemo(() => {
    const m = new Map<number, number[]>()
    for (const p of todasFechadas) m.set(p.bot_id, [...(m.get(p.bot_id) ?? []), p.pnl || 0])
    return m
  }, [todasFechadas])
  const hoje = new Date().toISOString().slice(0, 10)
  const kpi = useMemo(() => {
    const pnlDia = todasFechadas.filter((p) => (p.fechado_em || '').startsWith(hoje)).reduce((a, p) => a + (p.pnl || 0), 0)
    const pnlTotal = todasFechadas.reduce((a, p) => a + (p.pnl || 0), 0)
    const ganhos = todasFechadas.filter((p) => (p.pnl || 0) > 0)
    const perdas = todasFechadas.filter((p) => (p.pnl || 0) <= 0)
    const somaPerdas = Math.abs(perdas.reduce((a, p) => a + (p.pnl || 0), 0))
    const fl = somaPerdas ? ganhos.reduce((a, p) => a + (p.pnl || 0), 0) / somaPerdas : null
    const tradesHoje = todasFechadas.filter((p) => (p.aberto_em || '').startsWith(hoje)).length
    const limite = (detalhes.data ?? []).reduce((a, d) => a + (d.bot.max_trades_dia || 0), 0)
    const banca = (detalhes.data ?? []).reduce((a, d) => a + Number(d.bot.banca || 0), 0)
    const dd = drawdown(todasFechadas.map((p) => p.pnl || 0))
    return { pnlDia, pnlTotal, taxa: todasFechadas.length ? ganhos.length / todasFechadas.length : null, fl, n: todasFechadas.length, tradesHoje, limite, dd, ddPct: banca ? dd / banca : null }
  }, [todasFechadas, detalhes.data, hoje])
  const rodando = (bots.data ?? []).filter((b) => b.rodando).length

  const alertas = useMemo(() => {
    const nomes = new Map((bots.data ?? []).map((b) => [b.id, b.nome]))
    const l: (LogExecucao & { nome: string })[] = (logs.data ?? []).flat().map((x) => ({ ...x, nome: nomes.get(x.bot_id) || `bot ${x.bot_id}` }))
    l.sort((a, b) => (b.data_execucao || '').localeCompare(a.data_execucao || ''))
    // uma queda de rede derruba TODOS os robôs no mesmo minuto: vira UM evento em âmbar, com duração e ciclos
    // perdidos, em vez de uma parede vermelha que esconde o que de fato aconteceu
    const out: Alerta[] = []
    for (const a of l) {
      if (!ehErroDeRede(a.erro)) { out.push({ kind: 'log', ...a }); continue }
      const t = Date.parse(a.data_execucao)
      const grupo = out.find((x): x is QuedaRede => x.kind === 'rede' && x.inicioMs - t <= 5 * 60_000)
      if (grupo) {
        grupo.inicioMs = t; grupo.inicio = a.data_execucao; grupo.ciclos += 1; grupo.robos.add(a.nome)
        if (/RequestTimeout/.test(a.erro ?? '')) grupo.timeouts += 1
        continue
      }
      out.push({ kind: 'rede', id: `rede-${a.id}`, fim: a.data_execucao, inicio: a.data_execucao, inicioMs: t, ciclos: 1,
                 robos: new Set([a.nome]), timeouts: /RequestTimeout/.test(a.erro ?? '') ? 1 : 0 })
    }
    return out.slice(0, 12)
  }, [logs.data, bots.data])

  const acionar = async (b: StatusBot | undefined, id: number, ligado: boolean, forcar = false) => {
    setErroCtl(null)
    try {
      if (ligado) await ctl.parar.mutateAsync(id)
      else await ctl.ativar.mutateAsync({ id, forcar })
    } catch (e) {
      const gate = e instanceof ApiError && e.status === 409
      setErroCtl({ id, msg: e instanceof Error ? e.message : String(e), gate })
    }
    void b
  }

  return (
    <>
      <Header eyebrow="Visão geral" titulo="Robôs em operação" actions={<Link to="/bots/novo" className="btn primary">Novo robô</Link>} />
      <Page>
        <div className="grid" style={{ gridTemplateColumns: 'repeat(4, minmax(0, 1fr))' }}>
          <KPI l="P&L do dia" v={fmtSigned(kpi.pnlDia)} color={corPnl(kpi.pnlDia)} sub={`USDT · ${kpi.tradesHoje} de ${kpi.limite || '—'} trades`} />
          <KPI l="P&L acumulado" v={fmtSigned(kpi.pnlTotal)} color={kpi.pnlTotal < 0 ? 'var(--red)' : 'var(--text)'} sub={`USDT · ${kpi.n} trades`} />
          <KPI l="Taxa de acerto" v={kpi.taxa === null ? '—' : pct(kpi.taxa, 1)} sub={kpi.fl === null ? 'sem perdas registradas' : `fator de lucro ${fmt(kpi.fl, 2)}`} />
          <KPI l="Drawdown máximo" v={kpi.ddPct === null ? fmt(-kpi.dd, 0) : `−${pct(kpi.ddPct, 1)}`} color="var(--red)" sub={`${rodando} de ${bots.data?.length ?? 0} robôs rodando`} />
        </div>

        {bots.isPending && <Loading />}
        {bots.isError && <Err e={bots.error} />}
        {bots.data && !bots.data.length && <Card><Empty>Nenhum robô cadastrado. <Link to="/bots/novo">Criar o primeiro</Link>.</Empty></Card>}
        <div className="grid" style={{ gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' }}>
          {(bots.data ?? []).map((b) => {
            const d = porId.get(b.id)
            const pos = d?.posicao ?? null
            const dec = d?.ultima_decisao ?? null
            const aberto = pnlAberto(pos, precoQ.data?.preco)
            const ligado = b.rodando || b.ativo
            const pnls = curvaPorBot.get(b.id) ?? []
            const pts = curva(pnls)
            const resultado = pnls.reduce((a, p) => a + p, 0)
            const pendente = d?.estado?.ordem_pendente as { preco?: number } | undefined
            const protecao = pos
              ? `SL ${preco(pos.sl)} · TP ${preco(pos.tp)}${pos.trailing_ativo ? ' · trailing' : ''}`
              : pendente ? `ordem limitada pendente a ${preco(Number(pendente.preco))}`
                : b.rodando ? `ciclo ${d?.estado?.ciclos ?? 0} · ${d?.estado?.ultimo_ciclo ? hora(d.estado.ultimo_ciclo) : '—'}`
                  : `parado${b.ultima_execucao ? ' · ' + hora(b.ultima_execucao, true) : ''}`
            return (
              <div className="card" key={b.id} style={{ padding: 24, opacity: ligado ? 1 : 0.55 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span className={'dot' + (b.rodando ? ' pulse' : '')} style={{ width: 8, height: 8, flex: '0 0 8px', background: b.rodando ? 'var(--acc)' : 'var(--dim)' }} />
                  <div style={{ flex: '1 1 auto', minWidth: 0 }}>
                    <div style={{ fontSize: 17, fontWeight: 500 }}>{b.nome}</div>
                    <div className="muted" style={{ fontSize: 12 }}>{b.estilo_trade} · {b.timeframe} · {b.confluencia_tipo} · {b.ativo_nome}</div>
                  </div>
                  <ModoTag modo={b.modo_execucao} />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12, marginTop: 22 }}>
                  <Stat rotulo="Posição" valor={pos ? rotuloAcao(pos.direcao) : 'Sem posição'} cor={pos ? corAcao(pos.direcao) : 'var(--muted)'}
                    linha={pos ? `entrada ${preco(pos.preco_entrada)} · ${fmt(pos.quantidade, 4)}` : '—'} />
                  <Stat mono rotulo={pos ? 'P&L aberto' : 'P&L do dia'} valor={pos ? (aberto === null ? '—' : fmtSigned(aberto)) : fmtSigned(b.pnl_dia ?? 0)}
                    cor={corPnl(pos ? aberto : b.pnl_dia ?? 0)} linha={`USDT · total ${fmtSigned(resultado)}`} />
                  <Stat rotulo="Última decisão" valor={dec ? rotuloAcao(dec.acao) : '—'} cor={corAcao(dec?.acao)}
                    linha={dec ? `${dec.fase_onda ?? '—'} · ${dec.probabilidade !== null ? pct(dec.probabilidade) : '—'}` : 'sem decisões'} />
                </div>

                <div className="spark" title={pnls.length ? `resultado acumulado de ${pnls.length} trades fechados` : 'sem trades fechados'}>
                  <svg viewBox="0 0 100 100" preserveAspectRatio="none">
                    {pts
                      ? <polyline points={pts} fill="none" stroke={resultado < 0 ? 'var(--indigo)' : 'var(--acc)'} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
                      : <line x1={0} y1={50} x2={100} y2={50} stroke="var(--track)" strokeWidth={1} vectorEffect="non-scaling-stroke" strokeDasharray="4 4" />}
                  </svg>
                </div>

                {erroCtl?.id === b.id && (
                  <div className="err" style={{ marginTop: 14, display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span style={{ flex: 1 }}>{erroCtl.msg}</span>
                    {erroCtl.gate && <Btn small kind="danger" onClick={() => acionar(d, b.id, false, true)}>Forçar</Btn>}
                  </div>
                )}
                <div style={{ display: 'flex', gap: 10, marginTop: 18, alignItems: 'center' }}>
                  <span className="muted" style={{ fontSize: 12, flex: '1 1 auto', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{protecao}</span>
                  <Link to={`/bots/${b.id}`} className="btn primary" style={{ padding: '8px 16px', fontSize: 12 }}>Abrir →</Link>
                  <Btn kind={ligado ? 'ghost' : 'ok'} onClick={() => acionar(d, b.id, ligado)} disabled={ctl.ativar.isPending || ctl.parar.isPending}>{ligado ? 'Parar' : 'Ativar'}</Btn>
                </div>
              </div>
            )
          })}
        </div>

        <Card title="Alertas" sub="últimos eventos dos robôs" pad={false}>
          <div style={{ padding: '0 24px 10px' }}>
            {!alertas.length && <Empty>sem eventos</Empty>}
            {alertas.map((a) => {
              if (a.kind === 'rede') {
                const soTimeout = a.timeouts === a.ciclos
                return (
                  <div key={a.id} style={{ display: 'flex', gap: 18, padding: '11px 0', borderTop: '1px solid var(--border-3)', alignItems: 'center' }}>
                    <span className="mono muted" style={{ fontSize: 12, width: 88, flex: '0 0 88px' }}>{hora(a.fim, true)}</span>
                    <span className="dot" style={{ width: 6, height: 6, flex: '0 0 6px', background: 'var(--amber)' }} />
                    <span style={{ width: 140, flex: '0 0 140px' }}>{a.robos.size} robô{a.robos.size > 1 ? 's' : ''}</span>
                    <span style={{ color: 'var(--amber)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      title={[...a.robos].join(', ')}>
                      {soTimeout ? 'Bybit demorou a responder' : 'Sem conexão com a Bybit (internet/DNS)'}
                      {' · '}{a.ciclos} ciclo{a.ciclos > 1 ? 's' : ''} perdido{a.ciclos > 1 ? 's' : ''}
                      {a.inicio !== a.fim ? ` · desde ${hora(a.inicio)}` : ''}
                    </span>
                  </div>
                )
              }
              const cor = a.erro ? 'var(--red)' : a.acao === 'buy' || a.tipo_operacao === 'entrada' ? 'var(--green)' : a.acao === 'sell' ? 'var(--red)' : a.acao === 'hold' ? 'var(--amber)' : 'var(--muted-2)'
              return (
                <div key={a.id} style={{ display: 'flex', gap: 18, padding: '11px 0', borderTop: '1px solid var(--border-3)', alignItems: 'center' }}>
                  <span className="mono muted" style={{ fontSize: 12, width: 88, flex: '0 0 88px' }}>{hora(a.data_execucao, true)}</span>
                  <span className="dot" style={{ width: 6, height: 6, flex: '0 0 6px', background: cor }} />
                  <span style={{ width: 140, flex: '0 0 140px' }}>{a.nome}</span>
                  <span style={{ color: a.erro ? 'var(--red)' : 'var(--muted-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                    title={a.motivo ?? a.erro ?? ''}>
                    {a.erro ? `erro: ${a.erro}` : `${rotuloAcao(a.acao)}${a.preco ? ' a ' + preco(a.preco) : ''}${a.motivo ? ' · ' + a.motivo : ''}${a.resultado ? ' · P&L ' + fmtSigned(a.resultado) : ''}`}
                  </span>
                </div>
              )
            })}
          </div>
        </Card>
      </Page>
    </>
  )
}
