/**
 * Aba Estilo do Fibonacci de retração, no molde da janela da TradingView: níveis, cores, linha de tendência, fundo,
 * estender, inverter, preços, rótulos e posição, fonte e escala log. A janela em volta (abas Coordenadas e
 * Visibilidade, Modelo, Cancelar e Ok) é a DesenhoConfig, a mesma de todas as ferramentas.
 */
import type { ConfigFibo, EstiloLinha } from '../../lib/fibo'

export const ESTILOS: [EstiloLinha, string][] = [['solida', '────'], ['tracejada', '- - - -'], ['pontilhada', '· · · · ·']]
export const LARGURAS = [1, 2, 3, 4]
export const FONTES = [10, 11, 12, 14, 16, 20, 24, 28, 32, 40]

/** espessura e estilo de uma linha (as duas listas da TradingView) */
export function SeletorLinha({ estilo, largura, onEstilo, onLargura }: { estilo: EstiloLinha; largura: number; onEstilo: (e: EstiloLinha) => void; onLargura: (l: number) => void }) {
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

export default function FiboEstilo({ cfg: c, mudar }: { cfg: ConfigFibo; mudar: (parcial: Partial<ConfigFibo>) => void }) {
  const nivel = (i: number, parcial: Partial<ConfigFibo['niveis'][number]>) =>
    mudar({ niveis: c.niveis.map((n, k) => (k === i ? { ...n, ...parcial } : n)) })
  return (
    <>
      <div className="fcfg-linha">
        <label><input type="checkbox" checked={c.tendencia.ligada} onChange={(e) => mudar({ tendencia: { ...c.tendencia, ligada: e.target.checked } })} /> Linha de tendência</label>
        <input type="color" value={c.tendencia.cor} onChange={(e) => mudar({ tendencia: { ...c.tendencia, cor: e.target.value } })} aria-label="Cor da linha de tendência" />
        <SeletorLinha estilo={c.tendencia.estilo} largura={c.tendencia.largura}
          onEstilo={(estilo) => mudar({ tendencia: { ...c.tendencia, estilo } })} onLargura={(largura) => mudar({ tendencia: { ...c.tendencia, largura } })} />
      </div>
      <div className="fcfg-linha">
        <span>Linha dos níveis</span>
        <SeletorLinha estilo={c.estiloNiveis} largura={c.larguraNiveis}
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
  )
}
