# GroupsApp — Microservices Edition

Reescritura de GroupsApp como arquitectura de microservicios con Kafka, REST y gRPC.

Ver `../groupsapp/docs/superpowers/specs/2026-04-17-microservices-migration-design.md` para el diseño completo.

## Quick start

```bash
cp .env.example .env
./scripts/compile_proto.sh
docker compose up -d
python scripts/smoke_test.py
python scripts/e2e_demo.py
```

## Servicios

| # | Servicio | Puerto gRPC | Puerto HTTP |
|---|----------|-------------|-------------|
| 1 | gateway | — | 8000 |
| 2 | auth | 50051 | — |
| 3 | users | 50052 | 8003 (profile REST) |
| 4 | groups | 50053 | — |
| 5 | messaging | 50054 | 8001 (WS) |
| 6 | files | 50055 | 8002 (upload) |
| 7 | notifications | — | — (Kafka consumer) |

## Planes completados

### Plan 1 — Foundation ✅

- [x] Monorepo con 7 servicios
- [x] Proto contracts congelados en `proto/` (auth, users, groups, messaging, files, common)
- [x] PostgreSQL con 6 schemas (auth, users, groups, messaging, files, notifications)
- [x] Kafka con 3 topics (messages.sent, messages.read, presence.changed)
- [x] 7 servicios respondiendo (gRPC Healthcheck o HTTP /health)
- [x] `scripts/smoke_test.py` pasa

### Plan 2 — Auth + Gateway ✅

- [x] Register/login/refresh/logout end-to-end via Gateway
- [x] JWT validation en Gateway (Bearer token → gRPC Auth.ValidateToken)
- [x] Gateway CRUD de grupos, mensajes, archivos, usuarios

### Plan 3 — Users + Groups ✅

- [x] CRUD grupos completo via Gateway → Groups gRPC
- [x] Membership (join/leave/add/remove/change-role/verify)
- [x] Canales dentro de grupos
- [x] Users search y perfil via Gateway → Users gRPC

### Plan 4 — Kafka end-to-end ✅

- [x] Messaging publica `messages.sent` a Kafka tras cada mensaje WS
- [x] Messaging publica `messages.read` a Kafka al marcar como leído
- [x] Messaging publica `presence.changed` al conectar/desconectar WS
- [x] Notifications consume `messages.sent` → push a receptor (privados) / push a todos los miembros (grupos)
- [x] Notifications consume `presence.changed` → actualiza `last_seen` via Users.UpdateLastSeen
- [x] PushDirectMessage gRPC → envía via channel layer al WS del usuario

### Plan 5 — Users + Files + Gateway completeness ✅

- [x] Users REST endpoint `PATCH /profile` para actualizar avatar y bio (proto congelado)
- [x] Users dual-server (gRPC :50052 + REST :8003)
- [x] Gateway `GET /api/users/me/profile` y `PATCH /api/users/me/profile`
- [x] Gateway `GET /api/users/{user_id}/profile`
- [x] Gateway CORS middleware habilitado
- [x] Files upload funcional via Gateway → Files REST
- [x] Files metadata via Gateway → Files gRPC
- [x] `scripts/e2e_demo.py` — script de demo end-to-end

### Contratos gRPC (congelados)
Cualquier cambio a `proto/*.proto` requiere re-compilación y coordinación de equipo.

## API Gateway Endpoints

### Auth
- `POST /api/auth/register` — Register
- `POST /api/auth/login` — Login
- `POST /api/auth/refresh` — Refresh JWT
- `POST /api/auth/logout` — Logout

### Users
- `GET /api/users/me` — Get current user (basic info)
- `GET /api/users/me/profile` — Get full profile
- `PATCH /api/users/me/profile` — Update profile (avatar, bio)
- `GET /api/users/{user_id}/profile` — Get any user profile
- `GET /api/users/search?q=...` — Search users

### Groups
- `GET /api/groups/me` — List my groups
- `POST /api/groups` — Create group
- `GET /api/groups/{id}` — Get group
- `PATCH /api/groups/{id}` — Update group
- `DELETE /api/groups/{id}` — Delete group
- `POST /api/groups/{id}/join` — Join
- `POST /api/groups/{id}/leave` — Leave
- `GET /api/groups/{id}/members` — List members
- `POST /api/groups/{id}/members?user_id=...` — Add member
- `DELETE /api/groups/{id}/members/{uid}` — Remove member
- `PATCH /api/groups/{id}/members/{uid}/role` — Change role
- `GET /api/groups/{id}/channels` — List channels
- `POST /api/groups/{id}/channels` — Create channel
- `GET /api/groups/{id}/membership` — Verify membership

### Messages
- `GET /api/messages/history?group_id=...&limit=50` — Message history
- `GET /api/messages/conversations` — List conversations

### Files
- `POST /api/files/upload` — Upload file (multipart)
- `GET /api/files/{id}` — Get file metadata

### WebSocket
- `ws://host:8001/ws/chat/?token=JWT` — Real-time messaging
  - Send: `{"type": "message", "content": "...", "receiver_id": "...", "message_type": "text"}`
  - Send: `{"type": "message", "content": "...", "group_id": "...", "message_type": "text"}`
  - Send: `{"type": "read", "message_id": "..."}`
  - Receive: `{"type": "message", "message_id": "...", "sender_id": "...", "content": "..."}`
  - Receive: `{"event": "new_message", ...}` (push notification)
  - Receive: `{"event": "message_read", ...}` (read receipt)
