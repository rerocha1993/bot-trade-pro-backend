from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime

class OndaSchema(BaseModel):
    numero_onda: int
    tipo_onda: str
    data_inicio: datetime
    data_fim: datetime
    preco_inicio: float
    preco_fim: float
    proporcao_fibonacci: Optional[float]
    validada: Optional[bool] = False
    score_confianca: Optional[float]

class ContagemCandidataSchema(BaseModel):
    id: Optional[int]
    par: str
    timeframe: str
    ondas_detectadas: List[OndaSchema]
    score_confianca: float
    data_inicio: datetime
    data_fim: datetime
    nivel_ciclo: str
    status: str
    timestamp: Optional[datetime]

class ContagemValidadaSchema(ContagemCandidataSchema):
    pass

class RevisaoSchema(BaseModel):
    contagem_id: int
    tipo_revisao: str
    motivo: str
    dados_anteriores: Optional[Any]
    dados_corrigidos: Optional[Any]
    timestamp: Optional[datetime]
