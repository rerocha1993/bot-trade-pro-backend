import { useMemo, useState } from 'react'
import { useBacktests, useBots, useControleBot, useFechadas } from '../api/hooks'
import type { Posicao } from '../api/types'
import { Header, Page } from '../components/Layout'
import { Btn, Card, Empty, Err, KPI, Loading } from '../components/ui'
import { corAcao, corPnl, fmt, fmtSigned, hora, pct, preco, rotuloAcao } from '../lib/format'

function rMultiplo(p: Posicao): number | null {
  const sl = p.sl_inicial ?? p.sl
  if (!sl || p.pnl === null) return null
  const risco = Math.abs(p.preco_entrada - sl) * p.quantidade
  return risco > 0 ? p.pnl / risco : null
}

function csv(rows: (Posicao & { bot: string })[]): string {
  const cab = ['abertura', 'fechamento', 'robo', 'direcao', 'quantidade', 'entrada', 'saida', 'pnl', 'taxas', 'fase', 'cenario', 'motivo_saida']
  const linhas = rows.map((p) => [p.aberto_em, p.fechado_em, p.bot, p.direcao, p.quantidade, p.preco_entrada, p.preco_saida, p.pnl, p.taxas, p.fase_onda, p.cenario, p.motivo_saida]
    .map((v) => `"${String(v ?? '').replace(/"/g, '""')}"`).join(';'))
  return [cab.join(';'), ...linhas].join('\n')
}

export default function Historico() {
  const bots = useBots()
  const ids = useMemo(() => (bots.data ?? []).map((b) => b.id), [bots.data])
  const fechadas = useFechadas(ids, 500)
  const backtests = useBacktests()
  const ctl = useControleBot()
  const [botSel, setBotSel] = useState<number | 'todos'>('todos')
  const nomes = useMemo(() => new Map((bots.data ?? []).map((b) => [b.id, b.nome])), [bots.data])
  const rows = useMemo(() => (fechadas.data ?? []).flatMap((r) => r.posicoes)
    .filter((p) => p.status === 'fechada' && p.pnl !== null && (botSel === 'todos' || p.bot_id === botSel))
    .map((p) => ({ ...p, bot: nomes.get(p.bot_id) ?? `bot ${p.bot_id}` }))
    .sort((a, b) => (b.fechado_em || '').localeCompare(a.fechado_em || '')), [fechadas.data, botSel, nomes])
  const kpi = useMemo(() => {
    const asc = [...rows].reverse()
    const ganhos = asc.filter((p) => (p.pnl || 0) > 0), perdas = asc.filter((p) => (p.pnl || 0) <= 0)
    const somaG = ganhos.reduce((a, p) => a + (p.pnl || 0), 0), somaP = Math.abs(perdas.reduce((a, p) => a + (p.pnl || 0), 0))
    const rs = asc.map(rMultiplo).filter((r): r is number => r !== null)
    let acc = 0, pico = 0, dd = 0
    const curva = asc.map((p) => { acc += p.pnl || 0; pico = Math.max(pico, acc); dd = Math.max(dd, pico - acc); return acc })
    return { n: asc.length, taxa: asc.length ? ganhos.length / asc.length : null, pf: somaP ? somaG / somaP : null, r: rs.length ? rs.reduce((a, b) => a + b, 0) / rs.length : null, dd, total: acc, curva }
  }, [rows])
  const pontos = useMemo(() => {
    const c = kpi.curva
    if (c.length < 2) return ''
    const mn = Math.min(0, ...c), mx = Math.max(0, ...c), span = mx - mn || 1
    return c.map((v, i) => `${((i / (c.length - 1)) * 100).toFixed(2)},${(((mx - v) / span) * 92 + 4).toFixed(2)}`).join(' ')
  }, [kpi.curva])
  const baixarCsv = () => {
    const blob = new Blob([csv(rows)], { type: 'text/csv;charset=utf-8' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'posicoes_fechadas.csv'; a.click(); URL.revokeObjectURL(a.href)
  }

  return (
    <>
      <Header titulo="Histórico" subtitulo="resultado consolidado, posições fechadas e backtests de validação" actions={
        <div style={{ display: 'flex', gap: 8 }}>
          <select value={String(botSel)} onChange={(e) => setBotSel(e.target.value === 'todos' ? 'todos' : Number(e.target.value))} style={{ width: 180 }}>
            <option value="todos">todos os robôs</option>
            {(bots.data ?? []).map((b) => <option key={b.id} value={b.id}>{b.nome}</option>)}
          </select>
          <Btn onClick={baixarCsv} disabled={!rows.length}>Exportar CSV</Btn>
        </div>
      } />
      <Page>
        <div className="grid" style={{ gridTemplateColumns: 'repeat(6, minmax(0, 1fr))' }}>
          <KPI v={fmt(kpi.n)} l="trades" />
          <KPI v={kpi.taxa === null ? '—' : pct(kpi.taxa, 1)} l="taxa de acerto" />
          <KPI v={kpi.pf === null ? '—' : fmt(kpi.pf, 2)} l="fator de lucro" color={kpi.pf !== null && kpi.pf >= 1 ? 'var(--green)' : 'var(--red)'} />
          <KPI v={kpi.r === null ? '—' : fmt(kpi.r, 2)} l="R médio" />
          <KPI v={`−${fmt(kpi.dd, 2)}`} l="drawdown máximo (USDT)" color="var(--red)" />
          <KPI v={fmtSigned(kpi.total)} l="resultado (USDT)" color={corPnl(kpi.total)} />
        </div>

        <Card title="Curva de capital" sub="P&L acumulado das posições fechadas">
          <div style={{ position: 'relative', height: 210, borderLeft: '1px solid var(--border-2)', borderBottom: '1px solid var(--border-2)' }}>
            {pontos ? (
              <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
                <polyline points={`0,100 ${pontos} 100,100`} fill="rgba(127,216,222,0.10)" stroke="none" />
                <polyline points={pontos} fill="none" stroke="var(--acc)" strokeWidth={1.6} vectorEffect="non-scaling-stroke" />
              </svg>
            ) : <Empty>{fechadas.isPending ? 'carregando…' : 'ainda não há posições fechadas'}</Empty>}
            <span className="mono" style={{ position: 'absolute', right: 8, top: 8, fontSize: 11, color: corPnl(kpi.total) }}>{fmtSigned(kpi.total)} USDT</span>
          </div>
        </Card>

        <Card title="Posições fechadas" pad={false}>
          {fechadas.isError && <Err e={fechadas.error} />}
          <div style={{ overflowX: 'auto' }}>
            <table className="table">
              <thead><tr><th>Abertura</th><th>Robô</th><th>Direção</th><th className="r">Entrada</th><th className="r">Saída</th><th className="r">P&amp;L</th><th className="r">R</th><th>Fase</th><th>Motivo da saída</th></tr></thead>
              <tbody>
                {rows.slice(0, 200).map((p) => {
                  const r = rMultiplo(p)
                  return (
                    <tr key={p.id}>
                      <td className="muted">{hora(p.aberto_em, true)}</td>
                      <td className="sans">{p.bot}</td>
                      <td style={{ color: corAcao(p.direcao) }}>{rotuloAcao(p.direcao)}</td>
                      <td className="r">{preco(p.preco_entrada)}</td>
                      <td className="r">{preco(p.preco_saida)}</td>
                      <td className="r" style={{ color: corPnl(p.pnl) }}>{fmtSigned(p.pnl)}</td>
                      <td className="r" style={{ color: corPnl(r) }}>{r === null ? '—' : fmtSigned(r, 1)}</td>
                      <td style={{ color: 'var(--text-2)' }}>{p.fase_onda ?? '—'}</td>
                      <td className="ell" style={{ fontSize: 11, color: (p.motivo_saida || '').toLowerCase().startsWith('sl') ? 'var(--red)' : (p.motivo_saida || '').toLowerCase().startsWith('tp') ? 'var(--green)' : 'var(--text-2)' }}>{p.motivo_saida}</td>
                    </tr>
                  )
                })}
                {!rows.length && !fechadas.isPending && <tr><td colSpan={9}><Empty>sem posições fechadas</Empty></td></tr>}
              </tbody>
            </table>
          </div>
        </Card>

        <Card title="Backtests de validação" sub="obrigatório antes de ativar em testnet/real · válido por 30 dias" pad={false} right={
          <div style={{ display: 'flex', gap: 6 }}>
            {(bots.data ?? []).map((b) => <Btn key={b.id} small onClick={() => ctl.backtest.mutate({ id: b.id })} disabled={ctl.backtest.isPending}>Rodar · {b.nome}</Btn>)}
          </div>
        }>
          {backtests.isPending && <Loading />}
          {backtests.isError && <Err e={backtests.error} />}
          {ctl.backtest.isError && <Err e={ctl.backtest.error} />}
          <table className="table">
            <thead><tr><th>Data</th><th>Robô</th><th>Par · TF</th><th className="r">Dias</th><th className="r">Trades</th><th className="r">Acerto</th><th className="r">Retorno</th><th className="r">PF</th><th className="r">DD</th><th>Status</th><th>Motivo</th></tr></thead>
            <tbody>
              {(backtests.data ?? []).map((b) => (
                <tr key={b.id}>
                  <td className="muted">{hora(b.criado_em, true)}</td>
                  <td className="sans">{b.bot_id !== null ? nomes.get(b.bot_id) ?? `bot ${b.bot_id}` : '—'}</td>
                  <td>{b.par} · {b.timeframe}</td>
                  <td className="r">{b.dias ?? '—'}</td>
                  <td className="r">{b.trades ?? '—'}</td>
                  <td className="r">{b.taxa_acerto !== null ? pct(b.taxa_acerto, 1) : '—'}</td>
                  <td className="r" style={{ color: corPnl(b.retorno_pct) }}>{b.retorno_pct !== null ? fmtSigned(b.retorno_pct, 1) + '%' : '—'}</td>
                  <td className="r">{b.fator_lucro !== null ? fmt(b.fator_lucro, 2) : '—'}</td>
                  <td className="r red">{b.drawdown_max_pct !== null ? fmt(b.drawdown_max_pct, 1) + '%' : '—'}</td>
                  <td><span className="tag mono" style={{ textTransform: 'none', letterSpacing: 0, color: b.status === 'rodando' ? 'var(--amber)' : b.aprovado ? 'var(--green)' : 'var(--red)' }}>{b.status === 'rodando' ? 'rodando' : b.aprovado ? 'aprovado' : 'reprovado'}</span></td>
                  <td className="sans ell muted" style={{ fontSize: 11 }}>{b.motivo}</td>
                </tr>
              ))}
              {backtests.data && !backtests.data.length && <tr><td colSpan={11}><Empty>nenhum backtest ainda</Empty></td></tr>}
            </tbody>
          </table>
        </Card>
      </Page>
    </>
  )
}
