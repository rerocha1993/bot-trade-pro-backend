from conselho import livro_historico as lh
from conselho.coletor_livro_perp import ColetorLivroPerp, resumo


def test_resumo_soma_so_ate_a_faixa():
    livro = ([(100.0, 1.0), (99.95, 2.0), (99.8, 5.0)], [(100.2, 1.5), (100.25, 3.0), (100.5, 4.0)])
    r = resumo("bybit", 1792596000.7, livro, faixa_pct=0.002)
    assert r["mid"] == 100.1 and r["ts"] == 1792596000
    assert r["bids"] == 3.0              # 100 e 99,95 estão a até 0,2% de 100,1; 99,8 não
    assert r["asks"] == 4.5              # 100,2 e 100,25; 100,5 não
    assert round(r["alcance_asks_pct"], 4) == round(100.5 / 100.1 - 1, 4)
    assert resumo("bybit", 0, ([], [(1.0, 1.0)])) is None


def test_ciclo_grava_e_segue_quando_uma_corretora_falha(tmp_path):
    def quebrada():
        raise RuntimeError("fora do ar")
    c = ColetorLivroPerp(buscadores={"bybit": lambda: ([(100.0, 1.0)], [(100.1, 2.0)]), "okx": quebrada}, raiz=str(tmp_path))
    assert c.ciclo(1792596000) == 1
    (r,) = lh.carregar_periodo("bybit", 1792596000, 1792596001, str(tmp_path))
    assert r["bids"] == 1.0 and r["asks"] == 2.0
