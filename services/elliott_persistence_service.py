# services/elliott_persistence_service.py

from models.elliott_contagem_candidata import ElliottContagemCandidata
from models.elliott_contagem_validada import ElliottContagemValidada
from models.elliott_onda import ElliottOnda
from models.elliott_revisao import ElliottRevisao

class ElliottPersistenceService:
    def __init__(self, session):
        self.session = session

    def salvar_contagem_candidata(self, **kwargs):
        contagem = ElliottContagemCandidata(**kwargs)
        self.session.add(contagem)
        self.session.commit()
        return contagem.id

    def promover_contagem_para_validada(self, id_candidata):
        candidata = self.session.query(ElliottContagemCandidata).get(id_candidata)
        if not candidata:
            raise Exception("Candidata não encontrada")
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
        return validada.id

    def salvar_onda(self, **kwargs):
        onda = ElliottOnda(**kwargs)
        self.session.add(onda)
        self.session.commit()
        return onda.id

    def salvar_revisao(self, **kwargs):
        revisao = ElliottRevisao(**kwargs)
        self.session.add(revisao)
        self.session.commit()
        return revisao.id
    
    def salvar_contagem_micro_com_parent(
        self, par, micro_timeframe, macro_timeframe, contagem_micro
    ):
        """
        Salva a contagem micro (filha) já vinculando ao parent_id do macro vigente.
        """
        parent = self.buscar_parent_institucional(
            par,
            macro_timeframe,
            contagem_micro["data_inicio"],
        )
        parent_id = parent.id if parent else None

        nova = ElliottContagemCandidata(
            par=par,
            timeframe=micro_timeframe,
            hash=contagem_micro["hash"],
            score_confianca=contagem_micro["score_confianca"],
            status="candidata",
            parent_id=parent_id,
            estrutura=contagem_micro["estrutura"],
            data_inicio=contagem_micro["data_inicio"],
            data_fim=contagem_micro["data_fim"],
            nivel_ciclo=contagem_micro.get("nivel_ciclo"),
            metadados=contagem_micro.get("metadados", {}),
        )
        self.session.add(nova)
        self.session.commit()
        contagem_micro["id"] = nova.id
        return nova
