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
