/**
 * Os desenhos da moeda aberta: carrega do servidor, grava a cada mudança (meio segundo depois da última, para não
 * mandar um pedido por pixel arrastado), e guarda o histórico para desfazer (Ctrl+Z) e refazer (Ctrl+Y).
 *
 * `previa` mexe na tela sem gravar nem entrar no histórico (a janela de configuração mostra cada mudança na hora);
 * `mudar` grava e entra no histórico, com o "antes" de quando a prévia começou.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { carregarDesenhos, carregarModelos, gravarDesenhos, guardarCache, type Desenho } from './desenhos'

const ESPERA_MS = 500
const HISTORICO_MAX = 100

export type EstadoGravacao = 'carregando' | 'salvo' | 'salvando' | 'so_aqui'

export function useDesenhos(simbolo: string) {
  const [lista, setLista] = useState<Desenho[]>([])
  const [estado, setEstado] = useState<EstadoGravacao>('carregando')
  const hist = useRef<{ passado: Desenho[][]; futuro: Desenho[][] }>({ passado: [], futuro: [] })
  const [, setVersaoHist] = useState(0)
  const atual = useRef<Desenho[]>([])
  const confirmada = useRef<Desenho[]>([])        // a última lista que entrou no histórico (base para desfazer)
  const pendente = useRef<{ simbolo: string; lista: Desenho[] } | null>(null)
  const timer = useRef<number | null>(null)
  const geracao = useRef(0)

  const enviar = useCallback(async (manterVivo = false) => {
    if (timer.current) { window.clearTimeout(timer.current); timer.current = null }
    const p = pendente.current
    if (!p) return
    pendente.current = null
    try {
      await gravarDesenhos(p.simbolo, p.lista, manterVivo)
      if (!pendente.current) setEstado('salvo')
    } catch {
      setEstado('so_aqui')
    }
  }, [])

  const agendar = useCallback((sim: string, l: Desenho[]) => {
    guardarCache(sim, l)
    pendente.current = { simbolo: sim, lista: l }
    setEstado('salvando')
    if (timer.current) window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => { void enviar() }, ESPERA_MS)
  }, [enviar])

  // troca de moeda: grava o que faltava da anterior e carrega a nova
  useEffect(() => {
    void enviar()
    const g = ++geracao.current
    setEstado('carregando')
    setLista([]); atual.current = []; confirmada.current = []
    hist.current = { passado: [], futuro: [] }; setVersaoHist((v) => v + 1)
    void carregarModelos()
    carregarDesenhos(simbolo).then(({ lista: l, doServidor }) => {
      if (g !== geracao.current) return
      setLista(l); atual.current = l; confirmada.current = l
      setEstado(doServidor ? 'salvo' : 'so_aqui')
    })
  }, [simbolo, enviar])

  // fechando a aba no meio da espera: manda já
  useEffect(() => {
    const sair = () => { void enviar(true) }
    window.addEventListener('pagehide', sair)
    return () => { window.removeEventListener('pagehide', sair); void enviar() }
  }, [enviar])

  const previa = useCallback((l: Desenho[]) => { atual.current = l; setLista(l) }, [])

  /** `juntar`: mudanças seguidas com a mesma chave em menos de 1 s viram um passo só no histórico (arrastar a cor) */
  const ultimaJunta = useRef<{ chave: string; em: number } | null>(null)
  const mudar = useCallback((l: Desenho[], juntar?: string) => {
    const h = hist.current
    const agora = Date.now()
    const u = ultimaJunta.current
    const continua = !!juntar && !!u && u.chave === juntar && agora - u.em < 1000 && h.passado.length > 0
    ultimaJunta.current = juntar ? { chave: juntar, em: agora } : null
    if (!continua) h.passado = [...h.passado, confirmada.current].slice(-HISTORICO_MAX)
    h.futuro = []
    confirmada.current = l; atual.current = l
    setLista(l); setVersaoHist((v) => v + 1)
    agendar(simbolo, l)
  }, [simbolo, agendar])

  const desfazer = useCallback(() => {
    const h = hist.current
    const anterior = h.passado[h.passado.length - 1]
    if (!anterior) return
    h.passado = h.passado.slice(0, -1)
    h.futuro = [confirmada.current, ...h.futuro]
    confirmada.current = anterior; atual.current = anterior
    setLista(anterior); setVersaoHist((v) => v + 1)
    agendar(simbolo, anterior)
  }, [simbolo, agendar])

  const refazer = useCallback(() => {
    const h = hist.current
    const proxima = h.futuro[0]
    if (!proxima) return
    h.futuro = h.futuro.slice(1)
    h.passado = [...h.passado, confirmada.current]
    confirmada.current = proxima; atual.current = proxima
    setLista(proxima); setVersaoHist((v) => v + 1)
    agendar(simbolo, proxima)
  }, [simbolo, agendar])

  return {
    lista, estado, previa, mudar, desfazer, refazer,
    podeDesfazer: hist.current.passado.length > 0, podeRefazer: hist.current.futuro.length > 0,
    /** a lista como está agora (para quem lê fora do ciclo do React) */
    agora: () => atual.current,
  }
}
