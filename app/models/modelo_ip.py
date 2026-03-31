from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class RegistroIP(BaseModel):
    ip: str
    tipo: str
    ambiente: str
    contexto: str
    contexto_id: str
    expira_en: Optional[datetime]
    estado: str = "pendiente"
    entidad: Optional[str] = None
    es_permanente: bool = False