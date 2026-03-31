from fastapi import APIRouter, Request
from datetime import datetime, timedelta
from app.services.servicio_ip import crear_ip

slack_router = APIRouter()

@slack_router.post("/accion")
async def accion_slack(req: Request):
    payload = await req.json()

    ip = payload.get("ip")
    tipo = payload.get("tipo")
    ambiente = payload.get("ambiente")
    ttl = payload.get("ttl")
    entidad = payload.get("entidad")
    es_permanente = payload.get("es_permanente", False)

    expira_en = None
    if not es_permanente and ttl:
        expira_en = datetime.utcnow() + timedelta(minutes=int(ttl))

    crear_ip({
        "ip": ip,
        "tipo": tipo,
        "ambiente": ambiente,
        "contexto": "slack",
        "contexto_id": "usuario",
        "expira_en": expira_en,
        "estado": "pendiente",
        "entidad": entidad,
        "es_permanente": es_permanente
    })

    return {"text": f"IP {ip} enviada para aprobación en {ambiente}"}
