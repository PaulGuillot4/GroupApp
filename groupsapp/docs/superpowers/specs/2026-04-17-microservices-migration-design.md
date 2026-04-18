# Migración de GroupsApp a Microservicios con Kafka, REST y gRPC

**Fecha:** 2026-04-17
**Sprint:** 2 (Proyecto de Telemática, 7mo semestre)
**Duración:** 1 semana
**Equipo:** 3 personas

---

## 1. Contexto

GroupsApp es hoy un monolito Django (DRF + Channels + Daphne) con PostgreSQL y WebSocket, ya desplegado en EC2 tras Sprint 1. El requisito académico de Sprint 2 es reescribir el sistema como una arquitectura de microservicios que use **Apache Kafka**, **REST** y **gRPC** de forma justificable, con un mínimo de 5 servicios independientes.

Este documento especifica la arquitectura destino, los contratos entre servicios y el plan semanal de trabajo. No describe la implementación línea por línea — eso queda para el plan de implementación que se generará a partir de este spec.

---

## 2. Objetivos y restricciones

### 2.1 Objetivos

| ID | Objetivo |
|----|----------|
| O-01 | Descomponer el monolito en ≥5 microservicios con responsabilidades claras |
| O-02 | Usar REST en el borde (navegador ↔ sistema), gRPC en el interior (servicio ↔ servicio) y Kafka para eventos asíncronos |
| O-03 | Preservar funcionalidad core: auth, grupos, mensajería en tiempo real (WebSocket), subida de archivos |
| O-04 | Entregar una demo end-to-end reproducible para la sustentación |

### 2.2 Restricciones

| ID | Restricción |
|----|-------------|
| R-01 | 1 semana de trabajo efectivo |
| R-02 | 3 personas en el equipo |
| R-03 | Sin restricción de lenguajes (se elige Python + FastAPI/Django por reutilización) |
| R-04 | Single Postgres con schemas separados (no múltiples instancias de DB) |
| R-05 | Frontend Django existente se preserva — solo re-apunta al Gateway |

---

## 3. Arquitectura general

### 3.1 Topología

```
                       ┌──────────────┐
                       │   Browser    │
                       │ (Django UI)  │
                       └──────┬───────┘
                              │ REST + WebSocket
                              │
              ┌───────────────┼────────────────────┐
              │               │                    │
              │               ▼                    │
              │      ┌──────────────────┐          │ (WS directo
              │      │   API Gateway    │          │  a Messaging)
              │      │   (FastAPI)      │          │
              │      │  REST + JWT val. │          │
              │      └────────┬─────────┘          │
              │               │ gRPC               │
              │   ┌───────────┼────────────┐       │
              │   │           │            │       │
              ▼   ▼           ▼            ▼       ▼
         ┌────────┐ ┌────────┐ ┌─────────┐ ┌──────────┐
         │  Auth  │ │ Users  │ │ Groups  │ │Messaging │◄──┐
         │(Django)│ │(FastAPI)│ │(FastAPI)│ │(Channels)│   │
         └───┬────┘ └───┬────┘ └────┬────┘ └────┬─────┘   │
             │          │           │           │         │
             │          │           │           │ publica │
             │          │           │           ▼         │ gRPC
             │          │           │      ┌─────────┐    │ PushDirect
             │          │           │      │  Kafka  │    │ Message
             │          │           │      │ broker  │    │
             │          │           │      └────┬────┘    │
             │          │           │           │         │
             │          │           │           ▼ consume │
             │          │           │    ┌──────────────┐ │
             │          │           │    │Notifications │─┘
             │          │           │    │  (FastAPI)   │
             │          │           │    └──────────────┘
             │          │           │
             │          │           │
             ▼          ▼           ▼
         ┌─────────────────────────────┐          ┌──────────┐
         │   PostgreSQL (schemas:      │          │  Files   │
         │   auth, users, groups,      │          │(FastAPI) │
         │   messaging, files)         │          └──────────┘
         └─────────────────────────────┘
```

### 3.2 Principios

- **REST afuera, gRPC adentro.** Solo el Gateway habla REST con el mundo; los servicios internos se comunican por gRPC.
- **Kafka para eventos de negocio asíncronos.** No se abusa de Kafka para llamadas que son síncronas por naturaleza.
- **WebSocket vive solo en Messaging.** Es el único servicio con estado de conexión — todos los demás son stateless.
- **Cada servicio es dueño de su schema.** Los FKs cross-service se rompen intencionalmente; se reemplazan por UUIDs validados por flujo.
- **Confianza en la red interna.** El Gateway valida JWT una vez; los servicios internos confían en la metadata gRPC.

---

## 4. Catálogo de servicios

| # | Servicio | Stack | Schema | Responsabilidad |
|---|----------|-------|--------|-----------------|
| 1 | **API Gateway** | FastAPI | — | Punto REST único, valida JWT, traduce a gRPC |
| 2 | **Auth** | Django + DRF-SimpleJWT | `auth.users` (id, username, email, password_hash) | Register/login/refresh/logout, emite y valida JWT |
| 3 | **Users** | FastAPI + SQLAlchemy | `users.user_profiles` (user_id, avatar, bio, last_seen) | Perfil y búsqueda; compone datos llamando a Auth |
| 4 | **Groups** | FastAPI + SQLAlchemy | `groups.groups`, `groups.channels`, `groups.group_members` | Grupos/canales/miembros; expone `VerifyMembership` (método crítico) |
| 5 | **Messaging** | Django + Channels | `messaging.messages`, `messaging.message_statuses` | Persiste mensajes, sirve WebSocket, publica eventos a Kafka |
| 6 | **Files** | FastAPI | `files.files` (id, owner_id, url, mime, size) + volumen Docker | Upload + metadatos |
| 7 | **Notifications** | FastAPI + aiokafka | `notifications.audit_log` (opcional) | Consume Kafka y ejecuta efectos (push WS, auditoría) |

---

## 5. Contratos de comunicación

### 5.1 Kafka — topics y eventos

| Topic | Productor | Consumidor(es) | Payload |
|-------|-----------|----------------|---------|
| `messages.sent` | Messaging | Notifications | `{message_id, sender_id, type, group_id?, channel_id?, receiver_id?, content_preview, created_at}` |
| `messages.read` | Messaging | Notifications | `{message_id, reader_id, read_at}` |
| `presence.changed` | Messaging | Notifications, Users | `{user_id, status: online\|offline, timestamp}` |

Formato: JSON serializado, un evento por mensaje. 1 broker, 1 partición por topic (sin replicación — aceptable para el sprint).

### 5.2 gRPC — métodos por servicio

**Auth Service** (`auth.proto`)
- `Register(username, email, password) → (user_id, tokens)`
- `Login(username, password) → (access_token, refresh_token)`
- `Refresh(refresh_token) → (access_token, refresh_token)`
- `Logout(refresh_token) → ok`
- `ValidateToken(token) → (user_id, username, expires_at)`
- `GetUserById(user_id) → (id, username, email)`
- `GetUserByUsername(username) → (id, username, email)`

**Users Service** (`users.proto`)
- `GetProfile(user_id) → (user_id, username, avatar_url, bio, last_seen)`
- `SearchUsers(query, limit) → repeated UserSummary`
- `UpdateLastSeen(user_id, timestamp) → ok`

**Groups Service** (`groups.proto`)
- `CreateGroup(owner_id, name, description, subscription_type) → Group`
- `GetGroup(group_id) → Group`
- `UpdateGroup(group_id, fields) → Group`
- `DeleteGroup(group_id) → ok`
- `JoinGroup(user_id, group_id) → ok`
- `LeaveGroup(user_id, group_id) → ok`
- `ListMembers(group_id) → repeated Member`
- `AddMember(group_id, user_id) → ok`
- `RemoveMember(group_id, user_id) → ok`
- `ChangeRole(group_id, user_id, role) → ok`
- `ListChannels(group_id) → repeated Channel`
- `CreateChannel(group_id, name, description) → Channel`
- `GetChannel(channel_id) → (channel, group_id)`
- `VerifyMembership(user_id, group_id) → (is_member, role)` — **método crítico**, llamado por Messaging en cada envío
- `ListUserGroups(user_id) → repeated GroupSummary`

**Messaging Service** (`messaging.proto`)
- `PushDirectMessage(user_id, payload) → ok` — llamado por Notifications para empujar un evento al WebSocket del receptor
- `GetMessageHistory(scope, cursor, limit) → (messages, next_cursor)` — unificado; `scope = {group_id | channel_id | private_with_user_id}`
- `ListConversations(user_id) → repeated ConversationSummary`

**Files Service** (`files.proto`)
- `GetFileMetadata(file_id) → (url, mime, size, owner_id)`
- (upload va por REST, no gRPC)

**Notifications Service** — no expone gRPC, solo consume Kafka.

### 5.3 Gateway — rutas REST

Se preservan las rutas del README actual. Todas terminan en llamadas gRPC internas, excepto las dos siguientes:

| Ruta | Método | Transporte interno |
|------|--------|---------------------|
| `POST /api/files/upload` | — | **HTTP proxy** al Files Service (multipart no se fuerza por gRPC) |
| `GET /ws/chat/?token=<...>` | — | **Conexión WS directa** al Messaging Service (el Gateway no proxya WebSocket) |

Todas las demás rutas (`/api/auth/*`, `/api/users/*`, `/api/groups/*`, `/api/messages/*`) son Gateway (REST) → servicio interno (gRPC).

---

## 6. Autenticación y propagación de identidad

### 6.1 Flujos

- **Login:** `POST /api/auth/login` → Gateway → `Auth.Login` (gRPC) → JWT al browser.
- **Request autenticado HTTP:** Browser envía `Authorization: Bearer <token>` → Gateway llama `Auth.ValidateToken` (gRPC) → extrae `user_id` → lo propaga al servicio destino como metadata gRPC `x-user-id`.
- **WebSocket:** Browser conecta `ws://host/ws/chat/?token=...` directo a Messaging → Messaging llama `Auth.ValidateToken` (gRPC) en el handshake → guarda `user_id` en scope de conexión.
- **gRPC servicio → servicio:** Se propaga `x-user-id` como metadata. Para llamadas iniciadas por consumers Kafka se usa `x-system-call: <nombre-servicio>` (no hay usuario humano detrás).

### 6.2 Modelo de confianza

- Puertos gRPC internos NO expuestos al host (solo dentro de la red Docker).
- Gateway es el único validador de JWT para HTTP; Messaging lo es para WebSocket.
- Servicios internos confían en la metadata del llamante — no re-validan el token.

### 6.3 JWT lifetimes

Se preservan los actuales: **access 30 min, refresh 7 días, rotación de refresh, blacklist al logout**. Auth Service mantiene la blacklist.

---

## 7. Estrategia de datos

- **Un solo Postgres**, con 5 schemas (`auth`, `users`, `groups`, `messaging`, `files`). Cada servicio conecta con un user de DB que tiene permisos solo sobre su schema.
- **FKs cross-service prohibidas.** `messaging.messages.sender_id` es un `UUID` sin FK; la integridad se garantiza por flujo (JWT válido ⇒ usuario existe).
- **Sin duplicación.** Notifications NO persiste usuarios ni grupos; si necesita datos, los lee vía gRPC.
- **Nuke & seed.** No se migran datos del monolito. El monolito se conserva en rama `legacy/monolith`. La nueva arquitectura arranca con schemas vacíos + script `seed.py` que crea usuarios, grupos, canales y mensajes de prueba para la demo.

---

## 8. División del trabajo

### 8.1 Persona A — "Infra/Edge"

**Entregables:**
- Monorepo con estructura `services/{gateway,auth,users,groups,messaging,files,notifications}/` + `proto/`
- `docker-compose.yml` con todos los servicios + Postgres + Kafka + Zookeeper, con healthchecks y `depends_on`
- Schemas de Postgres pre-creados por un script de init
- **API Gateway (FastAPI):**
  - Middleware de validación JWT vía `Auth.ValidateToken`
  - Cliente gRPC hacia cada servicio interno
  - Mapeo de todas las rutas `/api/*` a llamadas gRPC
  - Proxy HTTP para `POST /api/files/upload`
  - Configuración CORS y manejo de errores unificado
- `seed.py` (datos de prueba) y `e2e_demo.py` (script end-to-end)
- `.proto` files compartidos y script de compilación (`buf` o `grpc_tools.protoc`)

**Hitos:**
- Día 1: compose levanta todos los esqueletos; healthcheck "hello world" en cada servicio
- Día 3: Gateway enruta correctamente a Auth (login funcional) y Groups (listar/crear)
- Día 5: todas las rutas REST del Gateway pasan a servicios
- Día 7: `e2e_demo.py` pasa 5 veces seguidas

### 8.2 Persona B — "Identity/Domain"

**Entregables:**
- **Auth Service (Django + DRF-SimpleJWT):**
  - Migra `apps/authentication/` del monolito
  - Schema `auth.users` (solo id, username, email, password_hash)
  - Servidor gRPC con los 7 métodos listados en §5.2
  - Preserva rotación + blacklist de refresh tokens
  - Tests happy-path (login, register, validate)
- **Users Service (FastAPI + SQLAlchemy):**
  - Schema `users.user_profiles` (user_id, avatar, bio, last_seen)
  - Servidor gRPC con `GetProfile`, `SearchUsers`, `UpdateLastSeen`
  - `GetProfile` compone llamando a `Auth.GetUserById` internamente
  - Consumer opcional de `presence.changed` (si sobra tiempo) para actualizar `last_seen`
- **Groups Service (FastAPI + SQLAlchemy):**
  - Migra `apps/groups/`
  - Schemas `groups.groups`, `groups.channels`, `groups.group_members`
  - Servidor gRPC con los 15 métodos listados en §5.2
  - Tests happy-path de `VerifyMembership` (crítico para Messaging)

**Hitos:**
- Día 2: Auth funcional end-to-end vía Gateway; Groups CRUD funcional
- Día 3: `Groups.VerifyMembership` estable (Messaging lo va a llamar el mismo día)
- Día 5: búsqueda de usuarios y perfil completos

### 8.3 Persona C — "Realtime/Data"

**Entregables:**
- **Messaging Service (Django + Channels):**
  - Migra `apps/chat_messages/`
  - Schemas `messaging.messages`, `messaging.message_statuses`
  - Cliente gRPC hacia `Auth.ValidateToken` (para handshake WS) y `Groups.VerifyMembership` (antes de aceptar mensaje de grupo)
  - Servidor gRPC con `PushDirectMessage`, `GetMessageHistory`, `ListConversations`
  - Productor Kafka: publica `messages.sent`, `messages.read`, `presence.changed`
  - WebSocket consumer que preserva compatibilidad con el frontend existente (mismo formato de eventos)
- **Files Service (FastAPI):**
  - Migra `apps/files/`
  - Endpoint REST `POST /upload` (multipart)
  - Servidor gRPC con `GetFileMetadata`
  - Schema `files.files`; volumen Docker para storage
- **Notifications Service (FastAPI + aiokafka):**
  - Consumer de los 3 topics
  - Cuando llega `messages.sent` con `type=private`, llama a `Messaging.PushDirectMessage` (gRPC) para empujar al WS del receptor
  - Cuando llega `presence.changed`, llama a `Users.UpdateLastSeen` (gRPC)
  - Logs estructurados (para la demo: verse en pantalla)

**Hitos:**
- Día 3: mensajería persistida + WS funcionando con frontend actual
- Día 4: Kafka producer + Notifications consumer vivo (se ve evento viajando en logs)
- Día 5: Files upload funcional
- Día 6: flujo completo mensaje privado → Kafka → Notifications → WS del receptor

---

## 9. Cronograma

| Día | Objetivo del día | Hito al final |
|-----|------------------|---------------|
| 1 | Contratos + scaffolding | `.proto` acordados; compose levanta los 7 servicios con hello-world |
| 2 | Auth + Groups funcionales | Login vía Gateway; CRUD de grupos vía Gateway |
| 3 | Messaging + WS | Envío/recepción de mensajes; `VerifyMembership` llamado antes de aceptar |
| 4 | Kafka end-to-end | `messages.sent` viajando; Notifications empuja al WS del receptor |
| 5 | Users + Files + frontend | Búsqueda, perfil, upload de imagen; frontend apunta al Gateway |
| 6 | E2E testing + bug bash | `e2e_demo.py` estable |
| 7 | Polish + docs + ensayo | Diagrama final, README, rehearsal de sustentación |

---

## 10. Testing

- **Por servicio:** 1 test de happy-path por método gRPC crítico (`Login`, `ValidateToken`, `VerifyMembership`, `send_message`). Framework: `pytest` + `grpcio-testing`.
- **E2E:** script `e2e_demo.py` que, vía REST al gateway: registra 2 usuarios → crea grupo → agrega miembro → envía mensaje → verifica llegada por WS → verifica evento Kafka consumido en Notifications.
- **Criterio de éxito:** `e2e_demo.py` pasa 5 veces seguidas sin intervención manual antes del día 7.

---

## 11. Fuera de alcance (explícito)

Se omite deliberadamente y se documenta como "futuro":

- Kubernetes y orquestación más allá de docker-compose
- Service mesh, distributed tracing (solo logs locales)
- Rate limiting, circuit breakers, retries automáticos
- Redis channel layer (se mantiene InMemory → Messaging corre single-replica)
- TLS entre servicios (la red Docker es la frontera de confianza)
- Replicación de Kafka (1 broker, 1 partición por topic)
- Búsqueda full-text avanzada (se usa ILIKE en Postgres)
- Estado "delivered" de mensajes (se mantienen solo `sent` y `read`)
- Migración de datos del monolito (nuke + seed)
- CI/CD automatizado (despliegue manual con `docker compose up`)

---

## 12. Escenario de demo para la sustentación

1. **Registro:** dos usuarios se registran vía REST al Gateway.
2. **Creación de grupo:** uno crea un grupo y agrega al otro.
3. **Chat en vivo:** ambos conectados por WebSocket; al enviar mensaje se ve aparecer en tiempo real.
4. **Evidencia de Kafka:** en una terminal lateral, `kafka-console-consumer` muestra los eventos `messages.sent` fluyendo.
5. **Evidencia de gRPC:** `grpcui` renderiza los `.proto` y permite invocar `VerifyMembership` manualmente.
6. **Evidencia de arquitectura:** `docker ps` muestra los 7 contenedores + Postgres + Kafka + Zookeeper corriendo.

---

## 13. Riesgos y mitigaciones

| Riesgo | Probabilidad | Mitigación |
|--------|--------------|------------|
| WebSocket + gRPC en Messaging es el punto más complejo; puede consumir más de 1 día | Alta | Persona C empieza Messaging desde día 2, no día 3; si bloquea, Persona A apoya |
| Kafka setup inicial (Zookeeper, topics) consume tiempo | Media | Persona A entrega Kafka corriendo desde día 1; topics creados por script de init |
| Cambios en `.proto` rompen integraciones mid-sprint | Media | Los 3 `.proto` principales (auth, groups, messaging) se congelan al final del día 1 |
| Frontend rompe al re-apuntar al Gateway | Media | Se mantienen rutas idénticas a la API actual; solo cambia el host |
| Algún método gRPC descubierto tarde como necesario | Baja | Buffer del día 6 absorbe extensiones menores |

---

## 14. Decisiones abiertas

Ninguna bloqueante. Todas las decisiones técnicas están tomadas en este documento.

Si durante la implementación aparece una decisión nueva (ej. qué versión de Kafka usar, qué librería de gRPC en Python), se toma en el momento y se documenta en un changelog al final de este spec.
