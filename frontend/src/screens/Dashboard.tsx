import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../api/client'
import { useBots, useControleBot, useDetalhes, useFechadas, useLogs } from '../api/hooks'
import type { LogExecucao, Posicao, StatusBot } from '../api/types'
import { Header, Page, usePreco } from '../components/Layout'
import { Btn, Card, Empty, Err, KPI, Loading, ModoTag, Tag } from '../components/ui'
import { corAcao, corPnl, fmt, fmtSigned, hora, pct, preco, rotuloAcao } from '../lib/format'

function pnlAberto(p: Posicao | null, precoAtual: number | undefined): number | null {
  if (!p || !precoAtual) return null
  return (p.direcao === 'buy' ? precoAtual - p.preco_entrada : p.preco_entrada - precoAtual) * p.quantidade
}

function drawdown(pnls: number[]): number {
  let acc = 0, pico = 0, dd = 0
  for (const p of pnls) { acc += p; pico = Math.max(pico, acc); dd = Math.max(dd, pico - acc) }
  return dd
}

export default function Dashboard() {
  const bots = useBots()
  const ids = useMemo(() => (bots.data ?? []).map((b) => b.id), [bots.data])
  const detalhes = useDetalhes(ids)
  const fechadas = useFechadas(ids)
  const logs = useLogs(ids)
  const precoQ = usePreco()
  const ctl = useControleBot()
  const [erroCtl, setErroCtl] = useState<{ id: number; msg: string; gate: boolean } | null>(null)

  const porId = useMemo(() => new Map((detalhes.data ?? []).map((d) => [d.bot.id, d])), [detalhes.data])
  const todasFechadas = useMemo(() => {
    const l = (fechadas.data ?? []).flatMap((r) => r.posicoes).filter((p) => p.status === 'fechada' && p.pnl !== null)
    return l.sort((a, b) => (a.fechado_em || '').localeCompare(b.fechado_em || ''))
  }, [fechadas.data])
  const hoje = new Date().toISOString().slice(0, 10)
  const kpi = useMemo(() => {
    const pnlDia = todasFechadas.filter((p) => (p.fechado_em || '').startsWith(hoje)).reduce((a, p) => a + (p.pnl || 0), 0)
    const pnlTotal = todasFechadas.reduce((a, p) => a + (p.pnl || 0), 0)
    const ganhos = todasFechadas.filter((p) => (p.pnl || 0) > 0).length
    const tradesHoje = todasFechadas.filter((p) => (p.aberto_em || '').startsWith(hoje)).length
    const limite = (detalhes.data ?? []).reduce((a, d) => a + (d.bot.max_trades_dia || 0), 0)
    const banca = (detalhes.data ?? []).reduce((a, d) => a + Number(d.bot.banca || 0), 0)
    const dd = drawdown(todasFechadas.map((p) => p.pnl || 0))
    return { pnlDia, pnlTotal, taxa: todasFechadas.length ? ganhos / todasFechadas.length : null, n: todasFechadas.length, tradesHoje, limite, dd, ddPct: banca ? dd / banca : null }
  }, [todasFechadas, detalhes.data, hoje])
  const rodando = (bots.data ?? []).filter((b) => b.rodando).length

  const alertas = useMemo(() => {
    const nomes = new Map((bots.data ?? []).map((b) => [b.id, b.nome]))
    const l: (LogExecucao & { nome: string })[] = (logs.data ?? []).flat().map((x) => ({ ...x, nome: nomes.get(x.bot_id) || `bot ${x.bot_id}` }))
    return l.sort((a, b) => (b.data_execucao || '').localeCompare(a.data_execucao || '')).slice(0, 12)
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
      <Header titulo="Dashboard" subtitulo="visão geral dos robôs, risco e resultado" />
      <Page>
        <div className="grid" style={{ gridTemplateColumns: 'repeat(6, minmax(0, 1fr))' }}>
          <KPI v={fmtSigned(kpi.pnlDia)} l="P&L do dia (USDT)" color={corPnl(kpi.pnlDia)} />
          <KPI v={fmtSigned(kpi.pnlTotal)} l="P&L acumulado (USDT)" color={corPnl(kpi.pnlTotal)} />
          <KPI v={`${kpi.tradesHoje} / ${kpi.limite || '—'}`} l="trades hoje · limite diário" />
          <KPI v={kpi.taxa === null ? '—' : pct(kpi.taxa, 1)} l={`taxa de acerto (${kpi.n} trades)`} />
          <KPI v={kpi.ddPct === null ? fmt(-kpi.dd, 0) : `−${pct(kpi.ddPct, 1)}`} l="drawdown máximo" color="var(--red)" />
          <KPI v={`${rodando} / ${bots.data?.length ?? 0}`} l="robôs rodando" color="var(--acc)" />
        </div>

        {bots.isPending && <Loading />}
        {bots.isError && <Err e={bots.error} />}
        {bots.data && !bots.data.length && <Card><Empty>Nenhum robô cadastrado. <Link to="/bots/novo">Criar o primeiro</Link>.</Empty></Card>}
        <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))' }}>
          {(bots.data ?? []).map((b) => {
            const d = porId.get(b.id)
            const pos = d?.posicao ?? null
            const dec = d?.ultima_decisao ?? null
            const aberto = pnlAberto(pos, precoQ.data?.preco)
            const ligado = b.rodando || b.ativo
            return (
              <div className="card" key={b.id} style={{ padding: '13px 14px', opacity: ligado ? 1 : 0.6 }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                  <span className={'dot' + (b.rodando ? ' pulse' : '')} style={{ width: 8, height: 8, marginTop: 5, background: b.rodando ? 'var(--green)' : 'var(--dim)' }} />
                  <div style={{ minWidth: 0, flex: '1 1 auto' }}>
                    <div style={{ fontSize: 14, fontWeight: 600 }}>{b.nome}</div>
                    <div className="mono muted" style={{ fontSize: 11, marginTop: 2 }}>{b.estilo_trade} · {b.timeframe} · {b.ativo_nome}</div>
                  </div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                    <Tag>{b.confluencia_tipo}</Tag>
                    <ModoTag modo={b.modo_execucao} />
                  </div>
                </div>
                <div className="mono" style={{ marginTop: 12, padding: '10px 12px', border: '1px solid var(--border-2)', background: 'var(--panel-2)' }}>
                  {pos ? (
                    <>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                        <span style={{ fontSize: 12.5, color: corAcao(pos.direcao) }}>{rotuloAcao(pos.direcao)}</span>
                        <span className="muted" style={{ fontSize: 11.5 }}>entrada {preco(pos.preco_entrada)} · {fmt(pos.quantidade, 4)}</span>
                        <span style={{ marginLeft: 'auto', fontSize: 13, color: corPnl(aberto) }}>{aberto === null ? '—' : fmtSigned(aberto)}</span>
                      </div>
                      <div className="muted" style={{ fontSize: 11.5, marginTop: 5 }}>SL {preco(pos.sl)} · TP {preco(pos.tp)}{pos.trailing_ativo ? ' · trailing' : ''}</div>
                    </>
                  ) : (
                    <>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                        <span className="muted" style={{ fontSize: 12.5 }}>SEM POSIÇÃO</span>
                        <span style={{ marginLeft: 'auto', fontSize: 13, color: corPnl(b.pnl_dia) }}>{b.pnl_dia === null ? '' : `dia ${fmtSigned(b.pnl_dia)}`}</span>
                      </div>
                      <div className="muted" style={{ fontSize: 11.5, marginTop: 5 }}>
                        {d?.estado?.ordem_pendente ? `ordem limitada pendente a ${preco(Number((d.estado.ordem_pendente as { preco?: number }).preco))}` : b.rodando ? `ciclo ${d?.estado?.ciclos ?? 0} · ${d?.estado?.ultimo_ciclo ? hora(d.estado.ultimo_ciclo) : '—'}` : `parado${b.ultima_execucao ? ' · ' + hora(b.ultima_execucao, true) : ''}`}
                      </div>
                    </>
                  )}
                </div>
                <div className="muted" style={{ marginTop: 10, fontSize: 11.5 }}>
                  Última decisão · <span className="mono" style={{ color: corAcao(dec?.acao) }}>{dec ? rotuloAcao(dec.acao) : '—'}</span>
                  {dec && <span className="mono"> {dec.fase_onda} · {dec.probabilidade !== null ? pct(dec.probabilidade) : ''} · {hora(dec.criado_em)}</span>}
                </div>
                {erroCtl?.id === b.id && (
                  <div className="err" style={{ marginTop: 10, display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span style={{ flex: 1 }}>{erroCtl.msg}</span>
                    {erroCtl.gate && <Btn small kind="danger" onClick={() => acionar(d, b.id, false, true)}>Forçar</Btn>}
                  </div>
                )}
                <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
                  <Link to={`/bots/${b.id}`} className="btn primary" style={{ flex: '1 1 auto', textAlign: 'center' }}>Detalhes</Link>
                  <Btn kind={ligado ? 'ghost' : 'ok'} onClick={() => acionar(d, b.id, ligado)} disabled={ctl.ativar.isPending || ctl.parar.isPending}>{ligado ? 'Parar' : 'Ativar'}</Btn>
                </div>
              </div>
            )
          })}
        </div>

        <Card title="Alertas recentes" sub="últimos eventos dos robôs" pad={false}>
          {!alertas.length && <Empty>sem eventos</Empty>}
          {alertas.map((a) => {
            const cor = a.erro ? 'var(--red)' : a.acao === 'buy' || a.tipo_operacao === 'entrada' ? 'var(--green)' : a.acao === 'sell' ? 'var(--red)' : a.acao === 'hold' ? 'var(--amber)' : 'var(--text-2)'
            return (
              <div key={a.id} style={{ display: 'flex', gap: 14, padding: '8px 14px', borderBottom: '1px solid var(--border-3)', alignItems: 'baseline' }}>
                <span className="mono muted" style={{ width: 92, flex: '0 0 92px' }}>{hora(a.data_execucao, true)}</span>
                <span style={{ width: 130, flex: '0 0 130px' }}>{a.nome}</span>
                <span style={{ color: cor, fontSize: 11.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {a.erro ? `erro: ${a.erro}` : `${rotuloAcao(a.acao)}${a.preco ? ' a ' + preco(a.preco) : ''}${a.motivo ? ' · ' + a.motivo : ''}${a.resultado ? ' · P&L ' + fmtSigned(a.resultado) : ''}`}
                </span>
              </div>
            )
          })}
        </Card>
      </Page>
    </>
  )
}
