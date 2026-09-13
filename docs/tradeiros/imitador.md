# Imitador: modelo × lives do Tradeiros

Gerado por `scripts/tradeiros_imitador.py` em 13/09/2026. Leitura e mapa às 13:00 UTC da data da live,
só com candles fechados. As lives decidem várias coisas em horas diferentes; o modelo faz um plano por dia.

## Resumo

| operador | lives | tipos (Jaccard médio) | zonas a ≤2% | hedge na faixa (±5 pp) |
|---|---|---|---|---|
| shaka | 22 | 0.45 | 13/60 | 5/7 |
| maroja | 11 | 0.52 | 7/26 | 3/5 |

## Por live

| data | operador | zona do preço | hedge do modelo | Jaccard | faltou no modelo | sobrou no modelo | zonas reais |
|---|---|---|---|---|---|---|---|
| 2022-11-07 | shaka | topo | 35% | 0.25 | venda_direcional | ficar_fora, hedge_aumentar | venda_direcional 21,400–21,400 ✗; compra 20,570–20,570 ✓ |
| 2022-11-21 | shaka | abaixo_do_valor | 90% (live 90–100% ✓) | 0.50 | ficar_fora, hedge_realizar | — | venda_direcional 16,280–16,280 ✓; venda_direcional 15,700–15,700 ✗; compra 15,000–15,276 ✗ |
| 2022-12-07 | shaka | fundo | 90% | 0.00 | compra, venda_direcional | ficar_fora | venda_direcional 17,100–17,300 ✗ |
| 2022-12-23 | shaka | meio | 40% | 0.67 | venda_direcional | — | venda_direcional 18,300–18,300 ✗ |
| 2022-12-23 | maroja | meio | 40% | 0.50 | compra, venda_direcional | — | hedge_aumentar 17,148–17,500 ✓; venda_direcional 18,900–19,475 ✗; compra 15,450–15,984 ✗ |
| 2023-01-14 | shaka | acima_do_valor | 29% | 0.25 | ficar_fora, hedge_aumentar | venda_direcional | hedge_aumentar 21,300–21,395 ✗; compra 18,639–18,900 ✗; compra 18,187–18,187 ✗; compra 16,800–16,800 ✓ |
| 2023-01-14 | maroja | acima_do_valor | 41% | 0.67 | ficar_fora | — | hedge_aumentar 21,300–21,395 ✓; compra 18,000–18,800 ✗; compra 16,800–16,800 ✓ |
| 2023-05-05 | shaka | meio | 20% | 0.50 | — | venda_direcional | — |
| 2023-07-28 | shaka | abaixo_do_valor | 20% | 0.33 | venda_direcional | hedge_aumentar | — |
| 2023-09-04 | shaka | entre_fundo_e_meio | 24% | 0.75 | venda_direcional | — | compra 24,750–24,760 ✓; venda_direcional 29,000–30,000 ✗ |
| 2024-01-10 | shaka | topo | 20% (live 20–25% ✓) | 0.67 | hedge_aumentar | — | — |
| 2024-01-10 | maroja | topo | 24% (live 55–60% ✗) | 0.33 | ficar_fora, hedge_aumentar | — | hedge_aumentar 47,900–48,900 ✗; compra 35,000–41,000 ✓ |
| 2024-03-15 | shaka | meio | 20% | 0.25 | compra, hedge_aumentar | ficar_fora | hedge_aumentar 72,000–73,000 ✗; compra 70,000–70,000 ✗; compra 69,000–69,000 ✗; compra 66,000–66,600 ✗; venda_direcional 72,000–74,000 ✓; compra 71,367–71,367 ✗ |
| 2024-04-19 | shaka | meio | 34% (live 50–50% ✗) | 0.80 | — | hedge_realizar | venda_direcional 66,500–68,300 ✓ |
| 2024-04-19 | maroja | meio | 43% (live 30–52% ✓) | 1.00 | — | — | — |
| 2024-04-25 | shaka | meio | 34% (live 30–30% ✓) | 0.40 | hedge_aumentar | hedge_realizar, venda_direcional | compra 63,900–66,000 ✗; hedge_aumentar 65,900–65,900 ✗; compra 59,000–62,000 ✓ |
| 2024-04-25 | maroja | meio | 42% | 0.50 | hedge_aumentar | hedge_realizar | — |
| 2024-07-10 | shaka | entre_meio_e_topo | 35% | 1.00 | — | — | hedge_aumentar 58,200–58,200 ✓; compra 55,000–57,000 ✓ |
| 2024-08-05 | shaka | abaixo_do_valor | 90% | 0.40 | ficar_fora, hedge_realizar | venda_direcional | hedge_aumentar 68,000–70,000 ✓; compra 49,000–50,000 ✓; hedge_aumentar 54,000–55,000 ✗; hedge_aumentar 57,200–60,000 ✗ |
| 2024-08-05 | maroja | abaixo_do_valor | 24% | 0.50 | ficar_fora | hedge_realizar | hedge_aumentar 68,000–70,000 ✓; hedge_aumentar 57,200–60,000 ✗ |
| 2024-08-06 | shaka | abaixo_do_valor | 90% | 0.33 | compra, hedge_aumentar | — | compra 49,000–54,000 ✗; hedge_aumentar 58,000–58,000 ✗; hedge_aumentar 61,000–62,000 ✗; compra 54,000–54,000 ✗ |
| 2024-12-06 | shaka | topo | 20% (live 30–70% ✗) | 0.33 | compra, hedge_aumentar | — | hedge_aumentar 101,899–101,899 ✗; hedge_aumentar 90,500–90,500 ✗; compra 100,000–100,000 ✗; compra 92,230–92,230 ✗ |
| 2024-12-06 | maroja | topo | 24% | 0.50 | hedge_aumentar | — | hedge_aumentar 101,000–104,000 ✗ |
| 2025-04-07 | maroja | abaixo_do_valor | 29% | 0.75 | compra | — | compra 77,200–77,200 ✗; compra 69,000–74,000 ✗ |
| 2025-06-25 | shaka | acima_do_valor | 58% (live 30–65% ✓) | 0.60 | compra | venda_direcional | compra 98,000–99,000 ✗; hedge_aumentar 104,000–104,000 ✗; hedge_aumentar 107,000–109,000 ✓; hedge_aumentar 107,000–108,000 ✓ |
| 2025-10-10 | shaka | entre_fundo_e_meio | 53% | 0.60 | compra | venda_direcional | compra 116,923–116,923 ✗ |
| 2025-11-19 | maroja | fundo | 26% (live 24–24% ✓) | 0.25 | ficar_fora, hedge_aumentar, hedge_realizar | — | compra 82,000–84,000 ✗; hedge_aumentar 92,800–96,500 ✗ |
| 2026-04-20 | maroja | entre_meio_e_topo | 37% (live 24.5–38% ✓) | 0.50 | compra, hedge_realizar | — | compra 73,200–73,200 ✗; hedge_aumentar 76,000–77,400 ✓; hedge_aumentar 78,649–80,000 ✓; compra 70,000–73,000 ✗; hedge_aumentar 85,000–90,000 ✗ |
| 2026-09-01 | shaka | meio | 24% | 0.25 | compra, hedge_aumentar, hedge_realizar | — | hedge_aumentar 78,228–78,228 ✗; hedge_aumentar 78,994–78,994 ✗; compra 76,287–77,500 ✗; hedge_aumentar 78,600–79,200 ✗; hedge_aumentar 80,528–81,091 ✗ |
| 2026-09-03 | shaka | entre_meio_e_topo | 24% (live 20–50% ✓) | 0.50 | hedge_aumentar | — | hedge_aumentar 80,500–81,800 ✗; hedge_aumentar 83,848–85,723 ✗; hedge_aumentar 81,600–81,600 ✗; hedge_aumentar 81,640–82,186 ✗ |
| 2026-09-04 | shaka | acima_do_valor | 24% | 0.25 | compra, hedge_aumentar, hedge_realizar | — | compra 74,340–74,340 ✗; hedge_aumentar 83,000–85,000 ✗; compra 75,400–75,400 ✗ |
| 2026-09-04 | maroja | acima_do_valor | 30% (live 41–41% ✗) | 0.20 | compra, hedge_aumentar, venda_direcional | hedge_realizar | hedge_aumentar 82,140–82,140 ✗; hedge_aumentar 80,673–81,207 ✗; compra 76,958–79,000 ✗; compra 75,550–75,550 ✗; compra 69,000–71,000 ✗; venda_direcional 82,000–86,000 ✗ |
| 2026-09-11 | shaka | entre_fundo_e_meio | 24% | 0.20 | compra, hedge_aumentar, hedge_realizar, venda_direcional | — | hedge_aumentar 78,750–80,000 ✗; compra 76,980–77,315 ✗; hedge_aumentar 78,500–80,826 ✗; compra 77,300–77,300 ✗; compra 75,000–75,000 ✗; venda_direcional 75,000–75,000 ✗ |
