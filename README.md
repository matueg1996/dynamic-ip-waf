# Dynamic IP WAF

Un sistema de control centralizado, dinámico y totalmente automatizado para gestionar listas de acceso de IPs (Allowlist y Blocklist) a través de múltiples soluciones de Web Application Firewall (WAF) tales como AWS WAF, GCP Cloud Armor e Imperva.

## Contexto y Propósito del Proyecto

En entornos de infraestructura web en la nube, bloquear una IP maliciosa o permitir temporalmente una IP de soporte a través de un WAF normalmente amerita:
1. Contactar a un ingeniero Cloud/DevOps.
2. Ingresar a las consolas en la nube (AWS/GCP).
3. Modificar reglas a mano y recordar quitarlas cuando dejen de ser necesarias.

**Dynamic IP WAF** viene a solucionar este cuello de botella y evitar el error humano introduciendo un panel de control inteligente. A través de este sistema, cualquier usuario autorizado puede solicitar permisos temporales (con un `TTL` o Time-to-Live definido) desde **Slack**, requiriendo una simple aprobación secundaria para que el sistema automáticamente parchee el WAF correspondiente.

---

## Arquitectura General

El sistema se basa en una arquitectura fuertemente desacoplada y orientada a microservicios que protege las instancias internas, descrita detalladamente en [architecture.md](./architecture.md).

Está conformado por los siguientes pilares:
1. **Slack App (UI)**: Maneja la interacción cotidiana. Los operadores aprueban, rechazan, o solicitan bloquear/habilitar IPs desde Slack.
2. **Control Plane (FastAPI)**: La API central (expuesta solo a través de un API Gateway propio y controlada por API Keys). Procesa las validaciones, mantiene la lógica de negocio y determina a qué ambiente afecta cada IP.
3. **PostgreSQL (Source of Truth)**: Base de datos centralizada; toda IP existente y su estado (pendiente, aprobada, expirada) vive aquí.
4. **TTL Expiration Worker**: Un proceso asíncrono que barre constantemente la base de datos buscando IPs cuyo tiempo de expiración se haya vencido, descartándolas para la siguiente sincronización.
5. **WAF Sync Service**: Agente "tonto" pero altamente confiable que consulta el estado completo del endpoint `/export`, y hace reemplazos absolutos en los distintos WAF de la nube (dejándolos como réplicas pasivas de nuestra base de datos).

---

## Organización del Código

El código está estructurado bajo principios de arquitecturas limpias y una separación estricta de responsabilidades. La carpeta principal es la siguiente:

```text
├── app/
│   ├── main.py                    # Punto de entrada de FastAPI y registro de eventos
│   ├── api/                       # Controladores y rutas HTTP
│   │   ├── rutas.py               # Gestión de los endpoints genéricos (/ip, /aprobar, /export)
│   │   └── slack.py               # Webhooks e integración de comandos provenientes de Slack
│   ├── db/                        # Capa de datos y Persistencia
│   │   ├── database.py            # Motor de conexión y sesiones para PostgreSQL
│   │   └── esquemas.py            # Modelos Pydantic para la validación de Entradas/Salidas
│   ├── models/                    # Entidades ORM (Mapeadores para Base de Datos)
│   │   └── modelo_ip.py           # Definición de la entidad IP, Ambiente, TTL y un Estado
│   ├── services/                  # Capa principal lógica del negocio
│   │   ├── servicio_ip.py         # Creación, verificación y cálculo de vencimientos de IPs
│   │   ├── exportador_waf.py      # Agrupa todo el "Source of truth" y lo empaqueta seguro como JSON
│   │   └── waf_sync_service.py    # Rutinas que se comunican con los SDK (boto3, google-cloud, etc.)
│   └── workers/                   # Background tasks independientes
│       └── expiration_worker.py   # Tarea auto-ejecutable ciclada para caducidad de TTLs
│
├── docker/                        # Contenedores para levantamiento simple y reproducible
│   ├── Dockerfile                 # Receta de la imagen Docker principal de FastAPI
│   └── docker-compose.yml         # Orquestador local (App, Postgres, Redis, Worker)
│
├── terraform/                     # Infraestructura provisionada como código (IaC)
│   └── main.tf                    # Aprovisionamiento de AWS WAF/GCP y recursos base en la nube
│
├── requirements.txt               # Paquetes y dependencias core (ej. FastAPI, SQLAlchemy, httpx)
└── architecture.md                # Documento ampliado de decisiones e hitos arquitectónicos
```

---

## Cómo Fluye la Información (Ciclo de Vida)

1. **La Petición:** Alguien en Slack ejecuta un comando (`/allow-ip 192.168.1.1 2h`).
2. **Validación:** El webhook de Slack llega al `app/api/slack.py`, y en conjunto con `app/services/servicio_ip.py`, se anota la IP como **Pendiente**.
3. **Consenso:** Un administrador usa el panel en Slack para "Aprobar" la IP, que cambia su estado en la DB de PostgreSQL.
4. **Propagación:** Regularmente (o empujado por eventos), el `waf_sync_service.py` lee un archivo consolidado generado por `exportador_waf.py` y sube la nueva lista al WAF elegido pisando la vieja lista.
5. **Caducidad Automática:** El reloj avanza 2 horas. El `expiration_worker.py` detecta que la IP expiró. En el próximo ciclo del Sync Service, como esta IP ya no aparecerá en el exportador, será removida instantáneamente del WAF, protegiendo automáticamente la aplicación.

---

## Seguridad
La API no se encuentra expuesta al público general ni a EC2s desprotegidas. Únicamente se invoca a través de tokens firmados o API Gateways limitados (Rate-Limits). Del mismo modo, sus interacciones hacia los WAF son "Pull-based" unidireccionales desde redes seguras.

---

## Beneficios Clave
- **Mitigación de Errores Humanos:** Nadie toca directamente el WAF ni ingresa a las consolas, evitando daños en reglas productivas o que las excepciones queden de por vida por olvido.
- **Trazabilidad Absoluta:** Todas las solicitudes, aprobaciones y expiraciones quedan registradas en Slack y en PostgreSQL con fecha y autor.
- **Eficiencia Operativa:** Libera a los equipos de DevOps/Seguridad del trabajo manual rutinario, descentralizando el control de forma confiable.
- **Higiene por Defecto (TTL):** El sistema garantiza que todo permiso (allowlist) o bloqueo manual caduque solo y desaparezca exactamente en el tiempo solicitado.

---

## Mejoras para Futuras Versiones (Roadmap)
- **Soporte Multi-Cloud Simultáneo:** Empujar la lista de forma nativa a AWS WAF, GCP Cloud Armor y Cloudflare al mismo tiempo para proteger arquitecturas híbridas.
- **Alertas Predictivas:** Notificar automáticamente en Slack cuando el TTL de una IP útil esté a 5 minutos de caducar, permitiendo extenderlo con un click.
- **Bloques de Subredes (CIDRs):** Admitir notaciones tipo `192.168.1.0/24` en lugar de una única IP.
- **Métricas y Prometheus:** Exportar estadísticas hacia Grafana para visualizar frecuencias de bloqueo, autores, e historial analítico.
- **Integraciones con SIEM Automáticas:** Que herramientas como Splunk o Datadog envíen la IP directo al servicio como "Pendiente" cuando detecten ataques y Slack solo pregunte "¿Aprobar bloqueo?".