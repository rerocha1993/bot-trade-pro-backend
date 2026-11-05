/**
 * Janela de configuração de um desenho, a mesma da TradingView para todas as ferramentas: abas Estilo (a de cada
 * ferramenta), Texto (quando tem), Coordenadas (preço e barra de cada ponto) e Visibilidade (em que tempos gráficos
 * aparece). Cada mudança aparece no gráfico na hora; Cancelar volta como estava; "Modelo" guarda ou recupera o padrão
 * da ferramenta (fica no servidor, vale para o PC e o celular).
 */
import { useEffect, useState } from 'react'
import { guardarModelo, modeloDe, temModelo, type Desenho, type Faixa, type Texto, type Visibilidade } from '../../lib/desenhos'
import type { ConfigFibo } from '../../lib/fibo'
import FiboEstilo, { FONTES, SeletorLinha } from './FiboConfig'
import { FERRAMENTA, type CfgHorizontal, type CfgTendencia } from './ferramentas'

interface Props {
  desenho: Desenho
  casas: number
  onMudar: (d: Desenho) => void
  onFechar: (ok: boolean) => void
}

type Aba = 'estilo' | 'texto' | 'coord' | 'vis'

/** data e hora (UTC) no formato do <input type="datetime-local"> */
const paraCampo = (t: number) => new Date(t * 1000).toISOString().slice(0, 16)
const doCampo = (s: string) => { const t = Date.parse(s + ':00Z'); return Number.isFinite(t) ? Math.floor(t / 1000) : null }

function EstiloTendencia({ c, mudar }: { c: CfgTendencia; mudar: (p: Partial<CfgTendencia>) => void }) {
  const st = (k: keyof CfgTendencia['stats'], nome: string) => (
    <label><input type="checkbox" checked={c.stats[k]} onChange={(e) => mudar({ stats: { ...c.stats, [k]: e.target.checked } })} /> {nome}</label>
  )
  return (
    <>
      <div className="fcfg-linha">
        <span>Linha</span>
        <input type="color" value={c.linha.cor} onChange={(e) => mudar({ linha: { ...c.linha, cor: e.target.value } })} aria-label="Cor da linha" />
        <SeletorLinha estilo={c.linha.estilo} largura={c.linha.largura}
          onEstilo={(estilo) => mudar({ linha: { ...c.linha, estilo } })} onLargura={(largura) => mudar({ linha: { ...c.linha, largura } })} />
      </div>
      <div className="fcfg-linha">
        <label><input type="checkbox" checked={c.estEsq} onChange={(e) => mudar({ estEsq: e.target.checked })} /> Estender antes do ponto 1</label>
        <label><input type="checkbox" checked={c.estDir} onChange={(e) => mudar({ estDir: e.target.checked })} /> Estender depois do ponto 2</label>
      </div>
      <div className="fcfg-linha">
        <span>Ponta 1</span>
        <select className="gselect" value={c.pontaEsq} onChange={(e) => mudar({ pontaEsq: e.target.value as CfgTendencia['pontaEsq'] })} aria-label="Ponta do ponto 1">
          <option value="normal">Normal</option><option value="seta">Seta</option>
        </select>
        <span>Ponta 2</span>
        <select className="gselect" value={c.pontaDir} onChange={(e) => mudar({ pontaDir: e.target.value as CfgTendencia['pontaDir'] })} aria-label="Ponta do ponto 2">
          <option value="normal">Normal</option><option value="seta">Seta</option>
        </select>
      </div>
      <div className="fcfg-linha">
        <label><input type="checkbox" checked={c.meio} onChange={(e) => mudar({ meio: e.target.checked })} /> Ponto do meio</label>
        <label><input type="checkbox" checked={c.precos} onChange={(e) => mudar({ precos: e.target.checked })} /> Rótulos de preço</label>
      </div>
      <div className="fcfg-secao">Estatísticas</div>
      <div className="fcfg-linha">
        {st('preco', 'Variação do preço')}{st('pct', 'Variação %')}{st('barras', 'Barras')}{st('tempo', 'Tempo')}{st('distancia', 'Distância')}{st('angulo', 'Ângulo')}
      </div>
      <div className="fcfg-linha">
        <span>Posição</span>
        <select className="gselect" value={c.statsPos} onChange={(e) => mudar({ statsPos: e.target.value as CfgTendencia['statsPos'] })} aria-label="Posição das estatísticas">
          <option value="esquerda">Esquerda</option><option value="centro">Centro</option><option value="direita">Direita</option>
        </select>
        <label><input type="checkbox" checked={c.statsSempre} onChange={(e) => mudar({ statsSempre: e.target.checked })} /> Sempre mostrar (não só selecionada)</label>
      </div>
    </>
  )
}

function EstiloHorizontal({ c, mudar }: { c: CfgHorizontal; mudar: (p: Partial<CfgHorizontal>) => void }) {
  return (
    <>
      <div className="fcfg-linha">
        <span>Linha</span>
        <input type="color" value={c.linha.cor} onChange={(e) => mudar({ linha: { ...c.linha, cor: e.target.value } })} aria-label="Cor da linha" />
        <SeletorLinha estilo={c.linha.estilo} largura={c.linha.largura}
          onEstilo={(estilo) => mudar({ linha: { ...c.linha, estilo } })} onLargura={(largura) => mudar({ linha: { ...c.linha, largura } })} />
      </div>
      <div className="fcfg-linha">
        <label><input type="checkbox" checked={c.rotuloPreco} onChange={(e) => mudar({ rotuloPreco: e.target.checked })} /> Rótulo do preço na escala</label>
      </div>
    </>
  )
}

function AbaTexto({ t, mudar }: { t: Texto; mudar: (t: Texto) => void }) {
  return (
    <>
      <div className="fcfg-linha">
        <input type="color" value={t.cor} onChange={(e) => mudar({ ...t, cor: e.target.value })} aria-label="Cor do texto" />
        <select className="gselect" value={t.tamanho} onChange={(e) => mudar({ ...t, tamanho: Number(e.target.value) })} aria-label="Tamanho do texto">
          {FONTES.map((f) => <option key={f} value={f}>{f}</option>)}
        </select>
        <button type="button" className={'gbotao' + (t.negrito ? ' on' : '')} onClick={() => mudar({ ...t, negrito: !t.negrito })} aria-label="Negrito"><b>B</b></button>
        <button type="button" className={'gbotao' + (t.italico ? ' on' : '')} onClick={() => mudar({ ...t, italico: !t.italico })} aria-label="Itálico"><i>I</i></button>
      </div>
      <textarea className="fcfg-texto" rows={4} value={t.texto} placeholder="Adicionar texto" onChange={(e) => mudar({ ...t, texto: e.target.value })} aria-label="Texto" />
      <div className="fcfg-linha">
        <span>Alinhamento</span>
        <select className="gselect" value={t.v} onChange={(e) => mudar({ ...t, v: e.target.value as Texto['v'] })} aria-label="Alinhamento vertical">
          <option value="cima">Em cima</option><option value="meio">No meio</option><option value="baixo">Embaixo</option>
        </select>
        <select className="gselect" value={t.h} onChange={(e) => mudar({ ...t, h: e.target.value as Texto['h'] })} aria-label="Alinhamento horizontal">
          <option value="esquerda">Esquerda</option><option value="centro">Centro</option><option value="direita">Direita</option>
        </select>
      </div>
    </>
  )
}

function LinhaFaixa({ nome, f, max, mudar }: { nome: string; f: Faixa; max: number; mudar: (f: Faixa) => void }) {
  const num = (v: string, campo: 'de' | 'ate') => { const n = Math.round(Number(v)); if (Number.isFinite(n)) mudar({ ...f, [campo]: Math.max(1, Math.min(max, n)) }) }
  return (
    <div className="fcfg-linha">
      <label style={{ width: 110 }}><input type="checkbox" checked={f.ligado} onChange={(e) => mudar({ ...f, ligado: e.target.checked })} /> {nome}</label>
      <input type="number" min={1} max={max} value={f.de} disabled={!f.ligado} onChange={(e) => num(e.target.value, 'de')} style={{ width: 70 }} aria-label={`${nome}: de`} />
      <span className="muted">até</span>
      <input type="number" min={1} max={max} value={f.ate} disabled={!f.ligado} onChange={(e) => num(e.target.value, 'ate')} style={{ width: 70 }} aria-label={`${nome}: até`} />
    </div>
  )
}

function AbaVisibilidade({ v, mudar }: { v: Visibilidade; mudar: (v: Visibilidade) => void }) {
  return (
    <>
      <LinhaFaixa nome="Minutos" f={v.minutos} max={59} mudar={(minutos) => mudar({ ...v, minutos })} />
      <LinhaFaixa nome="Horas" f={v.horas} max={24} mudar={(horas) => mudar({ ...v, horas })} />
      <LinhaFaixa nome="Dias" f={v.dias} max={366} mudar={(dias) => mudar({ ...v, dias })} />
      <div className="fcfg-linha">
        <label><input type="checkbox" checked={v.semanas} onChange={(e) => mudar({ ...v, semanas: e.target.checked })} /> Semanas</label>
        <label><input type="checkbox" checked={v.meses} onChange={(e) => mudar({ ...v, meses: e.target.checked })} /> Meses</label>
      </div>
      <div className="muted" style={{ fontSize: 12 }}>O desenho só aparece nos tempos gráficos marcados (o gráfico daqui vai de 1 min a 1 dia).</div>
    </>
  )
}

export default function DesenhoConfig({ desenho: d, casas, onMudar, onFechar }: Props) {
  const f = FERRAMENTA[d.tipo]
  const [aba, setAba] = useState<Aba>('estilo')
  const [aviso, setAviso] = useState<string | null>(null)
  const mudarCfg = (parcial: object) => onMudar({ ...d, cfg: { ...d.cfg, ...parcial } })

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onFechar(false)
      if (e.key === 'Enter' && !(e.target instanceof HTMLTextAreaElement)) onFechar(true)
    }
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  }, [onFechar])

  if (!f) return null
  const modelo = async (acao: string) => {
    if (acao === 'salvar') setAviso((await guardarModelo(d.tipo, d.cfg)) ? `salvo: as próximas "${f.nome}" já nascem assim` : 'salvo só neste navegador: o servidor não respondeu')
    if (acao === 'aplicar') onMudar({ ...d, cfg: modeloDe(d.tipo, f.padrao()) })
    if (acao === 'tv') onMudar({ ...d, cfg: f.padrao() })
    if (acao === 'esquecer') { await guardarModelo(d.tipo, null); setAviso('padrão apagado: as próximas nascem com o da TradingView') }
  }
  const passo = 10 ** -casas
  const abas: [Aba, string][] = [['estilo', 'Estilo'], ...(f.texto ? [['texto', 'Texto'] as [Aba, string]] : []), ['coord', 'Coordenadas'], ['vis', 'Visibilidade']]

  return (
    <div className="gsel-fundo" onClick={() => onFechar(false)}>
      <div className="gsel fcfg" onClick={(e) => e.stopPropagation()} role="dialog" aria-label={`Configurar ${f.nome}`}>
        <div className="fcfg-topo">
          <b>{f.nome}</b>
          <button type="button" className="btn ghost" onClick={() => onFechar(false)} aria-label="Fechar">✕</button>
        </div>
        <div className="tabs fcfg-abas">
          {abas.map(([id, nome]) => <button key={id} type="button" className={aba === id ? 'on' : ''} onClick={() => setAba(id)}>{nome}</button>)}
        </div>
        <div className="fcfg-corpo">
          {aba === 'estilo' && (
            d.tipo === 'fibo_retracao' ? <FiboEstilo cfg={d.cfg as ConfigFibo} mudar={mudarCfg} />
              : d.tipo === 'linha_tendencia' ? <EstiloTendencia c={d.cfg as CfgTendencia} mudar={mudarCfg} />
              : d.tipo === 'linha_horizontal' ? <EstiloHorizontal c={d.cfg as CfgHorizontal} mudar={mudarCfg} />
              : null
          )}
          {aba === 'texto' && <AbaTexto t={d.cfg.texto as Texto} mudar={(texto) => mudarCfg({ texto })} />}
          {aba === 'coord' && (
            <>
              {d.pts.map((p, i) => (
                <div key={i} className="fcfg-linha">
                  <span>#{i + 1} {f.soPreco ? '(preço)' : '(preço, barra UTC)'}</span>
                  <input type="number" step={passo} value={+p.p.toFixed(casas)} style={{ width: 150 }}
                    onChange={(e) => { const v = parseFloat(e.target.value); if (Number.isFinite(v)) onMudar({ ...d, pts: d.pts.map((q, k) => (k === i ? { ...q, p: v } : q)) }) }} aria-label={`Preço do ponto ${i + 1}`} />
                  {!f.soPreco && (
                    <input type="datetime-local" value={paraCampo(p.t)} style={{ width: 210 }}
                      onChange={(e) => { const v = doCampo(e.target.value); if (v !== null) onMudar({ ...d, pts: d.pts.map((q, k) => (k === i ? { ...q, t: v } : q)) }) }} aria-label={`Barra do ponto ${i + 1}`} />
                  )}
                </div>
              ))}
              {d.tipo === 'fibo_retracao' && <div className="muted" style={{ fontSize: 12 }}>O ponto 1 é onde o movimento começou e o 2 onde terminou: o nível 0 fica no ponto 2 e o 1 no ponto 1.</div>}
            </>
          )}
          {aba === 'vis' && <AbaVisibilidade v={d.vis} mudar={(vis) => onMudar({ ...d, vis })} />}
        </div>
        <div className="fcfg-pe">
          <select className="gselect" value="" onChange={(e) => { void modelo(e.target.value); e.target.value = '' }} aria-label="Modelo">
            <option value="">Modelo ▾</option>
            <option value="salvar">Salvar como padrão</option>
            {temModelo(d.tipo) && <option value="aplicar">Aplicar o padrão salvo</option>}
            <option value="tv">Voltar ao padrão da TradingView</option>
            {temModelo(d.tipo) && <option value="esquecer">Apagar o padrão salvo</option>}
          </select>
          {aviso && <span className="muted" style={{ fontSize: 12 }}>{aviso}</span>}
          <button type="button" className="btn ghost" style={{ marginLeft: 'auto' }} onClick={() => onFechar(false)}>Cancelar</button>
          <button type="button" className="btn primary" onClick={() => onFechar(true)}>Ok</button>
        </div>
      </div>
    </div>
  )
}
