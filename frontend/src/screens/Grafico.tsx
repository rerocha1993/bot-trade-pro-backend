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
 *
 * Desenhos: a barra da esquerda, no molde da TradingView (components/chart/BarraFerramentas.tsx), com as ferramentas
 * de components/chart/ferramentas.ts. Dois cliques (ou arrastar) desenham; clicar seleciona e mostra a barra flutuante
 * de estilo; arrastar as alças ou o corpo move; Delete apaga; duplo clique abre a configuração; Ctrl+Z e Ctrl+Y desfazem
 * e refazem; Ctrl+C e Ctrl+V clonam; Alt+T, Alt+H e Alt+F ligam a linha de tendência, a horizontal e o Fibonacci.
 * Ficam guardados por moeda no servidor (lib/useDesenhos.ts), iguais no PC e no celular.
 */
import { useQuery } from '@tanstack/react-query'
import type { LogicalRange } from 'lightweight-charts'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAbsorcao, useAvisosMapa, useFootprint, useNuvensCalor, useNuvensTop, usePosicionamento, usePresos } from '../api/hooks'
import { api } from '../api/client'
import type { NakedLongo, NuvensOverlay, SimbolosGrafico, TpoComposto, TpoDia, TpoGrafico } from '../api/types'
import ArvoreObjetos from '../components/chart/ArvoreObjetos'
import BarraEstilo from '../components/chart/BarraEstilo'
import BarraFerramentas from '../components/chart/BarraFerramentas'
import DesenhoConfig from '../components/chart/DesenhoConfig'
import { FERRAMENTAS } from '../components/chart/ferramentas'
import FootprintChart from '../components/chart/FootprintChart'
import GraficoTV, { casas, SEGUNDOS, type Ima, type InfoGrafico, type Vela } from '../components/chart/GraficoTV'
import PaineisFluxo, { inicioPaineis, marcasDistorcao, PASSO_MAX_PAINEIS } from '../components/chart/PaineisFluxo'
import { COR_TPO, type Selecao } from '../components/chart/tpoDesenho'
import ParedesAgora from '../components/ParedesAgora'
import { COR_FLUXO, colunasDaAbsorcao, imagemCalor, marcasAbsorcao, marcasPresos } from '../lib/camadasFluxo'
import type { ChartLevel } from '../lib/chart-tipos'
import { novoId, type Desenho } from '../lib/desenhos'
import { copiar } from '../lib/fibo'
import { useDesenhos } from '../lib/useDesenhos'

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
/** camadas de order flow do BTC (vieram da antiga aba Nuvens); sem `&c=` no endereço valem as do padrão */
const CAMADAS = [
  { id: 'abs', nome: 'Absorção', dica: 'Nuvem quente onde a agressão alavancada bateu numa parede e o preço não passou ("presos no topo/fundo")' },
  { id: 'pre', nome: 'Presos', dica: 'Seta e faixa amarela onde ficou gente presa no footprint (entrou forte e o preço fechou do outro lado)' },
  { id: 'par', nome: 'Paredes', dica: 'Mapa de calor: todo o livro acima de 3x o normal (Coinbase + Binance + Bybit)' },
  { id: 'niv', nome: 'Níveis', dica: 'Linhas dos 5 maiores níveis de compra e de venda no livro agora e dos naked POCs de dia, semana e mês' },
  { id: 'dis', nome: 'Distorção', dica: 'Seta "D" onde o preço foi para um lado e os alavancados abriram posição no outro (verde embaixo = vendidos contra a alta; vermelha em cima = comprados contra a queda)' },
] as const
const CAMADAS_PADRAO = 'abs,pre,dis'
/** o que `ir` (trocar tempo, moeda ou TPO) leva junto no endereço */
const MANTER_NO_ENDERECO = ['p', 'c', 'pt', 'v', 'fpt', 'fpl']
const PASSO_FLUXO = 300
const SETE_DIAS_FLUXO = 7 * 86400 - 600
const DIAS_PAREDES = 3
const TFS_PRESOS = [['300', '5 min'], ['1800', '30 min']] as const
const TFS_FP = [['300', '5m'], ['900', '15m'], ['1800', '30m'], ['3600', '1h'], ['14400', '4h']] as const
// múltiplos da faixa de US$ 20 que o coletor grava; 50 ou 250 repartiriam faixas e poriam volume na linha errada
const LINHAS_FP = ['20', '40', '100', '200', '500'] as const
/** a grade do livro do servidor: 0,1% do preço arredondado a US$ 10 (api/routes/nuvens_routes.py) */
const gradeLivro = (preco: number) => Math.max(10, Math.round((preco * 0.001) / 10) * 10)
/** nesses tempos o dia tem velas demais de largas para o perfil caber: ligar o TPO passa para 30 min */
const TEMPO_LARGO = ['4h', '1d']

const CHAVE_PREF_DESENHO = 'grafico.desenho.pref.v1'
type PrefDesenho = { ima: Ima; ficar: boolean; travar: boolean; ocultar: boolean }
function lerPrefDesenho(): PrefDesenho {
  const p: PrefDesenho = { ima: 'nao', ficar: false, travar: false, ocultar: false }
  try { return { ...p, ...JSON.parse(localStorage.getItem(CHAVE_PREF_DESENHO) || '{}') } } catch { return p }
}

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

const COR_NAKED = '#f5c04a'

/** rótulo curto do naked POC na escala: período e data de início (o rótulo inteiro fica na tela Mapa e avisos) */
function rotuloNaked(n: NakedLongo): string {
  const d = new Date(n.inicio_ms)
  const dd = String(d.getUTCDate()).padStart(2, '0'), mm = String(d.getUTCMonth() + 1).padStart(2, '0')
  const quando = n.periodo === 'mes' ? `mês ${mm}/${String(d.getUTCFullYear()).slice(2)}` : `${n.periodo === 'semana' ? 'sem. ' : ''}${dd}/${mm}`
  return `naked ${quando}`
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

  // desenhos (as ferramentas da TradingView): os desta moeda, guardados no servidor; o selecionado, a ferramenta ligada,
  // as preferências da barra (ímã, ficar no modo desenho, travar e esconder todos) e a configuração aberta
  const des = useDesenhos(simbolo)
  const desenhos = des.lista
  const [desSel, setDesSel] = useState<string | null>(null)
  const [ferramenta, setFerramenta] = useState<string | null>(null)
  const [pref, setPref] = useState<PrefDesenho>(lerPrefDesenho)
  const ima = pref.ima, ficar = pref.ficar
  const mudarPref = useCallback((p: Partial<PrefDesenho>) => setPref((v) => {
    const n = { ...v, ...p }
    try { localStorage.setItem(CHAVE_PREF_DESENHO, JSON.stringify(n)) } catch { /* modo privado */ }
    return n
  }), [])
  const [arvore, setArvore] = useState(false)
  const [config, setConfig] = useState<{ id: string; antes: Desenho[] } | null>(null)
  const copiado = useRef<Desenho | null>(null)
  useEffect(() => { setDesSel(null); setFerramenta(null); setConfig(null) }, [simbolo])
  const ferramentaAtual = ferramenta ? FERRAMENTAS.find((f) => f.tipo === ferramenta) ?? null : null
  const selecionado = desSel ? desenhos.find((d) => d.id === desSel && !d.oculto) ?? null : null
  const desAberto = config ? desenhos.find((d) => d.id === config.id) ?? null : null
  const trocar = useCallback((d: Desenho, juntar?: string) => {
    des.mudar(des.agora().map((x) => (x.id === d.id ? d : x)), juntar)
    if (d.oculto && d.id === desSel) setDesSel(null)
  }, [des, desSel])
  const apagar = useCallback((id: string) => {
    des.mudar(des.agora().filter((x) => x.id !== id))
    if (desSel === id) setDesSel(null)
  }, [des, desSel])
  const clonar = useCallback((d: Desenho) => {
    const c = { ...copiar(d), id: novoId(), oculto: false }
    des.mudar([...des.agora(), c]); setDesSel(c.id)
  }, [des])
  const ordem = useCallback((id: string, frente: boolean) => {
    const l = des.agora(), d = l.find((x) => x.id === id)
    if (!d) return
    const resto = l.filter((x) => x.id !== id)
    des.mudar(frente ? [...resto, d] : [d, ...resto])
  }, [des])
  const removerTodos = useCallback(() => {
    if (!desenhos.length || !window.confirm(`Remover os ${desenhos.length} desenhos desta moeda? (Ctrl+Z desfaz)`)) return
    des.mudar([]); setDesSel(null)
  }, [des, desenhos.length])
  const abrirConfig = useCallback((id: string) => {
    if (!des.agora().some((d) => d.id === id)) return
    setDesSel(id); setConfig({ id, antes: des.agora() })
  }, [des])
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      const alvo = e.target as HTMLElement | null
      if (config || escolhendo || (alvo && /^(INPUT|SELECT|TEXTAREA)$/.test(alvo.tagName))) return
      const k = e.key.toLowerCase()
      const ctrl = e.ctrlKey || e.metaKey
      if ((e.key === 'Delete' || e.key === 'Backspace') && desSel) { e.preventDefault(); apagar(desSel) }
      else if (e.key === 'Escape') { setFerramenta(null); setDesSel(null) }
      else if (ctrl && k === 'z' && !e.shiftKey) { e.preventDefault(); des.desfazer() }
      else if (ctrl && (k === 'y' || (k === 'z' && e.shiftKey))) { e.preventDefault(); des.refazer() }
      else if (ctrl && k === 'c' && desSel) { copiado.current = des.agora().find((d) => d.id === desSel) ?? null }
      else if (ctrl && k === 'v' && copiado.current) { e.preventDefault(); clonar(copiado.current) }
      else if (e.altKey && !ctrl) {
        const f = FERRAMENTAS.find((x) => x.atalho?.toLowerCase() === k)
        if (f) { e.preventDefault(); setFerramenta(f.tipo); setDesSel(null) }
      }
    }
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  }, [config, escolhendo, desSel, apagar, clonar, des])

  useEffect(() => {
    try { localStorage.setItem(GUARDADO, JSON.stringify({ s: simbolo, t: tempo })) } catch { /* modo privado */ }
  }, [simbolo, tempo])

  const nuvemParam = params.get('n')
  const ir = (s: string, t: string, tpo: string | null = diasTpo, j: Selecao | null = s === simbolo ? selecao : null,
              n: string | null = nuvemParam) => {
    const novo: Record<string, string> = { s, t }
    if (tpo) { novo.tpo = tpo; if (j) novo.j = `${j.de}-${j.ate}` }
    if (n) novo.n = n
    // painéis, camadas, presos e footprint seguem iguais ao trocar de tempo, de moeda ou o TPO
    for (const k of MANTER_NO_ENDERECO) { const v = params.get(k); if (v) novo[k] = v }
    setParams(novo, { replace: true })
  }
  // painéis de baixo (livro, liquidações, funding) e paredes de agora: dados do BTC, em velas de até 4 h; &p=0 esconde
  // camadas de fluxo só no BTC cotado em dólar: os dados (livro, presos, níveis) são todos em USD
  const ehBtc = /^BTC-(USD|USDT|USDC|FDUSD)$/.test(partes(simbolo).par)
  const fluxoLigado = params.get('p') !== '0'
  const fluxoCabe = (SEGUNDOS[tempo] ?? 0) <= PASSO_MAX_PAINEIS
  const [velasG, setVelasG] = useState<Vela[]>([])
  const tempos = useMemo(() => velasG.map((k) => k.t), [velasG])
  // camadas de order flow (&c=abs,pre,par,niv), presos de 5 ou 30 min (&pt=) e a vista de footprint (&v=fp)
  // "-" no endereço = todas desligadas (sem `c` valeria o padrão)
  const camadasOn = useMemo(() => new Set((params.get('c') ?? CAMADAS_PADRAO).split(',').filter((c) => c && c !== '-')), [params])
  const trocarParam = (chave: string, valor: string | null) =>
    setParams((q) => { const n = new URLSearchParams(q); if (valor === null) n.delete(chave); else n.set(chave, valor); return n }, { replace: true })
  const alternarCamada = (id: string) => {
    const n = new Set(camadasOn)
    if (n.has(id)) n.delete(id); else n.add(id)
    trocarParam('c', [...n].join(',') || '-')
  }
  const tfPresos = params.get('pt') === '300' ? 300 : 1800
  const vistaFp = ehBtc && params.get('v') === 'fp'
  const tfFp = TFS_FP.some(([v]) => v === params.get('fpt')) ? Number(params.get('fpt')) : 1800
  const linhaFp = (LINHAS_FP as readonly string[]).includes(params.get('fpl') ?? '') ? Number(params.get('fpl')) : 40
  // os dados de fluxo vão até 7 dias atrás (arredondado a 5 min para a chave do pedido não mudar a cada render)
  const inicioFluxo = ehBtc && !vistaFp && velasG.length
    ? Math.max(Math.floor(velasG[0].t / PASSO_FLUXO) * PASSO_FLUXO, Math.floor((Date.now() / 1000 - SETE_DIAS_FLUXO) / PASSO_FLUXO) * PASSO_FLUXO)
    : null
  const qAbs = useAbsorcao(camadasOn.has('abs') ? inicioFluxo : null)
  const qPresos = usePresos(inicioFluxo, tfPresos, camadasOn.has('pre'))
  // o mapa de paredes é o cálculo mais pesado (mediana de 24 h por faixa): só os últimos 3 dias, como na antiga aba Nuvens
  const inicioParedes = inicioFluxo === null ? null
    : Math.max(inicioFluxo, Math.floor((Date.now() / 1000 - DIAS_PAREDES * 86400) / PASSO_FLUXO) * PASSO_FLUXO)
  const qCalor = useNuvensCalor(camadasOn.has('par') ? inicioParedes : null, 'coinbase,binance,bybit', 3, PASSO_FLUXO)
  const qTop = useNuvensTop('coinbase,binance,bybit', ehBtc && camadasOn.has('niv'))
  const qFp = useFootprint(tfFp, linhaFp, vistaFp)
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

  // as camadas de order flow viram o que o gráfico desenha (só nos pares de BTC)
  const precoRef = ult?.c ?? null
  const absorcao = useMemo(() => (ehBtc && camadasOn.has('abs') && qAbs.data ? marcasAbsorcao(qAbs.data.eventos) : null), [ehBtc, camadasOn, qAbs.data])
  const presos = useMemo(() => (ehBtc && camadasOn.has('pre') && qPresos.data
    ? marcasPresos(qPresos.data.eventos, tfPresos, velasG, SEGUNDOS[tempo]) : null), [ehBtc, camadasOn, qPresos.data, tfPresos, velasG, tempo])
  // a distorção usa o mesmo pedido dos painéis de baixo (mesmo início e passo): não busca duas vezes
  const qPos = usePosicionamento(ehBtc && camadasOn.has('dis') && fluxoCabe ? inicioPaineis(tempos, SEGUNDOS[tempo]) : null, SEGUNDOS[tempo])
  const marcadores = useMemo(() => [...(presos?.markers ?? []), ...(ehBtc && camadasOn.has('dis') ? marcasDistorcao(qPos.data) : [])],
    [presos, ehBtc, camadasOn, qPos.data])
  // a grade fica a mesma enquanto a moeda não muda (com o preço perto de US$ 105 mil ela alternaria entre 100 e 110)
  const gradeFixa = useRef<{ s: string; g: number } | null>(null)
  if (precoRef && gradeFixa.current?.s !== simbolo) gradeFixa.current = { s: simbolo, g: gradeLivro(precoRef) }
  const gradeAbs = qCalor.data?.grade_usd ?? (gradeFixa.current?.s === simbolo ? gradeFixa.current.g : null)
  const heatmap = useMemo(() => {
    if (!ehBtc) return null
    const d = qCalor.data
    const abs = camadasOn.has('abs') && qAbs.data?.eventos.length && gradeAbs
      ? colunasDaAbsorcao(qAbs.data.eventos, PASSO_FLUXO, gradeAbs) : []
    // paredes e absorção juntas: uma imagem só, com as duas nuvens (no mesmo pixel fica a mais forte)
    if (camadasOn.has('par') && d?.grade_usd) return imagemCalor([...d.colunas, ...abs].sort((a, b) => a.ts - b.ts), d.passo_s, d.grade_usd, 1, 2)
    return abs.length && gradeAbs ? imagemCalor(abs, PASSO_FLUXO, gradeAbs) : null
  }, [ehBtc, camadasOn, qCalor.data, qAbs.data, gradeAbs])
  const camadas = useMemo(() => ({ heatmap, rects: [...(absorcao?.rects ?? []), ...(presos?.rects ?? [])], labels: absorcao?.labels ?? [] }),
    [heatmap, absorcao, presos])
  const qMapa = useAvisosMapa()
  const niveis = useMemo<ChartLevel[]>(() => (ehBtc && camadasOn.has('niv') ? [
    ...(qTop.data?.bids.slice(0, 5) ?? []).map((n) => ({ price: n.preco, label: `${Math.round(n.qtd)} BTC`, color: COR_FLUXO.bids, dashed: true })),
    ...(qTop.data?.asks.slice(0, 5) ?? []).map((n) => ({ price: n.preco, label: `${Math.round(n.qtd)} BTC`, color: COR_FLUXO.asks, dashed: true })),
    ...(qMapa.data?.naked_longos ?? []).map((n) => ({ price: n.preco, label: rotuloNaked(n), color: COR_NAKED, dashed: true })),
  ] : []), [ehBtc, camadasOn, qTop.data, qMapa.data])

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
          {ehBtc && CAMADAS.map((c) => (
            <button key={c.id} type="button" className={'gbotao' + (camadasOn.has(c.id) ? ' on' : '')} title={c.dica}
              onClick={() => alternarCamada(c.id)} disabled={vistaFp}>{c.nome}</button>
          ))}
          {ehBtc && camadasOn.has('pre') && !vistaFp && (
            <select className="gselect" value={String(tfPresos)} onChange={(e) => trocarParam('pt', e.target.value === '1800' ? null : e.target.value)} aria-label="Bloco dos presos">
              {TFS_PRESOS.map(([v, n]) => <option key={v} value={v}>presos {n}</option>)}
            </select>
          )}
          {ehBtc && (
            <button type="button" className={'gbotao' + (vistaFp ? ' on' : '')} onClick={() => trocarParam('v', vistaFp ? null : 'fp')}
              title="Footprint: compra e venda a mercado em cada preço de cada vela (Bybit perpétuo)">Footprint</button>
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
      {ferramentaAtual && (
        <div className="glegenda-tpo"><span className="gjuncao">{ferramentaAtual.nome}: {ferramentaAtual.pontos === 1 ? 'clique no preço' : 'clique no primeiro ponto e depois no segundo (ou arraste de um ao outro)'} · Esc cancela{ima !== 'nao' ? ` · ímã ${ima}` : ''}{ficar ? ' · fica ligada depois de desenhar' : ''}</span></div>
      )}
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
      {ehBtc && !vistaFp && CAMADAS.some((c) => camadasOn.has(c.id)) && (
        <div className="glegenda-tpo">
          {camadasOn.has('abs') && <span><b style={{ color: COR_FLUXO.asks }}>Absorção</b>: nuvem quente com contorno onde compra agressiva (top 10% do dia, OI subindo) bateu numa parede e o preço não passou; verde = o espelho no fundo
            {qAbs.data && <span className="muted"> · {qAbs.data.velas_com_livro_e_negocios < 24 ? 'ainda juntando ~2 h de livro e negócios' : `${qAbs.data.eventos.length} no período`}</span>}</span>}
          {camadasOn.has('pre') && <span><b style={{ color: COR_FLUXO.presos }}>Presos</b>: seta e faixa amarela no preço de quem ficou preso; "presos?" ainda espera as próximas velas
            {qPresos.data && <span className="muted"> · {qPresos.data.eventos.filter((e) => e.confirmado !== false).length} no período</span>}</span>}
          {camadasOn.has('par') && <span><b style={{ color: '#ece86e' }}>Paredes</b>: livro acima de 3x o normal nos últimos 3 dias; esquenta (até amarelo) com 12x ou mais{qCalor.isPending && <span className="muted"> · lendo o livro…</span>}</span>}
          {camadasOn.has('dis') && <span><b style={{ color: COR_FLUXO.bids }}>Distorção</b>: seta "D" verde embaixo = o preço subiu enquanto os alavancados abriam short (combustível para alta forçada); vermelha em cima = o preço caiu enquanto eles abriam long; "D×2" = agressão e contas juntas
            {!fluxoCabe ? <span className="muted"> · só até velas de 4 h</span>
              : qPos.data && <span className="muted"> · {qPos.data.velas.filter((v) => v.distorcao?.lado).length} velas no período</span>}</span>}
          {camadasOn.has('niv') && <span><b>Níveis</b>: os 5 maiores níveis de compra (verde) e de venda (vermelho) no livro agora, em BTC, e os naked POCs (amarelo) de dia, semana e mês que o preço ainda não tocou</span>}
          <span className="muted">leitura, não sinal: nada disso passou no teste contra sorteio</span>
        </div>
      )}
      <div className="card gcaixa">
        {vistaFp ? (
          <div style={{ display: 'grid', gap: 10 }}>
            <div className="gferramentas">
              <span className="muted" style={{ fontSize: 12 }}>vela</span>
              <select className="gselect" value={String(tfFp)} onChange={(e) => trocarParam('fpt', e.target.value)} aria-label="Tempo do footprint">
                {TFS_FP.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
              </select>
              <span className="muted" style={{ fontSize: 12 }}>linha de</span>
              <select className="gselect" value={String(linhaFp)} onChange={(e) => trocarParam('fpl', e.target.value)} aria-label="Altura da linha">
                {LINHAS_FP.map((v) => <option key={v} value={v}>US$ {v}</option>)}
              </select>
            </div>
            {qFp.isPending ? <div className="muted">montando o footprint…</div>
              : qFp.isError ? <div className="warn-txt">não deu para montar o footprint agora</div>
              : !qFp.data?.velas.length ? <div className="muted">ainda sem negócios gravados para o footprint</div>
              : <FootprintChart velas={qFp.data.velas} linha={qFp.data.linha_usd} />}
            <div className="muted" style={{ fontSize: 12 }}>
              Arraste para os lados e use a roda do mouse para o zoom. Chegando perto, cada linha mostra a <b style={{ color: COR_FLUXO.asks }}>venda a mercado</b> à
              esquerda e a <b style={{ color: '#3d8bfd' }}>compra a mercado</b> à direita (BTC, Bybit perpétuo). Contorno branco = POC da vela; negrito = desequilíbrio de 3
              para 1; <b style={{ color: COR_FLUXO.presos }}>contorno amarelo</b> = presos; Δ embaixo = compra menos venda da vela.
            </div>
          </div>
        ) : (
        <div className="gdes-grade">
          <BarraFerramentas ferramenta={ferramenta} onFerramenta={(t) => { setFerramenta(t); setDesSel(null) }}
            ima={pref.ima} onIma={(ima) => mudarPref({ ima })} ficar={pref.ficar} onFicar={(ficar) => mudarPref({ ficar })}
            travarTodos={pref.travar} onTravarTodos={(travar) => mudarPref({ travar })}
            ocultarTodos={pref.ocultar} onOcultarTodos={(ocultar) => { mudarPref({ ocultar }); setDesSel(null) }}
            nDesenhos={desenhos.length} onRemoverTodos={removerTodos}
            podeDesfazer={des.podeDesfazer} podeRefazer={des.podeRefazer} onDesfazer={des.desfazer} onRefazer={des.refazer}
            arvore={arvore} onArvore={setArvore} />
          <div className="gdes-area">
            <GraficoTV simbolo={simbolo} tempo={tempo} onInfo={setInfo} tpo={tpo} selecao={selecao} composto={composto} nuvens={nuvens} onDia={escolherDia}
              onVelas={setVelasG} onRange={setRange} camadas={camadas} marcadores={marcadores} niveis={niveis}
              desenhos={desenhos} onDesenhos={(l) => des.mudar(l)} desenhoSel={desSel} onDesenhoSel={setDesSel} onDesenhoConfig={abrirConfig}
              ferramenta={ferramenta} onFerramentaPronta={() => { if (!pref.ficar) setFerramenta(null) }} ima={pref.ima}
              travarTodos={pref.travar} ocultarTodos={pref.ocultar} />
            {selecionado && !ferramenta && !pref.ocultar && (
              <BarraEstilo desenho={selecionado} onMudar={(d) => trocar(d, `estilo:${d.id}`)} onConfig={() => abrirConfig(selecionado.id)}
                onClonar={() => clonar(selecionado)} onOrdem={(frente) => ordem(selecionado.id, frente)} onApagar={() => apagar(selecionado.id)} />
            )}
            {arvore && (
              <ArvoreObjetos lista={desenhos} sel={desSel} tempo={tempo} formatar={fmt} onSel={(id) => { setDesSel(id); setFerramenta(null) }}
                onMudar={(d) => trocar(d)} onApagar={apagar} onFechar={() => setArvore(false)} />
            )}
            {des.estado === 'so_aqui' && <div className="gdes-aviso warn-txt">desenhos guardados só neste navegador: o servidor não respondeu (tenta de novo na próxima mudança)</div>}
            {ehBtc && fluxoLigado && (fluxoCabe
              ? tempos.length > 0 && <PaineisFluxo tempos={tempos} range={range} passo={SEGUNDOS[tempo]} />
              : <div className="muted" style={{ fontSize: 12, padding: '10px 0' }}>os painéis de livro, liquidações e funding vão até velas de 4 h: escolha um tempo menor para vê-los</div>)}
          </div>
        </div>
        )}
      </div>
      {ehBtc && fluxoLigado && <ParedesAgora preco={ult?.c ?? null} />}
      {config && desAberto && (
        <DesenhoConfig desenho={desAberto} casas={dec}
          onMudar={(d) => des.previa(des.agora().map((x) => (x.id === d.id ? d : x)))}
          onFechar={(ok) => { if (ok) des.mudar(des.agora()); else des.previa(config.antes); setConfig(null) }} />
      )}
      {escolhendo && <Seletor atual={simbolo} onFechar={() => setEscolhendo(false)} onEscolher={(s) => { setEscolhendo(false); ir(s, tempo) }} />}
    </div>
  )
}
