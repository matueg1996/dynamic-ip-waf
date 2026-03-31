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
- `DELETE /ip/{ip}`: Revoca manualmente una IP, forzando su estado a expirado (incluso si era permanente o le restaba TTL).
- `GET /export`: Genera una vista consolidada de IPs a procesar. Solamente el *Sync Service* consume esta ruta.
- `POST /accion`: Webhook dedicado exclusivo para procesar el payload de los comandos enviados nativamente desde los tableros interactivos de Slack.

Cerebro del sistema

---

## PostgreSQL (Source of Truth)

Almacena:

- Estado actual de todas las IPs
- TTL
- Ambientes
- Historial básico (estado)

Fuente de verdad

---

## Worker de expiración (TTL)

Proceso continuo que:

- Revisa IPs con expiración
- Marca como expirada

```text
expira_en < now → estado = expirada
```

No se toca el WAF directamente

---

## Export API (/export)

Expone el estado actual del sistema:

```json
{
  "prod": {
    "allowlist": [],
    "blocklist": []
  }
}
```

Punto clave de integración

---

## WAF Sync Service

Componente que:
- Consume `/export`
- Interpreta el estado
- Actualiza el WAF

  Diseño clave:
- Hace overwrite completo
- No hace updates incrementales

---

## WAFs (Execution Layer)

Ejemplos:
- AWS WAF
- GCP Cloud Armor
- Imperva

Consumidores pasivos del estado

---

# Stack Tecnológico y Librerías Clave

Las decisiones del ecosistema base responden a la necesidad de rendimiento bajo I/O intensiva, simplicidad operativa y tipado seguro en frontera:

- **FastAPI (`fastapi`, `uvicorn`):** Seleccionado como el framework web base dadas sus capacidades asincrónicas extremas para lidiar con miles de req/sec consumiendo escasos recursos. Facilita la construcción declarativa y auto-generación de documentación (Swagger), crucial para un equipo DevOps.
- **Pydantic (`pydantic`):** Fomenta una barrera de bioseguridad. Su función es evaluar y validar rigurosamente la estructura y tipos (Data Transfer Object) de cada petición originada en Slack *antes* de ejecutar cualquier lógica de negocio, repeliendo payloads arbitrarios malformados instantáneamente.
- **SQLAlchemy (`sqlalchemy`):** ORM que permite modelar la tabla de IPs y sus estados abstrayendo el motor subyacente. Permite consultas complejas, simplifica los chequeos por ambiente e introduce mecanismos que blindan el acceso frente a inyecciones SQL.
- **PostgreSQL (`psycopg2`):** Base relacional elegida no solo por ser el estándar de la industria, sino por su potente soporte ACID y nivel de bloqueo transaccional (*Row-level locks*), fundamental para evitar condiciones de carrera si dos administradores actúan sobre el mismo requerimiento de Slack simultáneamente.
- **Requests (`requests`):** Librería cliente HTTP utilizada por el *WAF Sync Service* para consumir el endpoint de exportación de la API de forma sencilla y confiable, manejando cabeceras de autenticación y payloads JSON.
- **Python-dotenv (`python-dotenv`):** Componente clave para la gestión de la configuración. Permite desacoplar los secretos y variables de entorno del código fuente, cargándolos automáticamente desde un archivo `.env` local, facilitando la portabilidad entre entornos de desarrollo, staging y producción.

---

# Seguridad en capas

1. Cliente
   ↓
2. API Gateway (API Key + rate limiting)
   ↓
3. FastAPI (validaciones)
   ↓
4. PostgreSQL

**Exposición**
- API expuesta vía API Gateway
- Uso de API Key
- No exposición directa de EC2

---

# Flujo completo

1. Usuario solicita cambio (Slack/API)
2. IP queda en estado pendiente
3. Aprobación
4. Estado activa
5. Worker controla expiración
6. Sync consulta `/export`
7. WAF se actualiza

---

# Manejo de expiraciones

1. **Worker** → marca expirada
   ↓
2. **Sync** → ejecuta
   ↓
3. **WAF** → se actualiza
   ↓
4. IP desaparece
