from core.elliott import ElliottDetector
from core.fibonacci import Fibonacci
from core.fibonacci_elliott import FibonacciElliott
from core.vwap import VWAPCalculator
from core.tpo import TPOProfile
from core.order_flow import OrderFlowAnalyzerPro
from core.conexoes.conexao_bybit import BybitConnector
from core.fibonacci_strategies import FibonacciStrategies
from core.volume_profile_pro import VolumeProfilePRO
from services.orderblock_institutional_service import OrderBlockInstitutionalService
from services.ponto_institucional_service import PontoInstitucionalService
from services.elliott_service import ElliottService
from api.database import SessionLocal
from core.fase_onda_rules import (
    indicadores_para_fase, get_tolerancia_preco, bloquear_zona_institucional
)

class StrategyEngine:
    def __init__(self, ohlcv, bot, db=None, trades=None, order_book=None):
        self.ohlcv = ohlcv
        self.bot = bot
        self.fib_strat = FibonacciStrategies(ohlcv)
        self.con = BybitConnector(modo_execucao=bot.modo_execucao)
        self.trades = trades
        self.order_book = order_book
        self.db = db
        self.elliott_service = ElliottService(self.db)
        self.orderblock_service = OrderBlockInstitutionalService()
        self.db_session = SessionLocal()

    def verificar_elliott(self):
        if not self.bot.usar_elliott:
            return {"acao": None}
        precos = [c[4] for c in self.ohlcv]
        det = ElliottDetector(precos)
        valido, estrutura = det.validar_estrutura_basica()
        if valido:
            acao = "buy" if len(estrutura["impulsivas"]) > len(estrutura["corretivas"]) else "sell"
        else:
            acao = "hold"
        return {"acao": acao}

    def validar_fibonacci(self, acao, contexto_onda=None):
        if not self.bot.usar_fibonacci:
            return {}
        if contexto_onda == 2:
            return self.fib_strat.retracao_onda2()
        elif contexto_onda == 4:
            return self.fib_strat.retracao_onda4()
        elif contexto_onda == 3:
            return self.fib_strat.extensao_onda3()
        elif contexto_onda == 5:
            return self.fib_strat.extensao_onda5()
        else:
            return self.fib_strat.generico()

    def verificar_vwap(self):
        if not self.bot.usar_vwap:
            return {"acao": None}
        vwap = VWAPCalculator(self.ohlcv).obter_vwap_atual()
        preco = self.ohlcv[-1][4]
        if preco > vwap:
            return {"acao":"buy"}
        if preco < vwap:
            return {"acao":"sell"}
        return {"acao":"hold"}

    def verificar_tpo(self):
        if not self.bot.usar_tpo:
            return {"acao": None}
        precos = [c[4] for c in self.ohlcv]
        tpo = TPOProfile(precos)
        preco_atual = precos[-1]
        sinal = tpo.sinal_estrategico(preco_atual)
        return sinal

    def verificar_orderflow(self):
        if not self.bot.usar_orderflow:
            return {"acao": None}
        order_book = self.order_book  # Já está vindo do executor, plugado do websocket/cached
        trades = self.trades          # Idem, já atualizado no loop
        result = OrderFlowAnalyzerPro(order_book, trades, self.ohlcv).analisar()
        return result

    def verificar_volume_profile(self):
        if not self.bot.usar_volume_profile:
            return {"acao": None}
        vp = VolumeProfilePRO(self.ohlcv, num_bins=40)  # ajuste granularidade se quiser
        preco_atual = self.ohlcv[-1][4]
        sinal = vp.price_signal(preco_atual)
        return sinal
    
    def calcular_tp_sl(self, elliot_acao, fase_onda, indicadores_habilitados):
        preco_atual = self.ohlcv[-1][4]
        perfil = getattr(self.bot, "confluencia_tipo", "conservador")
        tolerancia_pct = getattr(self.bot, "tolerancia_pct", 0.01)
        exchanges_permitidas = self.bot.exchange.split(',') if self.bot.exchange else ['bybit', 'coinbase']

        sugestoes = []

        # OrderBlock
        if 'OrderBlock' in indicadores_habilitados:
            bloco_tp = self.selecionar_bloco_tp_sl(
                session=self.db_session,
                par=self.bot.ativo,
                direcao='sell' if elliot_acao == 'buy' else 'buy',
                preco_atual=preco_atual,
                perfil=perfil,
                tolerancia_pct=tolerancia_pct,
                exchanges_permitidas=['bybit', 'coinbase']
            )
            bloco_sl = self.selecionar_bloco_tp_sl(
                session=self.db_session,
                par=self.bot.ativo,
                direcao='buy' if elliot_acao == 'buy' else 'sell',
                preco_atual=preco_atual,
                perfil=perfil,
                tolerancia_pct=tolerancia_pct,
                exchanges_permitidas=['bybit', 'coinbase']
            )
            if bloco_tp:
                sugestoes.append({'tp': bloco_tp.preco, 'fonte_tp': 'orderblock'})
                self.orderblock_service.registrar_uso_bloco(
                    session=self.db_session, 
                    bloco_id=bloco_tp.id, 
                    tipo_uso='tp', 
                    bot_id=self.bot.id, 
                    decisao_id=None
                )
            if bloco_sl:
                sugestoes.append({'sl': bloco_sl.preco, 'fonte_sl': 'orderblock'})

        # TPO
        if 'TPO' in indicadores_habilitados:
           # Configuração profissional do range e granularidade
            perfil = getattr(self.bot, "estilo_trade", "default")
            if perfil == "scalping":
                prices = [c[4] for c in self.ohlcv[-50:]]  # só os 50 últimos candles
                bins = 10                                  # menos bins = mais sensível
                interval = 10.0                            # ajuste conforme volatilidade do ativo
                tolerancia = 0.01                          # tolerância mais apertada
            elif perfil == "daytrade":
                prices = [c[4] for c in self.ohlcv[-200:]]
                bins = 20
                interval = 50.0
                tolerancia = 0.02
            elif perfil == "swing":
                prices = [c[4] for c in self.ohlcv[-800:]]
                bins = 30
                interval = 100.0
                tolerancia = 0.03
            else:
                prices = [c[4] for c in self.ohlcv[-100:]]
                bins = 20
                interval = 50.0
                tolerancia = 0.02
            # Range_min/range_max podem vir de análise institucional, se desejar
            range_min, range_max = None, None

            tpo = TPOProfile(
                prices,
                interval=interval,
                tolerancia=tolerancia,     # Ou conforme config do perfil/bot
                range_min=range_min,
                range_max=range_max,
                bins=bins
            )
            zonas = tpo.analisar()
            tp = zonas.get("VAH")
            sl = zonas.get("VAL")
            fonte = 'tpo'

        # VWAP
        if 'VWAP' in indicadores_habilitados:
            vwap_calc = VWAPCalculator(self.ohlcv)
            vwap_result = vwap_calc.vwap_bandas()
            if vwap_result:
                tp_vwap = vwap_result['bandas'].get('+2σ', vwap_result['vwap'])
                sl_vwap = vwap_result['bandas'].get('-2σ', vwap_result['vwap'])
                sugestoes.append({'tp': tp_vwap, 'fonte_tp': 'vwap'})
                sugestoes.append({'sl': sl_vwap, 'fonte_sl': 'vwap'})

        # FibonacciElliott
        if 'Fibonacci' in indicadores_habilitados:
            ondas = self.elliott_service.get_ondas_validadas(self.bot.ativo, self.bot.timeframe)
            fib_elliott = FibonacciElliott(ondas)
            if fase_onda == "onda_2":
                fib_result = fib_elliott.validar_onda2()
            elif fase_onda == "onda_3":
                fib_result = fib_elliott.validar_onda3()
            elif fase_onda == "onda_4":
                fib_result = fib_elliott.validar_onda4()
            elif fase_onda == "onda_5":
                fib_result = fib_elliott.validar_onda5()
            else:
                fib_result = fib_elliott.validar_abc()
            if fib_result.get("tp"):
                sugestoes.append({'tp': fib_result["tp"], 'fonte_tp': 'fibonacci_elliott'})
            if fib_result.get("sl"):
                sugestoes.append({'sl': fib_result["sl"], 'fonte_sl': 'fibonacci_elliott'})

        tp_candidates = [(item['tp'], item.get('fonte_tp')) for item in sugestoes if 'tp' in item and item['tp'] is not None]
        sl_candidates = [(item['sl'], item.get('fonte_sl')) for item in sugestoes if 'sl' in item and item['sl'] is not None]
        tp_final, fonte_tp = None, None
        sl_final, fonte_sl = None, None

        # Lógica para perfil turbo/conservador (default = conservador)
        if elliot_acao == "buy":
            tp_above = [(v, f) for v, f in tp_candidates if v > preco_atual]
            sl_below = [(v, f) for v, f in sl_candidates if v < preco_atual]
            if tp_above:
                tp_final, fonte_tp = (max if perfil == 'turbo' else min)(tp_above, key=lambda x: x[0])
            if sl_below:
                sl_final, fonte_sl = (min if perfil == 'turbo' else max)(sl_below, key=lambda x: x[0])
        elif elliot_acao == "sell":
            tp_below = [(v, f) for v, f in tp_candidates if v < preco_atual]
            sl_above = [(v, f) for v, f in sl_candidates if v > preco_atual]
            if tp_below:
                tp_final, fonte_tp = (min if perfil == 'turbo' else max)(tp_below, key=lambda x: x[0])
            if sl_above:
                sl_final, fonte_sl = (max if perfil == 'turbo' else min)(sl_above, key=lambda x: x[0])

        fonte = f"tp:{fonte_tp}|sl:{fonte_sl}"
        return tp_final, sl_final, fonte

    def calcular_tpo(self, interval=50):
        """
        Calcula TP/SL institucional usando TPOProfile.
        :param interval: Número de candles a considerar (ajuste conforme perfil)
        :return: dict {'tp': valor, 'sl': valor, ...}
        """
        prices = [c[4] for c in self.ohlcv]  # Supondo [open, high, low, close, volume]
        tpo = TPOProfile(prices, interval=interval)
        res = tpo.analisar()
        # Exemplo institucional: TP na VAH, SL na VAL (ajuste conforme estratégia)
        return {
            'tp': res['VAH'],
            'sl': res['VAL'],
            'POC': res['POC'],
            'LVN': res['LVN'],
            'HVN': res['HVN'],
            'shape': res['shape'],
            'single_prints': res['single_prints']
        }

    def calcular_vwap(self, ultimos=50):
        """
        Calcula TP/SL institucional usando VWAPCalculator.
        :param ultimos: Número de candles a considerar (ajuste conforme perfil)
        :return: dict {'tp': valor, 'sl': valor, ...}
        """
        vwap_calc = VWAPCalculator(self.ohlcv[-ultimos:])
        res = vwap_calc.vwap_bandas()
        if not res:
            return {'tp': None, 'sl': None}
        vwap = res['vwap']
        bandas = res['bandas']
        # Exemplo institucional: TP na +2σ, SL na -2σ (ajuste conforme perfil)
        return {
            'tp': bandas.get('+2σ', vwap),
            'sl': bandas.get('-2σ', vwap),
            'vwap': vwap,
            'bandas': bandas
        }

    def decidir(self):
        # Atualiza status de blocos rompidos antes de qualquer decisão
        preco_atual = self.ohlcv[-1][4]
        OrderBlockInstitutionalService.atualizar_blocos_rompidos(
            self.db_session,
            self.bot.ativo,
            preco_atual
        )

        # 1. Elliott é a lei máxima: só opera se estrutura e direção forem válidas
        elliot_result = self.verificar_elliott()
        elliot_acao = elliot_result.get("acao")
        if elliot_acao not in ("buy", "sell"):
            return {
                "acao": "hold",
                "motivo": "Sem Elliott válido",
                "fase_onda": None,
                "votos": [],
                "indicadores_ativos": [],
                "tp": None,
                "sl": None
            }

        # 2. Descobre fase técnica da onda (Elliott PRO) e carrega regras contextuais institucionais
        fase_onda = self.elliott_service.definir_fase(self.bot.ativo, self.bot.timeframe)

        # 3. Calcula indicadores habilitados do banco/configuração
        indicadores_habilitados = []
        if self.bot.usar_vwap: indicadores_habilitados.append('VWAP')
        if self.bot.usar_fibonacci: indicadores_habilitados.append('Fibonacci')
        if self.bot.usar_tpo: indicadores_habilitados.append('TPO')
        if self.bot.usar_orderflow: indicadores_habilitados.append('OrderFlow')
        if self.bot.usar_volume_profile: indicadores_habilitados.append('VolumeProfile')
        if self.bot.usar_orderblock: indicadores_habilitados.append('OrderBlock')

        # 4. Filtro duplo: só ativar indicadores permitidos pela fase E habilitados pelo usuário
        indicadores_ativos = indicadores_para_fase(fase_onda, indicadores_habilitados)
        if not indicadores_ativos:
            return {
                "acao": "hold",
                "motivo": f"Fase {fase_onda}: Nenhum indicador ativo permitido para essa fase",
                "fase_onda": fase_onda,
                "votos": [],
                "indicadores_ativos": [],
                "tp": None,
                "sl": None
            }

        # 5. Executa análise real dos indicadores ativos (usando métodos já existentes)
        votos = 0
        total = 0
        confluentes = []
        funcoes_validacao = {
            'VWAP': self.verificar_vwap,
            'TPO': self.verificar_tpo,
            'OrderFlow': self.verificar_orderflow,
            'VolumeProfile': self.verificar_volume_profile,
            # Fibonacci e OrderBlock não entram como voto puro
        }
        for nome in indicadores_ativos:
            fn = funcoes_validacao.get(nome)
            if not fn:
                continue
            res = fn()
            ac = res.get("acao")
            if ac == elliot_acao:
                votos += 1
                confluentes.append(nome)
            if ac in ("buy", "sell"):
                total += 1

        # 6. Parametrização do modo: conservador/turbo
        modo = getattr(self.bot, "confluencia_tipo", "conservador").lower()
        if modo == "conservador":
            confluencia_ok = (votos == total) if total > 0 else True
        else:
            confluencia_ok = votos >= 1

        if not confluencia_ok:
            return {
                "acao": "hold",
                "motivo": f"Sem confluência com Elliott: {votos}/{total} ({confluentes}) [{modo}]",
                "fase_onda": fase_onda,
                "votos": confluentes,
                "indicadores_ativos": indicadores_ativos,
                "tp": None,
                "sl": None
            }

        # 7. Checagem de zonas institucionais (bloqueio ANTES de calcular TP/SL)
        from services.ponto_institucional_service import PontoInstitucionalService
        timeframes_institucionais = ["30m", "4h", "1d", "1w"]
        pontos = PontoInstitucionalService.obter_pontos_institucionais_ativos(
            self.db, self.bot.ativo, self.bot.exchange, timeframes_institucionais
        )
        tolerancia_preco = get_tolerancia_preco(fase_onda)
        raio = preco_atual * (tolerancia_preco or 0.002)
        bloqueio = []
        for p in pontos:
            if abs(float(p.preco) - preco_atual) <= raio:
                bloqueio.append({
                    "tipo": p.tipo,
                    "preco": float(p.preco),
                    "motivo": p.motivo,
                    "timeframe": p.tipo.split("_")[-1],
                })
        if fase_onda == "indefinido" or bloquear_zona_institucional(fase_onda) or bloqueio:
            return {
                "acao": "hold",
                "motivo": f"Bloqueado por zona institucional ou fase não permitida ({fase_onda}) | {bloqueio}",
                "fase_onda": fase_onda,
                "votos": confluentes,
                "indicadores_ativos": indicadores_ativos,
                "tp": None,
                "sl": None
            }

        # 8. Calcula TP/SL institucional (prioriza fase e só usa indicadores habilitados)
        tp, sl, tp_sl_usado = self.calcular_tp_sl(elliot_acao, fase_onda, indicadores_ativos)

        # 9. Blindagem institucional de TP/SL (garante sentido correto)
        if elliot_acao == "buy":
            if tp is not None and tp <= preco_atual:
                tp = None
            if sl is not None and sl >= preco_atual:
                sl = None
        elif elliot_acao == "sell":
            if tp is not None and tp >= preco_atual:
                tp = None
            if sl is not None and sl <= preco_atual:
                sl = None

        # 10. Retorna decisão profissional, 100% auditável
        return {
            "acao": elliot_acao,
            "motivo": f"Elliott + confluência ({votos}/{total}) {confluentes} [{modo}] | Fase: {fase_onda} | TP/SL via {tp_sl_usado}",
            "fase_onda": fase_onda,
            "votos": confluentes,
            "indicadores_ativos": indicadores_ativos,
            "tp": tp,
            "sl": sl
        }

    def obter_tp_sl_orderblock(self, session, par, direcao, preco_atual):
        """
        Seleciona o OrderBlock institucional mais relevante para o TP ou SL.
        """
        blocos = self.orderblock_service.consultar_blocos_ativos(session, par=par, direcao=direcao)
        if not blocos:
            return None, None, None  # Sem blocos institucionais ativos

        # Seleciona o bloco mais próximo do preço atual
        bloco_escolhido = min(
            blocos,
            key=lambda b: abs(b.preco - preco_atual)
        )
        tp_ou_sl = bloco_escolhido.preco
        volume = bloco_escolhido.volume
        origem = bloco_escolhido.exchange_origem
        return tp_ou_sl, volume, origem

    def atualizar_bloco_ao_romper(self, session, bloco_id):
        """
        Atualiza o bloco institucional para status 'rompido' após rompimento pelo preço.
        """
        self.orderblock_service.marcar_bloco_rompido(session, bloco_id)

    def selecionar_bloco_tp_sl(
        self, 
        session, 
        par: str, 
        direcao: str, 
        preco_atual: float, 
        perfil: str, 
        tolerancia_pct: float = 0.015,   # 1.5% do preço como exemplo
        volume_minimo: float = 0.0, 
        exchanges_permitidas: list = None
    ):
        """
        Seleciona o melhor bloco institucional para TP ou SL conforme perfil e estratégia.
        """
        blocos =  self.orderblock_service.consultar_blocos_ativos(session, par=par, direcao=direcao)
        if not blocos:
            return None

        # Filtra por exchange permitida, se aplicável
        if exchanges_permitidas:
            blocos = [b for b in blocos if b.exchange_origem in exchanges_permitidas]
        # Filtra por volume mínimo
        blocos = [b for b in blocos if b.volume >= volume_minimo]
        # Filtra por tolerância de distância ao preço atual
        blocos = [
            b for b in blocos 
            if abs(b.preco - preco_atual) / preco_atual <= tolerancia_pct
        ]

        if not blocos:
            return None

        # Estratégia por perfil
        if perfil == 'scalper':
            # Scalper: pega o bloco institucional mais próximo do preço atual
            bloco_escolhido = min(blocos, key=lambda b: abs(b.preco - preco_atual))
        elif perfil == 'swing':
            # Swing: prioriza bloco mais distante (alvo longo)
            bloco_escolhido = max(blocos, key=lambda b: abs(b.preco - preco_atual))
        elif perfil == 'institucional':
            # Institucional: prioriza o maior volume dentro da tolerância
            bloco_escolhido = max(blocos, key=lambda b: b.volume)
        else:  # Default (ex: daytrade)
            # Prioriza equilíbrio entre proximidade e volume (score simples)
            bloco_escolhido = max(
                blocos,
                key=lambda b: (b.volume / (abs(b.preco - preco_atual) + 1e-8))
            )
        return bloco_escolhido

