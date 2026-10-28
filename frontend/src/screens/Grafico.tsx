/**
 * Tela Gráfico: o gráfico no jeito da TradingView para qualquer moeda em Coinbase, Binance, Bybit e OKX (à vista e
 * perpétuo). A moeda e o tempo ficam no endereço (#/grafico?s=COINBASE:BTC-USD&t=30m), então dá para salvar o link.
 * As nuvens do livro só existem no COINBASE:BTC-USD.
 *
 * Botão TPO: o perfil de 30 min de cada dia (UTC) no gráfico, com POC, VAH e VAL seguindo até o preço voltar a
 * tocar; `&tpo=10` no endereço = ligado com 10 dias.
 *
 * Juntar dias: com "Juntar dias" ligado (ou segurando Shift), clicar no perfil de um dia e depois no de outro junta
 * todos os dias entre os dois num perfil só (o composto), com POC, VAH e VAL próprios. Fica no endereço como
 * `&j=<início do 1º dia>-<início do último>` (segundos UTC).
 *
 * Nuvens (só no COINBASE:BTC-USD): o Order Book Depth Overlay do TRDR desenhado em cada vela, com o livro da Coinbase;
 * `&n=0` desliga.
 */
import { useQuery } from '@tanstack/react-query'
import type { LogicalRange } from 'lightweight-charts'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { NuvensOverlay, SimbolosGrafico, TpoComposto, TpoDia, TpoGrafico } from '../api/types'
import GraficoTV, { casas, SEGUNDOS, type InfoGrafico } from '../components/chart/GraficoTV'
import PaineisFluxo, { PASSO_MAX_PAINEIS } from '../components/chart/PaineisFluxo'
import { COR_TPO, type Selecao } from '../components/chart/tpoDesenho'
import ParedesAgora from '../components/ParedesAgora'

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
const DIA_S = 86400
const COM_NUVEM = 'COINBASE:BTC-USD'
/** o livro das nuvens: só a Coinbase. A Binance à vista pára perto de 1% do preço (limite da API pública), então não
 *  tem o que somar nas faixas de 1–10%; somar o pedaço cortado dela distorcia a faixa de 1–2,5%. */
const LIVRO = { exchanges: 'coinbase', nome: 'Coinbase' }
/** quanto de livro pedir por tempo gráfico (a API vai até 7 dias) */
const JANELA_NUVENS_S: Record<string, number> = { '1m': 86400, '5m': 3 * 86400 }
const SETE_DIAS_S = 7 * 86400
/** livro mais velho que isso = coletor parado */
const LIVRO_ATRASADO_S = 300
/** nesses tempos o dia tem velas demais de largas para o perfil caber: ligar o TPO passa para 30 min */
const TEMPO_LARGO = ['4h', '1d']

function partes(simbolo: string) {
  const [corretora = '', par = '', perp] = simbolo.split(':')
  return { corretora, par, perp: perp === 'PERP' }
}

function lerJuncao(j: string | null): Selecao | null {
  const m = j?.match(/^(\d+)-(\d+)$/)
  if (!m) return null
  const dia = (t: number) => Math.floor(t / DIA_S) * DIA_S          // &j= editado à mão: volta para 00:00 UTC
  const a = dia(Number(m[1])), b = dia(Number(m[2]))
  return { de: Math.min(a, b), ate: Math.max(a, b) }
}

const ddmm = (t: number) => { const d = new Date(t * 1000); return `${String(d.getUTCDate()).padStart(2, '0')}/${String(d.getUTCMonth() + 1).padStart(2, '0')}` }

const tempoValido = (t: string | null | undefined): t is string => !!t && (TEMPOS as readonly string[]).includes(t)

function lerGuardado(): { s: string; t: string } | null {
  try { const v = JSON.parse(localStorage.getItem(GUARDADO) || 'null'); return v?.s && tempoValido(v?.t) ? v : null } catch { return null }
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
  const tParam = params.get('t')
  const tempo = tempoValido(tParam) ? tParam : guardado?.t || PADRAO.t
  const diasTpo = params.get('tpo')
  const selecao = useMemo(() => (diasTpo ? lerJuncao(params.get('j')) : null), [diasTpo, params])
  const [escolhendo, setEscolhendo] = useState(false)
  const [juntando, setJuntando] = useState(false)
  const [info, setInfo] = useState<InfoGrafico | null>(null)
  useEffect(() => { setJuntando(false) }, [simbolo])

  useEffect(() => {
    try { localStorage.setItem(GUARDADO, JSON.stringify({ s: simbolo, t: tempo })) } catch { /* modo privado */ }
  }, [simbolo, tempo])

  const nuvemParam = params.get('n')
  const ir = (s: string, t: string, tpo: string | null = diasTpo, j: Selecao | null = s === simbolo ? selecao : null,
              n: string | null = nuvemParam) => {
    const novo: Record<string, string> = { s, t }
    if (tpo) { novo.tpo = tpo; if (j) novo.j = `${j.de}-${j.ate}` }
    if (n) novo.n = n
    const p = params.get('p')
    if (p) novo.p = p
    setParams(novo, { replace: true })
  }
  // painéis de baixo (livro, liquidações, funding) e paredes de agora: dados do BTC, em velas de até 4 h; &p=0 esconde
  const ehBtc = partes(simbolo).par.startsWith('BTC-')
  const fluxoLigado = params.get('p') !== '0'
  const fluxoCabe = (SEGUNDOS[tempo] ?? 0) <= PASSO_MAX_PAINEIS
  const [tempos, setTempos] = useState<number[]>([])
  const [range, setRange] = useState<LogicalRange | null>(null)
  const ligarFluxo = () => setParams((q) => { const n = new URLSearchParams(q); if (fluxoLigado) n.set('p', '0'); else n.delete('p'); return n }, { replace: true })
  const temNuvem = simbolo === COM_NUVEM
  const livro = nuvemParam === '0' ? null : LIVRO
  const nuvensQ = useQuery({
    queryKey: ['grafico-nuvens', tempo, livro?.exchanges], enabled: temNuvem && !!livro, refetchInterval: 60_000,
    queryFn: () => {
      // com o fim junto, o servidor não recusa a janela de 7 dias se o relógio dele estiver um pouco à frente
      const fim = Math.floor(Date.now() / 1000)
      return api.get<NuvensOverlay>('/api/nuvens/overlay', {
      inicio: fim - (JANELA_NUVENS_S[tempo] ?? SETE_DIAS_S), fim,
      exchanges: livro!.exchanges, passo: SEGUNDOS[tempo], amostra: 'fechamento',
      })
    },
  })
  const nuvens = temNuvem && livro && nuvensQ.data?.passo_s === SEGUNDOS[tempo] ? nuvensQ.data : null
  const atrasoLivro = nuvens?.ultimo_ts ? Math.floor(Date.now() / 1000) - nuvens.ultimo_ts : null
  const tpoQ = useQuery({
    queryKey: ['grafico-tpo', simbolo, diasTpo], enabled: !!diasTpo, refetchInterval: 60_000,
    queryFn: () => api.get<TpoGrafico>('/api/grafico/tpo', { simbolo, dias: diasTpo as string }),
  })
  const tpo = diasTpo && tpoQ.data?.simbolo === simbolo ? tpoQ.data : null
  const umDiaSo = !selecao || selecao.de === selecao.ate
  const compQ = useQuery({
    queryKey: ['grafico-tpo-composto', simbolo, selecao?.de, selecao?.ate, tpo?.tick],
    enabled: !!tpo && !umDiaSo, refetchInterval: 60_000,
    queryFn: () => api.get<TpoComposto>('/api/grafico/tpo/composto',
      { simbolo, de: selecao!.de, ate: selecao!.ate, tick: tpo!.tick }),
  })
  const composto = !umDiaSo && compQ.data?.simbolo === simbolo && compQ.data.inicio === selecao!.de ? compQ.data : null

  // 1º clique marca o dia; o 2º junta tudo entre os dois; clicar de novo no mesmo dia desmarca
  const escolherDia = (d: TpoDia, shift: boolean) => {
    if (!juntando && !shift) return
    if (selecao && umDiaSo) {
      if (d.inicio === selecao.de) ir(simbolo, tempo, diasTpo, null)
      else { ir(simbolo, tempo, diasTpo, { de: Math.min(d.inicio, selecao.de), ate: Math.max(d.inicio, selecao.de) }); setJuntando(false) }
    } else ir(simbolo, tempo, diasTpo, { de: d.inicio, ate: d.inicio })
  }
  const desfazer = useCallback(() => {
    setJuntando(false)
    setParams((p) => { const n = new URLSearchParams(p); n.delete('j'); return n }, { replace: true })
  }, [setParams])
  useEffect(() => {
    if (!selecao && !juntando) return
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape' && !escolhendo) desfazer() }
    window.addEventListener('keydown', esc)
    return () => window.removeEventListener('keydown', esc)
  }, [selecao, juntando, escolhendo, desfazer])
  const ligarTpo = () => {
    if (diasTpo) { setJuntando(false); ir(simbolo, tempo, null) }
    else ir(simbolo, TEMPO_LARGO.includes(tempo) ? '30m' : tempo, '10')
  }
  const { corretora, par, perp } = partes(simbolo)
  const ult = info?.ultimo, ant = info?.anterior
  const variacao = ult && ant ? ult.c / ant.c - 1 : null
  const dec = ult ? casas(ult.c) : 2
  const fmt = (p: number) => p.toLocaleString('pt-BR', { minimumFractionDigits: dec, maximumFractionDigits: dec })

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
            <button key={t} type="button" className={t === tempo ? 'on' : ''} title={diasTpo && TEMPO_LARGO.includes(t) ? 'o TPO não cabe nesse tempo: desliga o TPO' : ''}
              onClick={() => { if (diasTpo && TEMPO_LARGO.includes(t)) { setJuntando(false); ir(simbolo, t, null) } else ir(simbolo, t) }}>{ROTULO_TEMPO[t] ?? t}</button>
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
          {diasTpo && (
            <button type="button" className={'gbotao' + (juntando ? ' on' : '')} onClick={() => setJuntando((v) => !v)}
              title="Clique no perfil de um dia e depois no de outro para juntar os dias entre eles (ou segure Shift)">Juntar dias</button>
          )}
          {selecao && <button type="button" className="gbotao" onClick={desfazer} title="Desfazer a junção (Esc)">✕ junção</button>}
          {temNuvem && (
            <button type="button" className={'gbotao' + (livro ? ' on' : '')} onClick={() => ir(simbolo, tempo, diasTpo, selecao, livro ? '0' : null)}
              title="Nuvens do livro: o Order Book Depth Overlay do TRDR em cada vela">Nuvens</button>
          )}
          {ehBtc && (
            <button type="button" className={'gbotao' + (fluxoLigado ? ' on' : '')} onClick={ligarFluxo}
              title="Painéis embaixo do gráfico: livro à vista e alavancado, liquidações e funding do BTC, e as paredes de agora">Fluxo</button>
          )}
        </div>
        {ult && (
          <span className="mono gpreco">
            {ult.c.toLocaleString('pt-BR', { minimumFractionDigits: dec, maximumFractionDigits: dec })}
            {variacao !== null && <span style={{ color: variacao >= 0 ? '#26a69a' : '#ef5350' }}> {variacao >= 0 ? '+' : ''}{(variacao * 100).toFixed(2)}%</span>}
          </span>
        )}
        {!temNuvem && <span className="gnota muted">sem nuvens: só no BTC-USD da Coinbase</span>}
      </div>
      <div className="gatalhos">
        {ATALHOS.map((s) => (
          <button key={s} type="button" className={'chip' + (s === simbolo ? ' on' : '')} onClick={() => ir(s, tempo)}>
            {s.replace(':PERP', ' perp').replace(':', ' ')}
          </button>
        ))}
      </div>
      {temNuvem && livro && (
        <div className="glegenda-tpo">
          <span><b style={{ color: 'rgb(38,166,154)' }}>▮ verde abaixo</b>: naquela faixa do livro a compra tem 70% ou mais (ratio 40 do TRDR)</span>
          <span><b style={{ color: 'rgb(239,83,80)' }}>▮ vermelho acima</b>: o mesmo para a venda; mais forte = mais perto de só um lado</span>
          <span className="muted">faixas de 1–2,5%, 2,5–5% e 5–10% do preço · livro da Coinbase no fechamento de cada vela (regra do TRDR; a Binance não alcança essas faixas)</span>
          {nuvensQ.isPending && <span className="muted">lendo o livro…</span>}
          {nuvensQ.isError && <span className="warn-txt">não deu para ler o livro agora</span>}
          {nuvens && !nuvens.pontos.length && <span className="warn-txt">sem livro gravado neste período</span>}
          {atrasoLivro !== null && atrasoLivro > LIVRO_ATRASADO_S && <span className="warn-txt">último livro gravado há {Math.round(atrasoLivro / 60)} min: coletor parado?</span>}
          {['1m', '5m', '15m'].includes(tempo) && <span className="muted">em tempo curto as faixas ficam fora da tela: arraste a escala de preço (à direita) para ver</span>}
        </div>
      )}
      {diasTpo && (
        <div className="glegenda-tpo">
          {tpoQ.isPending && <span className="muted">montando o TPO…</span>}
          {tpoQ.isError && <span className="warn-txt">não deu para montar o TPO agora</span>}
          {tpo && selecao && umDiaSo && <span className="gjuncao">dia {ddmm(selecao.de)} marcado: clique no perfil do outro dia para juntar</span>}
          {tpo && !selecao && juntando && <span className="gjuncao">clique no perfil do primeiro dia</span>}
          {!umDiaSo && compQ.isError && <span className="warn-txt">não deu para juntar esses dias agora</span>}
          {composto && (
            <span className="gjuncao mono">
              Junção {ddmm(composto.inicio)}–{ddmm(composto.fim - 1)} ({composto.n_dias} dias):{' '}
              <b style={{ color: COR_TPO.poc }}>POC {fmt(composto.poc)}</b> · <b style={{ color: COR_TPO.borda }}>VAH {fmt(composto.vah)}</b>{' '}
              · <b style={{ color: COR_TPO.borda }}>VAL {fmt(composto.val)}</b>
            </span>
          )}
          {tpo && <>
            <span><b style={{ color: COR_TPO.poc }}>━ POC</b> (onde o preço passou mais tempo)</span>
            <span><b style={{ color: COR_TPO.borda }}>━ VAH / VAL</b> (topo e fundo dos 70% do tempo)</span>
            <span className="muted">tracejado = o nível seguindo até o preço voltar; com nome na direita = ainda virgem</span>
            <span className="muted">faixa de {tpo.tick.toLocaleString('pt-BR', { maximumFractionDigits: 10 })} · dias em UTC (21h de Brasília)</span>
          </>}
        </div>
      )}
      <div className="card gcaixa">
        <GraficoTV simbolo={simbolo} tempo={tempo} onInfo={setInfo} tpo={tpo} selecao={selecao} composto={composto} nuvens={nuvens} onDia={escolherDia}
          onTempos={setTempos} onRange={setRange} />
        {ehBtc && fluxoLigado && (fluxoCabe
          ? tempos.length > 0 && <PaineisFluxo tempos={tempos} range={range} passo={SEGUNDOS[tempo]} />
          : <div className="muted" style={{ fontSize: 12, padding: '10px 0' }}>os painéis de livro, liquidações e funding vão até velas de 4 h: escolha um tempo menor para vê-los</div>)}
      </div>
      {ehBtc && fluxoLigado && <ParedesAgora preco={ult?.c ?? null} />}
      {escolhendo && <Seletor atual={simbolo} onFechar={() => setEscolhendo(false)} onEscolher={(s) => { setEscolhendo(false); ir(s, tempo) }} />}
    </div>
  )
}
