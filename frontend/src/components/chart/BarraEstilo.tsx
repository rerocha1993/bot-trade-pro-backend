/**
 * A barra flutuante que aparece com um desenho selecionado, como a da TradingView: cor, espessura e estilo da linha,
 * configurações, travar, esconder, clonar, trazer para a frente ou mandar para trás, e apagar. Dá para arrastá-la pela
 * alça da esquerda; o lugar fica guardado neste navegador.
 */
import { useRef, useState } from 'react'
import type { Desenho } from '../../lib/desenhos'
import { Icone, ICONES } from './BarraFerramentas'
import { ESTILOS, LARGURAS } from './FiboConfig'
import { FERRAMENTA } from './ferramentas'

const CHAVE_POS = 'grafico.barraEstilo.pos.v1'
type Pos = { x: number; y: number }
function lerPos(): Pos {
  try { const v = JSON.parse(localStorage.getItem(CHAVE_POS) || 'null'); if (Number.isFinite(v?.x) && Number.isFinite(v?.y)) return v } catch { /* nada */ }
  return { x: 60, y: 8 }
}

interface Props {
  desenho: Desenho
  onMudar: (d: Desenho) => void
  onConfig: () => void
  onClonar: () => void
  onOrdem: (frente: boolean) => void
  onApagar: () => void
}

export default function BarraEstilo({ desenho: d, onMudar, onConfig, onClonar, onOrdem, onApagar }: Props) {
  const f = FERRAMENTA[d.tipo]
  const [pos, setPos] = useState<Pos>(lerPos)
  const caixa = useRef<HTMLDivElement>(null)
  if (!f) return null
  const l = f.linha?.ler(d.cfg)
  const linha = (parcial: Partial<NonNullable<typeof l>>) => { if (f.linha && l) onMudar({ ...d, cfg: f.linha.gravar(d.cfg, { ...l, ...parcial }) }) }

  const arrastar = (e: React.PointerEvent) => {
    e.preventDefault()
    const pai = caixa.current?.parentElement?.getBoundingClientRect()
    const x0 = e.clientX - pos.x, y0 = e.clientY - pos.y
    let ultima = pos
    const mover = (ev: PointerEvent) => {
      const larg = caixa.current?.offsetWidth ?? 300
      ultima = {
        x: Math.max(0, Math.min((pai?.width ?? 2000) - larg, ev.clientX - x0)),
        y: Math.max(0, Math.min((pai?.height ?? 2000) - 40, ev.clientY - y0)),
      }
      setPos(ultima)
    }
    const soltar = () => {
      window.removeEventListener('pointermove', mover); window.removeEventListener('pointerup', soltar)
      try { localStorage.setItem(CHAVE_POS, JSON.stringify(ultima)) } catch { /* nada */ }
    }
    window.addEventListener('pointermove', mover); window.addEventListener('pointerup', soltar)
  }

  return (
    <div ref={caixa} className="gbarra-estilo" style={{ left: pos.x, top: pos.y }} role="toolbar" aria-label={`Estilo: ${f.nome}`}>
      <span className="gbe-alca" onPointerDown={arrastar} title="Arrastar a barra">⋮⋮</span>
      <span className="gbe-nome">{f.nome}</span>
      {l && <>
        <input type="color" value={l.cor} onChange={(e) => linha({ cor: e.target.value })} title="Cor da linha" aria-label="Cor da linha" />
        <select className="gselect" value={l.largura} onChange={(e) => linha({ largura: Number(e.target.value) })} aria-label="Espessura" title="Espessura">
          {LARGURAS.map((n) => <option key={n} value={n}>{n}px</option>)}
        </select>
        <select className="gselect" value={l.estilo} onChange={(e) => linha({ estilo: e.target.value as typeof l.estilo })} aria-label="Estilo da linha" title="Estilo da linha">
          {ESTILOS.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
        </select>
      </>}
      {!l && f.cor && (
        <input type="color" value={f.cor.ler(d.cfg)} onChange={(e) => onMudar({ ...d, cfg: f.cor!.gravar(d.cfg, e.target.value) })} title="Cor" aria-label="Cor" />
      )}
      {f.fundo && (
        <input type="color" className="gbe-fundo" value={f.fundo.ler(d.cfg)} onChange={(e) => onMudar({ ...d, cfg: f.fundo!.gravar(d.cfg, e.target.value) })} title="Cor do fundo" aria-label="Cor do fundo" />
      )}
      <button type="button" className="gbe-botao" onClick={onConfig} title="Configurações (duplo clique no desenho)"><Icone d={ICONES.engrenagem} /></button>
      <button type="button" className={'gbe-botao' + (d.travado ? ' on' : '')} onClick={() => onMudar({ ...d, travado: !d.travado })} title={d.travado ? 'Destravar' : 'Travar (não arrasta)'}>
        <Icone d={d.travado ? ICONES.cadeado : ICONES.cadeadoAberto} />
      </button>
      <button type="button" className="gbe-botao" onClick={() => onMudar({ ...d, oculto: true })} title="Esconder (volta pela lista de objetos)"><Icone d={ICONES.olhoRiscado} /></button>
      <button type="button" className="gbe-botao" onClick={onClonar} title="Clonar (Ctrl+C e Ctrl+V)"><Icone d={ICONES.clonar} /></button>
      <button type="button" className="gbe-botao" onClick={() => onOrdem(true)} title="Trazer para a frente"><Icone d={ICONES.frente} /></button>
      <button type="button" className="gbe-botao" onClick={() => onOrdem(false)} title="Mandar para trás"><Icone d={ICONES.tras} /></button>
      <button type="button" className="gbe-botao" onClick={onApagar} title="Apagar (Delete)"><Icone d={ICONES.lixeira} /></button>
    </div>
  )
}
