import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import { usePosicoesAbertas } from '../api/hooks'
import type { PosicaoAberta } from '../api/types'
import { Header, Page } from '../components/Layout'
import { Btn, Card, Empty, Err, Estado, KPI, KV, ModoTag, Tag } from '../components/ui'
import { corPnl, fmt, fmtSigned, hora, preco as fmtPreco, rotuloAcao } from '../lib/format'

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

function Acoes({ p, onFeito }: { p: PosicaoAberta; onFeito: (msg: string) => void }) {
  const qc = useQueryClient()
  const [confirmando, setConfirmando] = useState<Acao | null>(null)
  const agir = useMutation({
    mutationFn: (acao: Acao) => api.post<{ status?: string; aviso?: string; quantidade?: number; resultado?: number | null; canceladas?: number }>(
      `/posicoes/${p.bot_id}/${acao}`),
    onSuccess: (r, acao) => {
      setConfirmando(null)
      qc.invalidateQueries({ queryKey: ['posicoes-abertas'] })
      qc.invalidateQueries({ queryKey: ['bots'] })
      onFeito(r?.status === 'pendente'
        ? `${ROTULO[acao]}: ${r.aviso ?? 'o robô executa no próximo ciclo'}`
        : `${ROTULO[acao]}: feito${r?.resultado != null ? ` · ${fmtSigned(r.resultado)} USDT` : ''}`)
    },
  })
  const acoes: Acao[] = ['fechar', 'parcial', 'zero-a-zero', ...(p.escada ? ['cancelar-escada' as Acao] : [])]

  if (!p.rodando) {
    return <p className="sub">O robô não está rodando: ligue-o para poder intervir daqui (sem ele, a ordem sairia na corretora e o registro ficaria aberto no banco).</p>
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
      ) : acoes.map((a) => (
        <Btn key={a} small kind={a === 'fechar' ? 'primary' : undefined} onClick={() => setConfirmando(a)}>{ROTULO[a]}</Btn>
      ))}
      {agir.isError && <Err e={agir.error} />}
    </div>
  )
}

function Posicao({ p, onFeito }: { p: PosicaoAberta; onFeito: (msg: string) => void }) {
  const compra = p.direcao === 'buy'
  return (
    <Card
      title={<span>{p.bot} <span className="muted" style={{ fontSize: 12 }}>· {p.par} {p.timeframe ?? ''}</span></span>}
      sub={p.motivo_entrada ?? undefined}
      right={<div className="row">
        <Tag color={compra ? 'var(--green)' : 'var(--red)'}>{rotuloAcao(p.direcao)}</Tag>
        <ModoTag modo={p.modo} />
        {!p.rodando && <Tag color="var(--amber)">robô parado</Tag>}
      </div>}
    >
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

  return (
    <>
      <Header eyebrow="Mesa" titulo="Posições abertas"
        subtitulo="tudo que está aberto agora, em todos os robôs — e onde você intervém: realizar, travar no zero a zero ou fechar" />
      <Page>
        {msg && <Card pad><div className="row"><span>{msg}</span><Btn small onClick={() => setMsg(null)}>ok</Btn></div></Card>}
        <Estado query={q}>
          {lista.length === 0 ? <Empty>nenhuma posição aberta agora</Empty> : (
            <>
              <div className="grid" style={{ gridTemplateColumns: 'repeat(3, minmax(0, 1fr))' }}>
                <KPI l="Posições abertas" v={lista.length} sub={`${lista.filter((p) => p.rodando).length} com o robô rodando`} />
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
