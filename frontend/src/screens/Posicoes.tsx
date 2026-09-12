import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import { usePosicoesAbertas } from '../api/hooks'
import type { PosicaoAberta } from '../api/types'
import { Header, Page } from '../components/Layout'
import { Btn, Card, Empty, Err, Estado, KPI, KV, ModoTag, Tag } from '../components/ui'
import { corPnl, fmt, fmtSigned, hora, preco as fmtPreco } from '../lib/format'

type Acao = 'fechar' | 'parcial' | 'zero-a-zero' | 'cancelar-escada'
const ROTULO: Record<Acao, string> = {
  'fechar': 'Fechar agora',
  'parcial': 'Realizar metade',
  'zero-a-zero': 'Stop no zero a zero',
  'cancelar-escada': 'Cancelar escada',
}
const PERGUNTA: Record<Acao, string> = {
  'fechar': 'Fechar a posição inteira a mercado?',
  'parcial': 'Realizar metade da mão a mercado?',
  'zero-a-zero': 'Levar o stop para o preço de entrada?',
  'cancelar-escada': 'Cancelar as fatias que ainda estão no livro?',
}

function idade(iso: string | null | undefined): string {
  if (!iso) return '—'
  const min = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000))
  if (min < 60) return `${min} min`
  const h = Math.floor(min / 60)
  return h < 48 ? `${h} h ${min % 60} min` : `${Math.floor(h / 24)} dias`
}

/** O lado não pode depender de leitura atenta: fica grande, colorido e com a seta. */
function Lado({ compra, grande }: { compra: boolean; grande?: boolean }) {
  const cor = compra ? 'var(--green)' : 'var(--red)'
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6, color: cor, fontWeight: 600,
      fontSize: grande ? 17 : 12, letterSpacing: grande ? '0.04em' : 0,
      padding: grande ? '4px 12px' : '2px 8px', borderRadius: 8,
      border: `1px solid color-mix(in srgb, ${cor} 45%, transparent)`,
      background: `color-mix(in srgb, ${cor} 12%, transparent)`,
    }}>
      {compra ? '▲' : '▼'} {compra ? 'COMPRADO' : 'VENDIDO'}
    </span>
  )
}

function Acoes({ p, onFeito }: { p: PosicaoAberta; onFeito: (msg: string) => void }) {
  const qc = useQueryClient()
  const [confirmando, setConfirmando] = useState<Acao | null>(null)
  const [editando, setEditando] = useState(false)
  const [sl, setSl] = useState('')
  const [tp, setTp] = useState('')
  type Resposta = { status?: string; aviso?: string; quantidade?: number; resultado?: number | null; canceladas?: number; sl?: number; tp?: number }
  const invalidar = () => {
    qc.invalidateQueries({ queryKey: ['posicoes-abertas'] })
    qc.invalidateQueries({ queryKey: ['bots'] })
  }
  const agir = useMutation({
    mutationFn: (acao: Acao) => api.post<Resposta>(`/posicoes/${p.bot_id}/${acao}`),
    onSuccess: (r, acao) => {
      setConfirmando(null)
      invalidar()
      onFeito(r?.status === 'pendente'
        ? `${ROTULO[acao]}: ${r.aviso ?? 'o robô executa no próximo ciclo'}`
        : `${ROTULO[acao]}: feito${r?.resultado != null ? ` · ${fmtSigned(r.resultado)} USDT` : ''}`)
    },
  })
  const salvar = useMutation({
    mutationFn: () => api.post<Resposta>(`/posicoes/${p.bot_id}/stop-alvo`, {
      sl: sl === '' ? undefined : Number(sl), tp: tp === '' ? undefined : Number(tp),
    }),
    onSuccess: (r) => {
      setEditando(false)
      invalidar()
      onFeito(r?.status === 'pendente'
        ? `Stop e alvo: ${r.aviso ?? 'o robô aplica no próximo ciclo'}`
        : `Stop ${r.sl != null ? fmt(r.sl, 0) : '—'} · alvo ${r.tp != null ? fmt(r.tp, 0) : '—'} na corretora`)
    },
  })
  const acoes: Acao[] = ['fechar', 'parcial', 'zero-a-zero', ...(p.escada ? ['cancelar-escada' as Acao] : [])]

  if (!p.rodando) {
    return <p className="sub">O robô não está rodando: ligue-o para poder intervir daqui (sem ele, a ordem sairia na corretora e o registro ficaria aberto no banco).</p>
  }
  if (editando) {
    const compra = p.direcao === 'buy'
    return (
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'flex-end' }}>
        <label style={{ display: 'grid', gap: 4 }}>
          <span className="label">Stop {compra ? '(abaixo do preço)' : '(acima do preço)'}</span>
          <input type="number" step="0.1" value={sl} onChange={(e) => setSl(e.target.value)} placeholder={p.sl ? fmt(p.sl, 1) : 'sem stop'} style={{ width: 130 }} />
        </label>
        <label style={{ display: 'grid', gap: 4 }}>
          <span className="label">Alvo {compra ? '(acima do preço)' : '(abaixo do preço)'}</span>
          <input type="number" step="0.1" value={tp} onChange={(e) => setTp(e.target.value)} placeholder={p.tp ? fmt(p.tp, 1) : 'sem alvo'} style={{ width: 130 }} />
        </label>
        <Btn kind="primary" small onClick={() => salvar.mutate()} disabled={salvar.isPending || (sl === '' && tp === '')}>
          {salvar.isPending ? 'enviando…' : 'Salvar na corretora'}
        </Btn>
        <Btn small onClick={() => { setEditando(false); salvar.reset() }}>Voltar</Btn>
        <span className="sub" style={{ margin: 0, flexBasis: '100%' }}>
          Em branco mantém o valor atual. Preço agora: {p.preco ? fmtPreco(p.preco) : '—'}.
        </span>
        {salvar.isError && <Err e={salvar.error} />}
      </div>
    )
  }
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
      {confirmando ? (
        <>
          <span className="sub" style={{ margin: 0 }}>{PERGUNTA[confirmando]}</span>
          <Btn kind="danger" small onClick={() => agir.mutate(confirmando)} disabled={agir.isPending}>
            {agir.isPending ? 'enviando…' : 'Confirmar'}
          </Btn>
          <Btn small onClick={() => setConfirmando(null)}>Voltar</Btn>
        </>
      ) : (
        <>
          {acoes.map((a) => (
            <Btn key={a} small kind={a === 'fechar' ? 'primary' : undefined} onClick={() => setConfirmando(a)}>{ROTULO[a]}</Btn>
          ))}
          <Btn small onClick={() => { setSl(p.sl ? String(p.sl) : ''); setTp(p.tp ? String(p.tp) : ''); setEditando(true) }}>Editar stop e alvo</Btn>
        </>
      )}
      {agir.isError && <Err e={agir.error} />}
    </div>
  )
}

function Posicao({ p, onFeito }: { p: PosicaoAberta; onFeito: (msg: string) => void }) {
  const compra = p.direcao === 'buy'
  const cor = compra ? 'var(--green)' : 'var(--red)'
  return (
    <Card
      style={{ borderLeft: `3px solid ${cor}` }}
      title={<span>{p.bot} <span className="muted" style={{ fontSize: 12 }}>· {p.par} {p.timeframe ?? ''}</span></span>}
      sub={p.motivo_entrada ?? undefined}
      right={<div className="row"><Lado compra={compra} /><ModoTag modo={p.modo} />{!p.rodando && <Tag color="var(--amber)">robô parado</Tag>}</div>}
    >
      <div className="row" style={{ marginBottom: 14, gap: 12 }}>
        <Lado compra={compra} grande />
        <span className="mono" style={{ fontSize: 13 }}>
          {fmt(p.quantidade, 4)} {p.par.replace('USDT', '')} · entrada {fmt(p.preco_entrada, 1)} · agora {p.preco ? fmt(p.preco, 1) : '—'}
        </span>
      </div>
      <div className="grid" style={{ gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', marginBottom: 14 }}>
        <KPI l="Resultado agora" v={p.pnl_total === null ? '—' : fmtSigned(p.pnl_total)} color={corPnl(p.pnl_total)}
          sub={p.pnl_parcial ? `USDT · ${fmtSigned(p.pnl_parcial)} já realizado` : 'USDT · nada realizado ainda'} />
        <KPI l="Corrido" v={p.r_corrido === null ? '—' : `${p.r_corrido > 0 ? '+' : ''}${fmt(p.r_corrido, 2)}R`}
          color={corPnl(p.r_corrido)} sub={p.sl_inicial ? `stop inicial ${fmt(p.sl_inicial, 0)}` : 'sem stop inicial'} />
        <KPI l="Preço" v={p.preco ? fmtPreco(p.preco) : '—'} sub={`entrada ${fmt(p.preco_entrada, 0)}`} />
        <KPI l="Mão" v={fmt(p.quantidade, 4)}
          sub={p.escada ? `${p.escada.executadas ?? '—'} de ${p.escada.de ?? '—'} fatias · ${p.escada.pendentes} no livro` : `de ${fmt(p.quantidade_inicial, 4)} inicial`} />
      </div>
      <div>
        <KV k="Stop" v={p.sl ? fmt(p.sl, 0) : 'sem stop na corretora'} color={p.zero_a_zero ? 'var(--green)' : 'var(--red)'}
          src={p.zero_a_zero ? 'no zero a zero' : undefined} />
        <KV k="Alvo" v={p.tp ? fmt(p.tp, 0) : 'sem alvo'} color="var(--green)" />
        {p.escada?.precos?.length ? <KV k="Fatias no livro" v={p.escada.precos.map((x) => fmt(x, 0)).join(' · ')} /> : null}
        <KV k="Aberta há" v={idade(p.aberto_em)} src={hora(p.aberto_em, true)} />
      </div>
      <div style={{ marginTop: 14 }}><Acoes p={p} onFeito={onFeito} /></div>
    </Card>
  )
}

export default function Posicoes() {
  const q = usePosicoesAbertas()
  const [msg, setMsg] = useState<string | null>(null)
  const lista = q.data ?? []
  const total = lista.reduce((a, p) => a + (p.pnl_total ?? 0), 0)
  const compradas = lista.filter((p) => p.direcao === 'buy').length

  return (
    <>
      <Header eyebrow="Mesa" titulo="Posições abertas"
        subtitulo="tudo que está aberto agora, em todos os robôs — e onde você intervém: realizar, travar no zero a zero, mudar stop e alvo ou fechar" />
      <Page>
        {msg && <Card pad><div className="row"><span>{msg}</span><Btn small onClick={() => setMsg(null)}>ok</Btn></div></Card>}
        <Estado query={q}>
          {lista.length === 0 ? <Empty>nenhuma posição aberta agora</Empty> : (
            <>
              <div className="grid" style={{ gridTemplateColumns: 'repeat(3, minmax(0, 1fr))' }}>
                <KPI l="Posições abertas" v={lista.length}
                  sub={`${compradas} comprada(s) · ${lista.length - compradas} vendida(s)`} />
                <KPI l="Resultado somado" v={fmtSigned(total)} color={corPnl(total)} sub="USDT · aberto + já realizado" />
                <KPI l="No zero a zero" v={lista.filter((p) => p.zero_a_zero).length} sub="stop já na entrada" />
              </div>
              {lista.map((p) => <Posicao key={p.id} p={p} onFeito={setMsg} />)}
            </>
          )}
        </Estado>
      </Page>
    </>
  )
}
