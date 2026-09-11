"""
Calendário macro: quando o Forex Factory falha, o plano B (scraping, até 10 s de rede) não pode rodar a cada
decisão. No scalp de 1m isso era uma chamada por minuto por robô, travando o ciclo.
"""
import core.macro_event_checker as m


class _SemCalendario:
    def evento_proximo(self, *a, **k):
        return None

    def calendario(self):
        return None           # Forex Factory fora do ar


def test_fallback_usa_cache_entre_decisoes(monkeypatch):
    chamadas = []
    monkeypatch.setattr(m, "_DERIV", _SemCalendario())
    monkeypatch.setattr(m, "_cache_fallback", {})
    monkeypatch.setattr(m, "evento_via_scraping", lambda **k: chamadas.append(1) or False)
    for _ in range(5):
        assert m.evento_importante_agora() is False
    assert len(chamadas) == 1


def test_cache_expira(monkeypatch):
    chamadas = []
    relogio = [1000.0]
    monkeypatch.setattr(m, "_DERIV", _SemCalendario())
    monkeypatch.setattr(m, "_cache_fallback", {})
    monkeypatch.setattr(m.time, "monotonic", lambda: relogio[0])
    monkeypatch.setattr(m, "evento_via_scraping", lambda **k: chamadas.append(1) or True)
    assert m.evento_importante_agora() is True
    relogio[0] += m.CACHE_FALLBACK_S + 1
    assert m.evento_importante_agora() is True
    assert len(chamadas) == 2


def test_calendario_principal_nao_passa_pelo_fallback(monkeypatch):
    class _Com:
        def evento_proximo(self, *a, **k):
            return {"titulo": "CPI"}

        def calendario(self):
            return [{"x": 1}]

    monkeypatch.setattr(m, "_DERIV", _Com())
    monkeypatch.setattr(m, "evento_via_scraping", lambda **k: (_ for _ in ()).throw(AssertionError("não devia raspar")))
    assert m.evento_importante_agora() is True
