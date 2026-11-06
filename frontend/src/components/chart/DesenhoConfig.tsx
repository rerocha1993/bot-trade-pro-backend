/**
 * Janela de configuração de um desenho, a mesma da TradingView para todas as ferramentas: abas Estilo (montada pelos
 * `campos` de cada ferramenta; o Fibonacci tem a dele), Texto (quando tem), Coordenadas (preço e barra de cada ponto)
 * e Visibilidade (em que tempos gráficos aparece). Cada mudança aparece no gráfico na hora; Cancelar volta como estava;
 * "Modelo" guarda ou recupera o padrão da ferramenta (fica no servidor, vale para o PC e o celular).
 */
import { useEffect, useState } from 'react'
import { guardarModelo, modeloDe, temModelo, type Desenho, type Faixa, type Linha, type Texto, type Visibilidade } from '../../lib/desenhos'
import type { ConfigFibo } from '../../lib/fibo'
import FiboEstilo, { FONTES, SeletorLinha } from './FiboConfig'
import { FERRAMENTA, type Campo } from './ferramentas'
import { gravarCampo, lerCampo, type Fundo } from './ferramentasBase'

export type AbaConfig = 'estilo' | 'texto' | 'coord' | 'vis'

interface Props {
  desenho: Desenho
  casas: number
  aba?: AbaConfig
  onMudar: (d: Desenho) => void
  onFechar: (ok: boolean) => void
}

/** data e hora (UTC) no formato do <input type="datetime-local"> */
const paraCampo = (t: number) => new Date(t * 1000).toISOString().slice(0, 16)
const doCampo = (s: string) => { const t = Date.parse(s + ':00Z'); return Number.isFinite(t) ? Math.floor(t / 1000) : null }

/** a aba Estilo de qualquer ferramenta, pelos campos que ela declara; checkboxes seguidos ficam na mesma linha */
function EstiloPorCampos({ campos, cfg, mudar }: { campos: Campo[]; cfg: Desenho['cfg']; mudar: (cfg: Desenho['cfg']) => void }) {
  const set = (chave: string, v: unknown) => mudar(gravarCampo(cfg, chave, v))
  const blocos: (Campo | Campo[])[] = []
  for (const c of campos) {
    const ult = blocos[blocos.length - 1]
    if (c.tipo === 'bool' && Array.isArray(ult)) ult.push(c)
    else blocos.push(c.tipo === 'bool' ? [c] : c)
  }
  return (
    <>
      {blocos.map((b, i) => {
        if (Array.isArray(b)) return (
          <div key={i} className="fcfg-linha">
            {b.map((c) => c.tipo === 'bool' && (
              <label key={c.chave}><input type="checkbox" checked={!!lerCampo(cfg, c.chave)} onChange={(e) => set(c.chave, e.target.checked)} /> {c.nome}</label>
            ))}
          </div>
        )
        const c = b
        if (c.tipo === 'secao') return <div key={i} className="fcfg-secao">{c.nome}</div>
        if (c.tipo === 'linha') {
          const l = lerCampo(cfg, c.chave) as Linha
          return (
            <div key={i} className="fcfg-linha">
              <span style={{ minWidth: 110 }}>{c.nome}</span>
              <input type="color" value={l.cor} onChange={(e) => set(c.chave, { ...l, cor: e.target.value })} aria-label={`Cor: ${c.nome}`} />
              <SeletorLinha estilo={l.estilo} largura={l.largura} onEstilo={(estilo) => set(c.chave, { ...l, estilo })} onLargura={(largura) => set(c.chave, { ...l, largura })} />
            </div>
          )
        }
        if (c.tipo === 'cor') return (
          <div key={i} className="fcfg-linha">
            <span style={{ minWidth: 110 }}>{c.nome}</span>
            <input type="color" value={String(lerCampo(cfg, c.chave) ?? '#2962ff')} onChange={(e) => set(c.chave, e.target.value)} aria-label={c.nome} />
          </div>
        )
        if (c.tipo === 'fundo') {
          const f = lerCampo(cfg, c.chave) as Fundo
          return (
            <div key={i} className="fcfg-linha">
              <label style={{ minWidth: 110 }}><input type="checkbox" checked={f.ligado} onChange={(e) => set(c.chave, { ...f, ligado: e.target.checked })} /> {c.nome}</label>
              <input type="color" value={f.cor} disabled={!f.ligado} onChange={(e) => set(c.chave, { ...f, cor: e.target.value })} aria-label={`Cor: ${c.nome}`} />
              <span className="muted">transparência</span>
              <input type="range" min={0} max={100} value={f.transparencia} disabled={!f.ligado} onChange={(e) => set(c.chave, { ...f, transparencia: Number(e.target.value) })} aria-label={`Transparência: ${c.nome}`} />
              <span className="mono">{f.transparencia}%</span>
            </div>
          )
        }
        if (c.tipo === 'escolha') return (
          <div key={i} className="fcfg-linha">
            <span style={{ minWidth: 110 }}>{c.nome}</span>
            <select className="gselect" value={String(lerCampo(cfg, c.chave))} onChange={(e) => set(c.chave, e.target.value)} aria-label={c.nome}>
              {c.opcoes.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
            </select>
          </div>
        )
        if (c.tipo === 'niveis') {
          const lista = (lerCampo(cfg, c.chave) ?? []) as { valor: number; cor: string; ligado: boolean }[]
          const nivel = (k: number, parcial: object) => set(c.chave, lista.map((n, j) => (j === k ? { ...n, ...parcial } : n)))
          return (
            <div key={i}>
              <div className="fcfg-secao">{c.nome}</div>
              <div className="fcfg-niveis">
                {lista.map((n, k) => (
                  <div key={k} className="fcfg-nivel">
                    <input type="checkbox" checked={n.ligado} onChange={(e) => nivel(k, { ligado: e.target.checked })} aria-label={`Mostrar o nível ${n.valor}`} />
                    <input type="number" step="0.001" value={+n.valor.toFixed(4)} onChange={(e) => { const v = parseFloat(e.target.value); if (Number.isFinite(v)) nivel(k, { valor: v }) }} aria-label="Valor do nível" />
                    <input type="color" value={n.cor} onChange={(e) => nivel(k, { cor: e.target.value })} aria-label={`Cor do nível ${n.valor}`} />
                  </div>
                ))}
              </div>
            </div>
          )
        }
        if (c.tipo === 'numero') return (
          <div key={i} className="fcfg-linha">
            <span style={{ minWidth: 110 }}>{c.nome}</span>
            <input type="number" min={c.min} max={c.max} step={c.passo ?? 1} value={Number(lerCampo(cfg, c.chave))} style={{ width: 90 }}
              onChange={(e) => { const v = parseFloat(e.target.value); if (Number.isFinite(v)) set(c.chave, Math.max(c.min ?? -Infinity, Math.min(c.max ?? Infinity, v))) }} aria-label={c.nome} />
          </div>
        )
        return null
      })}
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
      <textarea className="fcfg-texto" rows={4} value={t.texto} placeholder="Adicionar texto" autoFocus onChange={(e) => mudar({ ...t, texto: e.target.value })} aria-label="Texto"
        onFocus={(e) => e.target.select()} />
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

export default function DesenhoConfig({ desenho: d, casas, aba: abaInicial = 'estilo', onMudar, onFechar }: Props) {
  const f = FERRAMENTA[d.tipo]
  const [aba, setAba] = useState<AbaConfig>(abaInicial)
  const [aviso, setAviso] = useState<string | null>(null)

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
  const temEstilo = d.tipo === 'fibo_retracao' || (f.campos?.length ?? 0) > 0
  const abas: [AbaConfig, string][] = [
    ...(temEstilo ? [['estilo', 'Estilo'] as [AbaConfig, string]] : []), ...(f.texto ? [['texto', 'Texto'] as [AbaConfig, string]] : []),
    ['coord', 'Coordenadas'], ['vis', 'Visibilidade'],
  ]
  const abaVista = abas.some(([id]) => id === aba) ? aba : abas[0][0]
  const mudarPonto = (i: number, parcial: Partial<{ t: number; p: number }>) => onMudar({ ...d, pts: d.pts.map((q, k) => (k === i ? { ...q, ...parcial } : q)) })

  return (
    <div className="gsel-fundo" onClick={() => onFechar(false)}>
      <div className="gsel fcfg" onClick={(e) => e.stopPropagation()} role="dialog" aria-label={`Configurar ${f.nome}`}>
        <div className="fcfg-topo">
          <b>{f.nome}</b>
          <button type="button" className="btn ghost" onClick={() => onFechar(false)} aria-label="Fechar">✕</button>
        </div>
        <div className="tabs fcfg-abas">
          {abas.map(([id, nome]) => <button key={id} type="button" className={abaVista === id ? 'on' : ''} onClick={() => setAba(id)}>{nome}</button>)}
        </div>
        <div className="fcfg-corpo">
          {abaVista === 'estilo' && (d.tipo === 'fibo_retracao'
            ? <FiboEstilo cfg={d.cfg as ConfigFibo} mudar={(parcial) => onMudar({ ...d, cfg: { ...d.cfg, ...parcial } })} />
            : <EstiloPorCampos campos={f.campos ?? []} cfg={d.cfg} mudar={(cfg) => onMudar({ ...d, cfg })} />)}
          {abaVista === 'texto' && <AbaTexto t={d.cfg.texto as Texto} mudar={(texto) => onMudar({ ...d, cfg: { ...d.cfg, texto } })} />}
          {abaVista === 'coord' && (
            <>
              {d.pts.map((p, i) => (
                <div key={i} className="fcfg-linha">
                  <span>#{i + 1} {f.tela ? '(posição na tela, %)' : f.soPreco ? '(preço)' : f.soTempo ? '(barra UTC)' : '(preço, barra UTC)'}</span>
                  {f.tela ? (
                    <>
                      <input type="number" min={0} max={100} step={1} value={Math.round(p.t * 100)} style={{ width: 80 }} onChange={(e) => mudarPonto(i, { t: Math.max(0, Math.min(100, Number(e.target.value))) / 100 })} aria-label="Da esquerda (%)" />
                      <input type="number" min={0} max={100} step={1} value={Math.round(p.p * 100)} style={{ width: 80 }} onChange={(e) => mudarPonto(i, { p: Math.max(0, Math.min(100, Number(e.target.value))) / 100 })} aria-label="De cima (%)" />
                    </>
                  ) : (
                    <>
                      {!f.soTempo && (
                        <input type="number" step={passo} value={+p.p.toFixed(casas)} style={{ width: 150 }}
                          onChange={(e) => { const v = parseFloat(e.target.value); if (Number.isFinite(v)) mudarPonto(i, { p: v }) }} aria-label={`Preço do ponto ${i + 1}`} />
                      )}
                      {!f.soPreco && (
                        <input type="datetime-local" value={paraCampo(p.t)} style={{ width: 210 }}
                          onChange={(e) => { const v = doCampo(e.target.value); if (v !== null) mudarPonto(i, { t: v }) }} aria-label={`Barra do ponto ${i + 1}`} />
                      )}
                    </>
                  )}
                </div>
              ))}
              {d.tipo === 'fibo_retracao' && <div className="muted" style={{ fontSize: 12 }}>O ponto 1 é onde o movimento começou e o 2 onde terminou: o nível 0 fica no ponto 2 e o 1 no ponto 1.</div>}
            </>
          )}
          {abaVista === 'vis' && <AbaVisibilidade v={d.vis} mudar={(vis) => onMudar({ ...d, vis })} />}
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
