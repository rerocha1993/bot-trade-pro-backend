import { useSentimento } from '../api/hooks'
import { Header, Page } from '../components/Layout'
import { Card, Err, Loading } from '../components/ui'
import { fmt, fmtSigned, pct } from '../lib/format'

const PESOS: Record<string, number> = { fear_greed: 0.40, funding: 0.25, long_short: 0.20, open_interest: 0.15, x_twitter: 0.20, liquidacoes: 0.15 }
const NOMES: Record<string, string> = { fear_greed: 'Fear & Greed', funding: 'Funding rate', long_short: 'Razão long/short', open_interest: 'Open interest 24 h', x_twitter: 'X / Twitter', liquidacoes: 'Liquidações 24 h' }

export default function Sentimento() {
  const s = useSentimento()
  const d = s.data
  const ang = d ? Math.max(-90, Math.min(90, d.score * 90)) : 0
  const comps = d ? Object.entries(d.componentes) : []
  const bruto = (k: string): string => {
    if (!d) return '—'
    if (k === 'fear_greed') return d.fear_greed ? `${d.fear_greed.valor}` : '—'
    if (k === 'funding') return d.funding !== null && d.funding !== undefined ? `${fmt(d.funding * 100, 4)}%` : '—'
    if (k === 'long_short') return d.long_short_ratio !== null && d.long_short_ratio !== undefined ? pct(d.long_short_ratio, 1) : '—'
    if (k === 'open_interest') return d.open_interest ? `${fmtSigned(d.open_interest.oi_var * 100, 1)}%` : '—'
    return fmt(d.componentes[k], 2)
  }
  const legenda = (k: string): string => {
    if (!d) return ''
    if (k === 'fear_greed') return d.fear_greed?.classificacao ?? ''
    if (k === 'funding') return '8 h · média das exchanges'
    if (k === 'long_short') return 'contas long na Bybit'
    if (k === 'open_interest') return d.open_interest ? `OI ${d.open_interest.oi_var >= 0 ? 'sobe' : 'cai'} · preço ${fmtSigned(d.open_interest.preco_var * 100, 1)}%` : ''
    return ''
  }
  return (
    <>
      <Header titulo="Sentimento" subtitulo="score composto e componentes · filtro contrário: euforia é topo, medo é fundo" />
      <Page>
        {s.isPending && <Loading />}
        {s.isError && <Err e={s.error} />}
        {d && (
          <div className="grid" style={{ gridTemplateColumns: 'minmax(300px, 32fr) minmax(0, 68fr)', alignItems: 'start' }}>
            <div className="card" style={{ padding: 18, textAlign: 'center' }}>
              <div className="gauge">
                <div className="ring" /><div className="hole" />
                <div className="needle" style={{ transform: `rotate(${ang}deg)` }} />
                <div className="pin" />
              </div>
              <div className="mono acc" style={{ fontSize: 34, marginTop: 14 }}>{fmtSigned(d.score, 2)}</div>
              <div className="eyebrow" style={{ letterSpacing: '0.18em' }}>zona {d.zona} · viés contrário {d.vies_contrario}</div>
              <div className="mono muted" style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10.5, marginTop: 16 }}>
                <span>−1 medo extremo</span><span>+1 ganância extrema</span>
              </div>
              <p className="warn" style={{ margin: '16px 0 0', textAlign: 'left' }}>
                Regra em vigor: acima de +0,60 as novas compras ficam bloqueadas no perfil conservador; abaixo de −0,60, as vendas.
                {d.bloqueia_compra && ' Agora: compras bloqueadas.'}{d.bloqueia_venda && ' Agora: vendas bloqueadas.'}
              </p>
            </div>
            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))' }}>
              {comps.map(([k, v]) => {
                const peso = PESOS[k] ?? 0
                const contrib = v * peso
                return (
                  <div className="card" key={k} style={{ padding: '13px 14px' }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                      <span style={{ fontSize: 12.5, fontWeight: 600, flex: '1 1 auto' }}>{NOMES[k] ?? k}</span>
                      <span className="mono muted" style={{ fontSize: 10.5 }}>peso {pct(peso)}</span>
                    </div>
                    <div className="mono" style={{ fontSize: 24, marginTop: 10 }}>{bruto(k)}</div>
                    <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>{legenda(k)}</div>
                    <div className="bar" style={{ margin: '12px 0 6px', position: 'relative' }}>
                      <span style={{ position: 'absolute', top: 0, height: 3, ...(v >= 0 ? { left: '50%', width: `${v * 50}%`, background: 'var(--green)' } : { right: '50%', width: `${-v * 50}%`, background: 'var(--red)' }) }} />
                      <span style={{ position: 'absolute', left: '50%', top: -3, bottom: -3, width: 1, background: 'rgba(255,255,255,0.15)' }} />
                    </div>
                    <div className="mono" style={{ fontSize: 11, color: contrib >= 0 ? 'var(--green)' : 'var(--red)' }}>contribuição {fmtSigned(contrib, 2)}</div>
                  </div>
                )
              })}
              {!comps.length && <Card><div className="empty">nenhum componente disponível (sem rede?)</div></Card>}
            </div>
          </div>
        )}
        <Card title="Histórico do score" sub="em construção">
          <div className="empty">O backend ainda não guarda a série do score. O Fear &amp; Greed histórico (desde 2018) está em data/historico/fear_greed.csv e entra no backtest do hedge.</div>
        </Card>
      </Page>
    </>
  )
}
