# Dynamic IP WAF

Un sistema de control centralizado, dinámico y automatizado para gestionar listas de acceso de IPs (Allowlist y Blocklist) a través de múltiples soluciones de Web Application Firewall (WAF) tales como AWS WAF, GCP Cloud Armor e Imperva.

## Contexto y Propósito del Proyecto

En entornos de infraestructura web en la nube, bloquear una IP maliciosa o permitir temporalmente una IP de soporte a través de un WAF normalmente amerita:
1. Contactar a un ingeniero Cloud/DevOps.
2. Ingresar a las consolas en la nube (AWS/GCP).
3. Modificar reglas a mano y recordar quitarlas cuando dejen de ser necesarias.

**Dynamic IP WAF** viene a solucionar este cuello de botella y evitar el error humano introduciendo un panel de control inteligente. A través de este sistema, cualquier usuario autorizado puede solicitar permisos temporales (con un `TTL` o Time-to-Live definido) desde **Slack**, requiriendo una simple aprobación secundaria para que el sistema automáticamente parchee el WAF correspondiente.

---

## Beneficios Clave
- **Mitigación de Errores Humanos:** Nadie toca directamente el WAF ni ingresa a las consolas, evitando daños en reglas productivas o que las excepciones queden de por vida por olvido.
- **Trazabilidad Absoluta:** Todas las solicitudes, aprobaciones y expiraciones quedan registradas en Slack y en PostgreSQL con fecha y autor. Como estrategia provisoria o alternativa rápida, al tener los logs de auditoría de Slack interconectados a un SIEM Corporativo (ej. Splunk, Datadog), se obtiene trazabilidad y control inmediato de quién solicitó un bloqueo/permiso y quién lo aprobó.
- **Eficiencia Operativa:** Libera a los equipos de DevOps/Seguridad del trabajo manual rutinario, descentralizando el control de forma confiable.
- **Higiene por Defecto (TTL):** El sistema garantiza que todo permiso (allowlist) o bloqueo manual caduque solo y desaparezca exactamente en el tiempo solicitado.

---

## Resumen Operativo

### Gestión y Consumo de IPs por el WAF
Las IPs se gestionan de forma centralizada en la base de datos PostgreSQL. El *WAF Sync Service* consume periódicamente un estado consolidado mediante el endpoint `/export`. Este servicio toma esta vista de IPs aprobadas y hace un reemplazo absoluto (sobrescritura) en los diferentes WAFs. Esto garantiza que el entorno cloud replique exactamente nuestra fuente de la verdad en cada iteración.

### Prevención de Bloqueo de Tráfico Legítimo
Para evitar el bloqueo de tráfico vital y reducir errores humanos:
- **Identidad Extendida:** Cada ingreso al sistema permite etiquetar la *entidad* a la que pertenece la IP (ej. un comerciante clave, un proveedor externo o tráfico malicioso). Esto provee un contexto visual rápido al WAF y a las auditorías sobre quién es el afectado por la regla.
- **Flujos de trabajo de aprobación:** Obliga a seguir un control basado en políticas donde a cada petición de un operador le sigue la revisión/aprobación de un segundo responsable (sistema *Maker-Checker*).
- **Métricas, registro o alertas:** Se monitorean los cambios de IPs y los intentos denegados, que pueden integrarse a paneles como Grafana para alertar visualmente sobre bloqueos masivos inesperados.
- **TTL implacable y Reglas Permanentes:** Por defecto, los permisos se eliminan al expirar su *TTL*, previniendo la acumulación de basura legacy. No obstante, existe la opción de marcar IPs esenciales como **permanentes**, desactivando el TTL por completo para permitir o bloquear entidades estáticas a largo plazo (revocables manualmente a través del endpoint `DELETE /ip/{ip}`).

### Supuestos, Limitaciones o Problemas Encontrados
- **Supuestos:** Las nubes de los proveedores aseguran alta disponibilidad para los endpoints de actualización de seguridad y las credenciales provisionadas no experimentan rotaciones asíncronas no avisadas.
- **Limitaciones:** El WAF Sync evalúa reemplazos totales cada ciclo en vez de deltas (modificaciones incrementales). Ante listas extraordinariamente grandes, podrían superarse las cuotas estándar (ej. AWS WAF suele limitar a 10.000 direcciones IPv4 por IP Set por defecto con su configuración básica).

---

## Arquitectura General

El sistema se basa en una arquitectura fuertemente desacoplada y orientada a microservicios que protege las instancias internas, descrita detalladamente en [architecture.md](./architecture.md).

Está conformado por los siguientes pilares:
1. **Slack App (UI)**: Maneja la interacción cotidiana. Los operadores aprueban, rechazan, o solicitan bloquear/habilitar IPs desde Slack.
2. **Control Plane (FastAPI)**: La API central (expuesta solo a través de un API Gateway propio y controlada por API Keys). Procesa las validaciones, mantiene la lógica de negocio y determina a qué ambiente afecta cada IP.
3. **PostgreSQL (Source of Truth)**: Base de datos centralizada; toda IP existente y su estado (pendiente, aprobada, expirada) vive aquí.
4. **TTL Expiration Worker**: Un proceso asíncrono que barre constantemente la base de datos buscando IPs cuyo tiempo de expiración se haya vencido, descartándolas para la siguiente sincronización.
5. **WAF Sync Service**: Agente encargado de consultar el `/export` y sincronizar los WAFs. **Nota:** En la versión actual, el método de actualización es un placeholder que debe integrarse con el SDK específico (ej: Boto3 para AWS, Google Cloud SDK para GCP) según el proveedor elegido.

---

## Cómo Fluye la Información (Ciclo de Vida)

1. **La Petición:** Alguien en Slack ejecuta un comando (`/allow-ip 192.168.1.1 2h`).
2. **Validación:** El webhook de Slack llega al `app/api/slack.py`, y en conjunto con `app/services/servicio_ip.py`, se anota la IP como **Pendiente**.
3. **Consenso:** Un administrador usa el panel en Slack para "Aprobar" la IP, que cambia su estado en la DB de PostgreSQL.
4. **Propagación:** El `waf_sync_service.py` lee el consolidado generado por `exportador_waf.py`. Este servicio es el punto de extensión donde se invocan los SDKs de nube para impactar las reglas reales.
5. **Caducidad Automática:** El reloj avanza 2 horas. El `expiration_worker.py` detecta que la IP expiró. En el próximo ciclo del Sync Service, como esta IP ya no aparecerá en el exportador, será removida instantáneamente del WAF, protegiendo automáticamente la aplicación.

---

## Seguridad
La API no se encuentra expuesta al público general ni a EC2s desprotegidas. Únicamente se invoca a través de tokens firmados o API Gateways limitados (Rate-Limits). Del mismo modo, sus interacciones hacia los WAF son "Pull-based" unidireccionales desde redes seguras.

---

El código está estructurado bajo principios de arquitecturas limpias y una separación estricta de responsabilidades. La siguiente lista resume la organización; para una explicación detallada de cada archivo y su función técnica, consulte el documento [architecture.md](./architecture.md).

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

## Despliegue y Ejecución

### Prerrequisitos
Para que el programa funcione correctamente, tener instalados:
- **Docker** y **Docker Compose** para la versión en contenedores de la solución.
- **Terraform** (opcional, para Infraestructura como código).
- Python 3.9+ (si se ejecuta localmente sin Docker).

### Configuración (Variables de Entorno)
El sistema utiliza un archivo `.env` para gestionar secretos y configuraciones sensibles. Siga estos pasos para configurar su entorno:

1. copiar el archivo de ejemplo:
   ```bash
   cp .env.example .env
   ```
2. editar el archivo `.env` y complete los valores:
   - `DATABASE_URL`: Cadena de conexión para PostgreSQL.
   - `API_KEY`: Clave secreta compartida para autorizar peticiones entre servicios. Esta clave es necesaria tanto para el acceso a la API desde el exterior como para que el *WAF Sync Service* pueda descargar las listas de IPs. Sin esta clave (cabecera `x-api-key`), todas las peticiones devolverán un error `401 Unauthorized`.
   - `WAF_EXPORT_URL`: URL completa del endpoint de exportación (ej. `http://api:8000/export` dentro de Docker).
   - `SLACK_SIGNING_SECRET`: Secreto de firma de su aplicación Slack para validar webhooks.
   - `SLACK_BOT_TOKEN`: Token `xoxb-*` de su bot de Slack para enviar notificaciones.

**IMPORTANTE:** Nunca subir el archivo `.env` a GitHub. El archivo `.gitignore` ya está configurado para excluirlo.

### Ejecución con Docker
La solución está empaquetada en contenedores. Para desplegar:
1. Navegar al directorio raíz del proyecto.
2. Configurar sus variables de entorno.
3. Ejecutar el comando para levantar la base de datos, el backend y el worker:
   ```bash
   docker-compose -f docker/docker-compose.yml up -d
   ```
4. La API del plano de control estará disponible en `http://localhost:8000`.

### Infraestructura como Código (IaC)
Se incluye soporte base en Terraform (`/terraform`) para automatizar y estandarizar el despliegue de los WAF Web ACLs y reglas en entornos multinube (como AWS y GCP).

### Despliegue en AWS (Nube)
Para llevar el Control Plane a un entorno productivo de Amazon Web Services, se recomienda utilizar:
- **Amazon ECS con AWS Fargate:** Para correr la imagen de Docker de FastAPI de manera sin servidor (*serverless*) y delegar el escalado al proveedor.
- **Amazon RDS (PostgreSQL):** Sustituyendo el contenedor local de BD por el servicio gestionado de AWS para garantizar persistencia, alta disponibilidad y respaldos automatizados.
- **AWS ALB o API Gateway:** Para exponer tu ruta pública (`/accion`) en HTTPS de manera segura, aislando el resto de los microservicios en subredes privadas.

### Integración con Slack (Configuración Pendiente)
Para que las peticiones y botones de Slack lleguen de manera exitosa a la API (FastAPI), se necesita completar los siguientes pasos en [Slack API](https://api.slack.com/apps):
1. **Crear una Slack App:** Desde el espacio de trabajo, crear una aplicación con permisos para usar *Slash Commands* (`/allow-ip`, `/block-ip`).
2. **Configurar el Webhook (Request URL):** En la sección "Interactivity & Shortcuts", habilitar la interactividad y apuntar la URL de respuesta publicamente hacia el despliegue: `https://<dominio-aws.com>/accion`.
3. **Firmas y Seguridad:** Extraer el *Signing Secret* y el *Bot User OAuth Token* de Slack para cargarlos como variables de entorno en el contenedor AWS de FastAPI. Esto garantiza que nadie falsifique comandos y la API solo escuche a los servidores autorizados de Slack.

---

## Mejoras para Futuras Versiones (Roadmap)
- **Soporte Multi-Cloud Simultáneo:** Pushear la lista de forma nativa a AWS WAF, GCP Cloud Armor y Cloudflare al mismo tiempo para proteger arquitecturas híbridas.
- **Alertas Predictivas:** Notificar automáticamente en Slack cuando el TTL de una IP útil esté a 5 minutos de caducar, permitiendo extenderlo con un click.
- **Bloques de Subredes (CIDRs):** Admitir notaciones tipo `192.168.1.0/24` en lugar de una única IP.
- **Métricas y Prometheus:** Exportar estadísticas hacia Grafana para visualizar frecuencias de bloqueo, autores, e historial analítico.
- **Integraciones con SIEM Automáticas:** Que herramientas como Splunk o Datadog envíen la IP directo al servicio como "Pendiente" cuando detecten ataques y Slack solo pregunte "¿Aprobar bloqueo?".
