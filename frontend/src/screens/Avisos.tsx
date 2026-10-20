import { useMemo, useState } from 'react'
import { useAvisosMapa, useAvisosUltimos } from '../api/hooks'
import type { Aviso, NivelMapa } from '../api/types'
import { Header, Page } from '../components/Layout'
import { Card, Chip, Empty, Estado, KPI, Tag } from '../components/ui'
import { fmt, preco as fmtPreco } from '../lib/format'

/** O mapa é por dia UTC: mostrar no fuso local trocaria o dia. */
const horaUTC = (ms: number) => `${new Date(ms).toISOString().slice(0, 10)} ${new Date(ms).toISOString().slice(11, 16)} UTC`

const GRUPO: Record<string, { nome: string; cor: string }> = {
  composto: { nome: 'composto', cor: 'var(--acc)' },
  ontem: { nome: 'ontem', cor: 'var(--indigo)' },
  sessao: { nome: 'sessão', cor: 'var(--muted)' },
  naked: { nome: 'naked POC', cor: 'var(--amber)' },
  abertura: { nome: 'abertura', cor: 'var(--green)' },
  pivo: { nome: 'pivô virgem', cor: 'var(--red)' },
}
const POSICAO: Record<string, string> = {
  fundo: 'fundo do composto', meio: 'meio do composto', topo: 'topo do composto',
  fora_abaixo: 'fora do composto, abaixo', fora_acima: 'fora do composto, acima', sem_composto: 'sem composto',
}
const PROXIMIDADE_PCT = 0.2
const SESSAO = { asia: 'Ásia', europa: 'Europa', america: 'América' } as const

function LinhaNivel({ n, preco }: { n: NivelMapa; preco: number }) {
  const g = GRUPO[n.grupo] ?? { nome: n.grupo, cor: 'var(--muted)' }
  const perto = Math.abs(n.distancia_pct) <= PROXIMIDADE_PCT
  const acima = n.preco >= preco
  return (
    <tr style={perto ? { background: 'color-mix(in srgb, var(--amber) 10%, transparent)' } : undefined}>
      <td className="sans">{n.rotulo}</td>
      <td><Tag color={g.cor}>{g.nome}</Tag></td>
      <td className="r">{fmt(n.preco, 0)}</td>
      <td className="r" style={{ color: acima ? 'var(--green)' : 'var(--red)' }}>
        {n.distancia_pct > 0 ? '+' : ''}{fmt(n.distancia_pct, 2)}%
      </td>
    </tr>
  )
}

function CardAviso({ a }: { a: Aviso }) {
  const cor = a.tipo === 'mapa' ? 'var(--acc)' : 'var(--amber)'
  return (
    <div style={{ padding: '12px 0', borderTop: '1px solid var(--border-3)' }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', flexWrap: 'wrap' }}>
        <Tag color={cor}>{a.tipo === 'mapa' ? 'mapa' : 'proximidade'}</Tag>
        <span style={{ fontWeight: 500 }}>{a.titulo}</span>
        <span className="muted mono" style={{ fontSize: 11, marginLeft: 'auto' }}>{horaUTC(a.ts)} · {fmtPreco(a.preco)}</span>
      </div>
      <pre className="mono" style={{ whiteSpace: 'pre-wrap', fontSize: 12, margin: '8px 0 0', color: 'var(--muted)' }}>{a.texto}</pre>
    </div>
  )
}

export default function Avisos() {
  const qMapa = useAvisosMapa()
  const qUlt = useAvisosUltimos(50)
  const [tipo, setTipo] = useState<'todos' | 'mapa' | 'proximidade'>('todos')
  const m = qMapa.data
  const avisos = useMemo(() => (qUlt.data?.avisos ?? []).filter((a) => tipo === 'todos' || a.tipo === tipo), [qUlt.data, tipo])
  const servico = m?.servico ?? qUlt.data?.servico
  const maisPerto = useMemo(() => (m ? [...m.niveis].sort((a, b) => Math.abs(a.distancia_pct) - Math.abs(b.distancia_pct))[0] : null), [m])

  return (
    <>
      <Header titulo="Conselho de avisos" par="BTCUSDT" eyebrow="Conselho"
        subtitulo="Mapa do dia (composto, ontem, sessões, naked POCs, aberturas, pivô virgem) e avisos de proximidade — só informação, sem probabilidade, stop ou alvo" />
      <Page>
        <Estado query={qMapa}>
          {!m ? <Empty>sem mapa</Empty> : (
            <>
              <div className="grid" style={{ gridTemplateColumns: 'repeat(4, minmax(0, 1fr))' }}>
                <KPI l="Preço do mapa" v={fmtPreco(m.preco)} sub={`candles fechados até ${horaUTC(m.ts)}`} />
                <KPI l="Posição no composto" v={POSICAO[m.posicao] ?? m.posicao}
                  color={m.posicao === 'meio' ? 'var(--muted)' : m.posicao.startsWith('fora') ? 'var(--amber)' : 'var(--text)'}
                  sub={m.composto ? `VAL ${fmt(m.composto.val, 0)} · POC ${fmt(m.composto.poc, 0)} · VAH ${fmt(m.composto.vah, 0)} (${m.dias_no_composto}d)` : 'sem composto'} />
                <KPI l="Nível mais perto" v={maisPerto ? `${maisPerto.distancia_pct > 0 ? '+' : ''}${fmt(maisPerto.distancia_pct, 2)}%` : '—'}
                  sub={maisPerto ? `${maisPerto.rotulo} · ${fmt(maisPerto.preco, 0)}` : null} />
                <KPI l="Serviço" v={servico?.ativo ? 'ligado' : 'desligado'} color={servico?.ativo ? 'var(--green)' : 'var(--muted)'}
                  sub={servico ? `${servico.ciclos} ciclo(s) · Telegram ${servico.telegram ? 'ativo' : 'inativo'}${servico.ultimo_erro ? ` · erro: ${servico.ultimo_erro}` : ''}` : 'SERVICO_AVISOS=1 no .env liga a thread'} />
              </div>

              <div><span className="alerta-pill">{m.ressalva}</span></div>

              <div className="grid" style={{ gridTemplateColumns: 'minmax(360px, 55fr) minmax(0, 45fr)', alignItems: 'start' }}>
                <Card title="Mapa do dia" sub={`${m.niveis.length} níveis, do mais alto ao mais baixo · amarelo = a menos de ${fmt(PROXIMIDADE_PCT, 1)}% do preço`} pad={false}>
                  {m.niveis.length === 0 ? <Empty>sem níveis (faltam candles)</Empty> : (
                    <table className="table">
                      <thead><tr><th>nível</th><th>grupo</th><th className="r">preço</th><th className="r">distância</th></tr></thead>
                      <tbody>
                        {m.niveis.map((n) => <LinhaNivel key={n.chave} n={n} preco={m.preco} />)}
                      </tbody>
                    </table>
                  )}
                </Card>

                <div style={{ display: 'grid', gap: 16 }}>
                  <Card title="Sessões" sub="máxima, POC e mínima por sessão (UTC): Ásia 00–08, Europa 08–13:30, América 13:30–20">
                    <table className="table" style={{ marginLeft: -24, marginRight: -24, width: 'calc(100% + 48px)' }}>
                      <thead><tr><th>sessão</th><th className="r">máx</th><th className="r">POC</th><th className="r">mín</th></tr></thead>
                      <tbody>
                        {(['asia', 'europa', 'america'] as const).flatMap((s) => [
                          m.sessoes_hoje[s] && (
                            <tr key={`hoje-${s}`}>
                              <td className="sans">{SESSAO[s]} de hoje</td>
                              <td className="r">{fmt(m.sessoes_hoje[s].maxima, 0)}</td><td className="r">{fmt(m.sessoes_hoje[s].poc, 0)}</td><td className="r">{fmt(m.sessoes_hoje[s].minima, 0)}</td>
                            </tr>
                          ),
                          m.sessoes_ontem[s] && (
                            <tr key={`ontem-${s}`}>
                              <td className="sans muted">{SESSAO[s]} de ontem</td>
                              <td className="r muted">{fmt(m.sessoes_ontem[s].maxima, 0)}</td><td className="r muted">{fmt(m.sessoes_ontem[s].poc, 0)}</td><td className="r muted">{fmt(m.sessoes_ontem[s].minima, 0)}</td>
                            </tr>
                          ),
                        ])}
                      </tbody>
                    </table>
                    {Object.keys(m.sessoes_hoje).length === 0 && Object.keys(m.sessoes_ontem).length === 0 && <Empty>sem sessões</Empty>}
                  </Card>

                  <Card title="Últimos avisos" sub={`gravados em data/avisos.jsonl · mapa às 00:00, 08:00 e 13:30 UTC · proximidade a ${fmt(PROXIMIDADE_PCT, 1)}%, um por nível por dia`}
                    right={<span style={{ display: 'flex', gap: 6 }}>
                      {(['todos', 'mapa', 'proximidade'] as const).map((t) => <Chip key={t} on={tipo === t} onClick={() => setTipo(t)}>{t}</Chip>)}
                    </span>}>
                    <Estado query={qUlt}>
                      {avisos.length === 0 ? <Empty>nenhum aviso gravado{servico?.ativo ? '' : ' · o serviço está desligado'}</Empty>
                        : avisos.map((a) => <CardAviso key={a.id} a={a} />)}
                    </Estado>
                  </Card>
                </div>
              </div>
            </>
          )}
        </Estado>
      </Page>
    </>
  )
}
