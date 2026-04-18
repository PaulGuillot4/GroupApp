# GroupsApp — Microservices Edition

Reescritura de GroupsApp como arquitectura de microservicios con Kafka, REST y gRPC.

Ver `../groupsapp/docs/superpowers/specs/2026-04-17-microservices-migration-design.md` para el diseño completo.

## Quick start

```bash
cp .env.example .env
./scripts/compile_proto.sh
docker compose up -d
python scripts/smoke_test.py
```

## Servicios

| # | Servicio | Puerto gRPC | Puerto HTTP |
|---|----------|-------------|-------------|
| 1 | gateway | — | 8000 |
| 2 | auth | 50051 | — |
| 3 | users | 50052 | — |
| 4 | groups | 50053 | — |
| 5 | messaging | 50054 | 8001 (WS) |
| 6 | files | 50055 | 8002 (upload) |
| 7 | notifications | 50056 | — |

## Plan 1 — Foundation (completado)

- [x] Monorepo con 7 servicios
- [x] Proto contracts congelados en `proto/` (auth, users, groups, messaging, files, common)
- [x] PostgreSQL con 6 schemas (auth, users, groups, messaging, files, notifications)
- [x] Kafka con 3 topics (messages.sent, messages.read, presence.changed)
- [x] 7 servicios respondiendo (gRPC Healthcheck o HTTP /health)
- [x] `scripts/smoke_test.py` pasa

### Contratos gRPC (congelados)
Cualquier cambio a `proto/*.proto` requiere re-compilación y coordinación de equipo.

## Próximos planes
- **Plan 2** — Auth + Gateway (login/register end-to-end)
- **Plan 3** — Users + Groups (CRUD y membership)
- **Plan 4** — Messaging + Kafka + Notifications
- **Plan 5** — Files + E2E + Demo
