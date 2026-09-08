import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { api } from '../api/client'
import { usePontos } from '../api/hooks'
import type { PontoInstitucional } from '../api/types'
import { Header, Page, usePreco } from '../components/Layout'
import { Btn, Card, Chip, Empty, Err, Loading } from '../components/ui'
import { fmt, hora, preco } from '../lib/format'

const CORES: Record<string, string> = { POC: '#fbbf24', VAH: '#fbbf24', VAL: '#fbbf24', VWAP: '#22d3ee', OB: '#34d399', OB_DEMANDA: '#34d399', OB_OFERTA: '#f87171', HVN: '#fbbf24', LVN: '#8a98a8' }
function corTipo(t: string): string {
  const k = t.toUpperCase()
  for (const [pref, c] of Object.entries(CORES)) if (k.includes(pref)) return k.includes('OFERTA') || k.includes('BEAR') ? '#f87171' : c
  return '#9aa8b8'
}
const statusDe = (p: PontoInstitucional) => (p.rompido ? 'rompido' : p.testado ? 'testado' : 'ativo')

export default function Pontos() {
  const par = 'BTCUSDT'
  const precoQ = usePreco(par)
  const [faixa, setFaixa] = useState(0.02)
  const [st, setSt] = useState<Record<string, boolean>>({ ativo: true, testado: true, rompido: false })
  const [tipos, setTipos] = useState<Record<string, boolean>>({})
  const pontos = usePontos(par, precoQ.data?.preco, faixa)
  const qc = useQueryClient()
  const marcar = useMutation({ mutationFn: ({ id, acao }: { id: number; acao: 'testar' | 'romper' }) => api.patch(`/pontos-institucionais/${id}/${acao}`), onSuccess: () => qc.invalidateQueries({ queryKey: ['pontos'] }) })
  const detector = useMutation({ mutationFn: () => api.post('/orderblocks/atualizar', { par }), onSuccess: () => qc.invalidateQueries({ queryKey: ['pontos'] }) })
  const todosTipos = useMemo(() => [...new Set((pontos.data ?? []).map((p) => p.tipo))].sort(), [pontos.data])
  const lista = useMemo(() => (pontos.data ?? [])
    .filter((p) => st[statusDe(p)] && (tipos[p.tipo] ?? true))
    .map((p) => ({ ...p, precoN: Number(p.preco), status: statusDe(p) }))
    .sort((a, b) => b.precoN - a.precoN), [pontos.data, st, tipos])
  const pAtual = precoQ.data?.preco
  const lo = pAtual ? pAtual * (1 - faixa) : 0, hi = pAtual ? pAtual * (1 + faixa) : 1
  const y = (p: number) => ((hi - p) / (hi - lo)) * 100

  return (
    <>
      <Header titulo="Pontos institucionais" subtitulo={`níveis detectados na faixa de ±${fmt(faixa * 100, 0)}% em torno do preço`} par={par} actions={
        <div style={{ display: 'flex', gap: 8 }}>
          <Btn kind="primary" onClick={() => detector.mutate()} disabled={detector.isPending}>{detector.isPending ? 'rodando…' : 'Rodar detector'}</Btn>
        </div>
      } />
      <Page>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {(['ativo', 'testado', 'rompido'] as const).map((s) => <Chip key={s} on={st[s]} onClick={() => setSt({ ...st, [s]: !st[s] })}>{s}s</Chip>)}
            <span style={{ width: 8 }} />
            {[0.02, 0.05, 0.1].map((f) => <Chip key={f} on={faixa === f} onClick={() => setFaixa(f)}>±{fmt(f * 100, 0)}%</Chip>)}
            <span style={{ width: 8 }} />
            {todosTipos.map((t) => <Chip key={t} on={tipos[t] ?? true} onClick={() => setTipos({ ...tipos, [t]: !(tipos[t] ?? true) })}>{t}</Chip>)}
          </div>
        </div>
        {detector.isError && <Err e={detector.error} />}
        <div className="grid" style={{ gridTemplateColumns: 'minmax(300px, 34fr) minmax(0, 66fr)', alignItems: 'start' }}>
          <Card title="Escada de preços" sub={pAtual ? `±${fmt(faixa * 100, 0)}% · ${preco(lo)} – ${preco(hi)}` : ''}>
            <div className="ladder">
              {lista.map((p) => (
                <div key={p.id} className="lv" style={{ top: `${y(p.precoN)}%`, borderTopStyle: p.status === 'testado' ? 'dashed' : 'solid', borderTopColor: corTipo(p.tipo), opacity: 0.35 + (p.relevancia ?? 0.5) * 0.65 }}>
                  <span style={{ color: corTipo(p.tipo) }}>{p.tipo} · {preco(p.precoN)}</span>
                </div>
              ))}
              {pAtual && <div className="now" style={{ top: `${y(pAtual)}%` }}><span>{preco(pAtual)} agora</span></div>}
            </div>
          </Card>
          <Card title="Pontos na faixa" sub={`${lista.length} de ${pontos.data?.length ?? 0}`} pad={false}>
            {pontos.isPending && <Loading />}
            {pontos.isError && <Err e={pontos.error} />}
            <table className="table">
              <thead><tr><th>Tipo</th><th className="r">Preço</th><th className="r">Relevância</th><th>Status</th><th>Identificado</th><th>Motivo</th><th></th></tr></thead>
              <tbody>
                {lista.map((p) => (
                  <tr key={p.id}>
                    <td className="sans"><span className="row" style={{ gap: 7 }}><span style={{ width: 6, height: 6, borderRadius: 1, background: corTipo(p.tipo), display: 'inline-block' }} />{p.tipo} · {p.exchange}</span></td>
                    <td className="r">{preco(p.precoN)}</td>
                    <td className="r" style={{ color: 'var(--text-2)' }}>{fmt(p.relevancia ?? 0, 2)}</td>
                    <td><span className="tag mono" style={{ textTransform: 'none', letterSpacing: 0, color: p.status === 'ativo' ? 'var(--green)' : p.status === 'testado' ? 'var(--amber)' : 'var(--red)' }}>{p.status}</span></td>
                    <td className="muted">{hora(p.data_identificacao, true)}</td>
                    <td className="sans ell muted" style={{ fontSize: 11 }}>{p.motivo}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      {p.status === 'ativo' && <Btn small kind="ghost" onClick={() => marcar.mutate({ id: p.id, acao: 'testar' })}>testado</Btn>}{' '}
                      {p.status !== 'rompido' && <Btn small kind="ghost" onClick={() => marcar.mutate({ id: p.id, acao: 'romper' })}>rompido</Btn>}
                    </td>
                  </tr>
                ))}
                {pontos.data && !lista.length && <tr><td colSpan={7}><Empty>nenhum ponto na faixa com esses filtros</Empty></td></tr>}
              </tbody>
            </table>
          </Card>
        </div>
      </Page>
    </>
  )
}
