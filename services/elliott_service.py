from core.elliott import ElliottEngine
from core.conexoes.conexao_bybit import BybitConnector
from core.spot_candles_fetcher import SpotCandlesFetcher
from models.elliott_revisao import ElliottRevisao
from models.elliott_contagem_candidata import ElliottContagemCandidata
from models.elliott_onda import ElliottOnda
from models.elliott_revisao import ElliottRevisao
from models.elliott_contagem_validada import ElliottContagemValidada
from models.elliott_onda import ElliottOnda

class ElliottService:
    """
    Serviço para orquestrar análise multi-timeframe, promover candidatas validadas, revisar contagens, e expor para API/Front.
    """
    def __init__(self, session):
        self.session = session

    def analisar_multi_timeframe(self, par, timeframes, candles_dict):
        for nivel, timeframe in enumerate(timeframes):
            candles = candles_dict[timeframe]
            engine = ElliottEngine(self.session, par, timeframe, candles, nivel_ciclo=nivel)
            engine.detectar_todas_contagens()
            engine.persistir_candidatas()
            # Expanda aqui para validação, promoção e revisão automática

    def promover_e_validar(self, id_candidata):
        """
        Busca candidata, valida institucionalmente, promove para validada, audita revisões.
        SEM lógica parcial, sempre registra revisão/rollback.
        """
        candidata = (
            self.session.query(ElliottContagemCandidata)
            .filter_by(id=id_candidata)
            .first()
        )
        if not candidata:
            raise Exception(f"Contagem candidata {id_candidata} não encontrada")

        # Regra institucional: validar se todos os requisitos foram cumpridos
        # (ex: score mínimo, consistência das ondas, zonas institucionais, etc)
        score_ok = candidata.score_confianca >= 0.7
        ondas_ok = all(o['validada'] for o in candidata.ondas_detectadas)
        if not (score_ok and ondas_ok):
            # Auditoria de rejeição
            revisao = ElliottRevisao(
                contagem_id=candidata.id,
                tipo_revisao="rejeicao_promocao",
                motivo="Score ou ondas insuficientes para promoção",
                dados_anteriores=candidata.ondas_detectadas,
                dados_corrigidos=None
            )
            self.session.add(revisao)
            self.session.commit()
            raise Exception("Candidata não atende aos requisitos de promoção institucional")

        # Promove para validada
        validada = ElliottContagemValidada(
            par=candidata.par,
            timeframe=candidata.timeframe,
            ondas_detectadas=candidata.ondas_detectadas,
            score_confianca=candidata.score_confianca,
            data_inicio=candidata.data_inicio,
            data_fim=candidata.data_fim,
            nivel_ciclo=candidata.nivel_ciclo,
            status="validada"
        )
        self.session.add(validada)
        self.session.commit()

        # Persiste as ondas da contagem validada
        for idx, onda in enumerate(candidata.ondas_detectadas):
            onda_db = ElliottOnda(
                contagem_id=validada.id,
                numero_onda=onda['numero_onda'],
                tipo_onda=onda['tipo_onda'],
                data_inicio=onda['data_inicio'],
                data_fim=onda['data_fim'],
                preco_inicio=onda['preco_inicio'],
                preco_fim=onda['preco_fim'],
                proporcao_fibonacci=onda.get('proporcao_fibonacci'),
                validada=True,
                score_confianca=onda.get('score_confianca', candidata.score_confianca),
                timestamp_registro=onda.get('timestamp_registro')
            )
            self.session.add(onda_db)
        self.session.commit()

        # Registrar auditoria de promoção
        revisao = ElliottRevisao(
            contagem_id=candidata.id,
            tipo_revisao="promocao_validada",
            motivo="Promoção institucional automática após validação",
            dados_anteriores=candidata.ondas_detectadas,
            dados_corrigidos=validada.ondas_detectadas
        )
        self.session.add(revisao)
        self.session.commit()

        return validada.id

    def revisar_rollback(self, id_contagem, motivo):
        """
        Audita uma revisão/rollback de contagem.
        Salva dados antigos, corrige estrutura, NUNCA só descarta.
        """
        contagem = (
            self.session.query(ElliottContagemValidada)
            .filter_by(id=id_contagem)
            .first()
        )
        if not contagem:
            raise Exception(f"Contagem validada {id_contagem} não encontrada para revisão")

        # Registrar revisão/rollback
        revisao = ElliottRevisao(
            contagem_id=contagem.id,
            tipo_revisao="rollback",
            motivo=motivo,
            dados_anteriores=contagem.ondas_detectadas,
            dados_corrigidos=None  # Preencher quando corrigido manualmente
        )
        self.session.add(revisao)
        self.session.commit()

        # Corrigir estrutura institucional (exemplo: marcar como rollback, atualizar status, remover flag de ativa)
        contagem.status = "rollback"
        self.session.commit()
        # Pode adicionar lógica para recalcular/corrigir ondas aqui, se necessário

        return True

    def consultar_estruturas_atuais(self, par, timeframe):
        """
        Consulta do ponto de ciclo validado atual (estrutura institucional) para API ou visualização.
        """
        contagem = (
            self.session.query(ElliottContagemValidada)
            .filter_by(par=par, timeframe=timeframe)
            .order_by(ElliottContagemValidada.data_fim.desc())
            .first()
        )
        if not contagem:
            return None

        ondas = (
            self.session.query(ElliottOnda)
            .filter_by(contagem_id=contagem.id)
            .order_by(ElliottOnda.numero_onda.asc())
            .all()
        )

        estrutura = {
            "contagem_id": contagem.id,
            "par": contagem.par,
            "timeframe": contagem.timeframe,
            "data_inicio": contagem.data_inicio,
            "data_fim": contagem.data_fim,
            "nivel_ciclo": contagem.nivel_ciclo,
            "score_confianca": contagem.score_confianca,
            "status": contagem.status,
            "ondas": [
                {
                    "numero_onda": o.numero_onda,
                    "tipo_onda": o.tipo_onda,
                    "data_inicio": o.data_inicio,
                    "data_fim": o.data_fim,
                    "preco_inicio": o.preco_inicio,
                    "preco_fim": o.preco_fim,
                    "proporcao_fibonacci": o.proporcao_fibonacci,
                    "validada": o.validada,
                    "score_confianca": o.score_confianca,
                    "timestamp_registro": o.timestamp_registro,
                }
                for o in ondas
            ]
        }
        return estrutura

    def definir_fase(self, par, timeframe):
        """
        Retorna a fase técnica da onda institucional do ativo/timeframe.
        Ex: 'inicio_onda_3', 'meio_onda_3', 'onda_5', 'correcao_a', 'consolidacao', etc.
        """
        # Busca a última contagem validada para o par/timeframe
        contagem = self.get_ultima_contagem_validada(par, timeframe)
        if not contagem or not contagem.ondas:
            return 'indefinido'

        ondas = contagem.ondas  # Supondo que ondas seja uma lista de dicionários ou objetos com numero, tipo, data/preco

        # Exemplo institucional: identificar se estamos na onda 3, 4, 5, A, B, C etc.
        ultimo_pivot = ondas[-1]
        # Você pode sofisticar com critérios temporais, preço atual, percentual da onda etc.
        # Exemplo de retorno profissional:
        if ultimo_pivot['tipo_onda'] == 'impulsiva' and ultimo_pivot['numero_onda'] == 3:
            # Checa se já está no início, meio ou fim da onda 3
            if self.esta_no_inicio_onda(ultimo_pivot):
                return 'inicio_onda_3'
            elif self.esta_no_meio_onda(ultimo_pivot):
                return 'meio_onda_3'
            else:
                return 'final_onda_3'
        elif ultimo_pivot['tipo_onda'] == 'impulsiva' and ultimo_pivot['numero_onda'] == 5:
            return 'onda_5'
        elif ultimo_pivot['tipo_onda'] == 'corretiva':
            if ultimo_pivot['numero_onda'] == 'A':
                return 'correcao_a'
            elif ultimo_pivot['numero_onda'] == 'B':
                return 'correcao_b'
            elif ultimo_pivot['numero_onda'] == 'C':
                return 'correcao_c'
        elif ultimo_pivot['tipo_onda'] == 'triangulo':
            return 'consolidacao'
        # Adicione mais lógica conforme todos os padrões do Elliott PRO
        else:
            return 'indefinido'

    def get_ultima_contagem_validada(self, par, timeframe):
        """
        Busca a última contagem validada institucional no banco (método profissional real).
        """
        contagem = (
            self.session.query(ElliottContagemValidada)
            .filter_by(par=par, timeframe=timeframe)
            .order_by(ElliottContagemValidada.data_fim.desc())
            .first()
        )
        return contagem

    def esta_no_inicio_onda(self, onda):
        # Implementação profissional (ex: percentual de tempo/preço decorrido)
        # Critério: preço atual perto do início, pouca variação
        preco_atual = self.get_preco_atual(onda['par'])  # Implemente busca do preço real
        dist = abs(preco_atual - onda['preco_inicio'])
        range_onda = abs(onda['preco_fim'] - onda['preco_inicio'])
        return dist < 0.15 * range_onda  # 15% do range, por exemplo

    def esta_no_meio_onda(self, onda):
        preco_atual = self.get_preco_atual(onda['par'])
        dist_inicio = abs(preco_atual - onda['preco_inicio'])
        dist_fim = abs(preco_atual - onda['preco_fim'])
        range_onda = abs(onda['preco_fim'] - onda['preco_inicio'])
        return dist_inicio > 0.15 * range_onda and dist_fim > 0.15 * range_onda

    def get_preco_atual(self, par):
        """
        Busca profissional do preço atual via conector Bybit institucional.
        """
        con = BybitConnector(modo_execucao="real")  # ou use seu padrão de ambiente
        preco = con.obter_preco_atual(par)
        if preco is None:
            raise Exception(f"Não foi possível obter o preço atual para {par}")
        return preco
    
    def get_ondas_validadas(self, par, timeframe):
        """
        Retorna a lista de ondas validadas (como dicionários) da última contagem validada para o par/timeframe.
        """
        contagem = self.get_ultima_contagem_validada(par, timeframe)
        if not contagem:
            return []
        ondas = (
            self.session.query(ElliottOnda)
            .filter_by(contagem_id=contagem.id)
            .order_by(ElliottOnda.numero_onda.asc())
            .all()
        )
        # Converte cada onda para dict, igual ao formato esperado pelo FibonacciElliott
        ondas_dict = []
        for o in ondas:
            ondas_dict.append({
                "numero_onda": o.numero_onda,
                "tipo_onda": o.tipo_onda,
                "data_inicio": o.data_inicio,
                "data_fim": o.data_fim,
                "preco_inicio": o.preco_inicio,
                "preco_fim": o.preco_fim,
                "proporcao_fibonacci": o.proporcao_fibonacci,
                "validada": o.validada,
                "score_confianca": o.score_confianca,
                "timestamp_registro": o.timestamp_registro,
            })
        return ondas_dict
    
    def buscar_ondas_validadas(self, par, timeframe, data_inicio, data_fim):
        """
        Busca TODAS as ondas validadas de um par/timeframe dentro de um intervalo (para parent/child).
        """
        contagens = (
            self.session.query(ElliottContagemValidada)
            .filter_by(par=par, timeframe=timeframe, status="validada")
            .filter(ElliottContagemValidada.data_fim >= data_inicio)
            .filter(ElliottContagemValidada.data_inicio <= data_fim)
            .all()
        )
        result = []
        for c in contagens:
            ondas = (
                self.session.query(ElliottOnda)
                .filter_by(contagem_id=c.id)
                .order_by(ElliottOnda.numero_onda.asc())
                .all()
            )
            for o in ondas:
                result.append({
                    "id": o.id,
                    "tipo": o.tipo_onda,
                    "numero": o.numero_onda,
                    "timestamp_inicio": o.data_inicio,
                    "timestamp_fim": o.data_fim,
                    "preco_inicio": o.preco_inicio,
                    "preco_fim": o.preco_fim,
                    "nivel": c.nivel_ciclo,
                    "parent_id": o.parent_id
                })
        return result

    def buscar_candles_spot(self, par, timeframe, t0, t1):
        """
        Busca candles reais (SPOT) via SpotCandlesFetcher só dentro do intervalo [t0, t1].
        """
        fetcher = SpotCandlesFetcher(exchange_id="bybit")
        from datetime import datetime
        dt0 = datetime.utcfromtimestamp(t0 / 1000)
        dt1 = datetime.utcfromtimestamp(t1 / 1000)
        return fetcher.fetch_all_candles(par, timeframe, dt0, dt1)

    def existe_contagem(self, par, timeframe, contagem, parent_id=None):
        """
        Checa se já existe uma contagem com o mesmo hash/estrutura e parent_id (NÃO duplica nunca!).
        """
        query = self.session.query(ElliottContagemCandidata).filter_by(
            par=par,
            timeframe=timeframe,
            hash=contagem['hash'],
        )
        if parent_id:
            query = query.filter_by(parent_id=parent_id)
        return self.session.query(query.exists()).scalar()

    def salvar_contagem_candidata(
        self,
        par: str,
        timeframe: str,
        contagem: dict,
        parent_id: int = None
    ) -> ElliottContagemCandidata:
        """
        Persiste uma nova contagem candidata institucional no banco,
        com suporte completo a hierarquia multi-timeframe (parent_id).
        
        Parâmetros:
            par (str): Par SPOT institucional, ex: "BTCUSDT"
            timeframe (str): Timeframe institucional, ex: "1D"
            contagem (dict): Estrutura com todos os dados da contagem (hash, score_confianca, estrutura, datas, etc)
            parent_id (int, opcional): ID da contagem candidata macro (parent) caso exista (para hierarquia multi-timeframe)

        Retorna:
            ElliottContagemCandidata: objeto persistido no banco, com id gerado.
        """
        nova = ElliottContagemCandidata(
            par=par,
            timeframe=timeframe,
            hash=contagem['hash'],
            score_confianca=contagem['score_confianca'],
            status="candidata",
            parent_id=parent_id,
            estrutura=contagem['estrutura'],
            data_inicio=contagem['data_inicio'],
            data_fim=contagem['data_fim'],
            nivel_ciclo=contagem.get('nivel_ciclo'),
            metadados=contagem.get('metadados', {})
        )
        self.session.add(nova)
        self.session.commit()
        contagem['id'] = nova.id  # Atualiza dict para uso em promoções
        return nova


    def salvar_onda(self, par, timeframe, onda, contagem_id, parent_id=None):
        """
        Salva onda vinculada à contagem (parent/child para multi-timeframe)
        """
        nova = ElliottOnda(
            par=par,
            timeframe=timeframe,
            contagem_id=contagem_id,
            parent_id=parent_id,
            tipo_onda=onda['tipo_onda'],
            numero_onda=onda['numero_onda'],
            data_inicio=onda['data_inicio'],
            data_fim=onda['data_fim'],
            preco_inicio=onda['preco_inicio'],
            preco_fim=onda['preco_fim'],
            nivel=onda.get('nivel', None),
            metadados=onda.get('metadados', {})
        )
        self.session.add(nova)
        self.session.commit()
        onda['id'] = nova.id
        return nova
    
    def validar_hierarquia(self, par=None):
        """
        Valida a hierarquia das contagens candidatas e validadas.
        Garante que cada micro (filha) tem parent_id válido e não há órfãos.
        Retorna lista de inconsistências.
        """
        inconsistencias = []

        # Todas as contagens com parent_id (filhas)
        contagens_filhas = self.session.query(ElliottContagemCandidata).filter(ElliottContagemCandidata.parent_id.isnot(None))
        if par:
            contagens_filhas = contagens_filhas.filter_by(par=par)
        contagens_filhas = contagens_filhas.all()

        # Checa se parent existe de verdade
        for filha in contagens_filhas:
            parent = self.session.query(ElliottContagemCandidata).filter_by(id=filha.parent_id).first()
            if not parent:
                inconsistencias.append(f"Filha {filha.id} aponta para parent_id {filha.parent_id} inexistente.")

        # Busca por órfãos (contagens sem parent_id E sem filhos, fora do maior timeframe)
        all_parents = set([c.parent_id for c in contagens_filhas if c.parent_id])
        all_ids = set([c.id for c in contagens_filhas])
        orfaos = self.session.query(ElliottContagemCandidata).filter(ElliottContagemCandidata.parent_id.is_(None))
        if par:
            orfaos = orfaos.filter_by(par=par)
        orfaos = orfaos.all()
        for orf in orfaos:
            tem_filho = self.session.query(ElliottContagemCandidata).filter_by(parent_id=orf.id).first()
            if not tem_filho:
                inconsistencias.append(f"Órfão encontrado: {orf.id} ({orf.par}/{orf.timeframe}) sem parent_id e sem filhos.")

        # Gera relatório/log (exemplo: só printa, mas pode salvar em tabela de log)
        if inconsistencias:
            print("Inconsistências de hierarquia encontradas:")
            for i in inconsistencias:
                print("-", i)
        else:
            print("Nenhuma inconsistência de hierarquia encontrada.")
        return inconsistencias
    
    def buscar_parent_institucional(self, par, macro_timeframe, micro_data_inicio):
        """
        Busca o ciclo macro vigente para a data de início da contagem micro.
        Permite vincular parent_id corretamente mesmo com ciclo macro em aberto.
        """
        parent = (
            self.session.query(ElliottContagemCandidata)
            .filter(
                ElliottContagemCandidata.par == par,
                ElliottContagemCandidata.timeframe == macro_timeframe,
                ElliottContagemCandidata.data_inicio <= micro_data_inicio,
                ElliottContagemCandidata.data_fim >= micro_data_inicio  # Engloba a micro
            )
            .order_by(ElliottContagemCandidata.data_inicio.desc())
            .first()
        )
        return parent


