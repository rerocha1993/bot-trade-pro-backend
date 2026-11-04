/**
 * Aba Aggr: o aggr.trade que o Maroja abre na live de 04/11/2026 para ver se a Coinbase está comprando. BTC-USD da
 * Coinbase em cima e, embaixo, o prêmio da Coinbase, o CVD dos perpétuos contra o da Coinbase, a compra e a venda a
 * mercado de cada mercado por vela e as liquidações. A leitura dele: alta saudável é a Coinbase comprando junto, ao longo
 * do tempo; só o alavancado comprando é squeeze.
 */
import type { LogicalRange } from 'lightweight-charts'
import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import GraficoTV, { SEGUNDOS, type Vela } from '../components/chart/GraficoTV'
import { PaineisAggr } from '../components/chart/PaineisFluxo'

const SIMBOLO = 'COINBASE:BTC-USD'
/** os negócios e as liquidações vão até velas de 4 h (PASSO_MAX_PAINEIS) */
const TEMPOS = ['1m', '5m', '15m', '30m', '1h', '4h'] as const

export default function Aggr() {
  const [params, setParams] = useSearchParams()
  const tempo = (TEMPOS as readonly string[]).includes(params.get('t') ?? '') ? params.get('t')! : '5m'
  const [velas, setVelas] = useState<Vela[]>([])
  const [range, setRange] = useState<LogicalRange | null>(null)
  const tempos = useMemo(() => velas.map((k) => k.t), [velas])
  return (
    <div className="gpag">
      <div className="gbarra">
        <div className="gsimbolo" style={{ cursor: 'default' }}>
          <span className="mono"><b>BTC-USD</b></span>
          <span className="muted">Coinbase · à vista</span>
        </div>
        <div className="gtempos" role="group" aria-label="Tempo gráfico">
          {TEMPOS.map((t) => (
            <button key={t} type="button" className={t === tempo ? 'on' : ''} onClick={() => setParams({ t })}>{t}</button>
          ))}
        </div>
      </div>
      <div className="muted" style={{ fontSize: 12, margin: '4px 0 8px' }}>
        Como o aggr.trade: quem está comprando a mercado em cada mercado. Alta saudável é a Coinbase comprando junto; só os perpétuos
        comprando é squeeze. Leitura para o olho, não sinal: nada disso passou no teste contra sorteio.
      </div>
      <div className="card gcaixa">
        <GraficoTV key={tempo} simbolo={SIMBOLO} tempo={tempo} onVelas={setVelas} onRange={setRange} />
        {tempos.length > 0 && <PaineisAggr tempos={tempos} range={range} passo={SEGUNDOS[tempo]} />}
      </div>
    </div>
  )
}
