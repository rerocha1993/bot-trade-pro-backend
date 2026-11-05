/**
 * A barra de desenho da esquerda, no molde da TradingView: cursor, os grupos de ferramentas (cada um mostra a última
 * usada; a setinha abre a lista do grupo), ímã (fraco ou forte), ficar no modo desenho, travar, esconder e remover
 * todos, desfazer e refazer, e a lista de objetos.
 */
import { useEffect, useRef, useState } from 'react'
import type { Ima } from './GraficoTV'
import { FERRAMENTA, FERRAMENTAS, GRUPOS, type GrupoId } from './ferramentas'

/** ícone de traço num quadrado de 18 (os caminhos das ferramentas estão em ferramentas.ts) */
export function Icone({ d, tam = 18 }: { d: string; tam?: number }) {
  return (
    <svg width={tam} height={tam} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth={1.3} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  )
}

export const ICONES = {
  cursor: 'M4 2 L4 15 L7.5 11.5 L10 16.5 L12 15.5 L9.5 10.5 L14 10.5 Z',
  ima: 'M4 3 V9 a5 5 0 0 0 10 0 V3 H11 V9 a2 2 0 0 1 -4 0 V3 Z M4 6 H7 M11 6 H14',
  ficar: 'M3 15 L4 11 L12 3 L15 6 L7 14 Z M10.5 4.5 L13.5 7.5',
  cadeado: 'M5.5 8 V6 a3.5 3.5 0 0 1 7 0 V8 M4 8 H14 V15.5 H4 Z',
  cadeadoAberto: 'M5.5 8 V6 a3.5 3.5 0 0 1 6.8 -1.2 M4 8 H14 V15.5 H4 Z',
  olho: 'M1.5 9 C4 4.5 14 4.5 16.5 9 C14 13.5 4 13.5 1.5 9 Z M9 9 m-2 0 a2 2 0 1 0 4 0 a2 2 0 1 0 -4 0',
  olhoRiscado: 'M1.5 9 C4 4.5 14 4.5 16.5 9 C14 13.5 4 13.5 1.5 9 Z M9 9 m-2 0 a2 2 0 1 0 4 0 a2 2 0 1 0 -4 0 M3 15 L15 3',
  lixeira: 'M3 5 H15 M7 5 V3 H11 V5 M5 5 L6 16 H12 L13 5 M8 8 V13 M10 8 V13',
  lista: 'M6 4 H15 M6 9 H15 M6 14 H15 M3 4 h0.5 M3 9 h0.5 M3 14 h0.5',
  desfazer: 'M6 3.5 L2.5 7 L6 10.5 M2.5 7 H11 a4 4 0 0 1 0 8 H8',
  refazer: 'M12 3.5 L15.5 7 L12 10.5 M15.5 7 H7 a4 4 0 0 0 0 8 H10',
  engrenagem: 'M9 6.5 a2.5 2.5 0 1 0 0.01 0 M9 1.5 V4 M9 14 V16.5 M1.5 9 H4 M14 9 H16.5 M3.7 3.7 L5.5 5.5 M12.5 12.5 L14.3 14.3 M3.7 14.3 L5.5 12.5 M12.5 5.5 L14.3 3.7',
  clonar: 'M6 6 H15 V15 H6 Z M3 12 V3 H12',
  frente: 'M4 10 H14 V16 H4 Z M9 2 V8 M6 5 L9 2 L12 5',
  tras: 'M4 2 H14 V8 H4 Z M9 10 V16 M6 13 L9 16 L12 13',
}

const CHAVE_ULTIMA = 'grafico.desenho.ultimaPorGrupo.v1'
function lerUltimas(): Partial<Record<GrupoId, string>> {
  try { return JSON.parse(localStorage.getItem(CHAVE_ULTIMA) || '{}') } catch { return {} }
}

interface Props {
  ferramenta: string | null
  onFerramenta: (tipo: string | null) => void
  ima: Ima
  onIma: (i: Ima) => void
  ficar: boolean
  onFicar: (v: boolean) => void
  travarTodos: boolean
  onTravarTodos: (v: boolean) => void
  ocultarTodos: boolean
  onOcultarTodos: (v: boolean) => void
  nDesenhos: number
  onRemoverTodos: () => void
  podeDesfazer: boolean
  podeRefazer: boolean
  onDesfazer: () => void
  onRefazer: () => void
  arvore: boolean
  onArvore: (v: boolean) => void
  desligada?: boolean
}

export default function BarraFerramentas(p: Props) {
  const [aberto, setAberto] = useState<string | null>(null)        // grupo ou 'ima' com a lista aberta
  const [ultimas, setUltimas] = useState(lerUltimas)
  const raiz = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!aberto) return
    const fora = (e: PointerEvent) => { if (!raiz.current?.contains(e.target as Node)) setAberto(null) }
    window.addEventListener('pointerdown', fora)
    return () => window.removeEventListener('pointerdown', fora)
  }, [aberto])

  const escolher = (tipo: string) => {
    const g = FERRAMENTA[tipo].grupo
    const novas = { ...ultimas, [g]: tipo }
    setUltimas(novas)
    try { localStorage.setItem(CHAVE_ULTIMA, JSON.stringify(novas)) } catch { /* sem armazenamento */ }
    p.onFerramenta(p.ferramenta === tipo ? null : tipo)
    setAberto(null)
  }

  return (
    <div ref={raiz} className={'gbarra-desenho' + (p.desligada ? ' off' : '')} role="toolbar" aria-label="Ferramentas de desenho" aria-orientation="vertical">
      <button type="button" className={'gbd-botao' + (!p.ferramenta ? ' on' : '')} onClick={() => p.onFerramenta(null)} title="Cursor (Esc)">
        <Icone d={ICONES.cursor} />
      </button>
      {GRUPOS.map((g) => {
        const lista = FERRAMENTAS.filter((f) => f.grupo === g.id)
        if (!lista.length) return null
        const atual = FERRAMENTA[ultimas[g.id] ?? ''] ?? lista[0]
        const ligado = !!p.ferramenta && FERRAMENTA[p.ferramenta]?.grupo === g.id
        const mostrada = ligado ? FERRAMENTA[p.ferramenta!] : atual
        return (
          <div key={g.id} className="gbd-grupo">
            <button type="button" className={'gbd-botao' + (ligado ? ' on' : '')} onClick={() => escolher(mostrada.tipo)}
              title={`${mostrada.nome}${mostrada.atalho ? ` (Alt+${mostrada.atalho})` : ''}`}>
              <Icone d={mostrada.icone} />
            </button>
            <button type="button" className="gbd-seta" onClick={() => setAberto(aberto === g.id ? null : g.id)} aria-label={`Mais ferramentas: ${g.nome}`} aria-expanded={aberto === g.id}>▸</button>
            {aberto === g.id && (
              <div className="gbd-menu" role="menu">
                <div className="gbd-menu-titulo">{g.nome}</div>
                {lista.map((f) => (
                  <button key={f.tipo} type="button" role="menuitem" className={'gbd-item' + (p.ferramenta === f.tipo ? ' on' : '')} onClick={() => escolher(f.tipo)}>
                    <Icone d={f.icone} /><span>{f.nome}</span>{f.atalho && <span className="muted mono">Alt+{f.atalho}</span>}
                  </button>
                ))}
              </div>
            )}
          </div>
        )
      })}
      <div className="gbd-sep" />
      <div className="gbd-grupo">
        <button type="button" className={'gbd-botao' + (p.ima !== 'nao' ? ' on' : '')} onClick={() => p.onIma(p.ima === 'nao' ? 'forte' : 'nao')}
          title={p.ima === 'nao' ? 'Ímã desligado' : p.ima === 'fraco' ? 'Ímã fraco: gruda só quando o ponteiro está perto' : 'Ímã forte: gruda sempre na abertura, máxima, mínima ou fechamento'}>
          <Icone d={ICONES.ima} />{p.ima === 'fraco' && <span className="gbd-mini">f</span>}
        </button>
        <button type="button" className="gbd-seta" onClick={() => setAberto(aberto === 'ima' ? null : 'ima')} aria-label="Modo do ímã" aria-expanded={aberto === 'ima'}>▸</button>
        {aberto === 'ima' && (
          <div className="gbd-menu" role="menu">
            {([['fraco', 'Ímã fraco', 'gruda quando o ponteiro está perto'], ['forte', 'Ímã forte', 'gruda sempre na vela'], ['nao', 'Sem ímã', '']] as const).map(([v, nome, dica]) => (
              <button key={v} type="button" role="menuitemradio" aria-checked={p.ima === v} className={'gbd-item' + (p.ima === v ? ' on' : '')} onClick={() => { p.onIma(v); setAberto(null) }}>
                <span>{nome}</span>{dica && <span className="muted">{dica}</span>}
              </button>
            ))}
          </div>
        )}
      </div>
      <button type="button" className={'gbd-botao' + (p.ficar ? ' on' : '')} onClick={() => p.onFicar(!p.ficar)} title="Ficar no modo desenho: a ferramenta continua ligada depois de desenhar">
        <Icone d={ICONES.ficar} />
      </button>
      <button type="button" className={'gbd-botao' + (p.travarTodos ? ' on' : '')} onClick={() => p.onTravarTodos(!p.travarTodos)} title={p.travarTodos ? 'Destravar todos os desenhos' : 'Travar todos os desenhos (seleciona, mas não arrasta)'}>
        <Icone d={p.travarTodos ? ICONES.cadeado : ICONES.cadeadoAberto} />
      </button>
      <button type="button" className={'gbd-botao' + (p.ocultarTodos ? ' on' : '')} onClick={() => p.onOcultarTodos(!p.ocultarTodos)} title={p.ocultarTodos ? 'Mostrar todos os desenhos' : 'Esconder todos os desenhos'}>
        <Icone d={p.ocultarTodos ? ICONES.olhoRiscado : ICONES.olho} />
      </button>
      <button type="button" className="gbd-botao" disabled={!p.nDesenhos} onClick={p.onRemoverTodos} title="Remover todos os desenhos desta moeda (dá para desfazer)">
        <Icone d={ICONES.lixeira} />
      </button>
      <div className="gbd-sep" />
      <button type="button" className="gbd-botao" disabled={!p.podeDesfazer} onClick={p.onDesfazer} title="Desfazer (Ctrl+Z)"><Icone d={ICONES.desfazer} /></button>
      <button type="button" className="gbd-botao" disabled={!p.podeRefazer} onClick={p.onRefazer} title="Refazer (Ctrl+Y)"><Icone d={ICONES.refazer} /></button>
      <div className="gbd-sep" />
      <button type="button" className={'gbd-botao' + (p.arvore ? ' on' : '')} onClick={() => p.onArvore(!p.arvore)} title="Lista de objetos (todos os desenhos desta moeda)">
        <Icone d={ICONES.lista} />{p.nDesenhos > 0 && <span className="gbd-mini">{p.nDesenhos}</span>}
      </button>
    </div>
  )
}
