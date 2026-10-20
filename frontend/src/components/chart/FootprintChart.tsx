import { useEffect, useRef } from 'react'
import type { VelaFootprint } from '../../api/types'

/**
 * Footprint no estilo do TradingView ("Volume footprint, compra e venda"): cada vela vira uma coluna; em cada linha
 * de preço, a venda agredida à esquerda (vermelho) e a compra agredida à direita (azul), com barra proporcional.
 * POC da vela com contorno; desequilíbrio diagonal de 3:1 em negrito; presos com contorno amarelo.
 */
const COR = {
  fundo: '#0b0f14', grade: 'rgba(255,255,255,0.05)', texto: '#c7cfda', fraco: '#6b7685',
  compra: '#3d8bfd', venda: '#f0544f', alta: '#2ecc84', baixa: '#f0544f', presos: '#f5c04a', poc: 'rgba(255,255,255,0.75)',
}
const COLUNA = 132
const VELA = 12
const EIXO = 64
const RODAPE = 40
const LINHA_PX = 18
const DESEQUILIBRIO = 3

const num = (v: number) => (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v >= 100 ? v.toFixed(0) : v >= 10 ? v.toFixed(1) : v.toFixed(2))
const hhmm = (s: number) => new Date(s * 1000).toISOString().slice(11, 16)

export default function FootprintChart({ velas, linha, preco }: { velas: VelaFootprint[]; linha: number; preco?: number }) {
  const ref = useRef<HTMLCanvasElement>(null)
  const caixa = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const cv = ref.current
    if (!cv || !velas.length) return
    const topo = Math.ceil(Math.max(...velas.map((v) => v.maxima)) / linha) * linha + linha
    const base = Math.floor(Math.min(...velas.map((v) => v.minima)) / linha) * linha - linha
    const nLinhas = Math.max(1, Math.round((topo - base) / linha))
    const largura = velas.length * COLUNA + EIXO
    const altura = nLinhas * LINHA_PX + RODAPE
    const dpr = window.devicePixelRatio || 1
    cv.width = largura * dpr
    cv.height = altura * dpr
    cv.style.width = `${largura}px`
    cv.style.height = `${altura}px`
    const g = cv.getContext('2d')
    if (!g) return
    g.setTransform(dpr, 0, 0, dpr, 0, 0)
    g.fillStyle = COR.fundo
    g.fillRect(0, 0, largura, altura)
    const y = (p: number) => ((topo - p) / linha) * LINHA_PX
    const maior = Math.max(1e-9, ...velas.flatMap((v) => v.linhas.map(([, c, s]) => Math.max(c, s))))

    // grade horizontal e eixo de preço
    g.font = '10px ui-monospace, Menlo, Consolas, monospace'
    g.textBaseline = 'middle'
    const passoEixo = Math.max(1, Math.round(28 / LINHA_PX))
    for (let k = 0; k <= nLinhas; k++) {
      const yy = k * LINHA_PX
      g.strokeStyle = COR.grade
      g.beginPath(); g.moveTo(0, yy); g.lineTo(largura - EIXO, yy); g.stroke()
      if (k % passoEixo === 0 && k < nLinhas) {
        g.fillStyle = COR.fraco
        g.textAlign = 'left'
        g.fillText((topo - (k + 0.5) * linha).toFixed(0), largura - EIXO + 6, yy + LINHA_PX / 2)
      }
    }

    velas.forEach((v, i) => {
      const x0 = i * COLUNA
      const mapa = new Map(v.linhas.map(([p, c, s]) => [Math.round(p / linha), { c, s }]))
      // separador da coluna
      g.strokeStyle = COR.grade
      g.beginPath(); g.moveTo(x0 + COLUNA - 0.5, 0); g.lineTo(x0 + COLUNA - 0.5, altura - RODAPE); g.stroke()
      // vela (pavio e corpo) numa faixa estreita à esquerda
      const subiu = v.fechamento >= v.abertura
      const cx = x0 + 4 + VELA / 2
      g.strokeStyle = subiu ? COR.alta : COR.baixa
      g.beginPath(); g.moveTo(cx, y(v.maxima)); g.lineTo(cx, y(v.minima)); g.stroke()
      g.fillStyle = subiu ? COR.alta : COR.baixa
      const yc1 = y(Math.max(v.abertura, v.fechamento)), yc2 = y(Math.min(v.abertura, v.fechamento))
      g.fillRect(x0 + 4, yc1, VELA, Math.max(1, yc2 - yc1))
      // células: venda | compra
      const xa = x0 + VELA + 8, xb = x0 + COLUNA - 6, meio = (xa + xb) / 2, meia = (xb - xa) / 2
      for (const [p, c, s] of v.linhas) {
        const yy = y(p + linha)
        const k = Math.round(p / linha)
        g.fillStyle = 'rgba(240,84,79,0.28)'
        g.fillRect(meio - (s / maior) * meia, yy + 1, (s / maior) * meia, LINHA_PX - 2)
        g.fillStyle = 'rgba(61,139,253,0.30)'
        g.fillRect(meio, yy + 1, (c / maior) * meia, LINHA_PX - 2)
        // desequilíbrio diagonal: compra nesta linha contra a venda na linha de baixo, e vice-versa
        const abaixo = mapa.get(k - 1), acima = mapa.get(k + 1)
        const compraForte = c > 0 && c >= DESEQUILIBRIO * Math.max(abaixo?.s ?? 0, 1e-9) && c >= 1
        const vendaForte = s > 0 && s >= DESEQUILIBRIO * Math.max(acima?.c ?? 0, 1e-9) && s >= 1
        g.font = `${vendaForte ? 'bold ' : ''}10px ui-monospace, Menlo, Consolas, monospace`
        g.fillStyle = vendaForte ? COR.venda : COR.texto
        g.textAlign = 'right'
        g.fillText(num(s), meio - 4, yy + LINHA_PX / 2)
        g.font = `${compraForte ? 'bold ' : ''}10px ui-monospace, Menlo, Consolas, monospace`
        g.fillStyle = compraForte ? COR.compra : COR.texto
        g.textAlign = 'left'
        g.fillText(num(c), meio + 4, yy + LINHA_PX / 2)
      }
      // POC da vela
      if (v.poc !== null) {
        g.strokeStyle = COR.poc
        g.lineWidth = 1
        g.strokeRect(xa + 0.5, y(v.poc + linha) + 0.5, xb - xa - 1, LINHA_PX - 1)
      }
      // presos: contorno amarelo na linha e etiqueta
      for (const e of v.presos) {
        if (e.confirmado === false) continue          // as velas seguintes mostraram que ninguém ficou preso
        const p = Math.floor(e.preco / linha) * linha
        g.strokeStyle = COR.presos
        g.lineWidth = e.confirmado ? 2.5 : 1.5
        g.setLineDash(e.confirmado ? [] : [4, 3])
        g.strokeRect(xa - 1, y(p + linha) - 1, xb - xa + 2, LINHA_PX + 2)
        g.setLineDash([])
        g.lineWidth = 1
        // etiqueta com fundo próprio, fora da linha marcada, para não cobrir os números
        g.font = 'bold 10px system-ui, sans-serif'
        const texto = `${e.lado === 'compradores' ? 'compradores' : 'vendedores'} presos${e.confirmado ? '' : '?'}`
        const w = g.measureText(texto).width + 10
        const ye = e.lado === 'compradores' ? y(p + linha) - 16 : y(p) + 2
        g.fillStyle = COR.presos
        g.fillRect(meio - w / 2, ye, w, 14)
        g.fillStyle = '#1a1405'
        g.textAlign = 'center'
        g.fillText(texto, meio, ye + 7)
      }
      // rodapé: delta e hora
      g.textAlign = 'center'
      g.font = 'bold 11px ui-monospace, Menlo, Consolas, monospace'
      g.fillStyle = v.delta >= 0 ? COR.compra : COR.venda
      g.fillText(`Δ ${v.delta >= 0 ? '+' : '−'}${num(Math.abs(v.delta))}`, x0 + COLUNA / 2, altura - RODAPE + 12)
      g.font = '10px system-ui, sans-serif'
      g.fillStyle = COR.fraco
      g.fillText(hhmm(v.ts), x0 + COLUNA / 2, altura - RODAPE + 28)
    })

    // preço atual
    if (preco) {
      const yy = y(preco)
      g.strokeStyle = 'rgba(255,255,255,0.5)'
      g.setLineDash([4, 4])
      g.beginPath(); g.moveTo(0, yy); g.lineTo(largura - EIXO, yy); g.stroke()
      g.setLineDash([])
      g.fillStyle = '#e8edf3'
      g.fillRect(largura - EIXO + 2, yy - 8, EIXO - 4, 16)
      g.fillStyle = '#0b0f14'
      g.textAlign = 'left'
      g.font = 'bold 10px ui-monospace, Menlo, Consolas, monospace'
      g.fillText(preco.toFixed(0), largura - EIXO + 6, yy)
    }

    // mostra a última vela e o preço atual
    const c = caixa.current
    if (c) {
      c.scrollLeft = c.scrollWidth
      if (preco) c.scrollTop = Math.max(0, y(preco) - c.clientHeight / 2)
    }
  }, [velas, linha, preco])

  return (
    <div ref={caixa} style={{ overflow: 'auto', maxHeight: 620, borderRadius: 10, WebkitOverflowScrolling: 'touch' }}>
      <canvas ref={ref} style={{ display: 'block' }} />
    </div>
  )
}
