import { useCarteira } from '../api/hooks'
import type { CarteiraStatus, DecisaoCarteira, OperadorCarteira } from '../api/types'
import { Header, Page } from '../components/Layout'
import { Card, Empty, Estado, Tag } from '../components/ui'
import { fmt, preco as fmtPreco } from '../lib/format'

/**
 * A carteira do Tradeiros em simulação: 1 BTC de colateral no inverse para o Shaka e 1 para o Maroja, com o hedge
 * vendido em escada nas resistências e recomprado nos suportes, e os trades de borda. Medida em BTC contra segurar 1 BTC.
 */
const COR = { ganho: '#2ecc84', perda: '#f0544f', hedge: '#f0544f', exposto: '#2ecc84', aviso: '#f5c04a' }
const NOME: Record<string, string> = { shaka: 'Shaka (agressivo)', maroja: 'Maroja (conservador)' }
const NOME_TIPO: Record<string, string> = {
  compra: 'compra', venda_direcional: 'venda', hedge_aumentar: 'subir o hedge', hedge_realizar: 'realizar o hedge',
  ficar_fora: 'ficar de fora',
}
const NOME_PERIODO: Record<string, string> = { treino: '2019–2022', 'validação': '2023–2024', holdout: '2025–2026' }
const dia = (ms: number) => new Date(ms).toISOString().slice(0, 10).split('-').reverse().join('/')
const hora = (ms: number) => new Date(ms).toISOString().slice(5, 16).replace('T', ' ')
const sinal = (v: number, dec = 2) => `${v >= 0 ? '+' : ''}${fmt(v, dec)}`
const zona = (z: [number, number] | null) => (z ? `${fmtPreco(z[0])} – ${fmtPreco(z[1])}` : '—')

/** Barra vendido × exposto: o quanto da carteira está protegido agora. */
function BarraHedge({ pct }: { pct: number }) {
  const v = Math.max(0, Math.min(100, pct))
  return (
    <div style={{ display: 'grid', gap: 4 }}>
      <div style={{ display: 'flex', height: 10, borderRadius: 5, overflow: 'hidden', background: 'var(--border-3)' }}>
        <div style={{ width: `${100 - v}%`, background: COR.exposto, opacity: 0.75 }} />
        <div style={{ width: `${v}%`, background: COR.hedge, opacity: 0.75 }} />
      </div>
      <div className="muted" style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
        <span>exposto {fmt(100 - v, 0)}%</span><span>vendido no inverse (hedge) {fmt(v, 1)}%</span>
      </div>
    </div>
  )
}

function CartaoOperador({ nome, o }: { nome: string; o: OperadorCarteira }) {
  if (o.erro) return <Card title={NOME[nome] ?? nome}><Empty>{o.erro}</Empty></Card>
  const e = o.estado
  const vsHodl = o.retorno_usd_pct - o.hodl_usd_pct
  return (
    <Card title={NOME[nome] ?? nome} right={<span className="muted" style={{ fontSize: 12 }}>{o.trades} trade{o.trades === 1 ? '' : 's'} fechado{o.trades === 1 ? '' : 's'}</span>}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <span className="mono" style={{ fontSize: 26 }}>{fmt(o.btc_final, 5)}</span>
        <span className="muted" style={{ fontSize: 12 }}>BTC (começou com 1)</span>
        <span className="mono" style={{ color: o.ganho_btc_pct >= 0 ? COR.ganho : COR.perda }}>{sinal(o.ganho_btc_pct)}% em BTC</span>
      </div>
      <div className="muted" style={{ fontSize: 12, margin: '6px 0 12px' }}>
        Em dólar {sinal(o.retorno_usd_pct)}% contra {sinal(o.hodl_usd_pct)}% de quem só segurou
        (<span style={{ color: vsHodl >= 0 ? COR.ganho : COR.perda }}>{sinal(vsHodl)} p.p.</span>) · pior queda em BTC {fmt(o.dd_btc_pct, 1)}%
        · funding {sinal(o.funding_btc * 1e8, 0)} sats · taxas −{fmt(o.taxas_btc * 1e8, 0)} sats
      </div>
      {e && <BarraHedge pct={e.hedge_pct} />}
      {e && (
        <div style={{ borderTop: '1px solid var(--border-3)', marginTop: 12, paddingTop: 10, display: 'grid', gap: 8, fontSize: 13 }}>
          {e.hedge.length > 0 && (
            <div>
              <b>Hedge aberto</b>
              {e.hedge.map((h, i) => (
                <div key={i} className="mono" style={{ fontSize: 12 }}>
                  vendido {fmt(h.contratos_usd, 0)} USD em {fmtPreco(h.entrada)} · stop {h.stop ? fmtPreco(h.stop) : 'sem (a carteira aceita a volta)'}
                </div>
              ))}
            </div>
          )}
          {e.escadas.map((x, i) => (
            <div key={i}>
              <b>Escada armada: {x.tipo}</b>
              <div className="mono" style={{ fontSize: 12 }}>
                {x.ordens.map((f) => <span key={f.preco} style={{ opacity: f.feita ? 0.4 : 1 }}>{fmtPreco(f.preco)}{f.feita ? ' ✓' : ''} · </span>)}
                {x.stop ? `stop ${fmtPreco(x.stop)}` : ''}
              </div>
            </div>
          ))}
          {e.trades.map((t, i) => (
            <div key={i} style={{ display: 'grid', gap: 2 }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <Tag color={t.lado === 'compra' ? COR.ganho : COR.perda}>{t.lado}</Tag>
                <Tag color={t.contratos_usd > 0 ? COR.aviso : 'var(--muted)'}>{t.contratos_usd > 0 ? 'posição aberta' : t.armado ? 'ordens postas' : 'esperando a reação'}</Tag>
                {t.risco_tirado && <Tag color={COR.ganho}>1R feito · stop no médio</Tag>}
              </div>
              <span className="mono" style={{ fontSize: 12 }}>
                zona {zona(t.zona)}{t.medio ? ` · médio ${fmtPreco(t.medio)}` : ''} · stop {fmtPreco(t.stop)} · alvo {fmtPreco(t.alvo)}
              </span>
            </div>
          ))}
          {!e.hedge.length && !e.escadas.length && !e.trades.length && <span className="muted">Nada aberto nem armado agora.</span>}
        </div>
      )}
    </Card>
  )
}

function PlanoDeHoje({ d }: { d: NonNullable<CarteiraStatus['ultimo']> }) {
  const hoje = Math.floor(d.fim_ms / 86_400_000) * 86_400_000
  const linhas: (DecisaoCarteira & { op: string })[] = Object.entries(d.operadores)
    .flatMap(([op, o]) => (o.log ?? []).filter((x) => x.ts === hoje).map((x) => ({ ...x, op })))
  return (
    <Card title={`Plano de hoje (${dia(hoje)})`} sub="refeito à 00:00 UTC só com o que já tinha fechado, como no backtest" pad={false}>
      {!linhas.length ? <Empty>sem plano para hoje ainda</Empty> : (
        <table className="table">
          <thead><tr><th>quem</th><th>o quê</th><th>zona</th><th>hedge alvo</th><th>por quê</th></tr></thead>
          <tbody>
            {linhas.map((x, i) => (
              <tr key={i}>
                <td className="sans">{x.op}</td>
                <td className="sans">{NOME_TIPO[x.tipo] ?? x.tipo}</td>
                <td>{zona(x.zona)}</td>
                <td className="r">{fmt(x.hedge_alvo * 100, 0)}%</td>
                <td className="sans muted" style={{ fontSize: 12 }}>{x.motivo} {x.regras.length ? `(${x.regras.join(', ')})` : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  )
}

function Backtest({ b }: { b: NonNullable<CarteiraStatus['backtest']> }) {
  return (
    <Card title="O que o backtest já mediu" pad={false}
      sub="mesma carteira de 2019 até hoje, contra a direção sorteada (30 sorteios) e contra deixar o mesmo hedge parado; só conta como vantagem se passar dos dois">
      <table className="table">
        <thead><tr><th>quem</th><th>período</th><th className="r">BTC</th><th className="r">hedge parado</th><th className="r">95% dos sorteios</th><th>vantagem</th></tr></thead>
        <tbody>
          {Object.entries(b.periodos ?? {}).flatMap(([op, ps]) => Object.entries(ps).map(([per, v]) => (
            <tr key={op + per}>
              <td className="sans">{op}</td>
              <td className="sans">{NOME_PERIODO[per] ?? per}</td>
              <td className="r" style={{ color: v.btc >= 1 ? COR.ganho : COR.perda }}>{sinal((v.btc - 1) * 100, 1)}%</td>
              <td className="r">{sinal((v.fixo - 1) * 100, 1)}%</td>
              <td className="r">{sinal((v.p95_sorteio - 1) * 100, 1)}%</td>
              <td>{v.vantagem ? <Tag color={COR.ganho}>sim</Tag> : <span className="muted">não</span>}</td>
            </tr>
          )))}
        </tbody>
      </table>
    </Card>
  )
}

export default function Carteira() {
  const q = useCarteira()
  const d = q.data?.ultimo
  return (
    <>
      <Header titulo="Carteira" eyebrow="Simulação ao vivo · método Tradeiros"
        subtitulo="Como o Shaka e o Maroja cuidam da carteira: o BTC fica de colateral no perpétuo inverse, sem alavancagem; nas resistências vendem uma parte em escada (o hedge) e nos suportes recompram. Cada um começa com 1 BTC virtual; o placar é em BTC, contra quem só segurou. Nada vai para a corretora." />
      <Page>
        <Estado query={q}>
          {!d ? <Empty>{q.data?.erro ? `erro: ${q.data.erro}` : 'calculando a primeira vez (leva uns segundos depois que a API sobe)…'}</Empty> : <>
            {q.data && !q.data.ativo && <div><span className="alerta-pill">A carteira está desligada (CARTEIRA=0 no .env): isto é o último cálculo guardado, não o de agora.</span></div>}
            {q.data?.erro && <div><span className="alerta-pill">Último erro: {q.data.erro}</span></div>}
            {d.falhas.length > 0 && <div><span className="alerta-pill">Sem dado novo de: {d.falhas.join(', ')} (segue com o histórico)</span></div>}
            <div className="muted" style={{ fontSize: 12 }}>
              desde {dia(d.inicio_ms)} · até o bloco de 30 min fechado às {hora(d.fim_ms)} UTC · recalcula a cada bloco
            </div>
            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))' }}>
              {Object.entries(d.operadores).map(([nome, o]) => <CartaoOperador key={nome} nome={nome} o={o} />)}
            </div>
            <PlanoDeHoje d={d} />
          </>}
        </Estado>
        {q.data?.backtest && <Backtest b={q.data.backtest} />}
      </Page>
    </>
  )
}
