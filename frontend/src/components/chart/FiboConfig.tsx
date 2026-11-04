/**
 * Configuração de um Fibonacci, no molde da janela da TradingView: aba Estilo (níveis, cores, linha de tendência,
 * fundo, estender, inverter, preços, rótulos e posição, fonte, log) e aba Coordenadas (preço e barra dos dois pontos).
 * Cada mudança aparece no gráfico na hora; Cancelar volta como estava; "Modelo" guarda ou recupera o padrão.
 */
import { useEffect, useState } from 'react'
import { PADRAO_TV, copiar, guardarPadrao, padraoFibo, type ConfigFibo, type EstiloLinha, type Fibo } from '../../lib/fibo'

interface Props {
  fibo: Fibo
  casas: number
  onMudar: (f: Fibo) => void
  onFechar: (ok: boolean) => void
}

const ESTILOS: [EstiloLinha, string][] = [['solida', '────'], ['tracejada', '- - - -'], ['pontilhada', '· · · · ·']]
const LARGURAS = [1, 2, 3, 4]
const FONTES = [10, 11, 12, 14, 16, 20, 24]

/** data e hora (UTC) no formato do <input type="datetime-local"> */
const paraCampo = (t: number) => new Date(t * 1000).toISOString().slice(0, 16)
const doCampo = (s: string) => { const t = Date.parse(s + ':00Z'); return Number.isFinite(t) ? Math.floor(t / 1000) : null }

function Linha({ estilo, largura, onEstilo, onLargura }: { estilo: EstiloLinha; largura: number; onEstilo: (e: EstiloLinha) => void; onLargura: (l: number) => void }) {
  return (
    <>
      <select className="gselect" value={largura} onChange={(e) => onLargura(Number(e.target.value))} aria-label="Espessura">
        {LARGURAS.map((l) => <option key={l} value={l}>{l}px</option>)}
      </select>
      <select className="gselect" value={estilo} onChange={(e) => onEstilo(e.target.value as EstiloLinha)} aria-label="Estilo da linha">
        {ESTILOS.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
      </select>
    </>
  )
}

export default function FiboConfig({ fibo, casas, onMudar, onFechar }: Props) {
  const [aba, setAba] = useState<'estilo' | 'coord'>('estilo')
  const [aviso, setAviso] = useState<string | null>(null)
  const c = fibo.cfg
  const mudar = (parcial: Partial<ConfigFibo>) => onMudar({ ...fibo, cfg: { ...c, ...parcial } })
  const nivel = (i: number, parcial: Partial<ConfigFibo['niveis'][number]>) =>
    mudar({ niveis: c.niveis.map((n, k) => (k === i ? { ...n, ...parcial } : n)) })

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onFechar(false)
      if (e.key === 'Enter' && !(e.target instanceof HTMLTextAreaElement)) onFechar(true)
    }
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  }, [onFechar])

  const modelo = (acao: string) => {
    if (acao === 'salvar') { guardarPadrao(c); setAviso('salvo: os próximos Fibonacci já nascem assim') }
    if (acao === 'aplicar') mudar(padraoFibo())
    if (acao === 'tv') mudar(copiar(PADRAO_TV))
    if (acao === 'esquecer') { guardarPadrao(null); setAviso('padrão apagado: os próximos nascem com o da TradingView') }
  }
  const passo = 10 ** -casas

  return (
    <div className="gsel-fundo" onClick={() => onFechar(false)}>
      <div className="gsel fcfg" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Configurar Fibonacci">
        <div className="fcfg-topo">
          <b>Fibonacci de retração</b>
          <button type="button" className="btn ghost" onClick={() => onFechar(false)} aria-label="Fechar">✕</button>
        </div>
        <div className="tabs fcfg-abas">
          <button type="button" className={aba === 'estilo' ? 'on' : ''} onClick={() => setAba('estilo')}>Estilo</button>
          <button type="button" className={aba === 'coord' ? 'on' : ''} onClick={() => setAba('coord')}>Coordenadas</button>
        </div>
        <div className="fcfg-corpo">
          {aba === 'estilo' ? (
            <>
              <div className="fcfg-linha">
                <label><input type="checkbox" checked={c.tendencia.ligada} onChange={(e) => mudar({ tendencia: { ...c.tendencia, ligada: e.target.checked } })} /> Linha de tendência</label>
                <input type="color" value={c.tendencia.cor} onChange={(e) => mudar({ tendencia: { ...c.tendencia, cor: e.target.value } })} aria-label="Cor da linha de tendência" />
                <Linha estilo={c.tendencia.estilo} largura={c.tendencia.largura}
                  onEstilo={(estilo) => mudar({ tendencia: { ...c.tendencia, estilo } })} onLargura={(largura) => mudar({ tendencia: { ...c.tendencia, largura } })} />
              </div>
              <div className="fcfg-linha">
                <span>Linha dos níveis</span>
                <Linha estilo={c.estiloNiveis} largura={c.larguraNiveis}
                  onEstilo={(estiloNiveis) => mudar({ estiloNiveis })} onLargura={(larguraNiveis) => mudar({ larguraNiveis })} />
              </div>
              <div className="fcfg-niveis">
                {c.niveis.map((n, i) => (
                  <div key={i} className="fcfg-nivel">
                    <input type="checkbox" checked={n.ligado} onChange={(e) => nivel(i, { ligado: e.target.checked })} aria-label={`Mostrar o nível ${n.valor}`} />
                    <input type="number" step="0.001" value={n.valor} onChange={(e) => { const v = parseFloat(e.target.value); if (Number.isFinite(v)) nivel(i, { valor: v }) }} aria-label="Valor do nível" />
                    <input type="color" value={n.cor} disabled={c.umaCor} onChange={(e) => nivel(i, { cor: e.target.value })} aria-label={`Cor do nível ${n.valor}`} />
                  </div>
                ))}
              </div>
              <div className="fcfg-linha">
                <label><input type="checkbox" checked={c.umaCor} onChange={(e) => mudar({ umaCor: e.target.checked })} /> Usar uma cor só</label>
                <input type="color" value={c.corUnica} disabled={!c.umaCor} onChange={(e) => mudar({ corUnica: e.target.value })} aria-label="Cor única" />
              </div>
              <div className="fcfg-linha">
                <label><input type="checkbox" checked={c.fundo} onChange={(e) => mudar({ fundo: e.target.checked })} /> Fundo</label>
                <span className="muted">transparência</span>
                <input type="range" min={0} max={100} value={c.transparencia} disabled={!c.fundo} onChange={(e) => mudar({ transparencia: Number(e.target.value) })} aria-label="Transparência do fundo" />
                <span className="mono">{c.transparencia}%</span>
              </div>
              <div className="fcfg-linha">
                <label><input type="checkbox" checked={c.estenderEsq} onChange={(e) => mudar({ estenderEsq: e.target.checked })} /> Estender à esquerda</label>
                <label><input type="checkbox" checked={c.estenderDir} onChange={(e) => mudar({ estenderDir: e.target.checked })} /> Estender à direita</label>
              </div>
              <div className="fcfg-linha">
                <label><input type="checkbox" checked={c.inverter} onChange={(e) => mudar({ inverter: e.target.checked })} /> Inverter</label>
                <label><input type="checkbox" checked={c.log} onChange={(e) => mudar({ log: e.target.checked })} /> Níveis em escala log</label>
              </div>
              <div className="fcfg-linha">
                <label><input type="checkbox" checked={c.precos} onChange={(e) => mudar({ precos: e.target.checked })} /> Preços</label>
                <label><input type="checkbox" checked={c.rotulos} onChange={(e) => mudar({ rotulos: e.target.checked })} /> Níveis</label>
                <select className="gselect" value={c.rotuloComo} disabled={!c.rotulos} onChange={(e) => mudar({ rotuloComo: e.target.value as ConfigFibo['rotuloComo'] })} aria-label="Níveis como">
                  <option value="valor">Valores</option>
                  <option value="percentual">Porcentagens</option>
                </select>
              </div>
              <div className="fcfg-linha">
                <span>Rótulos</span>
                <select className="gselect" value={c.horizontal} onChange={(e) => mudar({ horizontal: e.target.value as ConfigFibo['horizontal'] })} aria-label="Rótulo na horizontal">
                  <option value="esquerda">Esquerda</option>
                  <option value="centro">Centro</option>
                  <option value="direita">Direita</option>
                </select>
                <select className="gselect" value={c.vertical} onChange={(e) => mudar({ vertical: e.target.value as ConfigFibo['vertical'] })} aria-label="Rótulo na vertical">
                  <option value="cima">Em cima</option>
                  <option value="meio">No meio</option>
                  <option value="baixo">Embaixo</option>
                </select>
                <span>Fonte</span>
                <select className="gselect" value={c.fonte} onChange={(e) => mudar({ fonte: Number(e.target.value) })} aria-label="Tamanho da fonte">
                  {FONTES.map((f) => <option key={f} value={f}>{f}</option>)}
                </select>
              </div>
            </>
          ) : (
            <>
              {([['1', 't1', 'p1'], ['2', 't2', 'p2']] as const).map(([n, t, p]) => (
                <div key={n} className="fcfg-linha">
                  <span>#{n} (preço, barra UTC)</span>
                  <input type="number" step={passo} value={+fibo[p].toFixed(casas)} style={{ width: 150 }}
                    onChange={(e) => { const v = parseFloat(e.target.value); if (Number.isFinite(v)) onMudar({ ...fibo, [p]: v }) }} aria-label={`Preço do ponto ${n}`} />
                  <input type="datetime-local" value={paraCampo(fibo[t])} style={{ width: 210 }}
                    onChange={(e) => { const v = doCampo(e.target.value); if (v !== null) onMudar({ ...fibo, [t]: v }) }} aria-label={`Barra do ponto ${n}`} />
                </div>
              ))}
              <div className="muted" style={{ fontSize: 12 }}>O ponto 1 é onde o movimento começou e o 2 onde terminou: o nível 0 fica no ponto 2 e o 1 no ponto 1.</div>
            </>
          )}
        </div>
        <div className="fcfg-pe">
          <select className="gselect" value="" onChange={(e) => { modelo(e.target.value); e.target.value = '' }} aria-label="Modelo">
            <option value="">Modelo ▾</option>
            <option value="salvar">Salvar como padrão</option>
            <option value="aplicar">Aplicar o padrão salvo</option>
            <option value="tv">Voltar ao padrão da TradingView</option>
            <option value="esquecer">Apagar o padrão salvo</option>
          </select>
          {aviso && <span className="muted" style={{ fontSize: 12 }}>{aviso}</span>}
          <button type="button" className="btn ghost" style={{ marginLeft: 'auto' }} onClick={() => onFechar(false)}>Cancelar</button>
          <button type="button" className="btn primary" onClick={() => onFechar(true)}>Ok</button>
        </div>
      </div>
    </div>
  )
}
