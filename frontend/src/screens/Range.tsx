import { useMemo } from 'react'
import { useRangeContexto } from '../api/hooks'
import type { PerfilDia, PlanoRange } from '../api/types'
import { Header, Page } from '../components/Layout'
import { Card, Empty, Estado, KPI, KV, Tag } from '../components/ui'
import { fmt, preco as fmtPreco } from '../lib/format'

const COR = { poc: 'var(--amber)', va: 'var(--acc)', naked: 'var(--amber)', plano: 'var(--indigo)' }
const SESSAO = { asia: 'Ásia', europa: 'Europa', america: 'América' } as const

/** O perfil é por dia UTC: mostrar no fuso local trocaria o dia. */
const diaUTC = (ms: number) => new Date(ms).toISOString().slice(0, 10)
const horaUTC = (ms: number) => `${new Date(ms).toISOString().slice(0, 10)} ${new Date(ms).toISOString().slice(11, 16)} UTC`

/** Mapa vertical do range: área de valor, POC, extremos, naked POCs e a escada do plano. */
function Mapa({ lo, hi, val, vah, poc, minima, maxima, preco, naked, plano }: {
  lo: number; hi: number; val: number; vah: number; poc: number; minima: number; maxima: number
  preco: number; naked: number[]; plano: PlanoRange | null
}) {
  const y = (p: number) => `${((hi - p) / (hi - lo)) * 100}%`
  const linha = (p: number, cor: string, rotulo: string, tracejada = false, esquerda = false) => (
    <div key={`${rotulo}-${p}`} style={{ position: 'absolute', left: 0, right: 0, top: y(p), height: 0 }}>
      <div style={{ borderTop: `1px ${tracejada ? 'dashed' : 'solid'} ${cor}`, opacity: tracejada ? 0.6 : 1 }} />
      <div style={{ position: 'absolute', [esquerda ? 'left' : 'right']: 6, top: -15, fontSize: 11, color: cor,
                    fontFamily: 'var(--mono)', whiteSpace: 'nowrap' }}>
        {rotulo} {fmt(p, 0)}
      </div>
    </div>
  )
  return (
    <div style={{ position: 'relative', height: 460, background: 'color-mix(in srgb, var(--acc) 4%, transparent)', borderRadius: 10 }}>
      <div style={{
        position: 'absolute', left: 0, right: 0, top: y(vah), height: `${((vah - val) / (hi - lo)) * 100}%`,
        background: 'color-mix(in srgb, var(--acc) 12%, transparent)', borderTop: `1px solid ${COR.va}`, borderBottom: `1px solid ${COR.va}`,
      }} />
      {linha(maxima, 'var(--muted)', 'topo', true, true)}
      {linha(vah, COR.va, 'VAH')}
      {linha(poc, COR.poc, 'POC')}
      {linha(val, COR.va, 'VAL')}
      {linha(minima, 'var(--muted)', 'fundo', true, true)}
      {naked.map((p) => (
        <div key={`nk-${p}`} style={{ position: 'absolute', left: 0, width: 42, top: y(p), height: 0 }}>
          <div style={{ borderTop: `2px dotted ${COR.naked}` }} />
          <div style={{ position: 'absolute', left: 48, top: -8, fontSize: 10, color: COR.naked, fontFamily: 'var(--mono)', whiteSpace: 'nowrap' }}>
            naked {fmt(p, 0)}
          </div>
        </div>
      ))}
      {plano?.niveis.map((p, i) => (
        <div key={`fatia-${i}`} style={{ position: 'absolute', left: '30%', width: 60, top: y(p), height: 0, borderTop: `2px solid ${COR.plano}` }} />
      ))}
      {plano && linha(plano.stop, 'var(--red)', 'stop', true)}
      <div style={{ position: 'absolute', left: 0, right: 0, top: y(preco), height: 0 }}>
        <div style={{ borderTop: '2px solid var(--text)' }} />
        <div style={{ position: 'absolute', left: 6, top: -18, fontSize: 12, color: 'var(--text)', fontFamily: 'var(--mono)', fontWeight: 600 }}>
          {fmtPreco(preco)}
        </div>
      </div>
    </div>
  )
}

function LinhaPerfil({ p, atual }: { p: PerfilDia; atual: boolean }) {
  const sessoes = (['asia', 'europa', 'america'] as const)
    .map((s) => (p.sessoes[s] ? `${SESSAO[s]} ${fmt(p.sessoes[s].poc, 0)}` : null))
    .filter(Boolean).join(' · ')
  return (
    <tr>
      <td>{diaUTC(p.inicio)} {atual && <Tag color="var(--acc)">em formação</Tag>}</td>
      <td style={{ color: COR.poc }}>{fmt(p.poc, 0)}</td>
      <td>{fmt(p.val, 0)} – {fmt(p.vah, 0)}</td>
      <td className="muted">{fmt(p.minima, 0)} – {fmt(p.maxima, 0)}</td>
      <td className="muted">{sessoes || '—'}</td>
    </tr>
  )
}

export default function Range() {
  const q = useRangeContexto('BTCUSDT')
  const d = q.data
  const escala = useMemo(() => {
    if (!d?.range) return null
    const pontos = [d.range.minima, d.range.maxima, d.preco, ...(d.plano ? [d.plano.stop, d.plano.alvo2] : [])]
    const lo = Math.min(...pontos), hi = Math.max(...pontos)
    const folga = (hi - lo) * 0.06 || 1
    return { lo: lo - folga, hi: hi + folga }
  }, [d])
  const nakedPerto = useMemo(() => (d ? d.naked_pocs
    .filter((n) => Math.abs(n.preco / d.preco - 1) <= 0.12)
    .sort((a, b) => Math.abs(a.preco - d.preco) - Math.abs(b.preco - d.preco)) : []), [d])
  const nakedNoMapa = useMemo(() => (escala ? nakedPerto.filter((n) => n.preco >= escala.lo && n.preco <= escala.hi).map((n) => n.preco) : []),
    [escala, nakedPerto])
  const plano = d?.plano ?? d?.barrado ?? null

  return (
    <>
      <Header titulo="Jogo do range" par="BTCUSDT" eyebrow="Tradeiros"
        subtitulo="TPO por dia e por sessão, merge do range, naked POCs e o contexto de presos — a mesma leitura do robô 10" />
      <Page>
        <Estado query={q}>
          {!d ? <Empty>sem leitura</Empty> : (
            <>
              <div className="grid" style={{ gridTemplateColumns: 'repeat(4, minmax(0, 1fr))' }}>
                <KPI l="Range" v={d.range ? (d.range.valido ? 'válido' : 'sem range') : '—'}
                  color={d.range?.valido ? 'var(--green)' : 'var(--muted)'}
                  sub={d.range ? `merge de ${d.range.dias} dia(s), mínimo 3` : null} />
                <KPI l="Área de valor" v={d.range ? `${fmt(d.range.val, 0)} – ${fmt(d.range.vah, 0)}` : '—'}
                  sub={d.range?.largura_pct ? `largura ${fmt(d.range.largura_pct, 2)}% · POC ${fmt(d.range.poc, 0)}` : null} />
                <KPI l="Toques sem rotação" v={`VAL ${d.toques.val ?? 0} · VAH ${d.toques.vah ?? 0}`}
                  sub={d.aceitacao ? (d.aceitacao === 1 ? 'aceitação acima do VAH' : 'aceitação abaixo do VAL') : 'sem aceitação fora do valor'} />
                <KPI l="Long/short de contas" v={d.long_short?.atual ? fmt(d.long_short.atual, 2) : '—'}
                  sub={d.long_short?.mediana_30d ? `mediana 30d ${fmt(d.long_short.mediana_30d, 2)}` : 'sem dado'} />
              </div>

              <div className="grid" style={{ gridTemplateColumns: 'minmax(320px, 40fr) minmax(0, 60fr)', alignItems: 'start' }}>
                <Card title="Mapa do range" sub={d.ate_ms ? `blocos de 30 min fechados até ${horaUTC(d.ate_ms)}` : undefined}>
                  {d.range && escala
                    ? <Mapa lo={escala.lo} hi={escala.hi} val={d.range.val} vah={d.range.vah} poc={d.range.poc}
                      minima={d.range.minima} maxima={d.range.maxima} preco={d.preco}
                      naked={nakedNoMapa} plano={d.plano} />
                    : <Empty>sem range montado</Empty>}
                </Card>

                <div style={{ display: 'grid', gap: 16 }}>
                  <Card title="O que o robô faria agora"
                    right={<Tag color={d.plano ? 'var(--green)' : 'var(--muted)'}>{d.plano ? (d.plano.lado === 1 ? 'compra no VAL' : 'venda no VAH') : 'aguardar'}</Tag>}>
                    <p className="sub" style={{ marginTop: 0 }}>{d.motivo}</p>
                    {plano && (
                      <div>
                        <KV k="Fatias" v={plano.niveis.map((n) => fmt(n, 0)).join(' · ')} />
                        <KV k="Stop" v={fmt(plano.stop, 0)} color="var(--red)" />
                        <KV k="Tirar o risco" v={`${fmt(plano.alvo1, 0)} (POC) ou 1:1`} />
                        <KV k="Alvo final" v={fmt(plano.alvo2, 0)} color="var(--green)" />
                        <KV k="Risco/retorno" v={`${fmt(plano.rr, 2)}x`} />
                      </div>
                    )}
                  </Card>

                  <Card title="Presos" sub="long/short de contas da Bybit contra a mediana de 30 dias">
                    <div>
                      <KV k="Compra no VAL" color={d.long_short?.presos_no_val ? 'var(--green)' : 'var(--muted)'}
                        v={d.long_short?.presos_no_val ? 'liberada: multidão vendida' : 'barrada: faltam vendidos no fundo'} />
                      <KV k="Venda no VAH" color={d.long_short?.presos_no_vah ? 'var(--green)' : 'var(--muted)'}
                        v={d.long_short?.presos_no_vah ? 'liberada: multidão comprada' : 'barrada: faltam comprados no topo'} />
                    </div>
                    <p className="sub">Medido em 1.143 toques desde 2020: a borda segurou 74% com os presos do outro lado, contra 64% sem eles.</p>
                  </Card>

                  <Card title="Naked POCs" sub="POCs de dias anteriores que o preço ainda não voltou a tocar">
                    {nakedPerto.length === 0 ? <Empty>nenhum a menos de 12% do preço</Empty> : (
                      <div>
                        {nakedPerto.slice(0, 8).map((n) => (
                          <KV key={n.preco} k={fmt(n.preco, 0)}
                            v={`${n.preco > d.preco ? '+' : ''}${fmt((n.preco / d.preco - 1) * 100, 2)}% · ${diaUTC(n.dia_ms)}`} />
                        ))}
                      </div>
                    )}
                  </Card>
                </div>
              </div>

              <Card title="Perfis por dia e por sessão" sub="POC, área de valor e extremos de cada dia UTC (00:00 às 23:59 UTC)">
                <table className="table">
                  <thead><tr><th>dia</th><th>POC</th><th>área de valor</th><th>extremos</th><th>POC das sessões</th></tr></thead>
                  <tbody>
                    {[...d.perfis].reverse().map((p, i) => <LinhaPerfil key={p.inicio} p={p} atual={i === 0} />)}
                  </tbody>
                </table>
              </Card>
            </>
          )}
        </Estado>
      </Page>
    </>
  )
}
