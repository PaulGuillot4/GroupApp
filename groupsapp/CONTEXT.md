# CONTEXT.md – Decisiones Técnicas de GroupsApp

Este documento explica las decisiones técnicas detrás de la arquitectura del proyecto.
Se actualiza conforme se realizan cambios significativos.

---

## ¿Por qué Django monolítico?

**Decisión:** Una sola aplicación Django sirve la API REST, los WebSockets (Django Channels), y el frontend (templates + JS).

**Razón:** Para un proyecto universitario de telemática, un monolito es:
- Más simple de desplegar (un solo contenedor Docker)
- Más fácil de mantener por un equipo pequeño
- Suficiente para el volumen de tráfico esperado

**Trade-off:** Si el proyecto escala a miles de usuarios concurrentes, se debería considerar separar los WebSockets en un servicio independiente con Redis como channel layer.

---

## ¿Por qué InMemory Channel Layer?

**Decisión:** Se usa `channels.layers.InMemoryChannelLayer` en lugar de Redis.

**Razón:** 
- Elimina la dependencia de Redis durante el desarrollo
- Funciona bien para un solo proceso Daphne
- Reduce la complejidad del `docker-compose.yml`

**Limitación:** No funciona con múltiples workers/procesos. Para producción real, cambiar a `channels_redis.core.RedisChannelLayer` con un servicio Redis en docker-compose.

---

## Estrategia de Autenticación: JWT

**Decisión:** JWT (JSON Web Tokens) vía `djangorestframework-simplejwt`.

**Razón:**
- Stateless → no requiere sesiones en el servidor
- Los tokens se envían por header `Authorization: Bearer <token>`
- Para WebSockets, el token se pasa como query parameter `?token=<access_token>` ya que los headers no están disponibles en la conexión WS del navegador

**Seguridad:**
- Los tokens de acceso expiran en 30 minutos
- Los tokens de refresh duran 7 días y rotan automáticamente
- Los tokens de refresh se blacklistan al hacer logout o al rotar

---

## Estructura de WebSocket Events

El WebSocket usa un solo endpoint (`ws://host/ws/chat/?token=<token>`) para todo tipo de chat.

### Client → Server (acciones)
| Acción | Descripción |
|--------|-------------|
| `join_room` | Unirse a una sala (formato: `group_<uuid>`, `private_<id1>_<id2>`, `channel_<uuid>`) |
| `send_message` | Enviar un mensaje a la sala activa |
| `typing` | Notificar que el usuario está escribiendo |
| `mark_as_read` | Marcar un mensaje como leído |
| `set_presence` | Actualizar estado online/offline |

### Server → Client (eventos)
| Evento | Descripción |
|--------|-------------|
| `new_message` | Nuevo mensaje en una sala |
| `message_delivered` | Un mensaje fue entregado |
| `message_read` | Un mensaje fue leído |
| `user_typing` | Otro usuario está escribiendo |
| `presence_update` | Cambio de estado online/offline |

---

## Arquitectura de Código (Post-Refactorización)

```
apps/
├── core/                  # Módulo compartido (responses, exceptions, handler)
├── authentication/        # Login, register, logout, refresh (sin modelos propios)
├── users/                 # Modelo User, serializers, búsqueda
├── groups/                # Modelos Group/Channel/Member + services + permissions
├── chat_messages/         # Modelos Message/Status + WebSocket consumer + middleware
├── files/                 # Subida de archivos con validación
└── frontend/              # Templates Django (login, register, chat)
```

**Principios aplicados:**
- **SRP**: Cada vista hace una sola cosa. La lógica de negocio vive en `services.py`.
- **DRY**: `apps.core.responses.api_error_response()` se usa en todas las vistas.
- **Separación de capas**: Views → Services → Models.
- **Zero Secrets**: Todas las credenciales se cargan desde `.env` via `python-dotenv`.

---

## Stack Tecnológico

| Componente | Tecnología | Versión |
|-----------|-----------|---------|
| Backend | Django + DRF | 4.2.x |
| WebSockets | Django Channels + Daphne | 4.x |
| Auth | djangorestframework-simplejwt | 5.x |
| Base de Datos | PostgreSQL | 15 |
| Frontend | Tailwind CSS (CDN) + Vanilla JS | 3.x |
| Contenedores | Docker + Docker Compose | - |
| ASGI Server | Daphne | 4.x |
