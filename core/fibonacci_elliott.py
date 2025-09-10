class FibonacciElliott:
    """
    Calculadora institucional de proporções de Fibonacci para TODOS padrões Elliott:
    - Ondas 1-5
    - ABC
    - Flats (regular, expanded, running)
    - Triângulos (ABCDE)
    - Diagonais
    - WXY / WXYXZ (combinações complexas)
    """

    def __init__(self, ondas):
        """
        ondas: lista de dicts [{'numero': int, 'preco_inicio': float, 'preco_fim': float}, ...]
        """
        self.ondas = ondas

    # ===== IMPULSIVAS 1-5 =====

    def validar_onda2(self):
        if len(self.ondas) < 2:
            return None
        o1, o2 = self.ondas[0], self.ondas[1]
        tamanho_o1 = abs(o1['preco_fim'] - o1['preco_inicio'])
        retracao = abs(o2['preco_fim'] - o2['preco_inicio']) / tamanho_o1 if tamanho_o1 else None
        return retracao is not None and 0.5 <= retracao <= 0.618

    def validar_onda3(self):
        if len(self.ondas) < 3:
            return None
        o1, o3 = self.ondas[0], self.ondas[2]
        tamanho_o1 = abs(o1['preco_fim'] - o1['preco_inicio'])
        tamanho_o3 = abs(o3['preco_fim'] - o3['preco_inicio'])
        return tamanho_o1 > 0 and tamanho_o3 >= 1.618 * tamanho_o1

    def validar_onda4(self):
        if len(self.ondas) < 4:
            return None
        o1, o3, o4 = self.ondas[0], self.ondas[2], self.ondas[3]
        tamanho_o3 = abs(o3['preco_fim'] - o3['preco_inicio'])
        if tamanho_o3 == 0:
            return None
        retracao = abs(o4['preco_fim'] - o4['preco_inicio']) / tamanho_o3
        invade = (o4['preco_inicio'] < o1['preco_inicio']) or (o4['preco_fim'] < o1['preco_inicio'])
        return (0.236 <= retracao <= 0.382) and not invade

    def validar_onda5(self):
        if len(self.ondas) < 5:
            return None
        o1, o5 = self.ondas[0], self.ondas[4]
        tamanho_o1 = abs(o1['preco_fim'] - o1['preco_inicio'])
        tamanho_o5 = abs(o5['preco_fim'] - o5['preco_inicio'])
        return tamanho_o1 > 0 and tamanho_o5 >= tamanho_o1

    # ===== ABC CLÁSSICO =====

    def validar_abc(self):
        if len(self.ondas) < 3:
            return None
        a, b, c = self.ondas[0], self.ondas[1], self.ondas[2]
        tamanho_a = abs(a['preco_fim'] - a['preco_inicio'])
        tamanho_b = abs(b['preco_fim'] - b['preco_inicio'])
        tamanho_c = abs(c['preco_fim'] - c['preco_inicio'])
        if tamanho_a == 0:
            return None
        return (0.5 <= tamanho_b / tamanho_a <= 0.886) and (tamanho_c >= tamanho_a)

    # ===== FLATS =====

    def validar_flat_regular(self):
        if len(self.ondas) < 3:
            return None
        a, b, c = self.ondas[0], self.ondas[1], self.ondas[2]
        tamanho_a = abs(a['preco_fim'] - a['preco_inicio'])
        tamanho_b = abs(b['preco_fim'] - b['preco_inicio'])
        tamanho_c = abs(c['preco_fim'] - c['preco_inicio'])
        if tamanho_a == 0:
            return None
        return (0.9 <= tamanho_b / tamanho_a <= 1.1) and (0.9 <= tamanho_c / tamanho_a <= 1.1)

    def validar_flat_expanded(self):
        if len(self.ondas) < 3:
            return None
        a, b, c = self.ondas[0], self.ondas[1], self.ondas[2]
        tamanho_a = abs(a['preco_fim'] - a['preco_inicio'])
        tamanho_b = abs(b['preco_fim'] - b['preco_inicio'])
        tamanho_c = abs(c['preco_fim'] - c['preco_inicio'])
        if tamanho_a == 0:
            return None
        return (1.0 < tamanho_b / tamanho_a <= 1.38) and (tamanho_c / tamanho_a > 1.618)

    def validar_flat_running(self):
        if len(self.ondas) < 3:
            return None
        a, b, c = self.ondas[0], self.ondas[1], self.ondas[2]
        tamanho_a = abs(a['preco_fim'] - a['preco_inicio'])
        tamanho_b = abs(b['preco_fim'] - b['preco_inicio'])
        tamanho_c = abs(c['preco_fim'] - c['preco_inicio'])
        if tamanho_a == 0:
            return None
        return (tamanho_b / tamanho_a > 1) and (tamanho_c / tamanho_a < 1)

    # ===== TRIÂNGULO ABCDE =====

    def validar_triangulo(self):
        if len(self.ondas) < 5:
            return None
        proporcoes = []
        for i in range(1, 5):
            anterior = abs(self.ondas[i-1]['preco_fim'] - self.ondas[i-1]['preco_inicio'])
            atual = abs(self.ondas[i]['preco_fim'] - self.ondas[i]['preco_inicio'])
            if anterior == 0:
                return None
            proporcoes.append(atual / anterior)
        # Normalmente cada perna é 0.5–0.886 da anterior
        return all(0.5 <= p <= 0.886 for p in proporcoes)

    # ===== DIAGONAIS (LEADING/ENDING) =====

    def validar_diagonal_leading(self):
        if len(self.ondas) < 5:
            return None
        o1, o2, o3, o4, o5 = self.ondas[:5]
        tamanho_o1 = abs(o1['preco_fim'] - o1['preco_inicio'])
        tamanho_o3 = abs(o3['preco_fim'] - o3['preco_inicio'])
        tamanho_o5 = abs(o5['preco_fim'] - o5['preco_inicio'])
        if tamanho_o1 == 0:
            return None
        return (tamanho_o3 > tamanho_o1) and (tamanho_o5 > tamanho_o1)

    def validar_diagonal_ending(self):
        if len(self.ondas) < 5:
            return None
        for i in range(1, 5):
            anterior = abs(self.ondas[i-1]['preco_fim'] - self.ondas[i-1]['preco_inicio'])
            atual = abs(self.ondas[i]['preco_fim'] - self.ondas[i]['preco_inicio'])
            if atual >= anterior:
                return False
        return True

    # ===== WXY, WXYXZ =====

    def validar_wxy(self):
        if len(self.ondas) < 3:
            return None
        w, x, y = self.ondas[0], self.ondas[1], self.ondas[2]
        tamanho_w = abs(w['preco_fim'] - w['preco_inicio'])
        tamanho_y = abs(y['preco_fim'] - y['preco_inicio'])
        if tamanho_w == 0:
            return None
        proporcao = tamanho_y / tamanho_w
        return 0.618 <= proporcao <= 1.618

    def validar_wxyxz(self):
        if len(self.ondas) < 5:
            return None
        w, x, y, x2, z = self.ondas[0], self.ondas[1], self.ondas[2], self.ondas[3], self.ondas[4]
        tamanho_w = abs(w['preco_fim'] - w['preco_inicio'])
        tamanho_z = abs(z['preco_fim'] - z['preco_inicio'])
        if tamanho_w == 0:
            return None
        proporcao = tamanho_z / tamanho_w
        return 0.618 <= proporcao <= 1.618

    # ===== SCORE INSTITUCIONAL =====

    def score_confianca(self):
        checks = [
            self.validar_onda2(),
            self.validar_onda3(),
            self.validar_onda4(),
            self.validar_onda5(),
            self.validar_abc(),
            self.validar_flat_regular(),
            self.validar_flat_expanded(),
            self.validar_flat_running(),
            self.validar_triangulo(),
            self.validar_diagonal_leading(),
            self.validar_diagonal_ending(),
            self.validar_wxy(),
            self.validar_wxyxz()
        ]
        # Só considera os checks que realmente puderam ser calculados
        validos = [v for v in checks if v is not None]
        if not validos:
            return 0.0
        passed = sum(1 for v in validos if v)
        return passed / len(validos)
