/**
 * Tela Gráfico: o gráfico no jeito da TradingView para qualquer moeda em Coinbase, Binance, Bybit e OKX (à vista e
 * perpétuo). A moeda e o tempo ficam no endereço (#/grafico?s=COINBASE:BTC-USD&t=30m), então dá para salvar o link.
 * As nuvens do livro só existem no COINBASE:BTC-USD.
 *
 * Botão TPO: o perfil de 30 min de cada dia (UTC) no gráfico, com POC, VAH e VAL seguindo até o preço voltar a
 * tocar; `&tpo=10` no endereço = ligado com 10 dias.
 */
import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { SimbolosGrafico, TpoGrafico } from '../api/types'
import GraficoTV, { casas, type InfoGrafico } from '../components/chart/GraficoTV'
import { COR_TPO } from '../components/chart/tpoDesenho'

const PADRAO = { s: 'COINBASE:BTC-USD', t: '30m' }
const TEMPOS = ['1m', '5m', '15m', '30m', '1h', '4h', '1d'] as const
const ROTULO_TEMPO: Record<string, string> = { '1d': '1D' }
const CORRETORAS: { id: string; nome: string; perp: boolean }[] = [
  { id: 'COINBASE', nome: 'Coinbase', perp: false }, { id: 'BINANCE', nome: 'Binance', perp: true },
  { id: 'BYBIT', nome: 'Bybit', perp: true }, { id: 'OKX', nome: 'OKX', perp: true },
]
const ATALHOS = ['COINBASE:BTC-USD', 'BINANCE:BTC-USDT', 'BINANCE:BTC-USDT:PERP', 'BYBIT:BTC-USDT:PERP', 'COINBASE:ETH-USD', 'BINANCE:SOL-USDT']
const GUARDADO = 'grafico.ultimo'
const MOSTRAR_NA_LISTA = 150
const DIAS_TPO = ['5', '10', '20', '30'] as const
/** nesses tempos o dia tem velas demais de largas para o perfil caber: ligar o TPO passa para 30 min */
const TEMPO_LARGO = ['4h', '1d']

function partes(simbolo: string) {
  const [corretora = '', par = '', perp] = simbolo.split(':')
  return { corretora, par, perp: perp === 'PERP' }
}

function lerGuardado(): { s: string; t: string } | null {
  try { const v = JSON.parse(localStorage.getItem(GUARDADO) || 'null'); return v?.s && v?.t ? v : null } catch { return null }
}

/** Janela de escolha da moeda: corretora, à vista ou perpétuo, e a busca pelo nome. */
function Seletor({ atual, onEscolher, onFechar }: { atual: string; onEscolher: (s: string) => void; onFechar: () => void }) {
  const ini = partes(atual)
  const [corretora, setCorretora] = useState(ini.corretora || 'COINBASE')
  const [perp, setPerp] = useState(ini.perp)
  const [busca, setBusca] = useState('')
  const campo = useRef<HTMLInputElement>(null)
  const temPerp = CORRETORAS.find((c) => c.id === corretora)?.perp ?? false
  const mercado = perp && temPerp ? 'perp' : 'spot'
  const q = useQuery({
    queryKey: ['grafico-simbolos', corretora, mercado], staleTime: 12 * 3600_000,
    queryFn: () => api.get<SimbolosGrafico>('/api/grafico/simbolos', { corretora, mercado }),
  })
  useEffect(() => { campo.current?.focus() }, [])
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onFechar() }
    window.addEventListener('keydown', esc)
    return () => window.removeEventListener('keydown', esc)
  }, [onFechar])

  const lista = useMemo(() => {
    const todos = q.data?.simbolos ?? []
    const b = busca.trim().toUpperCase().replace(/[/:]/g, '-')
    if (!b) return todos
    const comeca = todos.filter((s) => s.base.startsWith(b) || `${s.base}-${s.cotacao}`.startsWith(b))
    const contem = todos.filter((s) => !comeca.includes(s) && `${s.base}-${s.cotacao}`.includes(b))
    return [...comeca, ...contem]
  }, [q.data, busca])

  return (
    <div className="gsel-fundo" onClick={onFechar}>
      <div className="gsel" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Escolher moeda">
        <div className="gsel-topo">
          <input ref={campo} value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar moeda (BTC, ETH, SOL…)"
            onKeyDown={(e) => { if (e.key === 'Enter' && lista[0]) onEscolher(lista[0].simbolo) }} />
          <button type="button" className="btn ghost" onClick={onFechar} aria-label="Fechar">✕</button>
        </div>
        <div className="gsel-filtros">
          <div className="tabs" style={{ padding: 0 }}>
            {CORRETORAS.map((c) => (
              <button key={c.id} type="button" className={c.id === corretora ? 'on' : ''} onClick={() => setCorretora(c.id)}>{c.nome}</button>
            ))}
          </div>
          <div className="tabs" style={{ padding: 0, marginLeft: 'auto' }}>
            <button type="button" className={mercado === 'spot' ? 'on' : ''} onClick={() => setPerp(false)}>À vista</button>
            <button type="button" className={mercado === 'perp' ? 'on' : ''} disabled={!temPerp} onClick={() => setPerp(true)}
              title={temPerp ? '' : 'a Coinbase não tem perpétuo aqui'}>Perpétuo</button>
          </div>
        </div>
        <div className="gsel-lista">
          {q.isPending && <div className="empty">buscando a lista da {corretora}…</div>}
          {q.isError && <div className="empty">a {corretora} não respondeu agora; tente de novo</div>}
          {q.data && !lista.length && <div className="empty">nenhum par com “{busca}” na {corretora} {mercado === 'perp' ? 'perpétuo' : 'à vista'}</div>}
          {lista.slice(0, MOSTRAR_NA_LISTA).map((s) => (
            <button key={s.simbolo} type="button" className={'gsel-item' + (s.simbolo === atual ? ' on' : '')} onClick={() => onEscolher(s.simbolo)}>
              <span className="mono"><b>{s.base}</b><span className="muted">-{s.cotacao}</span></span>
              <span className="muted">{mercado === 'perp' ? 'perpétuo' : 'à vista'}</span>
              {s.simbolo === 'COINBASE:BTC-USD' && <span className="tag" style={{ marginLeft: 'auto' }}>nuvens</span>}
              <span className="muted gsel-ex">{corretora}</span>
            </button>
          ))}
          {lista.length > MOSTRAR_NA_LISTA && <div className="empty">+{lista.length - MOSTRAR_NA_LISTA} pares: digite para filtrar</div>}
        </div>
      </div>
    </div>
  )
}

export default function Grafico() {
  const [params, setParams] = useSearchParams()
  const guardado = lerGuardado()
  const simbolo = (params.get('s') || guardado?.s || PADRAO.s).toUpperCase()
  const tempo = params.get('t') || guardado?.t || PADRAO.t
  const diasTpo = params.get('tpo')
  const [escolhendo, setEscolhendo] = useState(false)
  const [info, setInfo] = useState<InfoGrafico | null>(null)

  useEffect(() => {
    try { localStorage.setItem(GUARDADO, JSON.stringify({ s: simbolo, t: tempo })) } catch { /* modo privado */ }
  }, [simbolo, tempo])

  const ir = (s: string, t: string, tpo: string | null = diasTpo) => setParams(tpo ? { s, t, tpo } : { s, t }, { replace: true })
  const tpoQ = useQuery({
    queryKey: ['grafico-tpo', simbolo, diasTpo], enabled: !!diasTpo, refetchInterval: 60_000,
    queryFn: () => api.get<TpoGrafico>('/api/grafico/tpo', { simbolo, dias: diasTpo as string }),
  })
  const tpo = diasTpo && tpoQ.data?.simbolo === simbolo ? tpoQ.data : null
  const ligarTpo = () => {
    if (diasTpo) ir(simbolo, tempo, null)
    else ir(simbolo, TEMPO_LARGO.includes(tempo) ? '30m' : tempo, '10')
  }
  const { corretora, par, perp } = partes(simbolo)
  const ult = info?.ultimo, ant = info?.anterior
  const variacao = ult && ant ? ult.c / ant.c - 1 : null
  const dec = ult ? casas(ult.c) : 2

  return (
    <div className="gpag">
      <div className="gbarra">
        <button type="button" className="gsimbolo" onClick={() => setEscolhendo(true)} title="Trocar a moeda ou a corretora">
          <span className="mono"><b>{par || simbolo}</b></span>
          <span className="muted">{corretora}{perp ? ' · perpétuo' : ' · à vista'}</span>
          <span className="muted">▾</span>
        </button>
        <div className="gtempos" role="group" aria-label="Tempo gráfico">
          {TEMPOS.map((t) => (
            <button key={t} type="button" className={t === tempo ? 'on' : ''} onClick={() => ir(simbolo, t)}>{ROTULO_TEMPO[t] ?? t}</button>
          ))}
        </div>
        <div className="gferramentas">
          <button type="button" className={'gbotao' + (diasTpo ? ' on' : '')} onClick={ligarTpo}
            title="Perfil de 30 min de cada dia com POC, VAH e VAL">TPO 30m</button>
          {diasTpo && (
            <select className="gselect" value={diasTpo} onChange={(e) => ir(simbolo, tempo, e.target.value)} aria-label="Dias de TPO">
              {DIAS_TPO.map((d) => <option key={d} value={d}>{d} dias</option>)}
            </select>
          )}
        </div>
        {ult && (
          <span className="mono gpreco">
            {ult.c.toLocaleString('pt-BR', { minimumFractionDigits: dec, maximumFractionDigits: dec })}
            {variacao !== null && <span style={{ color: variacao >= 0 ? '#26a69a' : '#ef5350' }}> {variacao >= 0 ? '+' : ''}{(variacao * 100).toFixed(2)}%</span>}
          </span>
        )}
        <span className="gnota muted">{info?.nuvem ? 'nuvens do livro disponíveis neste par (em breve no gráfico)' : 'sem nuvens: só no BTC-USD da Coinbase'}</span>
      </div>
      <div className="gatalhos">
        {ATALHOS.map((s) => (
          <button key={s} type="button" className={'chip' + (s === simbolo ? ' on' : '')} onClick={() => ir(s, tempo)}>
            {s.replace(':PERP', ' perp').replace(':', ' ')}
          </button>
        ))}
      </div>
      {diasTpo && (
        <div className="glegenda-tpo">
          {tpoQ.isPending && <span className="muted">montando o TPO…</span>}
          {tpoQ.isError && <span className="warn-txt">não deu para montar o TPO agora</span>}
          {tpo && <>
            <span><b style={{ color: COR_TPO.poc }}>━ POC</b> (onde o preço passou mais tempo)</span>
            <span><b style={{ color: COR_TPO.borda }}>━ VAH / VAL</b> (topo e fundo dos 70% do tempo)</span>
            <span className="muted">tracejado = o nível seguindo até o preço voltar; com nome na direita = ainda virgem</span>
            <span className="muted">faixa de {tpo.tick.toLocaleString('pt-BR', { maximumFractionDigits: 10 })} · dias em UTC (21h de Brasília)</span>
          </>}
        </div>
      )}
      <div className="card gcaixa">
        <GraficoTV simbolo={simbolo} tempo={tempo} onInfo={setInfo} tpo={tpo} />
      </div>
      {escolhendo && <Seletor atual={simbolo} onFechar={() => setEscolhendo(false)} onEscolher={(s) => { setEscolhendo(false); ir(s, tempo) }} />}
    </div>
  )
}
