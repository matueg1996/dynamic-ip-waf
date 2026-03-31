# Servicio de exportación de reglas para el WAF.
from app.services.servicio_ip import obtener_ips_activas

def exportar_listas():
    resultado = {}

    for r in obtener_ips_activas():
        if r.ambiente not in resultado:
            resultado[r.ambiente] = {
                "allowlist": [],
                "blocklist": []
            }

        if r.tipo == "allow":
            resultado[r.ambiente]["allowlist"].append(r.ip)
        else:
            resultado[r.ambiente]["blocklist"].append(r.ip)

    return resultado