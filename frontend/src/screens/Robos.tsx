import { useRobos, useTradesRobos } from '../api/hooks'
import type { Robo, TradeRobo } from '../api/types'
import { Header, Page } from '../components/Layout'
import { Card, Empty, Estado, Tag } from '../components/ui'
import { fmt, preco as fmtPreco } from '../lib/format'

/** Os 4 robôs do conselho em simulação: banca virtual, placar e posição de cada um, e os trades fechados. */
const COR = { ganho: '#2ecc84', perda: '#f0544f', compra: '#2ecc84', venda: '#f0544f', aviso: '#f5c04a' }
const hora = (s: number) => new Date(s * 1000).toISOString().slice(5, 16).replace('T', ' ')
const NOME_SAIDA: Record<string, string> = { alvo: 'alvo', stop: 'stop', medio: 'zero a zero', tempo: 'tempo' }

function CartaoRobo({ r, inicial }: { r: Robo; inicial: number }) {
  const var_ = r.banca - inicial
  const p = r.posicao
  const corLado = p?.lado === 'compra' ? COR.compra : COR.venda
  return (
    <Card title={r.nome} right={<span className="muted" style={{ fontSize: 12 }}>{r.trades} trade{r.trades === 1 ? '' : 's'}</span>}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <span className="mono" style={{ fontSize: 26 }}>{fmt(r.banca, 2)}</span>
        <span className="muted" style={{ fontSize: 12 }}>USDT virtuais</span>
        <span className="mono" style={{ color: var_ >= 0 ? COR.ganho : COR.perda }}>{var_ >= 0 ? '+' : ''}{fmt(var_, 2)}</span>
      </div>
      <div className="muted" style={{ fontSize: 12, margin: '6px 0 12px' }}>
        {r.trades ? `${r.ganhos} de ${r.trades} no lucro · ${r.resultado_r >= 0 ? '+' : ''}${fmt(r.resultado_r, 2)} R no total · média ${fmt(r.media_r ?? 0, 2)} R` : 'ainda sem trade fechado'}
      </div>
      {!p ? <div className="muted" style={{ fontSize: 13 }}>Esperando sinal.</div> : (
        <div style={{ borderTop: '1px solid var(--border-3)', paddingTop: 10, display: 'grid', gap: 6, fontSize: 13 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <Tag color={corLado}>{p.lado}</Tag>
            <Tag color={p.status === 'aberta' ? COR.aviso : 'var(--muted)'}>{p.status === 'aberta' ? 'posição aberta' : 'ordens postas'}</Tag>
            {p.tomou_1r && <Tag color={COR.ganho}>1R feito · stop no médio</Tag>}
          </div>
          <span className="muted" style={{ fontSize: 12 }}>{p.motivo}</span>
          <span className="mono" style={{ fontSize: 12 }}>
            {p.medio ? <>médio {fmtPreco(p.medio)} · </> : <>limitadas {p.fatias.map(([x]) => fmtPreco(x)).join(' / ')} até {hora(p.valido_ate_s)} · </>}
            stop {fmtPreco(p.stop_atual)} · alvo {p.alvo ? fmtPreco(p.alvo) : '—'}
          </span>
        </div>
      )}
    </Card>
  )
}

function LinhaTrade({ t, nome }: { t: TradeRobo; nome: string }) {
  const ganhou = t.resultado_r > 0
  return (
    <tr>
      <td className="muted">{hora(t.saida_s)}</td>
      <td className="sans">{nome}</td>
      <td><Tag color={t.lado === 'compra' ? COR.compra : COR.venda}>{t.lado}</Tag></td>
      <td className="r">{fmtPreco(t.medio)}</td>
      <td>{NOME_SAIDA[t.saida] ?? t.saida}{t.tomou_1r ? ' (após 1R)' : ''}</td>
      <td className="r" style={{ color: ganhou ? COR.ganho : COR.perda }}>{t.resultado_r >= 0 ? '+' : ''}{fmt(t.resultado_r, 2)} R</td>
      <td className="r" style={{ color: ganhou ? COR.ganho : COR.perda }}>{t.resultado_usdt >= 0 ? '+' : ''}{fmt(t.resultado_usdt, 2)}</td>
    </tr>
  )
}

export default function Robos() {
  const q = useRobos()
  const qt = useTradesRobos()
  const d = q.data
  const nomes = Object.fromEntries((d?.robos ?? []).map((r) => [r.robo, r.nome]))
  return (
    <>
      <Header titulo="Robôs" eyebrow="Simulação ao vivo"
        subtitulo="Os 4 robôs das combinações recomendadas rodam com o mercado de verdade, mas em simulação: registram entradas, stops e alvos com taxa, sem mandar ordem para a corretora. Cada um começa com 1.000 USDT virtuais e arrisca 0,5% por trade; em 1R realiza metade e leva o stop ao médio. É o teste ao vivo que falta antes de pensar em conta real." />
      <Page>
        <Estado query={q}>
          {!d ? <Empty>sem leitura</Empty> : <>
            {!d.ativo && <div><span className="alerta-pill">Os robôs estão desligados (ROBOS=0 no .env ou a API acabou de subir).</span></div>}
            {d.ultimo_erro && <div><span className="alerta-pill">Último erro: {d.ultimo_erro}</span></div>}
            {d.velas5 > 0 && d.velas5 < 288 * 11 && <div><span className="alerta-pill">Carregando o histórico de 11 dias para o mapa…</span></div>}
            <div className="grid" style={{ gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' }}>
              {d.robos.map((r) => <CartaoRobo key={r.robo} r={r} inicial={d.banca_inicial} />)}
            </div>
          </>}
        </Estado>
        <Card title="Trades fechados" sub="do mais novo para o mais antigo; R já desconta as taxas" pad={false}>
          <Estado query={qt}>
            {!qt.data?.trades.length ? <Empty>nenhum trade fechado ainda</Empty> : (
              <table className="table">
                <thead><tr><th>saída (UTC)</th><th>robô</th><th>lado</th><th className="r">médio</th><th>como saiu</th><th className="r">R</th><th className="r">USDT</th></tr></thead>
                <tbody>{qt.data.trades.map((t) => <LinhaTrade key={`${t.robo}-${t.saida_s}`} t={t} nome={nomes[t.robo] ?? t.robo} />)}</tbody>
              </table>
            )}
          </Estado>
        </Card>
      </Page>
    </>
  )
}
