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

- `POST /ip`
- `POST /aprobar`
- `GET /export`

👉 Es el cerebro del sistema

---

## 3. PostgreSQL (Source of Truth)

Almacena:

- Estado actual de todas las IPs
- TTL
- Ambientes
- Historial básico (estado)

👉 Es la fuente de verdad

---

## 4. Worker de expiración (TTL)

Proceso continuo que:

- Revisa IPs con expiración
- Marca como expirada

```text
expira_en < now → estado = expirada
```

👉 No toca el WAF directamente

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

👉 Punto clave de integración

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

👉 Son consumidores pasivos del estado

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
