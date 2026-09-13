import { useState } from 'react'
import { useTradeirosBacktest, useTradeirosPlano } from '../api/hooks'
import type { DecisaoTradeiros, PlanoTradeiros, TradeirosAno, TradeirosPlanoResp } from '../api/types'
import { Header, Page } from '../components/Layout'
import { Card, Empty, Estado, KPI, KV, Tag } from '../components/ui'
import { fmt, preco as fmtPreco } from '../lib/format'

/** Verde = compra (inclui recomprar o hedge), vermelho = venda (inclui vender no inverse). */
const TIPO: Record<string, { rotulo: string; cor: string }> = {
  compra: { rotulo: 'compra', cor: 'var(--green)' },
  venda_direcional: { rotulo: 'venda direcional', cor: 'var(--red)' },
  hedge_aumentar: { rotulo: 'hedge ↑ vende no inverse', cor: 'var(--red)' },
  hedge_realizar: { rotulo: 'hedge ↓ recompra', cor: 'var(--green)' },
  ficar_fora: { rotulo: 'ficar fora', cor: 'var(--muted)' },
}
const ZONA: Record<string, string> = {
  sem_range: 'sem range', abaixo_do_valor: 'abaixo do valor', acima_do_valor: 'acima do valor', meio: 'meio do range',
  fundo: 'fundo do range', topo: 'topo do range', entre_fundo_e_meio: 'entre o fundo e o meio', entre_meio_e_topo: 'entre o meio e o topo',
}
const PERFIL = {
  shaka: { nome: 'Shaka', sub: 'agressivo · risco até 2% · entra pequeno sem esperar reação · mais peso ao fluxo · faz venda direcional' },
  maroja: { nome: 'Maroja', sub: 'conservador · risco até 1% · Elliott é o mapa · espera reação fora do valor · protege mais no mesmo dia' },
} as const
const FLUXO: Record<string, string> = {
  oi_reset: 'reset de OI', funding_negativo: 'funding negativo (30d)', funding_caro: 'funding caro', longs_presos: 'longs presos',
  shorts_presos: 'shorts presos', medo_extremo: 'medo extremo', euforia: 'euforia',
}

const horaUTC = (ms: number | null) => (ms ? `${new Date(ms).toISOString().slice(0, 10)} ${new Date(ms).toISOString().slice(11, 16)} UTC` : '—')
const pct = (x: number | null | undefined, dec = 1) => (x === null || x === undefined ? '—' : `${fmt(x * 100, dec)}%`)
const sinal = (x: number | null | undefined, dec = 1) => (x === null || x === undefined ? '—' : `${x >= 0 ? '+' : ''}${fmt(x, dec)}%`)
const nivel = (x: number | null | undefined) => (x === null || x === undefined ? '—' : fmt(x, 0))

function LinhaDecisao({ d }: { d: DecisaoTradeiros }) {
  const t = TIPO[d.tipo] ?? { rotulo: d.tipo, cor: 'var(--muted)' }
  return (
    <div style={{ padding: '10px 0', borderTop: '1px solid color-mix(in srgb, var(--muted) 22%, transparent)' }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <Tag color={t.cor}>{t.rotulo}</Tag>
        {d.exige_reacao && <Tag color="var(--amber)">espera reação</Tag>}
        <span className="muted mono" style={{ fontSize: 11 }}>{d.regras.join(' · ')}</span>
      </div>
      <p className="sub" style={{ margin: '6px 0 4px' }}>{d.motivo}</p>
      {d.zona && <KV k={d.pesos_fatias.length > 1 ? `Zona · ${d.pesos_fatias.length} limitadas` : 'Zona'} v={`${nivel(d.zona[0])} – ${nivel(d.zona[1])}`} />}
      {d.stop != null && <KV k={d.tipo === 'hedge_aumentar' ? 'Stop (pedágio)' : 'Stop a mercado'} v={nivel(d.stop)} color="var(--red)" />}
      {d.alvo != null && <KV k="Alvo" v={nivel(d.alvo)} color="var(--green)" />}
      {d.rr != null && <KV k="Risco/retorno" v={`${fmt(d.rr, 1)} R`} />}
      {d.risco > 0 && <KV k="Risco da carteira" v={pct(d.risco, 2)} />}
      {d.fracao_hedge > 0 && <KV k="Muda o hedge em" v={pct(d.fracao_hedge, 0)} />}
    </div>
  )
}

function CartaoPlano({ nome, p }: { nome: keyof typeof PERFIL; p: PlanoTradeiros }) {
  const info = PERFIL[nome]
  const sinais = Object.entries(p.fluxo).filter(([, v]) => v).map(([k]) => FLUXO[k] ?? k)
  return (
    <Card title={info.nome} sub={info.sub} right={<Tag color="var(--acc)">hedge {pct(p.hedge_alvo, 0)}</Tag>}>
      <div className="muted mono" style={{ fontSize: 11, marginBottom: 6 }}>
        hedge por {p.hedge_regras.join(' · ') || '—'}{sinais.length > 0 && ` · fluxo: ${sinais.join(', ')}`}
      </div>
      {p.decisoes.map((d, i) => <LinhaDecisao key={`${d.tipo}-${i}`} d={d} />)}
    </Card>
  )
}

function Conteudo({ d, replay }: { d: TradeirosPlanoResp; replay: boolean }) {
  const { leitura: lt, mapa } = d
  const r = lt.range
  const dv = lt.derivativos
  const naked = lt.naked_pocs.filter((x) => Math.abs(x / d.preco - 1) <= 0.12)
  const elliott = mapa.veto_onda_4 ? 'onda 4 provável: não operar' : mapa.setup_onda_2
    ? `setup de onda 2 ${mapa.setup_onda_2.vies === 'bull' ? 'de alta' : 'de baixa'}` : `grau operacional ${mapa.grau_operacional ?? '—'}`
  return (
    <>
      <p className="sub" style={{ marginTop: 0 }}>
        {replay ? 'Replay' : 'Ao vivo'} · {d.fonte} · preço {fmtPreco(d.preco)} · candles fechados até {horaUTC(d.dados_ate.candles)}
        {' '}· derivativos até {horaUTC(d.dados_ate.derivativos)}
      </p>
      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
        <KPI l="Range (merge)" v={r ? `${nivel(r.val)} – ${nivel(r.vah)}` : '—'}
          sub={r ? `${ZONA[lt.zona] ?? lt.zona} · p ${fmt(lt.p ?? 0, 2)} · POC ${nivel(r.poc)} · ${r.dias} dias` : 'sem range montado'} />
        <KPI l="Ciclo" v={lt.ciclo.estado ?? '—'}
          sub={`${sinal((lt.ciclo.do_topo ?? 0) * 100)} do topo ${nivel(lt.ciclo.ath)} · semanal ${lt.estrutura_semanal.tendencia ?? '—'} · 4h ${lt.estrutura.tendencia ?? '—'}`} />
        <KPI l="Elliott (várias contagens)" v={`alta ${pct(mapa.prob_bull, 0)} · baixa ${pct(mapa.prob_bear, 0)}`}
          color={mapa.inclinacao > 0.1 ? 'var(--green)' : mapa.inclinacao < -0.1 ? 'var(--red)' : undefined} sub={elliott} />
        <KPI l="Fluxo e sentimento" v={`Fear & Greed ${lt.sentimento ?? '—'}`}
          sub={`funding ${dv.funding != null ? fmt(dv.funding * 100, 4) + '%' : '—'} · OI ${dv.oi_vs_max_30d != null ? sinal(dv.oi_vs_max_30d * 100, 0) : '—'} da máx. 30d`} />
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', alignItems: 'start' }}>
        <CartaoPlano nome="shaka" p={d.planos.shaka} />
        <CartaoPlano nome="maroja" p={d.planos.maroja} />
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', alignItems: 'start' }}>
        <Card title="Níveis" sub="o que eles marcam antes da live">
          <div>
            <KV k="VAH · POC · VAL" v={r ? `${nivel(r.vah)} · ${nivel(r.poc)} · ${nivel(r.val)}` : '—'} />
            <KV k="Topo · fundo do range" v={r ? `${nivel(r.maxima)} · ${nivel(r.minima)}` : '—'} />
            <KV k="Abertura dia · semana · mês" v={`${nivel(lt.aberturas.dia)} · ${nivel(lt.aberturas.semana)} · ${nivel(lt.aberturas.mes)}`} />
            <KV k="Pivô virgem acima · abaixo" v={`${nivel(lt.pivo_virgem.acima)} · ${nivel(lt.pivo_virgem.abaixo)}`} />
            <KV k="Naked POCs a até 12%" v={naked.length ? naked.map((x) => nivel(x)).join(' · ') : '—'} />
            <KV k="Invalidação comum compra · venda" v={`${nivel(mapa.invalidacao_compra)} · ${nivel(mapa.invalidacao_venda)}`} />
            {lt.fib.niveis && (
              <KV k={`Fibonacci ${lt.fib.direcao === 'up' ? 'da alta' : 'da queda'} (${nivel(lt.fib.de)} → ${nivel(lt.fib.ate)})`}
                v={Object.entries(lt.fib.niveis).map(([k, x]) => `${k} ${nivel(x)}`).join(' · ')} />
            )}
          </div>
        </Card>

        <Card title="Contagens de Elliott" sub="refeitas uma vez por dia, com probabilidade e invalidação">
          {mapa.erro ? <Empty>{mapa.erro}</Empty> : mapa.contagens.length === 0 ? <Empty>sem contagem</Empty> : (
            <div style={{ overflowX: 'auto' }}>
              <table className="table">
                <thead><tr><th>grau</th><th>viés</th><th>fase</th><th>prob.</th><th>invalidação</th></tr></thead>
                <tbody>
                  {mapa.contagens.map((c, i) => (
                    <tr key={`${c.grau}-${i}`}>
                      <td>{c.grau}</td>
                      <td style={{ color: c.vies === 'bull' ? 'var(--green)' : 'var(--red)' }}>{c.vies === 'bull' ? 'alta' : 'baixa'}</td>
                      <td className="muted">{c.fase?.replaceAll('_', ' ')}</td>
                      <td>{pct(c.probabilidade, 0)}</td>
                      <td>{nivel(c.invalidacao)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </>
  )
}

function TabelaAnos({ nome, anos }: { nome: string; anos: TradeirosAno[] }) {
  const cor = (x: number | null) => (x === null ? undefined : x >= 0 ? 'var(--green)' : 'var(--red)')
  return (
    <div style={{ overflowX: 'auto', marginTop: 12 }}>
      <div className="eyebrow" style={{ marginBottom: 6 }}>{PERFIL[nome as keyof typeof PERFIL]?.nome ?? nome} · por ano</div>
      <table className="table">
        <thead>
          <tr><th>ano</th><th>BTC</th><th>USD</th><th>HODL USD</th><th>queda máx. USD</th><th>HODL queda</th><th>hedge médio</th>
            <th>trades</th><th>R</th><th>hedge fixo</th><th>sorteio p95</th><th>acima de</th></tr>
        </thead>
        <tbody>
          {anos.map((a) => (
            <tr key={a.ano}>
              <td>{a.ano}</td>
              <td style={{ color: cor(a.ganho_btc_pct) }}>{sinal(a.ganho_btc_pct)}</td>
              <td>{sinal(a.retorno_usd_pct)}</td>
              <td className="muted">{sinal(a.hodl_usd_pct)}</td>
              <td>{fmt(a.dd_usd_pct, 1)}%</td>
              <td className="muted">{fmt(a.dd_hodl_pct, 1)}%</td>
              <td>{fmt(a.hedge_medio_pct, 0)}%</td>
              <td>{a.trades}</td>
              <td style={{ color: cor(a.r_total) }}>{fmt(a.r_total, 1)}</td>
              <td className="muted">{a.fixo_btc != null ? sinal((a.fixo_btc - 1) * 100) : '—'}</td>
              <td className="muted">{a.sorteio_p95 != null ? sinal((a.sorteio_p95 - 1) * 100) : '—'}</td>
              <td>{a.percentil != null ? `${fmt(a.percentil * 100, 0)}% dos sorteios` : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Backtest() {
  const q = useTradeirosBacktest()
  const d = q.data
  return (
    <Card title="Backtest da carteira em BTC"
      sub="1 BTC no inverse, ano a ano. Só há vantagem se o BTC final passar do percentil 95 dos sorteios de direção nos mesmos candles E do hedge fixo">
      <Estado query={q}>
        {!d?.disponivel ? <Empty>ainda sem resultado: rode python scripts/backtest_tradeiros.py</Empty> : (
          <>
            <p className="sub" style={{ marginTop: 0 }}>gerado em {horaUTC(d.gerado_em)} · treino 2019–2022 · validação 2023–2024 · holdout 2025–2026</p>
            <div style={{ overflowX: 'auto' }}>
              <table className="table">
                <thead><tr><th>perfil</th><th>período</th><th>BTC</th><th>hedge fixo</th><th>sorteio p95</th><th>acima de</th><th>vantagem</th></tr></thead>
                <tbody>
                  {Object.entries(d.periodos).flatMap(([nome, pers]) => Object.entries(pers).map(([per, p]) => (
                    <tr key={`${nome}-${per}`}>
                      <td>{PERFIL[nome as keyof typeof PERFIL]?.nome ?? nome}</td>
                      <td>{per}</td>
                      <td style={{ color: p.btc >= 1 ? 'var(--green)' : 'var(--red)' }}>{sinal((p.btc - 1) * 100)}</td>
                      <td className="muted">{sinal((p.fixo - 1) * 100)}</td>
                      <td className="muted">{sinal((p.p95_sorteio - 1) * 100)}</td>
                      <td>{fmt(p.percentil * 100, 0)}%</td>
                      <td><Tag color={p.vantagem ? 'var(--green)' : 'var(--muted)'}>{p.vantagem ? 'sim' : 'não'}</Tag></td>
                    </tr>
                  )))}
                </tbody>
              </table>
            </div>
            {Object.entries(d.anos).map(([nome, anos]) => <TabelaAnos key={nome} nome={nome} anos={anos} />)}
          </>
        )}
      </Estado>
    </Card>
  )
}

export default function Tradeiros() {
  const [data, setData] = useState('')
  const [consulta, setConsulta] = useState<string | null>(null)
  const q = useTradeirosPlano(consulta)
  const campo = { background: 'transparent', color: 'var(--text)', border: '1px solid color-mix(in srgb, var(--muted) 40%, transparent)',
    borderRadius: 8, padding: '6px 10px', fontFamily: 'var(--mono)', fontSize: 12 }
  return (
    <>
      <Header titulo="Portal Tradeiros" eyebrow="Portal 2 · Shaka × Maroja"
        subtitulo="A leitura do dia, o mapa de Elliott com várias contagens e o plano de cada um — simulação: nada aqui envia ordem"
        actions={(
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <input type="date" aria-label="dia do replay" value={data} onChange={(e) => setData(e.target.value)} style={campo} />
            <button type="button" className="btn" style={campo} disabled={!data} onClick={() => setConsulta(data)}>Ver o dia</button>
            <button type="button" className="btn" style={campo} disabled={consulta === null} onClick={() => { setConsulta(null); setData('') }}>Ao vivo</button>
          </div>
        )} />
      <Page>
        <Estado query={q}>
          {!q.data ? <Empty>sem leitura</Empty> : <Conteudo d={q.data} replay={consulta !== null} />}
        </Estado>
        <Backtest />
      </Page>
    </>
  )
}
