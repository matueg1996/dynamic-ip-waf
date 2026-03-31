from sqlalchemy import Column, String, DateTime, Boolean
from app.db.database import Base

class TablaIP(Base):
    __tablename__ = "ips"

    id = Column(String, primary_key=True)
    ip = Column(String)
    tipo = Column(String)
    ambiente = Column(String)
    contexto = Column(String)
    contexto_id = Column(String)
    expira_en = Column(DateTime, nullable=True)
    estado = Column(String)
    entidad = Column(String, nullable=True)
    es_permanente = Column(Boolean, default=False)