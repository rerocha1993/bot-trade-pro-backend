/**
 * "Paredes de agora": no último retrato do livro do BTC (Coinbase + Binance + Bybit), as paredes mais fortes perto do
 * preço, 4 acima e 4 abaixo. A barra é quantas vezes a parede passa do normal daquela distância (ou das vizinhas).
 */
import { useMemo } from 'react'
import { useNuvensCalor } from '../api/hooks'
import type { CelulaCalor } from '../api/types'
import { corCalor, forca } from '../lib/calor'
import { fmt, preco as fmtPreco } from '../lib/format'
import { Card, Empty, Estado } from './ui'

const COR = { bids: '#2ecc84', asks: '#f0544f' }
const PASSO_S = 300
/** só a última coluna interessa: pede a última meia hora */
const JANELA_S = 1800
const FATOR = 3

function ParedeBarra({ c, preco, max }: { c: CelulaCalor; preco: number; max: number }) {
  const [lo, hi, lado, btc] = c
  const inten = forca(c)
  const meio = (lo + hi) / 2
  const dist = (meio / preco - 1) * 100
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '92px 1fr auto', gap: 10, alignItems: 'center', padding: '6px 0' }}>
      <span className="mono" style={{ color: lado === 0 ? COR.bids : COR.asks }}>{fmtPreco(meio)}</span>
      <div style={{ height: 14, borderRadius: 7, background: 'var(--line, rgba(255,255,255,0.06))' }}>
        <div style={{ height: '100%', width: `${Math.max(6, (inten / max) * 100)}%`, borderRadius: 7, background: corCalor(lado, inten) }} />
      </div>
      <span className="muted" style={{ fontSize: 12, textAlign: 'right', whiteSpace: 'nowrap' }}>{fmt(inten, 1)}x · {fmt(btc, 0)} BTC · {dist > 0 ? '+' : ''}{fmt(dist, 2)}%</span>
    </div>
  )
}

export default function ParedesAgora({ preco }: { preco: number | null }) {
  const inicio = Math.floor(Date.now() / 1000 / PASSO_S) * PASSO_S - JANELA_S
  const q = useNuvensCalor(inicio, 'coinbase,binance,bybit', FATOR, PASSO_S)
  const d = q.data
  const ultimaCol = d?.colunas.length ? d.colunas[d.colunas.length - 1] : null
  const paredes = useMemo(() => {
    if (!ultimaCol || !preco) return { acima: [] as CelulaCalor[], abaixo: [] as CelulaCalor[], max: 1 }
    const fortes = [...ultimaCol.celulas].sort((a, b) => forca(b) - forca(a)).slice(0, 12)
    const acima = fortes.filter((c) => c[0] > preco).sort((a, b) => b[0] - a[0]).slice(-4)
    const abaixo = fortes.filter((c) => c[1] < preco).sort((a, b) => b[0] - a[0]).slice(0, 4)
    return { acima, abaixo, max: Math.max(1, ...fortes.map((c) => forca(c))) }
  }, [ultimaCol, preco])

  return (
    <Card title="Paredes de agora" sub={`as mais fortes perto do preço no livro do BTC (Coinbase + Binance + Bybit); a barra é quantas vezes acima do normal${ultimaCol ? ` · retrato das ${new Date(ultimaCol.ts * 1000).toISOString().slice(11, 16)} UTC` : ''}`}>
      <Estado query={q}>
        {!preco || (!paredes.acima.length && !paredes.abaixo.length) ? <Empty>nenhuma parede acima do normal agora</Empty> : (
          <div>
            {paredes.acima.map((c) => <ParedeBarra key={`a${c[0]}`} c={c} preco={preco} max={paredes.max} />)}
            <div style={{ display: 'grid', gridTemplateColumns: '92px 1fr', gap: 10, alignItems: 'center', padding: '8px 0' }}>
              <span className="mono">{fmtPreco(preco)}</span>
              <div style={{ borderTop: '1px dashed var(--muted)', opacity: 0.6 }} />
            </div>
            {paredes.abaixo.map((c) => <ParedeBarra key={`b${c[0]}`} c={c} preco={preco} max={paredes.max} />)}
          </div>
        )}
      </Estado>
    </Card>
  )
}
