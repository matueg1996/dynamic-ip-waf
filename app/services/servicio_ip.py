"""
Servicio de gestión de IPs.
Contiene la lógica para crear, aprobar, obtener y revocar IPs en la base de datos.
"""
import uuid
from app.db.database import SessionLocal
from app.db.esquemas import TablaIP

def crear_ip(data):
    db = SessionLocal()

    registro = TablaIP(
        id=str(uuid.uuid4()),
        **data
    )

    db.add(registro)
    db.commit()
    db.refresh(registro)
    db.close()

    return registro


def aprobar_ip(ip, ambiente):
    db = SessionLocal()

    registro = db.query(TablaIP).filter_by(
        ip=ip,
        ambiente=ambiente,
        estado="pendiente"
    ).first()

    if registro:
        registro.estado = "activa"
        db.commit()

    db.close()
    return registro


def obtener_ips_activas():
    db = SessionLocal()
    registros = db.query(TablaIP).filter_by(estado="activa").all()
    db.close()
    return registros


def revocar_ip(ip, ambiente):
    db = SessionLocal()
    
    registro = db.query(TablaIP).filter_by(
        ip=ip,
        ambiente=ambiente,
        estado="activa"
    ).first()

    if registro:
        registro.estado = "expirada"
        db.commit()

    db.close()
    return registro