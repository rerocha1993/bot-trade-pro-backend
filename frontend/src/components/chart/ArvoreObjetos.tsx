/**
 * Lista de objetos (a "árvore de objetos" da TradingView): todos os desenhos desta moeda, o mais novo em cima. Clicar
 * seleciona; o olho esconde ou mostra, o cadeado trava, a lixeira apaga. Desenho que não aparece neste tempo gráfico
 * (aba Visibilidade) vem marcado.
 */
import { visivelNoTempo, type Desenho } from '../../lib/desenhos'
import { Icone, ICONES } from './BarraFerramentas'
import { FERRAMENTA } from './ferramentas'

interface Props {
  lista: Desenho[]
  sel: string | null
  tempo: string
  formatar: (p: number) => string
  onSel: (id: string) => void
  onMudar: (d: Desenho) => void
  onApagar: (id: string) => void
  onFechar: () => void
}

export default function ArvoreObjetos({ lista, sel, tempo, formatar, onSel, onMudar, onApagar, onFechar }: Props) {
  return (
    <div className="garvore" role="dialog" aria-label="Lista de objetos">
      <div className="garvore-topo">
        <b>Objetos</b><span className="muted">{lista.length}</span>
        <button type="button" className="btn ghost" style={{ marginLeft: 'auto' }} onClick={onFechar} aria-label="Fechar">✕</button>
      </div>
      <div className="garvore-lista">
        {!lista.length && <div className="muted" style={{ padding: 10, fontSize: 12 }}>Nenhum desenho nesta moeda. Escolha uma ferramenta na barra da esquerda.</div>}
        {[...lista].reverse().map((d) => {
          const f = FERRAMENTA[d.tipo]
          const foraDoTempo = !visivelNoTempo(d.vis, tempo)
          return (
            <div key={d.id} className={'garvore-item' + (d.id === sel ? ' on' : '') + (d.oculto || foraDoTempo ? ' apagado' : '')}>
              <button type="button" className="garvore-nome" onClick={() => onSel(d.id)} title={foraDoTempo ? 'não aparece neste tempo gráfico (aba Visibilidade)' : ''}>
                {f ? <Icone d={f.icone} tam={16} /> : null}
                <span>{f?.nome ?? d.tipo}</span>
                <span className="muted mono">{f ? f.resumo(d, formatar) : ''}</span>
              </button>
              <button type="button" className="gbe-botao" onClick={() => onMudar({ ...d, oculto: !d.oculto })} title={d.oculto ? 'Mostrar' : 'Esconder'}>
                <Icone d={d.oculto ? ICONES.olhoRiscado : ICONES.olho} tam={16} />
              </button>
              <button type="button" className={'gbe-botao' + (d.travado ? ' on' : '')} onClick={() => onMudar({ ...d, travado: !d.travado })} title={d.travado ? 'Destravar' : 'Travar'}>
                <Icone d={d.travado ? ICONES.cadeado : ICONES.cadeadoAberto} tam={16} />
              </button>
              <button type="button" className="gbe-botao" onClick={() => onApagar(d.id)} title="Apagar"><Icone d={ICONES.lixeira} tam={16} /></button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
