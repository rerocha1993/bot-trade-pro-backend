# services/elliott_service.py
"""
Serviço de Elliott: análise em memória (fonte da verdade para o bot) + persistência/auditoria
no banco (contagens candidatas -> validadas -> revisões) para histórico e painel.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from core.elliott import ElliottEngine
from core.elliott_pro.multidegree import AnaliseMultiGrau, analisar_serie
from models.elliott_contagem_candidata import ElliottContagemCandidata
from models.elliott_contagem_validada import ElliottContagemValidada
from models.elliott_onda import ElliottOnda
from models.elliott_revisao import ElliottRevisao


class ElliottService:
    def __init__(self, session=None, connector=None):
        self.session = session
        self.connector = connector

    # ------------------------------------------------------------ análise
    def _con(self):
        if self.connector is None:
            from core.conexoes.conexao_bybit import BybitConnector
            self.connector = BybitConnector("simulador")
        return self.connector

    def analisar(self, par: str, timeframe: str, ohlcv: Optional[List] = None, fator_atr: float = 2.0, limite: int = 300) -> Dict:
        """Cenários de Elliott para par/timeframe (em memória)."""
        dados = ohlcv or self._con().obter_ohlcv(par, timeframe, limite, somente_fechados=True)
        res = analisar_serie(dados, fator_atr)
        res["par"], res["timeframe"] = par, timeframe
        return res

    def analisar_multi_grau(self, par: str, estilo_trade: str, timeframe: str, perfil: str = "conservador") -> Dict:
        con = self._con()
        an = AnaliseMultiGrau(lambda tf, n: con.obter_ohlcv(par, tf, n, somente_fechados=True), par, estilo_trade, timeframe, perfil)
        return an.analisar()

    def definir_fase(self, par: str, timeframe: str, ohlcv: Optional[List] = None) -> str:
        return self.analisar(par, timeframe, ohlcv).get("fase", "indefinido")

    def get_preco_atual(self, par: str) -> float:
        return self._con().obter_preco_atual(par)

    # -------------------------------------------------------- persistência
    def analisar_multi_timeframe(self, par: str, timeframes: List[str], candles_dict: Dict[str, List]) -> Dict[str, int]:
        """Varredura histórica: salva contagens candidatas por timeframe."""
        salvos = {}
        for tf in timeframes:
            engine = ElliottEngine(self.session, par, tf, candles_dict[tf], nivel_ciclo=tf)
            engine.detectar_todas_contagens()
            salvos[tf] = engine.persistir_candidatas()
        return salvos

    def promover_e_validar(self, id_candidata: int, score_minimo: float = 0.7) -> int:
        cand = self.session.query(ElliottContagemCandidata).filter_by(id=id_candidata).first()
        if not cand:
            raise ValueError(f"Contagem candidata {id_candidata} não encontrada")
        ondas = cand.ondas_detectadas or []
        ok = (cand.score_confianca or 0) >= score_minimo and ondas and all(o.get("validada", True) for o in ondas)
        if not ok:
            self.session.add(ElliottRevisao(contagem_id=cand.id, tipo_revisao="rejeicao_promocao",
                                            motivo="Score ou ondas insuficientes", dados_anteriores=ondas))
            cand.status = "descartada"
            self.session.commit()
            raise ValueError("Candidata não atende aos requisitos de promoção")
        validada = ElliottContagemValidada(par=cand.par, timeframe=cand.timeframe, ondas_detectadas=ondas,
                                           score_confianca=cand.score_confianca, data_inicio=cand.data_inicio,
                                           data_fim=cand.data_fim, nivel_ciclo=cand.nivel_ciclo, status="validada")
        self.session.add(validada)
        self.session.flush()
        for o in ondas:
            self.session.add(ElliottOnda(
                contagem_id=validada.id, numero_onda=o["numero_onda"], tipo_onda=o["tipo_onda"],
                data_inicio=datetime.fromisoformat(o["data_inicio"]), data_fim=datetime.fromisoformat(o["data_fim"]),
                preco_inicio=o["preco_inicio"], preco_fim=o["preco_fim"], proporcao_fibonacci=o.get("proporcao_fibonacci"),
                validada=True, score_confianca=o.get("score_confianca", cand.score_confianca)))
        cand.status = "promovida"
        self.session.add(ElliottRevisao(contagem_id=cand.id, tipo_revisao="promocao_validada",
                                        motivo="Promoção automática após validação", dados_anteriores=ondas, dados_corrigidos=ondas))
        self.session.commit()
        return validada.id

    def promover_candidatas(self, par: str, timeframe: str, score_minimo: float = 0.7) -> int:
        n = 0
        for cand in self.session.query(ElliottContagemCandidata).filter_by(par=par, timeframe=timeframe, status="candidata").all():
            try:
                self.promover_e_validar(cand.id, score_minimo)
                n += 1
            except ValueError:
                continue
        return n

    def revisar_rollback(self, id_contagem: int, motivo: str) -> bool:
        contagem = self.session.query(ElliottContagemValidada).filter_by(id=id_contagem).first()
        if not contagem:
            raise ValueError(f"Contagem validada {id_contagem} não encontrada")
        self.session.add(ElliottRevisao(contagem_id=contagem.id, tipo_revisao="rollback", motivo=motivo,
                                        dados_anteriores=contagem.ondas_detectadas))
        contagem.status = "rollback"
        self.session.commit()
        return True

    def consultar_estruturas_atuais(self, par: str, timeframe: str) -> Optional[Dict]:
        contagem = self.get_ultima_contagem_validada(par, timeframe)
        if not contagem:
            return None
        return {"contagem_id": contagem.id, "par": contagem.par, "timeframe": contagem.timeframe,
                "data_inicio": contagem.data_inicio, "data_fim": contagem.data_fim, "nivel_ciclo": contagem.nivel_ciclo,
                "score_confianca": contagem.score_confianca, "status": contagem.status,
                "ondas": self.get_ondas_validadas(par, timeframe)}

    def get_ultima_contagem_validada(self, par: str, timeframe: str):
        return (self.session.query(ElliottContagemValidada).filter_by(par=par, timeframe=timeframe, status="validada")
                .order_by(ElliottContagemValidada.data_fim.desc()).first())

    def get_ondas_validadas(self, par: str, timeframe: str) -> List[Dict]:
        contagem = self.get_ultima_contagem_validada(par, timeframe)
        if not contagem:
            return []
        ondas = self.session.query(ElliottOnda).filter_by(contagem_id=contagem.id).order_by(ElliottOnda.numero_onda.asc()).all()
        return [{"numero_onda": o.numero_onda, "tipo_onda": o.tipo_onda, "data_inicio": o.data_inicio, "data_fim": o.data_fim,
                 "preco_inicio": o.preco_inicio, "preco_fim": o.preco_fim, "proporcao_fibonacci": o.proporcao_fibonacci,
                 "validada": o.validada, "score_confianca": o.score_confianca, "timestamp_registro": o.timestamp_registro}
                for o in ondas]

    def buscar_ondas_validadas(self, par, timeframe, data_inicio, data_fim) -> List[Dict]:
        contagens = (self.session.query(ElliottContagemValidada).filter_by(par=par, timeframe=timeframe, status="validada")
                     .filter(ElliottContagemValidada.data_fim >= data_inicio, ElliottContagemValidada.data_inicio <= data_fim).all())
        out = []
        for c in contagens:
            for o in self.session.query(ElliottOnda).filter_by(contagem_id=c.id).order_by(ElliottOnda.numero_onda.asc()).all():
                out.append({"id": o.id, "tipo": o.tipo_onda, "numero": o.numero_onda, "timestamp_inicio": o.data_inicio,
                            "timestamp_fim": o.data_fim, "preco_inicio": o.preco_inicio, "preco_fim": o.preco_fim,
                            "nivel": c.nivel_ciclo, "contagem_id": c.id})
        return out

    def validar_hierarquia(self, par: Optional[str] = None) -> List[str]:
        q = self.session.query(ElliottContagemCandidata).filter(ElliottContagemCandidata.parent_id.isnot(None))
        if par:
            q = q.filter_by(par=par)
        problemas = []
        for filha in q.all():
            if not self.session.query(ElliottContagemCandidata).filter_by(id=filha.parent_id).first():
                problemas.append(f"Filha {filha.id} aponta para parent_id {filha.parent_id} inexistente.")
        return problemas
