import { useMemo, useState } from 'react'
import { useMultigrau, useNiveis } from '../api/hooks'
import { Header, Page } from '../components/Layout'
import { Btn, Card, Chip, Err, Field, Loading, ProbBar, Seg } from '../components/ui'
import { preco } from '../lib/format'
import type { GrauKey, Overlays } from '../components/elliott'
import { AlinhamentoBox, CenarioCard, GRAUS, GrafPainel, OV_CHIPS } from '../components/elliott'

const TFS = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
// a tela de mercado nao mostra entradas e saidas: nao ha posicao aqui
const OV = OV_CHIPS.filter(([k]) => k !== 'trd')

export default function Mercado() {
  const [form, setForm] = useState({ par: 'BTCUSDT', timeframe: '15m', estilo: 'daytrade', perfil: 'conservador' })
  const [sel, setSel] = useState(form)
  const [grau, setGrau] = useState<GrauKey>('operacional')
  // timeframe, estilo e perfil valem na hora: antes só o botão "Analisar" aplicava, e clicar no timeframe
  // parecia não fazer nada. O botão continua para o PAR, que é digitado.
  const aplicar = (mudanca: Partial<typeof form>) => {
    const novo = { ...form, ...mudanca }
    setForm(novo)
    if (!('par' in mudanca)) {
      setSel(novo)
      if (mudanca.timeframe) setGrau('operacional')      // o timeframe escolhido é o grau operacional
    }
  }
  const [ov, setOv] = useState<Overlays>({ zig: true, tpo: true, vp: false, ob: true, vwap: true, inst: true, trd: false })
  const mg = useMultigrau(sel.par, sel.estilo, sel.timeframe, sel.perfil)
  const tfs = mg.data?.timeframes ?? { operacional: sel.timeframe, contexto: '—', macro: '—' }
  const tfAtual = tfs[grau] === '—' ? sel.timeframe : tfs[grau]
  const niveis = useNiveis(sel.par, tfAtual)
  const g = mg.data?.graus[grau]
  const linhas = useMemo(() => {
    const n = niveis.data
    if (!n) return []
    const out: { label: string; preco: number | null | undefined; fonte: string; cor?: string }[] = [
      { label: 'POC · TPO composto', preco: n.tpo?.POC, fonte: 'tpo', cor: 'var(--acc)' },
      { label: 'VAH · value area high', preco: n.tpo?.VAH, fonte: 'tpo' },
      { label: 'VAL · value area low', preco: n.tpo?.VAL, fonte: 'tpo' },
      { label: 'POC · Volume Profile', preco: n.volume_profile?.POC, fonte: 'vp' },
      { label: 'VWAP', preco: n.vwap?.vwap, fonte: 'vwap' },
      { label: 'VWAP banda superior', preco: n.vwap?.banda_sup, fonte: 'vwap', cor: 'var(--muted)' },
      { label: 'VWAP banda inferior', preco: n.vwap?.banda_inf, fonte: 'vwap', cor: 'var(--muted)' },
    ]
    for (const b of (n.order_blocks?.bullish || []).slice(-2)) out.push({ label: 'Order block demanda', preco: b.preco, fonte: 'ob', cor: 'var(--green)' })
    for (const b of (n.order_blocks?.bearish || []).slice(-2)) out.push({ label: 'Order block oferta', preco: b.preco, fonte: 'ob', cor: 'var(--red)' })
    if (g?.primario?.invalidacao) out.push({ label: 'Invalidação do cenário primário', preco: g.primario.invalidacao, fonte: 'elliott', cor: 'var(--red)' })
    for (const [i, a] of (g?.primario?.alvos || []).slice(0, 2).entries()) out.push({ label: `Alvo ${i + 1} do cenário primário`, preco: a, fonte: 'elliott', cor: 'var(--green)' })
    return out.filter((x) => x.preco).sort((a, b) => (b.preco as number) - (a.preco as number))
  }, [niveis.data, g])

  return (
    <>
      <Header titulo="Mercado" subtitulo="estudo do par antes de criar um robô" par={sel.par} />
      <Page>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'flex-end' }}>
          <Field label="Par"><input value={form.par} onChange={(e) => aplicar({ par: e.target.value.toUpperCase() })}
            onKeyDown={(e) => { if (e.key === 'Enter') setSel(form) }} style={{ width: 132 }} /></Field>
          <Field label="Timeframe"><select value={form.timeframe} onChange={(e) => aplicar({ timeframe: e.target.value })} style={{ width: 110 }}>{TFS.map((t) => <option key={t}>{t}</option>)}</select></Field>
          <div><span className="label">Estilo</span><div style={{ width: 280 }}><Seg value={form.estilo} options={['scalping', 'daytrade', 'swing'] as const} onChange={(v) => aplicar({ estilo: v })} /></div></div>
          <div><span className="label">Perfil</span><div style={{ width: 200 }}><Seg value={form.perfil} options={['conservador', 'turbo'] as const} onChange={(v) => aplicar({ perfil: v })} /></div></div>
          <Btn kind="primary" onClick={() => setSel(form)} disabled={form.par === sel.par}>Analisar par</Btn>
          {mg.isFetching && <span className="mono muted" style={{ fontSize: 11 }}>analisando…</span>}
        </div>

        <div className="grid" style={{ gridTemplateColumns: 'minmax(0, 60fr) minmax(230px, 22fr) minmax(220px, 18fr)', alignItems: 'start' }}>
          <div className="card">
            <div className="tabs">
              {GRAUS.map((k) => <button key={k} className={grau === k ? 'on' : ''} onClick={() => setGrau(k)}>{tfs[k]} {k}</button>)}
            </div>
            <div style={{ padding: '10px 10px 0' }}>
              <GrafPainel par={sel.par} tf={tfAtual} grau={g} ov={ov} height={400} />
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: '12px 14px 14px' }}>
              {OV.map(([k, l]) => <Chip key={k} on={ov[k]} onClick={() => setOv({ ...ov, [k]: !ov[k] })}>{l}</Chip>)}
            </div>
          </div>

          <Card title="Cenários de Elliott" sub={g ? `${tfAtual} · ${g.cenarios.length} cenários` : ''}>
            {mg.isPending && <Loading />}
            {mg.isError && <Err e={mg.error} />}
            {g && (
              <>
                <ProbBar bull={g.prob_bull} bear={g.prob_bear} />
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 14 }}>
                  {g.cenarios.slice(0, 6).map((c, i) => <CenarioCard key={c.id} c={c} prim={i === 0} compact />)}
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

          <Card title="Níveis agora" sub={tfAtual} pad={false}>
            {niveis.isPending && <Loading />}
            {niveis.isError && <Err e={niveis.error} />}
            <table className="table">
              <thead><tr><th>Nível</th><th className="r">Preço</th><th className="r">Fonte</th></tr></thead>
              <tbody>
                {linhas.map((l, i) => (
                  <tr key={i}>
                    <td className="sans" style={{ color: l.cor ?? 'var(--text)', fontSize: 11.5 }}>{l.label}</td>
                    <td className="r">{preco(l.preco)}</td>
                    <td className="r muted" style={{ fontSize: 10.5 }}>{l.fonte}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>
      </Page>
    </>
  )
}
