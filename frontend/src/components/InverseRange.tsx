import { useEffect, useState } from 'react'
import { ApiError } from '../api/client'
import { useInverseEstado, usePropostaRange, useRangeInverse } from '../api/hooks'
import { fmt, pct, preco } from '../lib/format'
import { Btn, Card, Field, KV } from './ui'

/** Recusa da API: bloqueio não passa nem forçando; aviso passa se o usuário confirmar. */
type Recusa = { acao: 'aprovar' | 'cancelar'; motivo?: string; avisos?: string[]; bloqueios?: string[] }

function lerRecusa(acao: Recusa['acao'], e: unknown): Recusa {
  if (e instanceof ApiError && e.detail && typeof e.detail === 'object') return { acao, ...(e.detail as Omit<Recusa, 'acao'>) }
  return { acao, motivo: e instanceof Error ? e.message : String(e) }
}

const STATUS: Record<string, string> = {
  aprovado: 'aprovado — a grade está operando',
  proposto: 'proposto pelo robô, esperando você aprovar',
  encerrado: 'encerrado: o topo rompeu de verdade',
  concluido: 'concluído: o movimento de baixa terminou',
}

/**
 * Range do Hedge Inverso: ver o que o robô propõe, aprovar, cancelar e acompanhar o rompimento.
 * Antes não havia botão — a aprovação só existia pela API, e a rota aceitava tudo calada.
 */
export function InverseRangeCard({ id }: { id: number }) {
  const est = useInverseEstado(id)
  const prop = usePropostaRange(id)
  const { aprovar, cancelar } = useRangeInverse()
  const [low, setLow] = useState('')
  const [high, setHigh] = useState('')
  const [recusa, setRecusa] = useState<Recusa | null>(null)
  const [ok, setOk] = useState<string | null>(null)

  const range = est.data?.range
  const maq = est.data?.estado?.rompimento
  const grade = est.data?.estado?.grade
  const p = prop.data?.proposta
  const valida = !!p?.valido
  const aprovado = range?.status === 'aprovado'

  // pré-preenche com a proposta válida; sem ela, com o range salvo — os dois campos continuam editáveis
  useEffect(() => {
    if (low || high) return
    const l = valida ? p?.low : range?.low
    const h = valida ? p?.high : range?.high
    if (l && h) { setLow(String(Math.round(l))); setHigh(String(Math.round(h))) }
  }, [valida, p?.low, p?.high, range?.low, range?.high, low, high])

  const nLow = Number(low), nHigh = Number(high)
  const numerosOk = nLow > 0 && nHigh > nLow

  const enviar = async (forcar = false) => {
    setRecusa(null); setOk(null)
    try {
      const r = await aprovar.mutateAsync({ id, low: nLow, high: nHigh, forcar }) as { range: number[]; forcado: boolean }
      setOk(`Range ${preco(r.range[0])} – ${preco(r.range[1])} aprovado${r.forcado ? ' (forçado)' : ''}. A grade é montada no próximo candle de 4h, com o preço daquele momento.`)
    } catch (e) { setRecusa(lerRecusa('aprovar', e)) }
  }

  const desfazer = async (forcar = false) => {
    setRecusa(null); setOk(null)
    try {
      await cancelar.mutateAsync({ id, forcar })
      setOk('Range cancelado. O robô volta a propor um range quando a contagem ficar corretiva.')
    } catch (e) { setRecusa(lerRecusa('cancelar', e)) }
  }

  return (
    <Card>
      <div className="eyebrow" style={{ marginBottom: 9 }}>Range do Hedge Inverso</div>
      <KV k="Status" v={range?.status ? (STATUS[range.status] ?? range.status) : 'sem range'}
          color={aprovado ? 'var(--green)' : range?.status === 'proposto' ? 'var(--amber)' : undefined}
          src={range?.low && range?.high ? `${preco(range.low)} – ${preco(range.high)}` : undefined} />
      {maq && <KV k="Situação" v={maq.descricao} color={maq.estado === 'range' ? undefined : 'var(--amber)'}
                  src={maq.ultimo_evento ? `último evento: ${maq.ultimo_evento.replace(/_/g, ' ')}` : undefined} />}
      {maq?.estado === 'aguardando_reteste' && (
        <KV k="Esperando reteste" v={preco(maq.nivel_rompido)} src={`alvo ${preco(maq.alvo)} (${maq.fonte_alvo}) · ${maq.candles_espera} candles`} />
      )}
      {maq?.reteste && (
        <KV k="Short de reteste" v={`${pct(maq.reteste.fracao, 0)} a ${preco(maq.reteste.preco_entrada)}`} color="var(--red)"
            src={`alvo ${preco(maq.alvo)} · stop acima de ${preco(maq.stop)}`} />
      )}
      {grade && <KV k="Vendido (em dólar)" v={pct(grade.fracao_aberta, 0)} src={`BTC realizado ${fmt(grade.btc_realizado, 6)}`} />}

      <div style={{ margin: '10px 0 8px', fontSize: 11.5, lineHeight: 1.45 }}>
        {prop.isPending ? <span className="muted">lendo a contagem de Elliott no diário…</span>
          : valida ? <span>Proposta do robô: <b>{preco(p?.low)} – {preco(p?.high)}</b>. {p?.motivo}</span>
          : <span className="warn-txt">Sem range agora: {p?.motivo ?? 'proposta indisponível'}.</span>}
      </div>

      {!aprovado && (
        <div className="form-grid" style={{ alignItems: 'end' }}>
          <Field label="Fundo (low)"><input value={low} inputMode="decimal" onChange={(e) => setLow(e.target.value)} /></Field>
          <Field label="Topo (high)"><input value={high} inputMode="decimal" onChange={(e) => setHigh(e.target.value)} /></Field>
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
        {!aprovado && <Btn kind="ok" disabled={!numerosOk || aprovar.isPending} onClick={() => enviar()}>{aprovar.isPending ? 'Aprovando…' : 'Aprovar range'}</Btn>}
        {aprovado && <Btn kind="danger" disabled={cancelar.isPending} onClick={() => desfazer()}>Cancelar range</Btn>}
      </div>

      {recusa?.bloqueios?.length ? (
        <div className="err" style={{ marginTop: 10 }}>
          <b>Não dá para {recusa.acao === 'aprovar' ? 'aprovar' : 'cancelar'}:</b>
          <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>{recusa.bloqueios.map((b) => <li key={b}>{b}</li>)}</ul>
        </div>
      ) : recusa?.avisos?.length ? (
        <div className="warn" style={{ marginTop: 10 }}>
          <b>Antes de {recusa.acao === 'aprovar' ? 'aprovar' : 'cancelar'}, confira:</b>
          <ul style={{ margin: '6px 0 8px', paddingLeft: 18 }}>{recusa.avisos.map((a) => <li key={a}>{a}</li>)}</ul>
          <Btn kind="danger" small onClick={() => (recusa.acao === 'aprovar' ? enviar(true) : desfazer(true))}>
            {recusa.acao === 'aprovar' ? 'Aprovar mesmo assim' : 'Cancelar mesmo assim'}
          </Btn>
        </div>
      ) : recusa ? <div className="err" style={{ marginTop: 10 }}>{recusa.motivo}</div> : null}
      {ok && <div className="muted" style={{ marginTop: 10, fontSize: 11.5 }}>{ok}</div>}

      <p className="muted" style={{ margin: '12px 0 0', fontSize: 11, lineHeight: 1.45 }}>
        Subindo no range, vende a cada nível até 100% no topo e recompra descendo. Topo rompido de verdade (2 fechamentos
        de 4h acima de +1%, ou 1 acima de +3%): fecha todo o short. Rompimento falso: o short fica. Fundo rompido de
        verdade: espera o respiro e vende ~90% no reteste, com stop se o preço voltar para o range.
      </p>
    </Card>
  )
}
