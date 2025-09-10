from core.conexoes.conexao_bybit import BybitConnector

class ExecutorReal:
    def __init__(self, par, modo_execucao='simulador'):
        self.par = par.replace("/", "")
        self.modo_execucao = modo_execucao  # 'real' ou 'simulador'
        self.bybit = BybitConnector(modo_execucao=modo_execucao).exchange

    def executar_ordem(self, direcao, quantidade, preco_entrada=None, stop_loss=None, take_profit=None):
        assert direcao in ['buy', 'sell'], f'Direção inválida: {direcao}'
        tipo_ordem = 'limit' if preco_entrada else 'market'
        params = {}
        if tipo_ordem == 'limit':
            params['price'] = preco_entrada
            params['timeInForce'] = 'PostOnly'

        # Agora sempre envia, não importa se 'real' ou 'simulador'
        try:
            ordem = self.bybit.create_order(
                symbol=self.par,
                type=tipo_ordem,
                side=direcao,
                amount=quantidade,
                params=params
            )
            print("✅ Ordem executada:", ordem)
        except Exception as e:
            print("❌ Erro ao executar ordem:", e)
            return

        # STOP LOSS
        if stop_loss:
            try:
                sl = self.bybit.create_order(
                    symbol=self.par,
                    type='stop_market',
                    side='sell' if direcao == 'buy' else 'buy',
                    amount=quantidade,
                    params={'stopPrice': stop_loss}
                )
                print("✅ SL ativado:", sl)
            except Exception as e:
                print("❌ Erro no SL:", e)

        # TAKE PROFIT
        if take_profit:
            try:
                tp = self.bybit.create_order(
                    symbol=self.par,
                    type='take_profit_market',
                    side='sell' if direcao == 'buy' else 'buy',
                    amount=quantidade,
                    params={'stopPrice': take_profit}
                )
                print("✅ TP ativado:", tp)
            except Exception as e:
                print("❌ Erro no TP:", e)
