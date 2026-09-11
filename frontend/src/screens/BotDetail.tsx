import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { useControleBot, useDecisoes, useMultigrau, usePosicoes, useSentimento, useStatusBot } from '../api/hooks'
import type { GrauKey, Overlays } from '../components/elliott'
import { AlinhamentoBox, CenarioCard, GRAUS, GrafPainel, OV_CHIPS } from '../components/elliott'
import { Header, Page, usePreco } from '../components/Layout'
import { Btn, Card, Chip, Empty, Err, KV, Loading, ModoTag, ProbBar, Tag } from '../components/ui'
import { InverseRangeCard } from '../components/InverseRange'
import { corAcao, corPnl, fmt, fmtSigned, hora, pct, preco, rotuloAcao } from '../lib/format'

export default function BotDetail() {
  const id = Number(useParams().id)
  const st = useStatusBot(Number.isFinite(id) ? id : null)
  const bot = st.data?.bot
  const mg = useMultigrau(bot?.ativo ?? 'BTCUSDT', bot?.estilo_trade ?? 'daytrade', bot?.timeframe ?? '15m', bot?.confluencia_tipo ?? 'conservador', !!bot)
  const [grau, setGrau] = useState<GrauKey>('operacional')
  const [ov, setOv] = useState<Overlays>({ zig: true, tpo: true, vp: false, ob: true, vwap: true, inst: true, trd: true })
  const decisoes = useDecisoes(bot ? id : null, 30)
  const posicoes = usePosicoes(bot ? id : null, 30)
  const sent = useSentimento(bot?.ativo ?? 'BTCUSDT')
  const precoQ = usePreco(bot?.ativo ?? 'BTCUSDT')
  const ctl = useControleBot()
  const [erro, setErro] = useState<{ msg: string; gate: boolean } | null>(null)

  if (st.isPending) return <><Header titulo="Robô" /><Page><Loading /></Page></>
  if (st.isError || !bot) return <><Header titulo="Robô" /><Page><Err e={st.error ?? 'não encontrado'} /></Page></>

  const tfs = mg.data?.timeframes ?? { operacional: bot.timeframe, contexto: '—', macro: '—' }
  const g = mg.data?.graus[grau]
  const pos = st.data.posicao
  const dec = st.data.ultima_decisao
  const estado = st.data.estado
  const fluxo = estado?.fluxo ?? null
  const ligado = st.data.rodando || bot.ativo_bot
  const precoAtual = precoQ.data?.preco
  // avanços já realizados pela saída escalonada, na ordem em que saíram
  const parciais = (pos?.saidas_feitas ?? '').split(',').map((a) => Number(a)).filter((a) => Number.isFinite(a) && a > 0)
  const aberto = pos && precoAtual ? (pos.direcao === 'buy' ? precoAtual - pos.preco_entrada : pos.preco_entrada - precoAtual) * pos.quantidade : null
  const refEntrada = pos?.preco_entrada ?? dec?.preco
  const tp = pos?.tp ?? dec?.tp ?? null, sl = pos?.sl ?? dec?.sl ?? null
  const rr = refEntrada && tp && sl && Math.abs(refEntrada - sl) > 0 ? Math.abs(tp - refEntrada) / Math.abs(refEntrada - sl) : null
  const banca = Number(bot.banca || 0)
  const votos = (dec?.votos || '').split(',').map((v) => v.trim()).filter(Boolean)
  const det = (dec?.detalhes && typeof dec.detalhes === 'object' ? dec.detalhes : {}) as Record<string, unknown>
  const trader = det.trader as { direcao?: string; superciclo?: string; leitura?: string } | null | undefined

  const acionar = async (forcar = false) => {
    setErro(null)
    try { if (ligado) await ctl.parar.mutateAsync(id); else await ctl.ativar.mutateAsync({ id, forcar }) } catch (e) {
      setErro({ msg: e instanceof Error ? e.message : String(e), gate: e instanceof ApiError && e.status === 409 })
    }
  }

  return (
    <>
      <Header titulo={bot.nome} subtitulo="detalhe do robô · decisão, cenários e risco" par={bot.ativo} actions={
        <div style={{ display: 'flex', gap: 8 }}>
          <Btn onClick={() => ctl.trailing.mutate({ id, on: !bot.trailing_manual })}>{bot.trailing_manual ? 'Desativar trailing' : 'Ativar trailing'}</Btn>
          <Link to={`/bots/${id}/editar`} className="btn">Editar</Link>
          <Btn kind={ligado ? 'danger' : 'ok'} onClick={() => acionar()}>{ligado ? 'Parar' : 'Ativar'}</Btn>
        </div>
      } />
      <Page>
        <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
          <span className="tag mono" style={{ textTransform: 'none', letterSpacing: 0 }}>{bot.estilo_trade} · {bot.timeframe} · {bot.ativo}</span>
          <Tag>{bot.confluencia_tipo}</Tag>
          <ModoTag modo={bot.modo_execucao} />
          <span className="tag mono" style={{ textTransform: 'none', letterSpacing: 0 }}>{bot.categoria} · {bot.estrategia} · {bot.tipo_entrada}</span>
          <span className="row mono muted" style={{ fontSize: 11.5, gap: 7 }}>
            <span className={'dot' + (st.data.rodando ? ' pulse' : '')} style={{ width: 6, height: 6, background: st.data.rodando ? 'var(--green)' : 'var(--dim)' }} />
            {st.data.rodando ? `rodando · ciclo ${estado?.ciclos ?? 0} · ${estado?.ultimo_ciclo ? hora(estado.ultimo_ciclo) : '—'}${estado?.erros ? ` · ${estado.erros} erros` : ''}` : 'parado'}
          </span>
        </div>
        {erro && <div className="err row"><span style={{ flex: 1 }}>{erro.msg}</span>{erro.gate && <Btn small kind="danger" onClick={() => acionar(true)}>Forçar (ignorar backtest)</Btn>}</div>}

        <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 60fr) minmax(230px, 25fr) minmax(190px, 15fr)', alignItems: 'start' }}>
          <div className="card">
            <div className="tabs">
              {GRAUS.map((k) => <button key={k} className={grau === k ? 'on' : ''} onClick={() => setGrau(k)}>{tfs[k]} {k}</button>)}
              {mg.isFetching && <span className="mono muted" style={{ marginLeft: 'auto', fontSize: 10, paddingRight: 8 }}>analisando…</span>}
            </div>
            <div style={{ padding: '10px 10px 0' }}>
              <GrafPainel par={bot.ativo} tf={tfs[grau]} grau={g} ov={ov} posicoes={posicoes.data?.posicoes} />
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: '12px 14px 14px' }}>
              {OV_CHIPS.map(([k, l]) => <Chip key={k} on={ov[k]} onClick={() => setOv({ ...ov, [k]: !ov[k] })}>{l}</Chip>)}
            </div>
          </div>

          <Card title="Cenários de Elliott" sub={g ? `${tfs[grau]} · ${g.cenarios.length} cenários` : ''}>
            {mg.isPending && <Loading />}
            {mg.isError && <Err e={mg.error} />}
            {g && (
              <>
                <ProbBar bull={g.prob_bull} bear={g.prob_bear} />
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 14 }}>
                  {g.cenarios.slice(0, 5).map((c, i) => <CenarioCard key={c.id} c={c} prim={i === 0} />)}
                  {!g.cenarios.length && <Empty>{g.erro || 'sem cenários neste grau'}</Empty>}
                </div>
              </>
            )}
            {mg.data && (
              <div style={{ marginTop: 16, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
                <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>Alinhamento multi-grau</div>
                <AlinhamentoBox mg={mg.data} />
              </div>
            )}
          </Card>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
            <Card>
              <div className="eyebrow">Decisão</div>
              <div className="mono" style={{ fontSize: 22, marginTop: 6, letterSpacing: '0.02em', color: corAcao(dec?.acao) }}>{dec ? rotuloAcao(dec.acao) : '—'}</div>
              <div className="mono muted" style={{ fontSize: 11, marginTop: 2 }}>{dec ? `${dec.fase_onda ?? '—'} · ${dec.probabilidade !== null ? pct(dec.probabilidade) : '—'} · ${hora(dec.criado_em)}` : 'sem decisões ainda'}</div>
              {dec?.motivo && <p style={{ margin: '9px 0 0', fontSize: 11.5, color: 'var(--text-2)', lineHeight: 1.4 }}>{dec.motivo}</p>}
              {!!votos.length && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 11 }}>
                  {votos.map((v) => <span key={v} className="tag mono" style={{ textTransform: 'none', letterSpacing: 0, borderColor: 'rgba(52,211,153,0.4)', color: 'var(--green)' }}>{v} ✓</span>)}
                </div>
              )}
            </Card>
            <Card>
              <div className="eyebrow" style={{ marginBottom: 9 }}>Alvo e proteção</div>
              <KV k="TP" v={preco(tp)} color="var(--green)" src={pos ? 'posição' : 'decisão'} />
              <KV k="SL" v={preco(sl)} color="var(--red)" src={pos?.trailing_ativo ? 'trailing' : pos ? 'posição' : 'decisão'} />
              <KV k="R:R" v={rr === null ? '—' : fmt(rr, 1)} color="var(--acc)" src={bot.rr_minimo ? `mínimo ${fmt(bot.rr_minimo, 1)}` : 'padrão do perfil'} />
              {pos && <KV k="Aberto" v={aberto === null ? '—' : fmtSigned(aberto)} color={corPnl(aberto)} src={`${rotuloAcao(pos.direcao)} ${preco(pos.preco_entrada)}`} />}
              {pos && parciais.length > 0 && <KV k="Realizado" v={fmtSigned(pos.pnl_parcial ?? 0)} color={corPnl(pos.pnl_parcial ?? 0)} src={`${parciais.length} parcial${parciais.length > 1 ? 'is' : ''} · ${parciais.map((a) => pct(a, 0)).join(', ')} do caminho`} />}
            </Card>
            <Card>
              <div className="eyebrow" style={{ marginBottom: 9 }}>Tamanho e limites</div>
              <KV k="Risco" v={`${fmt(banca * bot.risco_pct, 2)} USDT · ${pct(bot.risco_pct, 1)}`} />
              <KV k="Quantidade" v={pos ? fmt(pos.quantidade, 4) : `${bot.min_quantidade ?? '—'} – ${bot.max_quantidade ?? '—'}`}
                  src={pos && parciais.length > 0 ? `de ${fmt(pos.quantidade_inicial ?? pos.quantidade, 4)} na entrada` : undefined} />
              <KV k="Trades do dia" v={`${estado?.trades_dia ?? 0} / ${bot.max_trades_dia}`} />
              <KV k="P&L do dia" v={fmtSigned(estado?.pnl_dia ?? 0)} color={corPnl(estado?.pnl_dia ?? 0)} src={`limite −${pct(bot.max_perda_dia_pct, 1)}`} />
            </Card>
            {bot.estrategia === 'inverse_range' && <InverseRangeCard id={id} />}
            {fluxo && (
              <Card>
                <div className="eyebrow" style={{ marginBottom: 9 }}>Motor de fluxo</div>
                <KV k="Régua da barra" v={`${fmt(fluxo.barras.tamanho, 3)} ${fluxo.barras.tipo === 'dolar' ? 'USD' : fluxo.barras.tipo === 'tick' ? 'negócios' : 'BTC'}`}
                    src={fluxo.barras.calibrado ? `alvo de ${fluxo.barras.segundos_alvo}s por barra` : 'ainda calibrando pelo fluxo'} />
                <KV k="Ritmo" v={fluxo.barras.ritmo_s === null ? '—' : `${fmt(fluxo.barras.ritmo_s, 1)}s por barra`}
                    src={`${fluxo.barras.barras} barras · ${fluxo.barras.negocios_vistos} negócios`} />
                <KV k="Contexto" v={fluxo.contexto ? `${fluxo.contexto.direcao} · ${fluxo.contexto.vies_contexto}/${fluxo.contexto.vies_macro}` : '—'}
                    color={fluxo.contexto?.direcao === 'hold' ? 'var(--amber)' : 'var(--acc)'}
                    src={fluxo.contexto ? `${fluxo.contexto.niveis.length} níveis · lido há ${fmt(fluxo.contexto.idade_s, 0)}s` : undefined} />
                {fluxo.barras.lacunas > 0 && <KV k="Negócios perdidos" v={String(fluxo.barras.lacunas)} color="var(--amber)" src="buffer do websocket girou antes de consumir" />}
                <div style={{ padding: '4px 0' }}><span className="label" style={{ marginBottom: 2 }}>Última leitura</span>
                  <span className="mono" style={{ fontSize: 11, color: 'var(--muted)' }}>{fluxo.ultimo_motivo}</span></div>
              </Card>
            )}
            <Card>
              <div className="eyebrow" style={{ marginBottom: 9 }}>Filtros</div>
              <div style={{ padding: '4px 0' }}><span className="label" style={{ marginBottom: 2 }}>Sentimento</span>
                <span className="mono" style={{ fontSize: 12, color: sent.data?.bloqueia_compra || sent.data?.bloqueia_venda ? 'var(--amber)' : 'var(--acc)' }}>
                  {sent.data ? `${fmtSigned(sent.data.score, 2)} · ${sent.data.zona}${sent.data.bloqueia_compra ? ' · bloqueia compras' : sent.data.bloqueia_venda ? ' · bloqueia vendas' : ''}` : '…'}
                </span></div>
              <div style={{ padding: '4px 0' }}><span className="label" style={{ marginBottom: 2 }}>Trader (superciclo)</span>
                <span className="mono" style={{ fontSize: 12, color: 'var(--amber)' }}>{trader?.superciclo ? `${trader.superciclo} · ${rotuloAcao(trader.direcao)}` : mg.data?.alinhamento.estado_superciclo ?? '—'}</span></div>
              <div style={{ padding: '4px 0' }}><span className="label" style={{ marginBottom: 2 }}>Regime</span>
                <span className="mono muted" style={{ fontSize: 12 }}>{String((g?.regime as { regime?: string } | undefined)?.regime ?? '—')}{bot.usar_filtro_regime ? '' : ' (filtro desligado)'}</span></div>
            </Card>
          </div>
        </div>

        <Card title="Decisões recentes" pad={false}>
          <div style={{ overflowX: 'auto' }}>
            <table className="table">
              <thead><tr><th>Hora</th><th>Ação</th><th>Fase</th><th>Cenário primário</th><th className="r">Prob.</th><th className="r">Preço</th><th>Motivo</th></tr></thead>
              <tbody>
                {(decisoes.data ?? []).map((d) => (
                  <tr key={d.id}>
                    <td className="muted">{hora(d.criado_em, true)}</td>
                    <td style={{ color: corAcao(d.acao) }}>{rotuloAcao(d.acao)}</td>
                    <td style={{ color: 'var(--text-2)' }}>{d.fase_onda ?? '—'}</td>
                    <td className="sans ell" style={{ color: 'var(--text-2)' }}>{d.cenario ?? '—'}</td>
                    <td className="r">{d.probabilidade !== null ? pct(d.probabilidade) : '—'}</td>
                    <td className="r">{preco(d.preco)}</td>
                    <td className="ell" style={{ color: d.acao === 'hold' ? 'var(--amber)' : 'var(--text-2)', fontSize: 11, maxWidth: 520 }} title={d.motivo ?? ''}>{d.motivo}</td>
                  </tr>
                ))}
                {decisoes.data && !decisoes.data.length && <tr><td colSpan={7} className="empty">sem decisões</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>
      </Page>
    </>
  )
}
