/**
 * Componentes de Elliott compartilhados entre as telas: cartão de cenário, caixa de alinhamento multi-grau
 * e o painel de gráfico com os overlays.
 *
 * Moraram dentro da tela do robô por um tempo e a tela de mercado importava de lá, o que fazia uma tela
 * depender da outra. Aqui são componentes de verdade: as telas dependem deles, e eles não dependem de tela nenhuma.
 */
import { useMemo } from 'react'
import { useCandles, useNiveis } from '../api/hooks'
import type { AnaliseGrau, Cenario, MultiGrau, Posicao } from '../api/types'
import { corPnl, corVies, fmtSigned, pct, preco, rotuloAcao, rotuloVies } from '../lib/format'
import { marcadoresPosicoes, overlaysElliott, overlaysNiveis } from '../lib/overlays'
import PriceChart from './chart/PriceChart'
import { Err, Loading } from './ui'

export const OV_CHIPS = [
  ['zig', 'ZigZag + ondas'],
  ['tpo', 'TPO'],
  ['vp', 'Volume Profile'],
  ['ob', 'Order blocks'],
  ['vwap', 'VWAP + bandas'],
  ['inst', 'POC / VAH / VAL'],
  ['trd', 'Entradas e saídas'],
] as const

export type OvKey = (typeof OV_CHIPS)[number][0]
export type Overlays = Record<OvKey, boolean>

export const GRAUS = ['operacional', 'contexto', 'macro'] as const
export type GrauKey = (typeof GRAUS)[number]

export function CenarioCard({ c, prim, compact }: { c: Cenario; prim: boolean; compact?: boolean }) {
  const p = c.probabilidade
  return (
    <div className={'scen' + (prim ? ' prim' : '')} style={compact ? { padding: '9px 10px' } : undefined}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
        <span className={c.vies === 'bull' ? 'arrow-up' : 'arrow-dn'} />
        <span style={{ flex: '1 1 auto', minWidth: 0, fontSize: compact ? 11.5 : 12, lineHeight: 1.35 }}>{c.nome}</span>
        <span className="mono" style={{ fontSize: 13, color: prim ? 'var(--acc)' : 'var(--text)' }}>{pct(p)}</span>
      </div>
      {!compact && (
        <>
          <div className="bar" style={{ margin: '8px 0' }}>
            <span style={{ width: `${Math.min(100, p * 100)}%`, background: c.vies === 'bull' ? 'var(--green)' : 'var(--red)' }} />
          </div>
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
            <span className="tag mono" style={{ textTransform: 'none', letterSpacing: 0 }}>{c.fase}</span>
            <span className="tag mono" style={{ textTransform: 'none', letterSpacing: 0, borderColor: prim ? 'rgba(127,216,222,0.5)' : undefined, color: prim ? 'var(--acc)' : undefined }}>
              {prim ? 'primário' : c.completo ? 'completo' : 'em andamento'}
            </span>
            {c.prob_sucesso !== undefined && c.prob_sucesso !== null && (
              <span className="tag mono" style={{ textTransform: 'none', letterSpacing: 0 }}>calibrado {pct(c.prob_sucesso)}</span>
            )}
          </div>
        </>
      )}
      <div className="mono muted" style={{ fontSize: 10.5, marginTop: compact ? 6 : 7 }}>
        inval. {preco(c.invalidacao)} · alvos {c.alvos.slice(0, 3).map(preco).join(' · ') || '—'}
      </div>
    </div>
  )
}

export function AlinhamentoBox({ mg }: { mg: MultiGrau }) {
  const vies = (g: AnaliseGrau) => (g.prob_bull >= 0.6 ? 'alta' : g.prob_bear >= 0.6 ? 'baixa' : 'neutro')
  const a = mg.alinhamento
  const linhas: [string, string, string][] = GRAUS.map((k) => [
    `${k} ${mg.timeframes[k]}`,
    mg.graus[k].fase + (mg.graus[k].primario ? '' : ' (sem cenário)'),
    vies(mg.graus[k]),
  ])
  if (a.vies_mestre) linhas.push(['mestre travado', '—', rotuloVies(a.vies_mestre)])
  if (a.estado_superciclo) linhas.push(['trader (superciclo)', a.estado_superciclo, rotuloVies(a.vies_trader)])
  return (
    <div>
      {linhas.map(([g, f, v]) => (
        <div key={g} className="mono" style={{ display: 'flex', gap: 8, alignItems: 'baseline', padding: '4px 0', fontSize: 11 }}>
          <span className="muted" style={{ width: 120, flex: '0 0 120px', textTransform: 'capitalize' }}>{g}</span>
          <span style={{ flex: '1 1 auto', minWidth: 0 }}>{f}</span>
          <span style={{ color: corVies(v) }}>{v}</span>
        </div>
      ))}
      <div className={a.bloqueado ? 'warn' : 'info'} style={{ marginTop: 8, fontSize: 11 }}>
        {a.bloqueado ? 'Bloqueado' : a.alinhado ? 'Alinhado' : a.contra_tendencia ? 'Contra a tendência (tamanho reduzido)' : 'Sem consenso'} · direção {rotuloAcao(a.direcao)}
        {a.fator_tamanho !== undefined && a.fator_tamanho !== 1 && ` · tamanho ×${a.fator_tamanho}`}
        <div className="muted" style={{ marginTop: 4, fontSize: 10.5 }}>{a.motivo}</div>
      </div>
    </div>
  )
}

export function GrafPainel({ par, tf, grau, ov, posicoes, height = 430, logScale }: {
  par: string
  tf: string
  grau: AnaliseGrau | undefined
  ov: Partial<Overlays>
  posicoes?: Posicao[]
  height?: number
  logScale?: boolean
}) {
  const candles = useCandles(par, tf, 300)
  const niveis = useNiveis(par, tf, !!(ov.tpo || ov.vp || ov.ob || ov.vwap || ov.inst))
  const dados = candles.data ?? []
  const ultimo = dados[dados.length - 1]
  const ell = useMemo(() => overlaysElliott(grau, ultimo?.close, ultimo?.time), [grau, ultimo?.close, ultimo?.time])
  const niv = useMemo(() => overlaysNiveis(niveis.data, ultimo?.time), [niveis.data, ultimo?.time])
  const levels = useMemo(() => [
    ...(ov.zig ? ell.levels : []),
    ...(ov.inst ? niv.levels.filter((l) => ['POC', 'VAH', 'VAL'].includes(l.label)) : []),
    ...(ov.vwap ? niv.levels.filter((l) => l.label.includes('VWAP') || l.label.includes('σ')) : []),
  ], [ov.zig, ov.inst, ov.vwap, ell.levels, niv.levels])
  const markers = useMemo(() => (ov.trd ? marcadoresPosicoes(posicoes, dados) : []), [ov.trd, posicoes, dados])
  const var24 = useMemo(() => {
    if (dados.length < 2) return null
    const tfSeg = dados[1].time - dados[0].time
    const n = Math.max(1, Math.round(86400 / Math.max(tfSeg, 1)))
    const base = dados[Math.max(0, dados.length - 1 - n)]
    return ultimo.close / base.close - 1
  }, [dados, ultimo])

  if (candles.isPending) return <Loading />
  if (candles.isError) return <Err e={candles.error} />
  return (
    <div className="chart-wrap">
      <div className="chart-price">
        <div className="p">{ultimo ? preco(ultimo.close) : '—'}</div>
        {var24 !== null && <div className="d" style={{ color: corPnl(var24) }}>{fmtSigned(var24 * 100, 2)}% · 24 h</div>}
      </div>
      <PriceChart
        candles={dados}
        paths={ov.zig ? ell.paths : []}
        labels={ov.zig ? ell.labels : []}
        levels={levels}
        rects={ov.ob ? niv.rects : []}
        profile={ov.tpo ? niv.profile : ov.vp ? niv.vpProfile : null}
        markers={markers}
        height={height}
        logScale={logScale}
      />
    </div>
  )
}
