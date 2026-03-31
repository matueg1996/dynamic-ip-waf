# Arquitectura del sistema

## Visión general

El sistema implementa una arquitectura desacoplada orientada a controlar la gestión de IPs (allow/block) para uno o múltiples WAFs, separando claramente:

- Interfaz de usuario
- Lógica de negocio
- Persistencia
- Exposición segura
- Ejecución sobre infraestructura externa (WAF)

---

## Diagrama de alto nivel

```text
                    ┌───────────────┐
                    │     Usuario   │
                    └──────┬────────┘
                           │
                           ▼
                    ┌───────────────┐
                    │    Slack App  │
                    └──────┬────────┘
                           │
                           ▼
                    ┌───────────────┐
                    │  FastAPI App  │
                    │ (Control Plane)│
                    └──────┬────────┘
                           │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
  ┌────────────┐    ┌──────────────┐   ┌──────────────┐
  │ PostgreSQL │    │ Worker TTL   │   │ Export API   │
  │ (Source of │    │ Expiration   │   │ (/export)    │
  │ Truth)     │    └──────────────┘   └──────┬───────┘
  └────────────┘                             │
                                             ▼
                                   ┌────────────────┐
                                   │ WAF Sync       │
                                   │ Service        │
                                   └──────┬─────────┘
                                          │
              ┌───────────────────────────┼───────────────────────────┐
              ▼                           ▼                           ▼
       ┌──────────────┐           ┌──────────────┐            ┌──────────────┐
       │ AWS WAF      │           │ GCP WAF      │            │ Imperva WAF  │
       └──────────────┘           └──────────────┘            └──────────────┘
```
---

# Componentes

## Slack (Interfaz de usuario)

Punto de entrada para los usuarios.

Permite:
- Solicitar bloqueos / habilitaciones
- Definir ambiente
- Definir TTL
- Definir la entidad afectada por la IP

Maneja:
- autenticación
- permisos
- trazabilidad

---

## FastAPI (Control Plane)

Responsable de:

- Procesar requests
- Validar datos
- Persistir información
- Manejar estados (pendiente, activa, expirada)

Endpoints clave:

- `POST /ip`: Registra una nueva solicitud de manejo de IP en estado "pendiente".
- `POST /aprobar`: Transiciona la solicitud pendiente a un estado "activa".
- `DELETE /ip/{ip}`: Revoca manualmente una IP, forzando su estado a expirado.
- `GET /export`: Genera una vista consolidada de IPs a procesar.
- `POST /accion`: Webhook dedicado para procesar comandos desde Slack.

---

## PostgreSQL (Source of Truth)

Almacena:

- Estado actual de todas las IPs
- TTL y fechas de expiración
- Ambientes (prod, staging, etc.)
- Historial y metadatos (entidad, contexto)

---

## Worker de expiración (TTL)

Proceso continuo que:

- Revisa IPs con expiración vencida
- Las marca automáticamente como estado "expirada"

---

## Export API (/export)

Expone el estado consolidado del sistema para que los servicios de sincronización puedan consumirlo de forma segura.

---

## WAF Sync Service

Componente encargado de:
- Consumir el endpoint `/export`.
- Interpretar el estado de la base de datos.
- Sincronizar el WAF mediante SDKs específicos (AWS Boto3, GCP Cloud SDK).

---

## WAFs (Execution Layer)

Los cortafuegos de aplicaciones web (AWS WAF, Cloud Armor) que ejecutan las reglas de bloqueo o permiso basadas en el estado sincronizado.

---

# Stack y Librerías Clave

Las decisiones del ecosistema base responden a la necesidad de rendimiento bajo I/O intensiva, simplicidad operativa, y estados seguros:

- **FastAPI (`fastapi`, `uvicorn`):** Seleccionado como el framework web base dadas sus capacidades asincrónicas extremas para lidiar con miles de req/sec consumiendo escasos recursos. Facilita la construcción declarativa y auto-generación de documentación (Swagger).
- **Pydantic (`pydantic`):** Fomenta la barrera de seguridad. Su función es evaluar y validar rigurosamente la estructura y tipos (Data Transfer Object) de cada petición.
- **SQLAlchemy (`sqlalchemy`):** ORM que permite modelar la tabla de IPs y sus estados abstrayendo el motor subyacente.
- **PostgreSQL (`psycopg2`):** Base relacional elegida por su soporte ACID y robustez en el manejo de transacciones concurrentes.
- **Requests (`requests`):** Utilizada por el *Sync Service* para realizar peticiones HTTP hacia el plano de control y potenciales APIs externas.
- **Python Dotenv (`python-dotenv`):** Componente crítico para la gestión de secretos; permite inyectar variables de entorno desde archivos `.env`.

---

# Seguridad en capas

1. **Cliente**: Interfaz de Slack o llamadas directas a la API.
2. **API Gateway**: Capa de control de acceso mediante API Keys y Rate Limiting.
3. **FastAPI**: Validaciones de esquema y lógica de negocio.
4. **PostgreSQL**: Persistencia segura con tipos de datos estrictos.

---

# Flujo completo de IP

1. Usuario solicita cambio (Slack o API).
2. La IP queda registrada en estado "pendiente".
3. Un administrador aprueba la IP.
4. El estado cambia a "activa".
5. El **Sync Service** detecta el cambio y actualiza el WAF.
6. El **Worker de Expiración** marca la IP como "expirada" cuando vence su TTL.
7. En el siguiente ciclo de sincronización, la IP desaparece del WAF.

---

# Estructura de Archivos

A continuación se detalla el propósito de cada archivo clave en el repositorio:

### Raíz del Proyecto
- [`.env.example`](file:///c:/Users/Hall-9000/.gemini/antigravity/scratch/dynamic-ip-waf/.env.example): Plantilla de configuración para variables de entorno necesarias.
- [`.gitignore`](file:///c:/Users/Hall-9000/.gemini/antigravity/scratch/dynamic-ip-waf/.gitignore): Define qué archivos y directorios no deben ser rastreados por Git.
- [`architecture.md`](file:///c:/Users/Hall-9000/.gemini/antigravity/scratch/dynamic-ip-waf/architecture.md): Este documento; detalla las decisiones técnicas y de diseño.
- [`README.md`](file:///c:/Users/Hall-9000/.gemini/antigravity/scratch/dynamic-ip-waf/README.md): Documentación general, guía de inicio rápido y despliegue.
- [`requirements.txt`](file:///c:/Users/Hall-9000/.gemini/antigravity/scratch/dynamic-ip-waf/requirements.txt): Listado de dependencias de Python.

### Directorio `app/` (Servicio Central)
- [`app/main.py`](file:///c:/Users/Hall-9000/.gemini/antigravity/scratch/dynamic-ip-waf/app/main.py): Orquestador principal de FastAPI; inicializa la app y registra los routers.
- [`app/api/rutas.py`](file:///c:/Users/Hall-9000/.gemini/antigravity/scratch/dynamic-ip-waf/app/api/rutas.py): Controladores CRUD de la API.
- [`app/api/slack.py`](file:///c:/Users/Hall-9000/.gemini/antigravity/scratch/dynamic-ip-waf/app/api/slack.py): Lógica de integración con Slack.
- [`app/db/database.py`](file:///c:/Users/Hall-9000/.gemini/antigravity/scratch/dynamic-ip-waf/app/db/database.py): Configuración de SQLAlchemy.
- [`app/db/esquemas.py`](file:///c:/Users/Hall-9000/.gemini/antigravity/scratch/dynamic-ip-waf/app/db/esquemas.py): Mapeadores para Base de Datos de IP (SQLAlchemy).
- [`app/models/modelo_ip.py`](file:///c:/Users/Hall-9000/.gemini/antigravity/scratch/dynamic-ip-waf/app/models/modelo_ip.py): Modelos Pydantic para validación de datos.
- [`app/services/exportador_waf.py`](file:///c:/Users/Hall-9000/.gemini/antigravity/scratch/dynamic-ip-waf/app/services/exportador_waf.py): Lógica de empaquetado para exportación JSON.
- [`app/services/servicio_ip.py`](file:///c:/Users/Hall-9000/.gemini/antigravity/scratch/dynamic-ip-waf/app/services/servicio_ip.py): Capa de servicios y lógica de negocio.
- [`app/services/waf_sync_service.py`](file:///c:/Users/Hall-9000/.gemini/antigravity/scratch/dynamic-ip-waf/app/services/waf_sync_service.py): Módulo de sincronización con nubes.
- [`app/workers/expiration_worker.py`](file:///c:/Users/Hall-9000/.gemini/antigravity/scratch/dynamic-ip-waf/app/workers/expiration_worker.py): Tarea en segundo plano para TTLs.

### Otros Directorios
- [`docker/Dockerfile`](file:///c:/Users/Hall-9000/.gemini/antigravity/scratch/dynamic-ip-waf/docker/Dockerfile): Instrucciones de construcción del contenedor.
- [`docker/docker-compose.yml`](file:///c:/Users/Hall-9000/.gemini/antigravity/scratch/dynamic-ip-waf/docker/docker-compose.yml): Orquestación local.
- [`terraform/main.tf`](file:///c:/Users/Hall-9000/.gemini/antigravity/scratch/dynamic-ip-waf/terraform/main.tf): Aprovisionamiento de infraestructura como código.
