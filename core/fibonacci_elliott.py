# core/fibonacci_elliott.py
"""
Validação de proporções de Fibonacci para padrões de Elliott.

`ondas` é uma lista de dicts com ao menos {'preco_inicio', 'preco_fim'} em ordem temporal.
Cada validador devolve um dict padronizado:
    {'ok': True|False|None, 'razao': float|None, 'ideal': bool, 'motivo': str}
`ok=None` significa "não há ondas suficientes para avaliar".

Regras (impulso 1-2-3-4-5):
    Onda 2: retrai entre 23.6% e 88.6% da onda 1 (ideal 50%-61.8%) e NÃO ultrapassa o início da 1.
    Onda 3: maior que a onda 1 (ideal >= 161.8%); nunca é a mais curta entre 1, 3 e 5.
    Onda 4: retrai entre 23.6% e 61.8% da onda 3 (ideal 23.6%-38.2%) e NÃO invade o território da 1.
    Onda 5: entre 61.8% e 161.8% da onda 1 (ideal ~100%) ou 61.8% de (1+3).
Correção ABC:
    B retrai 38.2%-88.6% de A (ideal 50%-61.8%); C ~ 100% de A (61.8%-161.8%).
"""
from __future__ import annotations

from typing import Dict, List, Optional


def _tamanho(onda: Dict) -> float:
    return abs(float(onda["preco_fim"]) - float(onda["preco_inicio"]))


def _sobe(onda: Dict) -> bool:
    return float(onda["preco_fim"]) >= float(onda["preco_inicio"])


def _res(ok, razao, ideal, motivo) -> Dict:
    return {"ok": ok, "razao": (round(razao, 4) if razao is not None else None), "ideal": bool(ideal), "motivo": motivo}


class FibonacciElliott:
    def __init__(self, ondas: List[Dict]):
        self.ondas = list(ondas or [])

    # ------------------------------------------------------------ impulso
    def validar_onda2(self) -> Dict:
        if len(self.ondas) < 2:
            return _res(None, None, False, "ondas insuficientes")
        o1, o2 = self.ondas[0], self.ondas[1]
        t1 = _tamanho(o1)
        if t1 == 0:
            return _res(False, None, False, "onda 1 nula")
        r = _tamanho(o2) / t1
        # não pode ultrapassar o início da onda 1
        if _sobe(o1):
            invalida = float(o2["preco_fim"]) <= float(o1["preco_inicio"])
        else:
            invalida = float(o2["preco_fim"]) >= float(o1["preco_inicio"])
        ok = (0.236 <= r <= 0.886) and not invalida
        ideal = 0.5 - 1e-6 <= r <= 0.618 + 1e-6
        return _res(ok, r, ideal, f"onda 2 retraiu {r:.1%} da onda 1" + (" (ultrapassou o início da 1)" if invalida else ""))

    def validar_onda3(self) -> Dict:
        if len(self.ondas) < 3:
            return _res(None, None, False, "ondas insuficientes")
        o1, o3 = self.ondas[0], self.ondas[2]
        t1 = _tamanho(o1)
        if t1 == 0:
            return _res(False, None, False, "onda 1 nula")
        r = _tamanho(o3) / t1
        # deve romper o fim da onda 1
        rompe = float(o3["preco_fim"]) > float(o1["preco_fim"]) if _sobe(o1) else float(o3["preco_fim"]) < float(o1["preco_fim"])
        ok = r >= 1.0 and rompe
        ideal = r >= 1.618 - 1e-6
        return _res(ok, r, ideal, f"onda 3 = {r:.2f}x onda 1" + ("" if rompe else " (não rompeu o topo/fundo da 1)"))

    def validar_onda4(self) -> Dict:
        if len(self.ondas) < 4:
            return _res(None, None, False, "ondas insuficientes")
        o1, o3, o4 = self.ondas[0], self.ondas[2], self.ondas[3]
        t3 = _tamanho(o3)
        if t3 == 0:
            return _res(False, None, False, "onda 3 nula")
        r = _tamanho(o4) / t3
        if _sobe(o1):
            invade = float(o4["preco_fim"]) < float(o1["preco_fim"])
        else:
            invade = float(o4["preco_fim"]) > float(o1["preco_fim"])
        ok = (0.236 <= r <= 0.618) and not invade
        ideal = 0.236 - 1e-6 <= r <= 0.382 + 1e-6
        return _res(ok, r, ideal, f"onda 4 retraiu {r:.1%} da onda 3" + (" (invadiu a onda 1)" if invade else ""))

    def validar_onda5(self) -> Dict:
        if len(self.ondas) < 5:
            return _res(None, None, False, "ondas insuficientes")
        o1, o3, o5 = self.ondas[0], self.ondas[2], self.ondas[4]
        t1, t3, t5 = _tamanho(o1), _tamanho(o3), _tamanho(o5)
        if t1 == 0:
            return _res(False, None, False, "onda 1 nula")
        r = t5 / t1
        rompe = float(o5["preco_fim"]) > float(o3["preco_fim"]) if _sobe(o1) else float(o5["preco_fim"]) < float(o3["preco_fim"])
        mais_curta = t3 < t1 and t3 < t5  # onda 3 nunca é a mais curta
        ok = (0.382 <= r <= 2.618) and not mais_curta
        ideal = 0.618 - 1e-6 <= r <= 1.618 + 1e-6
        return _res(ok, r, ideal, f"onda 5 = {r:.2f}x onda 1" + ("" if rompe else " (truncada)") + (" (onda 3 é a mais curta)" if mais_curta else ""))

    # ------------------------------------------------------------- ABC
    def validar_abc(self) -> Dict:
        if len(self.ondas) < 3:
            return _res(None, None, False, "ondas insuficientes")
        a, b, c = self.ondas[0], self.ondas[1], self.ondas[2]
        ta = _tamanho(a)
        if ta == 0:
            return _res(False, None, False, "onda A nula")
        rb = _tamanho(b) / ta
        rc = _tamanho(c) / ta
        ok = (0.382 <= rb <= 1.382) and (0.618 <= rc <= 2.618)
        ideal = (0.5 <= rb <= 0.786) and (0.9 <= rc <= 1.1)
        return _res(ok, rc, ideal, f"B={rb:.1%} de A, C={rc:.2f}x A")

    # ----------------------------------------------------------- flats
    def _abc_tamanhos(self):
        a, b, c = self.ondas[0], self.ondas[1], self.ondas[2]
        return _tamanho(a), _tamanho(b), _tamanho(c)

    def validar_flat_regular(self) -> Dict:
        if len(self.ondas) < 3:
            return _res(None, None, False, "ondas insuficientes")
        ta, tb, tc = self._abc_tamanhos()
        if ta == 0:
            return _res(False, None, False, "onda A nula")
        ok = (0.9 <= tb / ta <= 1.05) and (0.9 <= tc / ta <= 1.1)
        return _res(ok, tc / ta, ok, f"flat regular B={tb / ta:.2f} C={tc / ta:.2f}")

    def validar_flat_expanded(self) -> Dict:
        if len(self.ondas) < 3:
            return _res(None, None, False, "ondas insuficientes")
        ta, tb, tc = self._abc_tamanhos()
        if ta == 0:
            return _res(False, None, False, "onda A nula")
        ok = (1.05 < tb / ta <= 1.382) and (tc / ta >= 1.236)
        return _res(ok, tc / ta, ok, f"flat expandido B={tb / ta:.2f} C={tc / ta:.2f}")

    def validar_flat_running(self) -> Dict:
        if len(self.ondas) < 3:
            return _res(None, None, False, "ondas insuficientes")
        ta, tb, tc = self._abc_tamanhos()
        if ta == 0:
            return _res(False, None, False, "onda A nula")
        ok = (tb / ta > 1.05) and (tc / ta < 1.0)
        return _res(ok, tc / ta, ok, f"flat running B={tb / ta:.2f} C={tc / ta:.2f}")

    # ------------------------------------------------------- triângulo
    def validar_triangulo(self) -> Dict:
        if len(self.ondas) < 5:
            return _res(None, None, False, "ondas insuficientes")
        props = []
        for i in range(1, 5):
            ant = _tamanho(self.ondas[i - 1])
            atual = _tamanho(self.ondas[i])
            if ant == 0:
                return _res(False, None, False, "perna nula")
            props.append(atual / ant)
        ok = all(0.5 <= p <= 0.9 for p in props)
        return _res(ok, props[-1], ok, "pernas contraindo " + ", ".join(f"{p:.2f}" for p in props))

    # ------------------------------------------------------- diagonais
    def validar_diagonal_leading(self) -> Dict:
        if len(self.ondas) < 5:
            return _res(None, None, False, "ondas insuficientes")
        t = [_tamanho(o) for o in self.ondas[:5]]
        if t[0] == 0:
            return _res(False, None, False, "onda 1 nula")
        # 3 > 1 e 5 < 3 com sobreposição permitida entre 4 e 1
        ok = t[2] > t[0] and t[4] < t[2]
        return _res(ok, t[2] / t[0], ok, "diagonal leading" if ok else "não é diagonal leading")

    def validar_diagonal_ending(self) -> Dict:
        if len(self.ondas) < 5:
            return _res(None, None, False, "ondas insuficientes")
        t = [_tamanho(o) for o in self.ondas[:5]]
        ok = t[0] > t[2] > t[4] and t[1] > t[3]
        return _res(ok, (t[4] / t[0]) if t[0] else None, ok, "diagonal ending (pernas encolhendo)" if ok else "não é diagonal ending")

    # ------------------------------------------------------- WXY / WXYXZ
    def validar_wxy(self) -> Dict:
        if len(self.ondas) < 3:
            return _res(None, None, False, "ondas insuficientes")
        w, y = self.ondas[0], self.ondas[2]
        tw = _tamanho(w)
        if tw == 0:
            return _res(False, None, False, "onda W nula")
        r = _tamanho(y) / tw
        ok = 0.618 <= r <= 1.618
        return _res(ok, r, 0.9 <= r <= 1.1, f"Y = {r:.2f}x W")

    def validar_wxyxz(self) -> Dict:
        if len(self.ondas) < 5:
            return _res(None, None, False, "ondas insuficientes")
        w, z = self.ondas[0], self.ondas[4]
        tw = _tamanho(w)
        if tw == 0:
            return _res(False, None, False, "onda W nula")
        r = _tamanho(z) / tw
        ok = 0.618 <= r <= 1.618
        return _res(ok, r, 0.9 <= r <= 1.1, f"Z = {r:.2f}x W")

    # ---------------------------------------------------------- scores
    def score_impulso(self) -> float:
        checks = [self.validar_onda2(), self.validar_onda3(), self.validar_onda4(), self.validar_onda5()]
        return self._score(checks)

    def score_abc(self) -> float:
        return self._score([self.validar_abc()])

    def score_confianca(self) -> float:
        """Melhor score entre impulso e ABC (compatibilidade com o código antigo)."""
        return max(self.score_impulso(), self.score_abc())

    @staticmethod
    def _score(checks: List[Dict]) -> float:
        validos = [c for c in checks if c["ok"] is not None]
        if not validos:
            return 0.0
        if any(c["ok"] is False for c in validos):
            return 0.0
        pontos = sum(1.0 if c["ideal"] else 0.7 for c in validos)
        return round(pontos / len(validos), 3)

    # ------------------------------------------------ alvos por fase
    def alvos_onda3(self) -> Optional[Dict]:
        if len(self.ondas) < 2:
            return None
        o1, o2 = self.ondas[0], self.ondas[1]
        t1 = _tamanho(o1)
        base = float(o2["preco_fim"])
        s = 1 if _sobe(o1) else -1
        return {"invalidacao": base, "alvo_1": base + s * 1.0 * t1, "alvo_2": base + s * 1.618 * t1,
                "alvo_3": base + s * 2.618 * t1}

    def alvos_onda5(self) -> Optional[Dict]:
        if len(self.ondas) < 4:
            return None
        o1, o3, o4 = self.ondas[0], self.ondas[2], self.ondas[3]
        t1, t3 = _tamanho(o1), _tamanho(o3)
        base = float(o4["preco_fim"])
        s = 1 if _sobe(o1) else -1
        return {"invalidacao": base, "alvo_1": base + s * 0.618 * t1, "alvo_2": base + s * 1.0 * t1,
                "alvo_3": base + s * 0.618 * (t1 + t3)}

    def alvos_onda_c(self) -> Optional[Dict]:
        if len(self.ondas) < 2:
            return None
        a, b = self.ondas[0], self.ondas[1]
        ta = _tamanho(a)
        base = float(b["preco_fim"])
        s = 1 if _sobe(a) else -1
        return {"invalidacao": base, "alvo_1": base + s * 0.618 * ta, "alvo_2": base + s * 1.0 * ta,
                "alvo_3": base + s * 1.618 * ta}
