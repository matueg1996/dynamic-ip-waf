from fastapi import APIRouter, Header, HTTPException
from datetime import datetime, timedelta
from app.services.servicio_ip import crear_ip, aprobar_ip, revocar_ip
from app.services.exportador_waf import exportar_listas

router = APIRouter()

API_KEY = "mi-api-key"

def validar_api_key(api_key: str):
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="No autorizado")


@router.post("/ip")
def agregar_ip(
    ip: str,
    tipo: str,
    ambiente: str,
    ttl_minutos: int = None,
    entidad: str = None,
    es_permanente: bool = False,
    x_api_key: str = Header(None)
):
    validar_api_key(x_api_key)

    expira_en = None
    if not es_permanente and ttl_minutos:
        expira_en = datetime.utcnow() + timedelta(minutes=ttl_minutos)

    registro = crear_ip({
        "ip": ip,
        "tipo": tipo,
        "ambiente": ambiente,
        "contexto": "manual",
        "contexto_id": "default",
        "expira_en": expira_en,
        "estado": "pendiente",
        "entidad": entidad,
        "es_permanente": es_permanente
    })

    return {"estado": "pendiente_aprobacion", "registro": registro}


@router.post("/aprobar")
def aprobar(ip: str, ambiente: str, x_api_key: str = Header(None)):
    validar_api_key(x_api_key)
    return aprobar_ip(ip, ambiente)


@router.get("/export")
def exportar(x_api_key: str = Header(None)):
    validar_api_key(x_api_key)
    return exportar_listas()


@router.delete("/ip/{ip}")
def revocar(ip: str, ambiente: str, x_api_key: str = Header(None)):
    validar_api_key(x_api_key)
    return revocar_ip(ip, ambiente)