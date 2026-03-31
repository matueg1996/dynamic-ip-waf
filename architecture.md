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

## 1. Slack (Interfaz de usuario)

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

## 2. FastAPI (Control Plane)

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

## 3. PostgreSQL (Source of Truth)

Almacena:

- Estado actual de todas las IPs
- TTL
- Ambientes
- Historial básico (estado)

Fuente de verdad

---

## 4. Worker de expiración (TTL)

Proceso continuo que:

- Revisa IPs con expiración
- Marca como expirada

```text
expira_en < now → estado = expirada
```

No toca el WAF directamente

---

## 5. Export API (/export)

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

## 6. WAF Sync Service

Componente que:
- Consume `/export`
- Interpreta el estado
- Actualiza el WAF

  Diseño clave:
- Hace overwrite completo
- No hace updates incrementales

---

## 7. WAFs (Execution Layer)

Ejemplos:
- AWS WAF
- GCP Cloud Armor
- Imperva

Son consumidores pasivos del estado

---

# Stack Tecnológico y Librerías Clave

Las decisiones del ecosistema base responden a la necesidad de rendimiento bajo I/O intensiva, simplicidad operativa y tipado seguro en frontera:

- **FastAPI (`fastapi`, `uvicorn`):** Seleccionado como el framework web base dadas sus capacidades asincrónicas extremas para lidiar con miles de req/sec consumiendo escasos recursos. Facilita la construcción declarativa y auto-generación de documentación (Swagger), crucial para un equipo DevOps.
- **Pydantic (`pydantic`):** Fomenta una barrera de bioseguridad. Su función es evaluar y validar rigurosamente la estructura y tipos (Data Transfer Object) de cada petición originada en Slack *antes* de ejecutar cualquier lógica de negocio, repeliendo payloads arbitrarios malformados instantáneamente.
- **SQLAlchemy (`sqlalchemy`):** ORM que permite modelar la tabla de IPs y sus estados abstrayendo el motor subyacente. Permite consultas complejas, simplifica los chequeos por ambiente e introduce mecanismos que blindan el acceso frente a inyecciones SQL.
- **PostgreSQL (`psycopg2`):** Base relacional elegida no solo por ser el estándar de la industria, sino por su potente soporte ACID y nivel de bloqueo transaccional (*Row-level locks*), fundamental para evitar condiciones de carrera si dos administradores actúan sobre el mismo requerimiento de Slack simultáneamente.

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

---

## Compensaciones (Trade-Offs) Arquitectónicas

1. **Reemplazo Absoluto vs. Actualizaciones Incrementales**
   - *Decisión:* El **WAF Sync Service** reescribe por completo los IP sets en cada ciclo en lugar de enviar solo los cambios recientes.
   - *Pros:* Simplicidad absoluta, elimina inconsistencias (drift state) entre la fuente de la verdad (PostgreSQL) y el cloud.
   - *Contras:* Es ineficiente en términos de consumo de APIs y ancho de banda si la lista escala a decenas de miles de IPs.

2. **Arquitectura Pull vs. Push hacia los WAFs**
   - *Decisión:* Un proceso cíclico (Sync Service) lee el estado y lo envía a los proveedores, en lugar de que la DB inyecte datos instantáneos bajo demanda y eventos.
   - *Pros:* Mayor tolerancia a fallos. Si un proveedor de nube se cae brevemente, el Sync lo reintenta automáticamente en el siguiente tick.
   - *Contras:* Retraso forzado (*Eventual Consistency*) entre la solicitud de bloqueo y la implementación en el borde perimetral.

---

## Detalles Operativos Profundos

### Gestión y Consumo de Conjuntos de IP por el WAF
El flujo de consumo está garantizado mediante agentes mediadores:
1. El endpoint de consolidación de API extrae de forma unificada aquellas IPs en estado de "Aprobado" agrupándolas por entorno (staging, prod, dev).
2. Los SDK de los proveedores (ej: `boto3` para AWS, APIs de red de GCP) recogen esta foto para empaquetarla en el formato JSON propietario del IP Set del proveedor de la nube.
3. Se invoca el respectivo método PUT o Update sobrescribiendo todo con el listado puro. El WAF en la nube asume las políticas sin ejecutar lógica de negocio adicional.

### Ayuda Continua a Evitar Bloqueos Legítimos
La prevención de bloqueos accidentales a usuarios y proveedores confiables radica en varios mecanismos de control:
- **Trazabilidad de Entidades (Identidad):** El esquema impone la captura de un campo de "Entidad", permitiendo clasificar exactamente de quién es la IP (proveedor externo, comerciante, origen malicioso de botnet). Visibilizar la entidad previene revocaciones de accesos clave.
- **Flujos de Aprobación por Slack:** Aplicando el principio de autorización delegada, la persona que solicita el cambio no puede auto-aprobarse, previniendo mitigaciones erróneas o por sesgos humanos.
- **Segregación Restringida:** Los endpoints controlan que bajo ninguna circunstancia el borrado de una regla aplique transversalmente. Las IPs se gestionan explícitamente dentro de su "ambiente de aplicación" (Staging, Prod).
- **Gestión Automatizada de TTL vs Reglas Permanentes:** El TTL desactiva automáticamente reglas manuales asegurando perfiles esbeltos. Sin embargo, para necesidades críticas (servicios de pago o merchants estables), el modo "es_permanente=True" evade el reloj TTL permitiendo flujos de *Always-Allow/Always-Block* ininterrumpidos y revocables solo bajo demanda API.

### Resoluciones contra Supuestos, Limitaciones y Problemas
- **Supuestos:** Se presume una latencia y disponibilidad aceptable por parte del Control Plane de las Clouds.
- **Limitaciones de Infraestructura:** El Hard Limit de reglas WAF de Amazon o GCP no se elude; de generarse picos altísimos de peticiones denegadas simultáneas será vital delegar resoluciones macro a CIDRs (bloques enteros).
- **Problemas Encontrados:** Posibles condiciones de carrera a nivel base de datos durante aprobaciones concurrentes demandaron bloqueos transaccionales a nivel tabla si dos administradores aprobaban o rechazaban la misma IP al unísono.

---

## Cumplimiento (Compliance), Entornos Multinube y Telemetría

### Entornos Multinube (Consideraciones sobre AWS y GCP)
La lógica de negocio está fuertemente centralizada desentendiéndose completamente del cloud. Implementar WAFs adicionales o múltiples integraciones es solo cuestión de añadir nuevos "Exportadores" y adaptadores al *Sync Service* sin tocar un ápice la API ni la DB.

### Cumplimiento o Auditoría (ej. relevancia para PCI DSS)
Al conservar todo en PostgreSQL y Slack de manera inmutable:
- Ofrece **Non-repudiation** y trazabilidad sobre quién, a qué hora, por cuánto tiempo, y por qué permitió o prohibió el acceso de una IP al perímetro.
- Satisface controles típicos de **PCI DSS y SOC 2** que requieren que todo cambio al firewall (WAF en este caso) sea justificado y aprobado, evidenciando procesos formales de control de cambios al instante frente a un auditor.
- **De forma provisoria (Quick Win):** Simplemente teniendo los audit logs puros de Slack integrados directamente a un sistema SIEM (como Splunk, Datadog o QRadar), se goza de un registro histórico en tiempo real con perfecta trazabilidad de comandos de _quién pidió la acción_ y _quién dió click en Aprobar_ para el WAF, sin requerir análisis profundo de código de backend.

### Métricas, Registro y Alertas (Observabilidad)
- **Registro de actividad (Logging):** Las transacciones fallidas, intentos de Sync rehusados o denegaciones se capturan integralmente.
- **Alertas sobre Múltiples Expiraciones o Cambios en IPs:** Exponer endpoints como `/metrics` para conectar Prometheus y Grafana permite disparar alertas si (por ejemplo) se vacía un IP Set entero sorpresivamente, o si el Sync Service no logra terminar un ciclo en sus tiempos nominales para alertar temprano fallos masivos.
