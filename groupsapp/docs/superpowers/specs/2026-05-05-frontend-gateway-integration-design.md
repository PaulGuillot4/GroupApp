# Frontend Gateway Integration Design

**Fecha:** 2026-05-05
**Objetivo:** Servir el frontend completo (HTML/JS/CSS) desde el Gateway de microservicios en `localhost:8000`, con paridad total de funcionalidad WebSocket respecto al monolito original.

---

## 1. Contexto

`groupsapp-ms/` tiene un Gateway FastAPI (puerto 8000) que expone una REST API completa, pero no sirve ninguna interfaz web. El frontend existe en `groupsapp/` como templates Django con un `chat.js` de 1130 líneas que maneja toda la lógica del cliente.

El objetivo es que el usuario pueda abrir `http://localhost:8000` y usar la aplicación completa sin necesitar el monolito `groupsapp/` corriendo.

---

## 2. Arquitectura destino

```
Browser (localhost:8000)
    │
    ├── GET /  /auth/login/  /auth/register/  /app/
    │       └── Gateway sirve Jinja2 templates
    │
    ├── GET /static/*
    │       └── Gateway sirve StaticFiles (JS/CSS)
    │
    ├── /api/*  (REST)
    │       └── Gateway → gRPC services (ya implementado)
    │
    ├── GET /media/{path}
    │       └── Gateway proxy HTTP → files:8002/files/{path}
    │
    └── WS /ws/chat/?token=JWT
            └── Gateway proxy WS → messaging:8001/ws/chat/?token=JWT
                                          │
                                    ChatConsumer (paridad total)
```

### Principio de puerto único
Solo el Gateway (8000) está expuesto al browser. Los puertos 8001 (Daphne/messaging) y 8002 (REST/files) son internos entre contenedores Docker.

---

## 3. Cambios por componente

### 3.1 Gateway — template y static serving

**Archivos nuevos:**
- `services/gateway/templates/base.html` — copiado del monolito
- `services/gateway/templates/auth/login.html` — copiado del monolito
- `services/gateway/templates/auth/register.html` — copiado del monolito
- `services/gateway/templates/app/chat.html` — copiado del monolito
- `services/gateway/static/js/chat.js` — copiado + ~12 líneas modificadas
- `services/gateway/static/css/chat.css` — copiado del monolito
- `services/gateway/static/css/app.css` — copiado del monolito
- `services/gateway/src/routes/frontend.py` — 4 rutas HTML
- `services/gateway/src/routes/ws_proxy.py` — proxy WebSocket bidireccional

**Archivos modificados:**
- `services/gateway/src/main.py` — montar StaticFiles, Jinja2Templates, incluir nuevos routers
- `services/gateway/src/routes/groups.py` — alias `GET /api/groups/`
- `services/gateway/src/routes/messages.py` — aliases rutas de historia
- `services/gateway/src/routes/files.py` — proxy `/media/{path}`
- `services/gateway/requirements.txt` — agregar `jinja2`, `websockets`, `aiofiles`
- `services/gateway/Dockerfile` — COPY templates/ y static/

### 3.2 Gateway — rutas HTML (`routes/frontend.py`)

| Ruta | Comportamiento |
|---|---|
| `GET /` | Redirige a `/auth/login/` |
| `GET /auth/login/` | Renderiza `auth/login.html` |
| `GET /auth/register/` | Renderiza `auth/register.html` |
| `GET /app/` | Renderiza `app/chat.html` |

### 3.3 Gateway — proxy WebSocket (`routes/ws_proxy.py`)

El Gateway recibe la conexión WebSocket en `/ws/chat/?token=JWT` y abre simultáneamente una conexión hacia `ws://messaging:8001/ws/chat/?token=JWT`, reenviando todos los frames en ambas direcciones (bidireccional). El token JWT viaja sin modificar — el ChatConsumer del messaging service sigue siendo responsable de validarlo.

```
Browser ←── WS frames ──→ Gateway (8000) ←── WS frames ──→ messaging:8001
```

Implementación: FastAPI WebSocket endpoint + `websockets` library para la conexión upstream.

### 3.4 Gateway — aliases REST

El `chat.js` usa rutas del monolito que difieren de las del ms. Se agregan aliases en los routers existentes:

| Ruta que usa chat.js | Alias apunta a |
|---|---|
| `GET /api/groups/` | `GroupsService.ListUserGroups` (user_id del JWT) |
| `GET /api/messages/group/<uuid>/` | `GetMessageHistory(group_id=uuid)` |
| `GET /api/messages/channel/<uuid>/` | `GetMessageHistory(channel_id=uuid)` |
| `GET /api/messages/private/<user_id>/` | `GetMessageHistory(private_with=user_id, requesting_user_id=JWT)` |

### 3.5 Gateway — proxy de archivos media

Nueva ruta en `routes/files.py`:

```
GET /media/{path}  →  proxy HTTP a files:8002/files/{path}
```

Variable de entorno `FILES_BASE_URL=http://localhost:8000/media` en el Gateway. Todas las subidas nuevas generan URLs del tipo `http://localhost:8000/media/<uuid>.ext`, accesibles desde el browser.

---

### 3.6 Messaging service — ChatConsumer (reescritura)

`services/messaging/chat/consumers.py` se reescribe para tener paridad total con el consumer del monolito.

#### Acciones cliente → servidor

| Acción (`type`) | Comportamiento |
|---|---|
| `join_room` | Valida acceso (miembro de grupo/canal/chat privado compartido), `group_add` al channel layer, marca mensajes previos como `delivered` |
| `send_message` | Crea `Message` en DB, `group_send` al room, maneja sala privada canónica, produce evento Kafka `messages.sent` |
| `typing` | `group_send` al room con `chat.user_typing` excluyendo al sender |
| `mark_as_read` | Actualiza `MessageStatus` a `read`, notifica al sender con `chat.message_read` |
| `set_presence` | `group_send` a todas las salas del usuario con `presence.update` |

#### Eventos servidor → cliente

| Evento channel layer | Método consumer | JSON al browser |
|---|---|---|
| `chat.new_message` | `chat_new_message` | `{type:"message", ...}` + auto-mark delivered |
| `chat.message_delivered` | `chat_message_delivered` | `{type:"delivered", message_id}` |
| `chat.message_read` | `chat_message_read` | `{type:"read", message_id}` |
| `chat.user_typing` | `chat_user_typing` | `{type:"typing", user_id}` |
| `presence.update` | `presence_update` | `{type:"presence", user_id, status, last_seen}` |
| `push_notification` | `push_notification` | `payload_json` (ya existe) |

#### Lifecycle

- **connect():** valida JWT, `group_add` a `user_<id>`, `group_add` a todos los grupos del usuario (vía `ListUserGroups` gRPC), acepta conexión
- **disconnect():** `group_discard` de todas las salas, envía `presence.update offline`, actualiza `last_seen` en DB

#### Nombres de sala

```python
"user_<id>"                          # sala personal
"group_<uuid>"                       # sala de grupo
"channel_<uuid>"                     # sala de canal
"private_" + "_".join(sorted([u1, u2]))  # sala privada canónica
```

El ms actual usaba `user_<receiver_id>` para mensajes privados — se corrige con la sala canónica ordenada.

---

### 3.7 chat.js — adaptaciones de formato de respuesta

El JS no cambia su lógica ni sus URLs (los aliases REST y el WS proxy hacen transparente el cambio). Solo se adaptan ~12 líneas donde el formato de respuesta difiere:

| Ubicación en chat.js | Monolito | MS |
|---|---|---|
| Perfil de usuario | `response.id` | `response.user_id` |
| Historia de mensajes | `response.results` | `response.messages` |
| Paginación | `response.next` (URL) | `response.next_cursor` (string vacío o cursor) |
| Conversations | `{id, type, last_message, ...}` | `{type, conversation_id, display_name, last_message_preview}` |

---

## 4. Docker-compose

### Cambios en `groupsapp-ms/docker-compose.yml`

**Quitar `ports:` de messaging y files** (solo accesibles internamente):
```yaml
messaging:
  # ports:        ← eliminar
  #   - "8001:8001"

files:
  # ports:        ← eliminar
  #   - "8002:8002"
```

**Agregar variables al gateway:**
```yaml
gateway:
  environment:
    FILES_BASE_URL: http://localhost:8000/media
    MESSAGING_WS: ws://messaging:8001
```

---

## 5. Definition of Done

- `docker compose up -d` en `groupsapp-ms/` levanta todo
- `http://localhost:8000` muestra la pantalla de login
- Register + Login funcionan y redirigen a `/app/`
- Chat en tiempo real funciona (enviar/recibir mensajes en grupos y privados)
- Typing indicator aparece cuando otro usuario escribe
- Ticks de entregado y leído se actualizan correctamente
- Subida de imágenes/archivos funciona y se muestran en el chat
- El monolito `groupsapp/` no necesita estar corriendo

---

## 6. Fuera de alcance

- Migrar el panel de administración Django (`/admin/`)
- Avatar de usuario (el ms no tiene endpoint de subida de avatar aún)
- HTTPS / producción (solo desarrollo local)
- Tests automatizados del frontend
