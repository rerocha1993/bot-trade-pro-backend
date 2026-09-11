import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { api } from '../api/client'
import { useCandles, useDial, useHistorico, useMestre, usePlano, useTrader } from '../api/hooks'
import type { GrauMestre, HipoteseViva, Plano, Superciclo } from '../api/types'
import PriceChart from '../components/chart/PriceChart'
import { Header, Page } from '../components/Layout'
import { Btn, Card, Chip, Empty, Err, KV, Loading, ProbBar } from '../components/ui'
import { corAcao, corVies, fmt, pct, preco, rotuloAcao } from '../lib/format'
import { overlaysElliott } from '../lib/overlays'

const GRAUS = [['ciclo', '1w ciclo'], ['primario', '1d primário'], ['intermediario', '4h intermediário']] as const
type Grau = (typeof GRAUS)[number][0]

const COR_ESTADO: Record<string, string> = {
  impulso_alta: 'var(--green)', zona_onda_2: 'var(--green)', novo_impulso: 'var(--green)', fundo_terminal: 'var(--acc)',
  impulso_maduro: 'var(--amber)', correcao_inicial: 'var(--red)', correcao_em_curso: 'var(--red)', recuo_profundo: 'var(--muted)',
}

function SupercicloCard({ sc, direcao }: { sc: Superciclo; direcao: string }) {
  const cor = COR_ESTADO[sc.estado] ?? 'var(--muted)'
  const crit = sc.criterios_terminal
  return (
    <Card title="Superciclo (escala log, desde 2011)" sub={sc.fase_ciclo === 'impulso' ? 'perna de alta em andamento' : 'correção de ciclo'}>
      <div className="row" style={{ gap: 12 }}>
        <span className="state-pill" style={{ color: cor, borderColor: cor }}>{sc.estado}</span>
        <span className="mono" style={{ fontSize: 22, color: corAcao(direcao) }}>{rotuloAcao(direcao)}</span>
      </div>
      <p style={{ margin: '10px 0 0', fontSize: 11.5, color: 'var(--text-2)', lineHeight: 1.45 }}>{sc.leitura}</p>
      <div style={{ marginTop: 10 }}>
        {sc.fase_ciclo === 'impulso' ? (
          <>
            <KV k="Topo histórico" v={preco(sc.ath)} />
            <KV k="Fundo da perna" v={preco(sc.fundo_perna)} src={`${fmt(sc.meses_desde_fundo, 0)} meses`} />
            <KV k="Extensão log" v={fmt(sc.extensao_log, 2)} src={sc.extensao_vs_ciclo_anterior != null ? `${fmt(sc.extensao_vs_ciclo_anterior, 2)}× do ciclo anterior (madura ≥ 0,618)` : 'sem ciclo anterior'} />
            <KV k="Recuo da perna" v={fmt(sc.recuo_log, 2)} src={`queda desde o topo ${fmt(sc.queda_desde_ath_pct, 1)}%`} />
          </>
        ) : (
          <>
            <KV k="Topo confirmado" v={preco(sc.topo)} src={`${fmt(sc.meses_desde_topo, 0)} meses`} />
            <KV k="Mínimo" v={preco(sc.minimo)} src={`queda ${fmt(sc.queda_pct, 1)}%`} />
            <KV k="Retração log" v={`${fmt(sc.retracao_log_minimo, 2)} (mín) · ${fmt(sc.retracao_log_preco, 2)} (agora)`} src="zona 0,382 – 0,5" />
            <KV k="Recuperação" v={fmt(sc.recuperacao_log, 2)} src="≥ 0,382 = correção terminada" />
            {crit && <div style={{ display: 'flex', gap: 5, marginTop: 8, flexWrap: 'wrap' }}>
              {Object.entries(crit).map(([k, v]) => <span key={k} className="tag mono" style={{ textTransform: 'none', letterSpacing: 0, color: v ? 'var(--green)' : 'var(--muted)', borderColor: v ? 'rgba(127,216,222,0.5)' : undefined }}>{k} {v ? '✓' : '✗'}</span>)}
            </div>}
          </>
        )}
      </div>
    </Card>
  )
}

const COR_MODO: Record<string, string> = {
  acumular: 'var(--green)', deixar_andar: 'var(--green)', nao_perseguir: 'var(--amber)',
  reduzir: 'var(--amber)', hedge: 'var(--red)', aguardar: 'var(--muted)',
}

function PlanoCard({ p }: { p: Plano }) {
  const cor = COR_MODO[p.modo] ?? 'var(--muted)'
  const Zona = ({ z, lado }: { z: Plano['zonas_compra'][number]; lado: 'compra' | 'venda' }) => (
    <div className="mono" style={{ display: 'flex', gap: 8, fontSize: 11, padding: '3px 0', borderBottom: '1px solid var(--border-3)' }}>
      <span style={{ color: lado === 'compra' ? 'var(--green)' : 'var(--red)', width: 74, flex: '0 0 74px' }}>{preco(z.preco)}</span>
      <span className="muted" style={{ width: 52, flex: '0 0 52px' }}>{z.distancia_pct > 0 ? '+' : ''}{z.distancia_pct.toFixed(1).replace('.', ',')}%</span>
      <span className="muted ell" style={{ flex: 1 }}>{z.fontes.join(' · ')}</span>
    </div>
  )
  return (
    <Card title="Plano do par" sub={`todos os robôs de ${p.par} leem daqui`}>
      <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
        <span className="state-pill" style={{ color: cor, borderColor: cor }}>{p.modo}</span>
        <span className="mono" style={{ fontSize: 18, color: corAcao(p.direcao_grau_maior) }}>{rotuloAcao(p.direcao_grau_maior)}</span>
        <span className="tag mono" style={{ textTransform: 'none', letterSpacing: 0 }}>risco {pct(p.risco_permitido)}</span>
        <span className="tag mono" style={{ textTransform: 'none', letterSpacing: 0 }}>hedge até {pct(p.teto_hedge)}</span>
      </div>
      <p style={{ margin: '9px 0 0', fontSize: 11.5, color: 'var(--text-2)', lineHeight: 1.45 }}>{p.modo_descricao}</p>
      <div className="row" style={{ gap: 6, marginTop: 10 }}>
        <span className="tag mono" style={{ textTransform: 'none', letterSpacing: 0, color: p.pode_comprar ? 'var(--green)' : 'var(--muted)' }}>
          {p.pode_comprar ? 'compra liberada' : 'compra bloqueada'}
        </span>
        <span className="tag mono" style={{ textTransform: 'none', letterSpacing: 0, color: p.pode_vender ? 'var(--red)' : 'var(--muted)' }}>
          {p.pode_vender ? 'venda liberada' : 'venda bloqueada'}
        </span>
      </div>
      {!!p.zonas_venda.length && (
        <>
          <div className="eyebrow" style={{ margin: '14px 0 4px' }}>Zonas de venda</div>
          {p.zonas_venda.map((z, i) => <Zona key={i} z={z} lado="venda" />)}
        </>
      )}
      {!!p.zonas_compra.length && (
        <>
          <div className="eyebrow" style={{ margin: '14px 0 4px' }}>Zonas de compra</div>
          {p.zonas_compra.map((z, i) => <Zona key={i} z={z} lado="compra" />)}
        </>
      )}
      <div className="mono muted" style={{ fontSize: 10.5, marginTop: 12, lineHeight: 1.5 }}>{p.motivo}</div>
    </Card>
  )
}

function Hipotese({ h }: { h: HipoteseViva }) {
  return (
    <div className="scen" style={{ padding: '8px 10px' }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
        <span className={h.vies === 'bull' ? 'arrow-up' : 'arrow-dn'} />
        <span style={{ flex: '1 1 auto', minWidth: 0, fontSize: 11.5, lineHeight: 1.35 }}>{h.nome}</span>
        <span className="mono" style={{ fontSize: 13 }}>{pct(h.probabilidade_madura)}</span>
      </div>
      <div className="bar" style={{ margin: '6px 0' }}><span style={{ width: `${Math.min(100, h.probabilidade_madura * 100)}%`, background: corVies(h.vies) }} /></div>
      <div className="mono muted" style={{ fontSize: 10.5 }}>
        {h.fase} · nasceu {h.nascimento ?? '—'} · {h.idade_passos ?? 0} passos · {h.testes ?? 0} testes · {h.alvos_batidos ?? 0} alvos · inval {preco(h.invalidacao)} · alvos {(h.alvos ?? []).slice(0, 2).map(preco).join(' · ') || '—'}
      </div>
    </div>
  )
}

function GraficoMestre({ par, grau, g }: { par: string; grau: Grau; g: GrauMestre | undefined }) {
  const semanal = useHistorico(par, '1w', 900, grau === 'ciclo')
  const diario = useHistorico(par, '1d', 1500, grau === 'primario')
  const h4 = useCandles(par, '4h', 1000, false)
  const q = grau === 'ciclo' ? semanal : grau === 'primario' ? diario : h4
  const dados = q.data ?? []
  const ultimo = dados[dados.length - 1]
  const ell = useMemo(() => overlaysElliott(g, ultimo?.close, ultimo?.time), [g, ultimo?.close, ultimo?.time])
  const labels = useMemo(() => {
    const l = [...ell.labels]
    for (const p of g?.pivots ?? []) if (p.confirmado) l.push({ time: Math.floor(p.ts / 1000), price: p.preco, text: `${p.tipo === 'H' ? '▽' : '△'} ${preco(p.preco)}`, color: p.tipo === 'H' ? '#8fa1ee' : '#7fd8de' })
    return l
  }, [ell.labels, g?.pivots])
  if (q.isPending) return <Loading />
  if (q.isError) return <Err e={q.error} />
  return <PriceChart candles={dados} paths={ell.paths} labels={labels} levels={ell.levels} logScale={grau !== 'intermediario'} height={440} />
}

export default function Trader() {
  const par = 'BTCUSDT'
  const trader = useTrader(par)
  const mestre = useMestre(par)
  const dial = useDial(par)
  const plano = usePlano(par)
  const [grau, setGrau] = useState<Grau>('ciclo')
  const qc = useQueryClient()
  const travar = useMutation({ mutationFn: (p: { grau: string; cenario_id: string }) => api.post('/api/elliott/mestre/travar', { par, ...p, motivo: 'escolha no painel' }), onSuccess: () => qc.invalidateQueries({ queryKey: ['mestre'] }) })
  const destravar = useMutation({ mutationFn: () => api.post('/api/elliott/mestre/destravar', { par, motivo: 'destravada no painel' }), onSuccess: () => qc.invalidateQueries({ queryKey: ['mestre'] }) })
  const reconstruir = useMutation({ mutationFn: () => api.post('/api/elliott/trader/reconstruir', { par }), onSuccess: () => qc.invalidateQueries({ queryKey: ['trader'] }) })
  const t = trader.data
  const g = mestre.data?.graus?.[grau]
  const trava = mestre.data?.trava ?? null
  const niveisDial = useMemo(() => {
    const d = dial.data
    if (!d?.niveis) return []
    return [...d.niveis].sort((a, b) => Math.abs(a.preco - d.preco) - Math.abs(b.preco - d.preco)).slice(0, 10).sort((a, b) => b.preco - a.preco)
  }, [dial.data])

  return (
    <>
      <Header titulo="Mesa do trader" subtitulo="superciclo em escala log, ciclo mandando no primário, contagem mestre e dial de hedge" actions={
        <Btn onClick={() => reconstruir.mutate()} disabled={reconstruir.isPending} title="Apaga a memória persistida e evolui de novo desde 2011">{reconstruir.isPending ? 'reconstruindo…' : 'Reconstruir memória'}</Btn>
      } />
      <Page>
        {trader.isPending && <Loading />}
        {trader.isError && <Err e={trader.error} />}
        {t?.erro && <div className="err">{t.erro}</div>}
        {t && !t.erro && (
          <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))', alignItems: 'start' }}>
            {plano.data && !plano.data.erro && <PlanoCard p={plano.data} />}
            <SupercicloCard sc={t.superciclo} direcao={t.direcao} />
            <Card title="Contagens maduras" sub={`${t.n_vivas} hipóteses vivas · ${t.data}`}>
              <div className="eyebrow">Ciclo semanal manda no primário diário</div>
              <ProbBar bull={t.prob_bull} bear={t.prob_bear} />
              <div className="mono muted" style={{ fontSize: 11, marginTop: 8 }}>
                ciclo: <span style={{ color: corAcao(t.ciclo.direcao) }}>{rotuloAcao(t.ciclo.direcao)}</span> {pct(Math.max(t.ciclo.prob_bull, t.ciclo.prob_bear))} · {t.ciclo.primaria ?? '—'}
                {(t.ciclo.exaurido.bull || t.ciclo.exaurido.bear) && <span className="amber"> · exaurido {t.ciclo.exaurido.bull ? 'bull' : 'bear'}</span>}
              </div>
              <div className="mono muted" style={{ fontSize: 11, marginTop: 2 }}>
                primário subordinado: <span style={{ color: corAcao(t.subordinado.direcao) }}>{rotuloAcao(t.subordinado.direcao)}</span> bull {pct(t.subordinado.prob_bull)} / bear {pct(t.subordinado.prob_bear)}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 12 }}>
                {t.vivas.map((h, i) => <Hipotese key={h.chave ?? i} h={h} />)}
                {!t.vivas.length && <Empty>nenhuma hipótese viva no primário: siga o superciclo</Empty>}
              </div>
            </Card>
            <Card title="Dial de hedge" sub="carteira em BTC · short inverso só protege">
              {dial.isPending && <Loading />}
              {dial.isError && <Err e={dial.error} />}
              {dial.data && !dial.data.erro && (
                <>
                  <div className={dial.data.impulso_de_alta ? 'info' : 'warn'} style={{ marginBottom: 10 }}>{dial.data.recomendacao}</div>
                  <KV k="Barreira" v={preco(dial.data.barreira?.preco)} color="var(--red)" src={(dial.data.barreira?.fontes ?? []).join(' · ') || '—'} />
                  <KV k="Suporte" v={preco(dial.data.suporte?.preco)} color="var(--green)" src={(dial.data.suporte?.fontes ?? []).join(' · ') || '—'} />
                  <KV k="Exaustão" v={fmt(dial.data.exaustao.score, 2)} color={dial.data.exaustao.score >= 0.6 ? 'var(--amber)' : undefined} src={`${dial.data.exaustao.confluencias} sinais concordando`} />
                  <KV k="Superciclo" v={dial.data.superciclo?.estado ?? '—'} src={dial.data.impulso_de_alta ? 'deixar andar' : 'hedge permitido'} />
                  <div className="eyebrow" style={{ margin: '12px 0 6px' }}>Níveis próximos</div>
                  {niveisDial.map((n, i) => (
                    <div key={i} className="mono" style={{ display: 'flex', gap: 8, fontSize: 11, padding: '3px 0', borderBottom: '1px solid var(--border-3)' }}>
                      <span style={{ color: n.preco > dial.data!.preco ? 'var(--red)' : 'var(--green)' }}>{preco(n.preco)}</span>
                      <span className="muted" style={{ flex: 1 }}>{n.fonte}</span>
                      <span className="muted">peso {fmt(n.peso, 1)}</span>
                    </div>
                  ))}
                </>
              )}
              {dial.data?.erro && <Err e={dial.data.erro} />}
            </Card>
          </div>
        )}

        <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 66fr) minmax(280px, 34fr)', alignItems: 'start' }}>
          <div className="card">
            <div className="tabs">
              {GRAUS.map(([k, l]) => <button key={k} className={grau === k ? 'on' : ''} onClick={() => setGrau(k)}>{l}</button>)}
              <span className="mono muted" style={{ marginLeft: 'auto', fontSize: 10, paddingRight: 8 }}>{g?.desde ? `desde ${g.desde}` : ''}{grau !== 'intermediario' ? ' · escala log' : ''}</span>
            </div>
            <div style={{ padding: '10px 10px 12px' }}>
              <GraficoMestre par={par} grau={grau} g={g} />
            </div>
          </div>
          <Card title="Contagem mestre" sub={g?.timeframe ?? ''} pad={false}>
            <div className="card-b">
              {mestre.isPending && <Loading />}
              {mestre.isError && <Err e={mestre.error} />}
              {trava && (
                <div className="info" style={{ marginBottom: 10 }}>
                  <div className="row" style={{ gap: 8 }}>
                    <span style={{ flex: 1 }}>Trava ativa ({trava.grau}): {trava.cenario?.nome ?? trava.fase} · viés {rotuloVies(trava.vies)} · inval {preco(trava.invalidacao)}{trava.status && trava.status !== 'ativa' ? ` · ${trava.status}` : ''}</span>
                    <Btn small kind="ghost" onClick={() => destravar.mutate()}>Destravar</Btn>
                  </div>
                </div>
              )}
              {g && (
                <>
                  {g.prob_bull !== undefined && <ProbBar bull={g.prob_bull ?? 0} bear={g.prob_bear ?? 0} />}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 12 }}>
                    {g.cenarios.slice(0, 6).map((c, i) => (
                      <div key={c.id} className={'scen' + (i === 0 ? ' prim' : '')} style={{ padding: '8px 10px' }}>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                          <span className={c.vies === 'bull' ? 'arrow-up' : 'arrow-dn'} />
                          <span style={{ flex: '1 1 auto', minWidth: 0, fontSize: 11.5, lineHeight: 1.35 }}>{c.nome}</span>
                          <span className="mono" style={{ fontSize: 13, color: i === 0 ? 'var(--acc)' : undefined }}>{pct(c.probabilidade)}</span>
                        </div>
                        <div className="row" style={{ marginTop: 6, gap: 8 }}>
                          <span className="mono muted" style={{ fontSize: 10.5, flex: 1 }}>{c.fase} · inval {preco(c.invalidacao)} · alvos {c.alvos.slice(0, 2).map(preco).join(' · ') || '—'}</span>
                          <Chip on={trava?.cenario?.id === c.id} onClick={() => travar.mutate({ grau, cenario_id: c.id })}>{trava?.cenario?.id === c.id ? 'travado' : 'travar'}</Chip>
                        </div>
                      </div>
                    ))}
                    {!g.cenarios.length && <Empty>{g.erro || 'sem cenários'}</Empty>}
                  </div>
                </>
              )}
              {travar.isError && <Err e={travar.error} />}
            </div>
          </Card>
        </div>
      </Page>
    </>
  )
}

function rotuloVies(v: string) { return v === 'bull' ? 'alta' : v === 'bear' ? 'baixa' : v }
