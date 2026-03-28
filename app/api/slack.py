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

    expira_en = None
    if ttl:
        expira_en = datetime.utcnow() + timedelta(minutes=int(ttl))

    crear_ip({
        "ip": ip,
        "tipo": tipo,
        "ambiente": ambiente,
        "contexto": "slack",
        "contexto_id": "usuario",
        "expira_en": expira_en,
        "estado": "pendiente"
    })

    return {"text": f"IP {ip} enviada para aprobación en {ambiente}"}
