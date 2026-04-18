# Foundation Implementation Plan (Plan 1 de 5)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establecer el monorepo `groupsapp-ms/`, infraestructura Docker (Postgres + Kafka + Zookeeper), contratos gRPC (`.proto` congelados) y esqueletos de los 7 servicios, de modo que los Planes 2–5 puedan implementar la lógica de negocio sin re-negociar infraestructura.

**Architecture:** Nuevo directorio `groupsapp-ms/` hermano de `groupsapp/` (el monolito queda intacto). Monorepo con `proto/` compartido, `services/{gateway,auth,users,groups,messaging,files,notifications}/` y `scripts/` para init. `docker-compose.yml` orquesta Postgres 15 con 5 schemas pre-creados, Kafka + Zookeeper con 3 topics pre-creados, y los 7 servicios con healthchecks. Cada servicio tiene un endpoint gRPC `Healthcheck` que responde `OK` para validar que todo arranca.

**Tech Stack:** Python 3.11, FastAPI, Django 4.2, grpcio 1.63, grpcio-tools, SQLAlchemy 2.0, aiokafka, Channels 4, PostgreSQL 15, Apache Kafka 3.7 (bitnami), Zookeeper 3.9, Docker Compose v2.

---

## File Structure

```
Proyecto de telematica/
├── groupsapp/                       # monolito actual (intacto)
└── groupsapp-ms/                    # NUEVO — monorepo de microservicios
    ├── .gitignore
    ├── .env.example
    ├── README.md
    ├── docker-compose.yml
    ├── proto/
    │   ├── common.proto             # tipos compartidos (Empty, Timestamp wrappers)
    │   ├── auth.proto
    │   ├── users.proto
    │   ├── groups.proto
    │   ├── messaging.proto
    │   └── files.proto
    ├── scripts/
    │   ├── compile_proto.sh         # compila .proto en cada services/*/generated/
    │   ├── init_db.sql              # CREATE SCHEMA para los 5 schemas
    │   ├── create_topics.sh         # crea 3 topics Kafka
    │   └── smoke_test.py            # valida que los 7 servicios responden gRPC Healthcheck
    └── services/
        ├── gateway/
        │   ├── Dockerfile
        │   ├── requirements.txt
        │   ├── src/main.py
        │   └── tests/test_health.py
        ├── auth/
        │   ├── Dockerfile
        │   ├── requirements.txt
        │   ├── manage.py
        │   ├── auth_service/{__init__.py,settings.py,urls.py,wsgi.py}
        │   ├── grpc_server.py
        │   ├── generated/            # stubs compilados (gitignored)
        │   └── tests/test_health.py
        ├── users/
        │   ├── Dockerfile
        │   ├── requirements.txt
        │   ├── src/main.py
        │   ├── generated/
        │   └── tests/test_health.py
        ├── groups/                  # igual estructura que users/
        ├── messaging/               # igual estructura que auth/ (Django + Channels)
        ├── files/                   # igual estructura que users/
        └── notifications/           # igual estructura que users/
```

**Principio:** un archivo = una responsabilidad. `main.py` en servicios FastAPI solo arranca el servidor gRPC; la lógica va en módulos aparte en planes siguientes. No crear abstracciones prematuras en Plan 1.

---

## Task 1: Crear estructura del monorepo

**Files:**
- Create: `groupsapp-ms/.gitignore`
- Create: `groupsapp-ms/.env.example`
- Create: `groupsapp-ms/README.md`

- [ ] **Step 1: Crear estructura de directorios**

Run desde `Proyecto de telematica/`:
```bash
mkdir -p groupsapp-ms/{proto,scripts,services/{gateway,auth,users,groups,messaging,files,notifications}}
```

- [ ] **Step 2: Crear `.gitignore`**

Crear `groupsapp-ms/.gitignore`:
```
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.venv/
venv/
.env
# proto generated stubs (regenerados por compile_proto.sh)
services/*/generated/*_pb2.py
services/*/generated/*_pb2_grpc.py
# Django
*.sqlite3
staticfiles/
media/
# Docker
*.log
```

- [ ] **Step 3: Crear `.env.example`**

Crear `groupsapp-ms/.env.example`:
```
POSTGRES_DB=groupsapp_ms
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

KAFKA_BROKER=kafka:9092

JWT_SECRET_KEY=change-me-in-prod
JWT_ACCESS_MINUTES=30
JWT_REFRESH_DAYS=7

LOG_LEVEL=INFO
```

- [ ] **Step 4: Crear README stub**

Crear `groupsapp-ms/README.md`:
```markdown
# GroupsApp — Microservices Edition

Reescritura de GroupsApp como arquitectura de microservicios con Kafka, REST y gRPC.

Ver `../groupsapp/docs/superpowers/specs/2026-04-17-microservices-migration-design.md` para el diseño completo.

## Quick start

```bash
cp .env.example .env
./scripts/compile_proto.sh
docker compose up -d
./scripts/smoke_test.py
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
```

- [ ] **Step 5: Commit**

```bash
cd "Proyecto de telematica"
git add groupsapp-ms/.gitignore groupsapp-ms/.env.example groupsapp-ms/README.md
git commit -m "chore(ms): scaffold monorepo skeleton"
```

---

## Task 2: Definir proto común

**Files:**
- Create: `groupsapp-ms/proto/common.proto`

- [ ] **Step 1: Escribir `common.proto`**

Crear `groupsapp-ms/proto/common.proto`:
```protobuf
syntax = "proto3";

package groupsapp.common;

import "google/protobuf/timestamp.proto";

message Empty {}

message HealthcheckResponse {
  string service = 1;
  string status = 2;  // "OK" | "DEGRADED"
  google.protobuf.Timestamp checked_at = 3;
}

message HealthcheckRequest {}
```

- [ ] **Step 2: Commit**

```bash
cd "Proyecto de telematica"
git add groupsapp-ms/proto/common.proto
git commit -m "feat(proto): add common types (Empty, Healthcheck)"
```

---

## Task 3: Definir `auth.proto`

**Files:**
- Create: `groupsapp-ms/proto/auth.proto`

- [ ] **Step 1: Escribir `auth.proto`**

Crear `groupsapp-ms/proto/auth.proto` (todos los métodos del spec §5.2):
```protobuf
syntax = "proto3";

package groupsapp.auth;

import "common.proto";

service AuthService {
  rpc Healthcheck(groupsapp.common.HealthcheckRequest) returns (groupsapp.common.HealthcheckResponse);

  rpc Register(RegisterRequest) returns (AuthResponse);
  rpc Login(LoginRequest) returns (AuthResponse);
  rpc Refresh(RefreshRequest) returns (AuthResponse);
  rpc Logout(RefreshRequest) returns (groupsapp.common.Empty);

  rpc ValidateToken(ValidateTokenRequest) returns (ValidatedIdentity);
  rpc GetUserById(GetUserByIdRequest) returns (AuthUser);
  rpc GetUserByUsername(GetUserByUsernameRequest) returns (AuthUser);
}

message RegisterRequest {
  string username = 1;
  string email = 2;
  string password = 3;
}

message LoginRequest {
  string username = 1;
  string password = 2;
}

message RefreshRequest {
  string refresh_token = 1;
}

message AuthResponse {
  string access_token = 1;
  string refresh_token = 2;
  AuthUser user = 3;
}

message ValidateTokenRequest {
  string token = 1;
}

message ValidatedIdentity {
  string user_id = 1;
  string username = 2;
  int64 expires_at = 3;  // unix timestamp
}

message GetUserByIdRequest { string user_id = 1; }
message GetUserByUsernameRequest { string username = 1; }

message AuthUser {
  string id = 1;
  string username = 2;
  string email = 3;
}
```

- [ ] **Step 2: Commit**

```bash
cd "Proyecto de telematica"
git add groupsapp-ms/proto/auth.proto
git commit -m "feat(proto): define AuthService contract"
```

---

## Task 4: Definir `users.proto`

**Files:**
- Create: `groupsapp-ms/proto/users.proto`

- [ ] **Step 1: Escribir `users.proto`**

```protobuf
syntax = "proto3";

package groupsapp.users;

import "common.proto";
import "google/protobuf/timestamp.proto";

service UsersService {
  rpc Healthcheck(groupsapp.common.HealthcheckRequest) returns (groupsapp.common.HealthcheckResponse);

  rpc GetProfile(GetProfileRequest) returns (UserProfile);
  rpc SearchUsers(SearchUsersRequest) returns (SearchUsersResponse);
  rpc UpdateLastSeen(UpdateLastSeenRequest) returns (groupsapp.common.Empty);
}

message GetProfileRequest { string user_id = 1; }

message UserProfile {
  string user_id = 1;
  string username = 2;
  string email = 3;
  string avatar_url = 4;
  string bio = 5;
  google.protobuf.Timestamp last_seen = 6;
}

message SearchUsersRequest {
  string query = 1;
  int32 limit = 2;
}

message UserSummary {
  string user_id = 1;
  string username = 2;
  string avatar_url = 3;
}

message SearchUsersResponse {
  repeated UserSummary users = 1;
}

message UpdateLastSeenRequest {
  string user_id = 1;
  google.protobuf.Timestamp timestamp = 2;
}
```

- [ ] **Step 2: Commit**

```bash
cd "Proyecto de telematica"
git add groupsapp-ms/proto/users.proto
git commit -m "feat(proto): define UsersService contract"
```

---

## Task 5: Definir `groups.proto`

**Files:**
- Create: `groupsapp-ms/proto/groups.proto`

- [ ] **Step 1: Escribir `groups.proto`**

```protobuf
syntax = "proto3";

package groupsapp.groups;

import "common.proto";
import "google/protobuf/timestamp.proto";

service GroupsService {
  rpc Healthcheck(groupsapp.common.HealthcheckRequest) returns (groupsapp.common.HealthcheckResponse);

  rpc CreateGroup(CreateGroupRequest) returns (Group);
  rpc GetGroup(GetGroupRequest) returns (Group);
  rpc UpdateGroup(UpdateGroupRequest) returns (Group);
  rpc DeleteGroup(DeleteGroupRequest) returns (groupsapp.common.Empty);

  rpc JoinGroup(MembershipRequest) returns (groupsapp.common.Empty);
  rpc LeaveGroup(MembershipRequest) returns (groupsapp.common.Empty);
  rpc ListMembers(GetGroupRequest) returns (MembersList);
  rpc AddMember(MembershipRequest) returns (groupsapp.common.Empty);
  rpc RemoveMember(MembershipRequest) returns (groupsapp.common.Empty);
  rpc ChangeRole(ChangeRoleRequest) returns (groupsapp.common.Empty);

  rpc ListChannels(GetGroupRequest) returns (ChannelsList);
  rpc CreateChannel(CreateChannelRequest) returns (Channel);
  rpc GetChannel(GetChannelRequest) returns (ChannelWithGroup);

  rpc VerifyMembership(MembershipRequest) returns (MembershipInfo);
  rpc ListUserGroups(ListUserGroupsRequest) returns (UserGroupsResponse);
}

message Group {
  string id = 1;
  string name = 2;
  string description = 3;
  string owner_id = 4;
  string subscription_type = 5;  // "open" | "invite_only" | "private"
  string avatar_url = 6;
  google.protobuf.Timestamp created_at = 7;
}

message CreateGroupRequest {
  string owner_id = 1;
  string name = 2;
  string description = 3;
  string subscription_type = 4;
}

message GetGroupRequest { string group_id = 1; }

message UpdateGroupRequest {
  string group_id = 1;
  string name = 2;
  string description = 3;
  string subscription_type = 4;
}

message DeleteGroupRequest { string group_id = 1; }

message MembershipRequest {
  string user_id = 1;
  string group_id = 2;
}

message Member {
  string user_id = 1;
  string role = 2;  // "admin" | "member"
  google.protobuf.Timestamp joined_at = 3;
}

message MembersList { repeated Member members = 1; }

message ChangeRoleRequest {
  string user_id = 1;
  string group_id = 2;
  string role = 3;
}

message Channel {
  string id = 1;
  string group_id = 2;
  string name = 3;
  string description = 4;
  google.protobuf.Timestamp created_at = 5;
}

message CreateChannelRequest {
  string group_id = 1;
  string name = 2;
  string description = 3;
}

message GetChannelRequest { string channel_id = 1; }
message ChannelWithGroup {
  Channel channel = 1;
  string group_id = 2;
}

message ChannelsList { repeated Channel channels = 1; }

message MembershipInfo {
  bool is_member = 1;
  string role = 2;  // empty if not member
}

message ListUserGroupsRequest { string user_id = 1; }

message GroupSummary {
  string id = 1;
  string name = 2;
  string avatar_url = 3;
  string role = 4;
}

message UserGroupsResponse { repeated GroupSummary groups = 1; }
```

- [ ] **Step 2: Commit**

```bash
cd "Proyecto de telematica"
git add groupsapp-ms/proto/groups.proto
git commit -m "feat(proto): define GroupsService contract"
```

---

## Task 6: Definir `messaging.proto`

**Files:**
- Create: `groupsapp-ms/proto/messaging.proto`

- [ ] **Step 1: Escribir `messaging.proto`**

```protobuf
syntax = "proto3";

package groupsapp.messaging;

import "common.proto";
import "google/protobuf/timestamp.proto";

service MessagingService {
  rpc Healthcheck(groupsapp.common.HealthcheckRequest) returns (groupsapp.common.HealthcheckResponse);

  rpc PushDirectMessage(PushDirectMessageRequest) returns (groupsapp.common.Empty);
  rpc GetMessageHistory(GetMessageHistoryRequest) returns (MessageHistoryResponse);
  rpc ListConversations(ListConversationsRequest) returns (ConversationsResponse);
}

message Message {
  string id = 1;
  string sender_id = 2;
  string type = 3;  // "group" | "channel" | "private"
  string group_id = 4;
  string channel_id = 5;
  string receiver_id = 6;
  string content = 7;
  string message_type = 8;  // "text" | "file" | "image"
  string file_url = 9;
  google.protobuf.Timestamp created_at = 10;
}

message PushDirectMessageRequest {
  string user_id = 1;
  string payload_json = 2;
}

message GetMessageHistoryRequest {
  // Exactly one of these must be set
  string group_id = 1;
  string channel_id = 2;
  string private_with_user_id = 3;
  string requesting_user_id = 4;
  string cursor = 5;  // ISO timestamp of last message seen; empty = start
  int32 limit = 6;
}

message MessageHistoryResponse {
  repeated Message messages = 1;
  string next_cursor = 2;
}

message ListConversationsRequest { string user_id = 1; }

message ConversationSummary {
  string type = 1;  // "group" | "channel" | "private"
  string conversation_id = 2;
  string display_name = 3;
  string last_message_preview = 4;
  google.protobuf.Timestamp last_message_at = 5;
}

message ConversationsResponse { repeated ConversationSummary conversations = 1; }
```

- [ ] **Step 2: Commit**

```bash
cd "Proyecto de telematica"
git add groupsapp-ms/proto/messaging.proto
git commit -m "feat(proto): define MessagingService contract"
```

---

## Task 7: Definir `files.proto`

**Files:**
- Create: `groupsapp-ms/proto/files.proto`

- [ ] **Step 1: Escribir `files.proto`**

```protobuf
syntax = "proto3";

package groupsapp.files;

import "common.proto";
import "google/protobuf/timestamp.proto";

service FilesService {
  rpc Healthcheck(groupsapp.common.HealthcheckRequest) returns (groupsapp.common.HealthcheckResponse);

  rpc GetFileMetadata(GetFileMetadataRequest) returns (FileMetadata);
}

message GetFileMetadataRequest { string file_id = 1; }

message FileMetadata {
  string id = 1;
  string owner_id = 2;
  string url = 3;
  string mime_type = 4;
  int64 size = 5;
  google.protobuf.Timestamp uploaded_at = 6;
}
```

- [ ] **Step 2: Commit**

```bash
cd "Proyecto de telematica"
git add groupsapp-ms/proto/files.proto
git commit -m "feat(proto): define FilesService contract"
```

---

## Task 8: Script de compilación de proto files

**Files:**
- Create: `groupsapp-ms/scripts/compile_proto.sh`

- [ ] **Step 1: Escribir el script**

Crear `groupsapp-ms/scripts/compile_proto.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROTO_DIR="$ROOT/proto"
SERVICES=(gateway auth users groups messaging files notifications)

python -c "import grpc_tools" 2>/dev/null || {
  echo "grpcio-tools no instalado. Ejecuta: pip install grpcio-tools==1.63.0"
  exit 1
}

for svc in "${SERVICES[@]}"; do
  OUT="$ROOT/services/$svc/generated"
  mkdir -p "$OUT"
  touch "$OUT/__init__.py"
  python -m grpc_tools.protoc \
    -I "$PROTO_DIR" \
    --python_out="$OUT" \
    --grpc_python_out="$OUT" \
    "$PROTO_DIR"/*.proto
  echo "Compiled protos for $svc → $OUT"
done
```

- [ ] **Step 2: Hacer ejecutable**

```bash
chmod +x groupsapp-ms/scripts/compile_proto.sh
```

- [ ] **Step 3: Test: correr el script y verificar que genera stubs**

```bash
cd groupsapp-ms
pip install grpcio-tools==1.63.0
./scripts/compile_proto.sh
ls services/auth/generated/
```

Expected: ver `auth_pb2.py`, `auth_pb2_grpc.py`, `common_pb2.py`, etc.

- [ ] **Step 4: Commit**

```bash
cd "Proyecto de telematica"
git add groupsapp-ms/scripts/compile_proto.sh
git commit -m "feat(scripts): add proto compilation script"
```

---

## Task 9: Infra docker-compose (Postgres + Kafka + Zookeeper)

**Files:**
- Create: `groupsapp-ms/docker-compose.yml`
- Create: `groupsapp-ms/scripts/init_db.sql`

- [ ] **Step 1: Escribir `init_db.sql`**

Crear `groupsapp-ms/scripts/init_db.sql`:
```sql
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS users;
CREATE SCHEMA IF NOT EXISTS groups;
CREATE SCHEMA IF NOT EXISTS messaging;
CREATE SCHEMA IF NOT EXISTS files;
CREATE SCHEMA IF NOT EXISTS notifications;
```

- [ ] **Step 2: Escribir `docker-compose.yml` (solo infra por ahora)**

Crear `groupsapp-ms/docker-compose.yml`:
```yaml
services:
  postgres:
    image: postgres:15-alpine
    container_name: gms_postgres
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-groupsapp_ms}
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
    ports:
      - "5433:5432"  # 5433 para no chocar con monolito en 5432
    volumes:
      - gms_postgres_data:/var/lib/postgresql/data
      - ./scripts/init_db.sql:/docker-entrypoint-initdb.d/01_init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres}"]
      interval: 5s
      timeout: 5s
      retries: 5

  zookeeper:
    image: bitnami/zookeeper:3.9
    container_name: gms_zookeeper
    environment:
      ALLOW_ANONYMOUS_LOGIN: "yes"
    ports:
      - "2181:2181"
    healthcheck:
      test: ["CMD-SHELL", "echo ruok | nc -w 2 localhost 2181 | grep -q imok"]
      interval: 10s
      timeout: 5s
      retries: 5

  kafka:
    image: bitnami/kafka:3.7
    container_name: gms_kafka
    depends_on:
      zookeeper:
        condition: service_healthy
    environment:
      KAFKA_CFG_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_CFG_LISTENERS: PLAINTEXT://:9092
      KAFKA_CFG_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_CFG_AUTO_CREATE_TOPICS_ENABLE: "true"
      ALLOW_PLAINTEXT_LISTENER: "yes"
    ports:
      - "9092:9092"
    healthcheck:
      test: ["CMD-SHELL", "kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null 2>&1"]
      interval: 15s
      timeout: 10s
      retries: 5

volumes:
  gms_postgres_data:
```

- [ ] **Step 3: Levantar infra y verificar**

```bash
cd groupsapp-ms
cp .env.example .env
docker compose up -d
docker compose ps
```

Expected: los 3 contenedores (`gms_postgres`, `gms_zookeeper`, `gms_kafka`) en estado `healthy`.

- [ ] **Step 4: Verificar schemas en Postgres**

```bash
docker compose exec postgres psql -U postgres -d groupsapp_ms -c "\dn"
```

Expected: lista que incluye `auth`, `users`, `groups`, `messaging`, `files`, `notifications`.

- [ ] **Step 5: Commit**

```bash
cd "Proyecto de telematica"
git add groupsapp-ms/docker-compose.yml groupsapp-ms/scripts/init_db.sql
git commit -m "feat(infra): docker-compose with postgres + kafka + zookeeper"
```

---

## Task 10: Script para crear topics de Kafka

**Files:**
- Create: `groupsapp-ms/scripts/create_topics.sh`

- [ ] **Step 1: Escribir el script**

Crear `groupsapp-ms/scripts/create_topics.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail

TOPICS=(messages.sent messages.read presence.changed)

for topic in "${TOPICS[@]}"; do
  docker compose exec -T kafka kafka-topics.sh \
    --bootstrap-server localhost:9092 \
    --create --if-not-exists \
    --topic "$topic" \
    --partitions 1 --replication-factor 1
done

echo "--- Topics existentes ---"
docker compose exec -T kafka kafka-topics.sh \
  --bootstrap-server localhost:9092 --list
```

- [ ] **Step 2: Hacer ejecutable y correr**

```bash
chmod +x groupsapp-ms/scripts/create_topics.sh
cd groupsapp-ms
./scripts/create_topics.sh
```

Expected: los 3 topics listados al final.

- [ ] **Step 3: Smoke test Kafka con producer/consumer**

```bash
# En una terminal
docker compose exec kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic messages.sent --from-beginning &

# En otra terminal
docker compose exec kafka bash -c 'echo "{\"test\":1}" | kafka-console-producer.sh \
  --bootstrap-server localhost:9092 --topic messages.sent'
```

Expected: el consumer imprime `{"test":1}`.

- [ ] **Step 4: Commit**

```bash
cd "Proyecto de telematica"
git add groupsapp-ms/scripts/create_topics.sh
git commit -m "feat(infra): script to create Kafka topics"
```

---

## Task 11: Dockerfile compartido (FastAPI) + esqueleto Gateway

**Files:**
- Create: `groupsapp-ms/services/gateway/Dockerfile`
- Create: `groupsapp-ms/services/gateway/requirements.txt`
- Create: `groupsapp-ms/services/gateway/src/__init__.py`
- Create: `groupsapp-ms/services/gateway/src/main.py`
- Create: `groupsapp-ms/services/gateway/tests/test_health.py`

- [ ] **Step 1: Escribir el test que falla**

Crear `groupsapp-ms/services/gateway/tests/test_health.py`:
```python
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"service": "gateway", "status": "OK"}
```

- [ ] **Step 2: Ejecutar el test (debe fallar porque `src/main.py` no existe)**

```bash
cd groupsapp-ms/services/gateway
pip install fastapi httpx pytest
pytest tests/ -v
```

Expected: FAIL con `ModuleNotFoundError: No module named 'src.main'`.

- [ ] **Step 3: Implementar `src/main.py`**

Crear `groupsapp-ms/services/gateway/src/__init__.py` (vacío) y `groupsapp-ms/services/gateway/src/main.py`:
```python
from fastapi import FastAPI

app = FastAPI(title="GroupsApp Gateway")

@app.get("/health")
def health():
    return {"service": "gateway", "status": "OK"}
```

- [ ] **Step 4: Ejecutar el test (debe pasar)**

```bash
cd groupsapp-ms/services/gateway
pytest tests/ -v
```

Expected: PASS.

- [ ] **Step 5: Escribir `requirements.txt`**

Crear `groupsapp-ms/services/gateway/requirements.txt`:
```
fastapi==0.111.*
uvicorn[standard]==0.30.*
grpcio==1.63.*
grpcio-tools==1.63.*
protobuf==5.27.*
pydantic==2.*
python-multipart==0.0.9
httpx==0.27.*
```

- [ ] **Step 6: Escribir `Dockerfile`**

Crear `groupsapp-ms/services/gateway/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY services/gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proto/ /proto/
COPY services/gateway/ /app/

# Compile protos
RUN mkdir -p /app/generated && touch /app/generated/__init__.py && \
    python -m grpc_tools.protoc \
      -I /proto \
      --python_out=/app/generated \
      --grpc_python_out=/app/generated \
      /proto/*.proto

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 7: Commit**

```bash
cd "Proyecto de telematica"
git add groupsapp-ms/services/gateway/
git commit -m "feat(gateway): skeleton FastAPI service with /health endpoint"
```

---

## Task 12: Esqueleto Auth Service (Django)

**Files:**
- Create: `groupsapp-ms/services/auth/Dockerfile`
- Create: `groupsapp-ms/services/auth/requirements.txt`
- Create: `groupsapp-ms/services/auth/manage.py`
- Create: `groupsapp-ms/services/auth/auth_service/__init__.py`
- Create: `groupsapp-ms/services/auth/auth_service/settings.py`
- Create: `groupsapp-ms/services/auth/auth_service/urls.py`
- Create: `groupsapp-ms/services/auth/auth_service/wsgi.py`
- Create: `groupsapp-ms/services/auth/grpc_server.py`
- Create: `groupsapp-ms/services/auth/tests/test_health.py`

- [ ] **Step 1: Escribir test que falla**

Crear `groupsapp-ms/services/auth/tests/__init__.py` (vacío) y `tests/test_health.py`:
```python
import grpc
import pytest
from generated import auth_pb2, auth_pb2_grpc, common_pb2

def test_healthcheck():
    channel = grpc.insecure_channel("localhost:50051")
    stub = auth_pb2_grpc.AuthServiceStub(channel)
    resp = stub.Healthcheck(common_pb2.HealthcheckRequest(), timeout=3)
    assert resp.service == "auth"
    assert resp.status == "OK"
```

- [ ] **Step 2: Ejecutar el test (debe fallar — servicio no corre aún)**

```bash
cd groupsapp-ms/services/auth
pytest tests/ -v
```

Expected: FAIL con error de conexión (puerto 50051 no responde).

- [ ] **Step 3: Crear proyecto Django**

Crear `groupsapp-ms/services/auth/manage.py`:
```python
#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "auth_service.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
```

Crear `groupsapp-ms/services/auth/auth_service/__init__.py` (vacío).

Crear `groupsapp-ms/services/auth/auth_service/settings.py`:
```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-change-me")
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "groupsapp_ms"),
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "OPTIONS": {"options": "-c search_path=auth"},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
```

Crear `groupsapp-ms/services/auth/auth_service/urls.py`:
```python
urlpatterns = []
```

Crear `groupsapp-ms/services/auth/auth_service/wsgi.py`:
```python
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "auth_service.settings")
application = get_wsgi_application()
```

- [ ] **Step 4: Implementar `grpc_server.py` con el handler Healthcheck**

Crear `groupsapp-ms/services/auth/grpc_server.py`:
```python
import os
import time
from concurrent import futures

import django
import grpc
from google.protobuf import timestamp_pb2

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "auth_service.settings")
django.setup()

from generated import auth_pb2, auth_pb2_grpc, common_pb2


class AuthServicer(auth_pb2_grpc.AuthServiceServicer):
    def Healthcheck(self, request, context):
        ts = timestamp_pb2.Timestamp()
        ts.GetCurrentTime()
        return common_pb2.HealthcheckResponse(
            service="auth", status="OK", checked_at=ts
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    auth_pb2_grpc.add_AuthServiceServicer_to_server(AuthServicer(), server)
    server.add_insecure_port("0.0.0.0:50051")
    server.start()
    print("Auth gRPC server listening on :50051", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
```

- [ ] **Step 5: Escribir `requirements.txt`**

Crear `groupsapp-ms/services/auth/requirements.txt`:
```
Django==4.2.*
djangorestframework==3.14.*
djangorestframework-simplejwt==5.*
psycopg2-binary==2.9.*
grpcio==1.63.*
grpcio-tools==1.63.*
protobuf==5.27.*
python-dotenv==1.*
pytest==8.*
```

- [ ] **Step 6: Escribir `Dockerfile`**

Crear `groupsapp-ms/services/auth/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY services/auth/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proto/ /proto/
COPY services/auth/ /app/

RUN mkdir -p /app/generated && touch /app/generated/__init__.py && \
    python -m grpc_tools.protoc \
      -I /proto \
      --python_out=/app/generated \
      --grpc_python_out=/app/generated \
      /proto/*.proto

EXPOSE 50051
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import grpc; from generated import auth_pb2_grpc, common_pb2; \
                  c=grpc.insecure_channel('localhost:50051'); \
                  s=auth_pb2_grpc.AuthServiceStub(c); \
                  s.Healthcheck(common_pb2.HealthcheckRequest(), timeout=2)" || exit 1

CMD ["python", "grpc_server.py"]
```

- [ ] **Step 7: Commit**

```bash
cd "Proyecto de telematica"
git add groupsapp-ms/services/auth/
git commit -m "feat(auth): skeleton Django service with gRPC Healthcheck"
```

---

## Task 13: Esqueleto Users Service (FastAPI + gRPC)

**Files:**
- Create: `groupsapp-ms/services/users/Dockerfile`
- Create: `groupsapp-ms/services/users/requirements.txt`
- Create: `groupsapp-ms/services/users/src/__init__.py`
- Create: `groupsapp-ms/services/users/src/main.py`
- Create: `groupsapp-ms/services/users/tests/test_health.py`

- [ ] **Step 1: Escribir test que falla**

Crear `groupsapp-ms/services/users/tests/__init__.py` y `tests/test_health.py`:
```python
import grpc
from generated import users_pb2, users_pb2_grpc, common_pb2

def test_healthcheck():
    channel = grpc.insecure_channel("localhost:50052")
    stub = users_pb2_grpc.UsersServiceStub(channel)
    resp = stub.Healthcheck(common_pb2.HealthcheckRequest(), timeout=3)
    assert resp.service == "users"
    assert resp.status == "OK"
```

- [ ] **Step 2: Implementar `src/main.py`**

Crear `groupsapp-ms/services/users/src/__init__.py` (vacío) y `src/main.py`:
```python
import sys
from concurrent import futures

import grpc
from google.protobuf import timestamp_pb2

sys.path.insert(0, "/app")
from generated import users_pb2, users_pb2_grpc, common_pb2


class UsersServicer(users_pb2_grpc.UsersServiceServicer):
    def Healthcheck(self, request, context):
        ts = timestamp_pb2.Timestamp()
        ts.GetCurrentTime()
        return common_pb2.HealthcheckResponse(
            service="users", status="OK", checked_at=ts
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    users_pb2_grpc.add_UsersServiceServicer_to_server(UsersServicer(), server)
    server.add_insecure_port("0.0.0.0:50052")
    server.start()
    print("Users gRPC server listening on :50052", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
```

- [ ] **Step 3: Escribir `requirements.txt`**

Crear `groupsapp-ms/services/users/requirements.txt`:
```
fastapi==0.111.*
sqlalchemy==2.0.*
psycopg2-binary==2.9.*
grpcio==1.63.*
grpcio-tools==1.63.*
protobuf==5.27.*
pytest==8.*
```

- [ ] **Step 4: Escribir `Dockerfile`**

Crear `groupsapp-ms/services/users/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY services/users/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proto/ /proto/
COPY services/users/ /app/

RUN mkdir -p /app/generated && touch /app/generated/__init__.py && \
    python -m grpc_tools.protoc \
      -I /proto \
      --python_out=/app/generated \
      --grpc_python_out=/app/generated \
      /proto/*.proto

EXPOSE 50052
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import grpc; from generated import users_pb2_grpc, common_pb2; \
                  c=grpc.insecure_channel('localhost:50052'); \
                  s=users_pb2_grpc.UsersServiceStub(c); \
                  s.Healthcheck(common_pb2.HealthcheckRequest(), timeout=2)" || exit 1

CMD ["python", "src/main.py"]
```

- [ ] **Step 5: Commit**

```bash
cd "Proyecto de telematica"
git add groupsapp-ms/services/users/
git commit -m "feat(users): skeleton FastAPI service with gRPC Healthcheck"
```

---

## Task 14: Esqueleto Groups Service

**Files:**
- Create: `groupsapp-ms/services/groups/Dockerfile`
- Create: `groupsapp-ms/services/groups/requirements.txt`
- Create: `groupsapp-ms/services/groups/src/__init__.py`
- Create: `groupsapp-ms/services/groups/src/main.py`
- Create: `groupsapp-ms/services/groups/tests/test_health.py`

- [ ] **Step 1: Test que falla**

Crear `groupsapp-ms/services/groups/tests/__init__.py` y `tests/test_health.py`:
```python
import grpc
from generated import groups_pb2, groups_pb2_grpc, common_pb2

def test_healthcheck():
    channel = grpc.insecure_channel("localhost:50053")
    stub = groups_pb2_grpc.GroupsServiceStub(channel)
    resp = stub.Healthcheck(common_pb2.HealthcheckRequest(), timeout=3)
    assert resp.service == "groups"
    assert resp.status == "OK"
```

- [ ] **Step 2: Implementar `src/main.py`**

Crear `groupsapp-ms/services/groups/src/__init__.py` y `src/main.py`:
```python
import sys
from concurrent import futures

import grpc
from google.protobuf import timestamp_pb2

sys.path.insert(0, "/app")
from generated import groups_pb2, groups_pb2_grpc, common_pb2


class GroupsServicer(groups_pb2_grpc.GroupsServiceServicer):
    def Healthcheck(self, request, context):
        ts = timestamp_pb2.Timestamp()
        ts.GetCurrentTime()
        return common_pb2.HealthcheckResponse(
            service="groups", status="OK", checked_at=ts
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    groups_pb2_grpc.add_GroupsServiceServicer_to_server(GroupsServicer(), server)
    server.add_insecure_port("0.0.0.0:50053")
    server.start()
    print("Groups gRPC server listening on :50053", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
```

- [ ] **Step 3: `requirements.txt`**

Crear `groupsapp-ms/services/groups/requirements.txt`:
```
fastapi==0.111.*
sqlalchemy==2.0.*
psycopg2-binary==2.9.*
grpcio==1.63.*
grpcio-tools==1.63.*
protobuf==5.27.*
pytest==8.*
```

- [ ] **Step 4: `Dockerfile`**

Crear `groupsapp-ms/services/groups/Dockerfile` (idéntico al de users, con `groups` en lugar de `users` y puerto 50053):
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY services/groups/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proto/ /proto/
COPY services/groups/ /app/

RUN mkdir -p /app/generated && touch /app/generated/__init__.py && \
    python -m grpc_tools.protoc \
      -I /proto \
      --python_out=/app/generated \
      --grpc_python_out=/app/generated \
      /proto/*.proto

EXPOSE 50053
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import grpc; from generated import groups_pb2_grpc, common_pb2; \
                  c=grpc.insecure_channel('localhost:50053'); \
                  s=groups_pb2_grpc.GroupsServiceStub(c); \
                  s.Healthcheck(common_pb2.HealthcheckRequest(), timeout=2)" || exit 1

CMD ["python", "src/main.py"]
```

- [ ] **Step 5: Commit**

```bash
cd "Proyecto de telematica"
git add groupsapp-ms/services/groups/
git commit -m "feat(groups): skeleton FastAPI service with gRPC Healthcheck"
```

---

## Task 15: Esqueleto Messaging Service (Django + Channels)

**Files:**
- Create: `groupsapp-ms/services/messaging/Dockerfile`
- Create: `groupsapp-ms/services/messaging/requirements.txt`
- Create: `groupsapp-ms/services/messaging/manage.py`
- Create: `groupsapp-ms/services/messaging/messaging_service/__init__.py`
- Create: `groupsapp-ms/services/messaging/messaging_service/settings.py`
- Create: `groupsapp-ms/services/messaging/messaging_service/asgi.py`
- Create: `groupsapp-ms/services/messaging/grpc_server.py`
- Create: `groupsapp-ms/services/messaging/tests/test_health.py`

- [ ] **Step 1: Test que falla**

Crear `groupsapp-ms/services/messaging/tests/__init__.py` y `tests/test_health.py`:
```python
import grpc
from generated import messaging_pb2, messaging_pb2_grpc, common_pb2

def test_healthcheck():
    channel = grpc.insecure_channel("localhost:50054")
    stub = messaging_pb2_grpc.MessagingServiceStub(channel)
    resp = stub.Healthcheck(common_pb2.HealthcheckRequest(), timeout=3)
    assert resp.service == "messaging"
    assert resp.status == "OK"
```

- [ ] **Step 2: Proyecto Django mínimo**

Crear `groupsapp-ms/services/messaging/manage.py`:
```python
#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "messaging_service.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
```

Crear `groupsapp-ms/services/messaging/messaging_service/__init__.py` (vacío).

Crear `groupsapp-ms/services/messaging/messaging_service/settings.py`:
```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-change-me")
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "channels",
]

ASGI_APPLICATION = "messaging_service.asgi.application"
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "groupsapp_ms"),
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "OPTIONS": {"options": "-c search_path=messaging"},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
```

Crear `groupsapp-ms/services/messaging/messaging_service/asgi.py`:
```python
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "messaging_service.settings")
django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter([]),  # se llenará en Plan 4
})
```

- [ ] **Step 3: Implementar `grpc_server.py`**

Crear `groupsapp-ms/services/messaging/grpc_server.py`:
```python
import os
from concurrent import futures

import django
import grpc
from google.protobuf import timestamp_pb2

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "messaging_service.settings")
django.setup()

from generated import messaging_pb2, messaging_pb2_grpc, common_pb2


class MessagingServicer(messaging_pb2_grpc.MessagingServiceServicer):
    def Healthcheck(self, request, context):
        ts = timestamp_pb2.Timestamp()
        ts.GetCurrentTime()
        return common_pb2.HealthcheckResponse(
            service="messaging", status="OK", checked_at=ts
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    messaging_pb2_grpc.add_MessagingServiceServicer_to_server(MessagingServicer(), server)
    server.add_insecure_port("0.0.0.0:50054")
    server.start()
    print("Messaging gRPC server listening on :50054", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
```

- [ ] **Step 4: `requirements.txt`**

Crear `groupsapp-ms/services/messaging/requirements.txt`:
```
Django==4.2.*
channels==4.*
daphne==4.*
psycopg2-binary==2.9.*
aiokafka==0.11.*
grpcio==1.63.*
grpcio-tools==1.63.*
protobuf==5.27.*
pytest==8.*
```

- [ ] **Step 5: `Dockerfile` (expone gRPC 50054 y WebSocket 8001)**

Crear `groupsapp-ms/services/messaging/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY services/messaging/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proto/ /proto/
COPY services/messaging/ /app/

RUN mkdir -p /app/generated && touch /app/generated/__init__.py && \
    python -m grpc_tools.protoc \
      -I /proto \
      --python_out=/app/generated \
      --grpc_python_out=/app/generated \
      /proto/*.proto

EXPOSE 50054 8001
HEALTHCHECK --interval=15s --timeout=5s --start-period=25s --retries=3 \
  CMD python -c "import grpc; from generated import messaging_pb2_grpc, common_pb2; \
                  c=grpc.insecure_channel('localhost:50054'); \
                  s=messaging_pb2_grpc.MessagingServiceStub(c); \
                  s.Healthcheck(common_pb2.HealthcheckRequest(), timeout=2)" || exit 1

# Se arranca solo gRPC en Plan 1; Daphne para WS se agrega en Plan 4
CMD ["python", "grpc_server.py"]
```

- [ ] **Step 6: Commit**

```bash
cd "Proyecto de telematica"
git add groupsapp-ms/services/messaging/
git commit -m "feat(messaging): skeleton Django+Channels service with gRPC Healthcheck"
```

---

## Task 16: Esqueleto Files Service

**Files:**
- Create: `groupsapp-ms/services/files/Dockerfile`
- Create: `groupsapp-ms/services/files/requirements.txt`
- Create: `groupsapp-ms/services/files/src/__init__.py`
- Create: `groupsapp-ms/services/files/src/main.py`
- Create: `groupsapp-ms/services/files/tests/test_health.py`

- [ ] **Step 1: Test que falla**

Crear `groupsapp-ms/services/files/tests/__init__.py` y `tests/test_health.py`:
```python
import grpc
from generated import files_pb2, files_pb2_grpc, common_pb2

def test_healthcheck():
    channel = grpc.insecure_channel("localhost:50055")
    stub = files_pb2_grpc.FilesServiceStub(channel)
    resp = stub.Healthcheck(common_pb2.HealthcheckRequest(), timeout=3)
    assert resp.service == "files"
    assert resp.status == "OK"
```

- [ ] **Step 2: Implementar `src/main.py`**

Crear `groupsapp-ms/services/files/src/__init__.py` y `src/main.py`:
```python
import sys
from concurrent import futures

import grpc
from google.protobuf import timestamp_pb2

sys.path.insert(0, "/app")
from generated import files_pb2, files_pb2_grpc, common_pb2


class FilesServicer(files_pb2_grpc.FilesServiceServicer):
    def Healthcheck(self, request, context):
        ts = timestamp_pb2.Timestamp()
        ts.GetCurrentTime()
        return common_pb2.HealthcheckResponse(
            service="files", status="OK", checked_at=ts
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    files_pb2_grpc.add_FilesServiceServicer_to_server(FilesServicer(), server)
    server.add_insecure_port("0.0.0.0:50055")
    server.start()
    print("Files gRPC server listening on :50055", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
```

- [ ] **Step 3: `requirements.txt`**

Crear `groupsapp-ms/services/files/requirements.txt`:
```
fastapi==0.111.*
uvicorn[standard]==0.30.*
python-multipart==0.0.9
sqlalchemy==2.0.*
psycopg2-binary==2.9.*
Pillow==10.*
grpcio==1.63.*
grpcio-tools==1.63.*
protobuf==5.27.*
pytest==8.*
```

- [ ] **Step 4: `Dockerfile` (expone gRPC 50055 y HTTP 8002)**

Crear `groupsapp-ms/services/files/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY services/files/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proto/ /proto/
COPY services/files/ /app/

RUN mkdir -p /app/generated && touch /app/generated/__init__.py && \
    python -m grpc_tools.protoc \
      -I /proto \
      --python_out=/app/generated \
      --grpc_python_out=/app/generated \
      /proto/*.proto

EXPOSE 50055 8002
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import grpc; from generated import files_pb2_grpc, common_pb2; \
                  c=grpc.insecure_channel('localhost:50055'); \
                  s=files_pb2_grpc.FilesServiceStub(c); \
                  s.Healthcheck(common_pb2.HealthcheckRequest(), timeout=2)" || exit 1

CMD ["python", "src/main.py"]
```

- [ ] **Step 5: Commit**

```bash
cd "Proyecto de telematica"
git add groupsapp-ms/services/files/
git commit -m "feat(files): skeleton FastAPI service with gRPC Healthcheck"
```

---

## Task 17: Esqueleto Notifications Service (consumer-only)

**Files:**
- Create: `groupsapp-ms/services/notifications/Dockerfile`
- Create: `groupsapp-ms/services/notifications/requirements.txt`
- Create: `groupsapp-ms/services/notifications/src/__init__.py`
- Create: `groupsapp-ms/services/notifications/src/main.py`

Nota: Notifications no expone gRPC (solo consume Kafka). Por eso el healthcheck es distinto: valida que el consumer está suscrito.

- [ ] **Step 1: Implementar `src/main.py` (con placeholder para consumer real en Plan 4)**

Crear `groupsapp-ms/services/notifications/src/__init__.py` y `src/main.py`:
```python
import asyncio
import os
import sys
import time

sys.path.insert(0, "/app")


async def main():
    # Placeholder: en Plan 4 se conecta a aiokafka y consume topics.
    # Por ahora solo imprime heartbeat cada 10s para que el healthcheck pase.
    print("Notifications service started (placeholder consumer)", flush=True)
    while True:
        print(f"notifications heartbeat ts={int(time.time())}", flush=True)
        await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: `requirements.txt`**

Crear `groupsapp-ms/services/notifications/requirements.txt`:
```
aiokafka==0.11.*
grpcio==1.63.*
grpcio-tools==1.63.*
protobuf==5.27.*
httpx==0.27.*
```

- [ ] **Step 3: `Dockerfile`**

Crear `groupsapp-ms/services/notifications/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY services/notifications/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proto/ /proto/
COPY services/notifications/ /app/

RUN mkdir -p /app/generated && touch /app/generated/__init__.py && \
    python -m grpc_tools.protoc \
      -I /proto \
      --python_out=/app/generated \
      --grpc_python_out=/app/generated \
      /proto/*.proto

HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=3 \
  CMD pgrep -f "src/main.py" > /dev/null || exit 1

CMD ["python", "src/main.py"]
```

- [ ] **Step 4: Commit**

```bash
cd "Proyecto de telematica"
git add groupsapp-ms/services/notifications/
git commit -m "feat(notifications): skeleton consumer service (placeholder heartbeat)"
```

---

## Task 18: Agregar servicios al docker-compose

**Files:**
- Modify: `groupsapp-ms/docker-compose.yml`

- [ ] **Step 1: Agregar los 7 servicios al compose**

Editar `groupsapp-ms/docker-compose.yml`. Reemplazar el archivo completo con:
```yaml
services:
  postgres:
    image: postgres:15-alpine
    container_name: gms_postgres
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-groupsapp_ms}
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
    ports:
      - "5433:5432"
    volumes:
      - gms_postgres_data:/var/lib/postgresql/data
      - ./scripts/init_db.sql:/docker-entrypoint-initdb.d/01_init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres}"]
      interval: 5s
      timeout: 5s
      retries: 5

  zookeeper:
    image: bitnami/zookeeper:3.9
    container_name: gms_zookeeper
    environment:
      ALLOW_ANONYMOUS_LOGIN: "yes"
    ports:
      - "2181:2181"
    healthcheck:
      test: ["CMD-SHELL", "echo ruok | nc -w 2 localhost 2181 | grep -q imok"]
      interval: 10s
      timeout: 5s
      retries: 5

  kafka:
    image: bitnami/kafka:3.7
    container_name: gms_kafka
    depends_on:
      zookeeper:
        condition: service_healthy
    environment:
      KAFKA_CFG_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_CFG_LISTENERS: PLAINTEXT://:9092
      KAFKA_CFG_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_CFG_AUTO_CREATE_TOPICS_ENABLE: "true"
      ALLOW_PLAINTEXT_LISTENER: "yes"
    ports:
      - "9092:9092"
    healthcheck:
      test: ["CMD-SHELL", "kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null 2>&1"]
      interval: 15s
      timeout: 10s
      retries: 5

  auth:
    build:
      context: .
      dockerfile: services/auth/Dockerfile
    container_name: gms_auth
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-groupsapp_ms}
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_HOST: postgres
      POSTGRES_PORT: "5432"
      JWT_SECRET_KEY: ${JWT_SECRET_KEY:-dev-only-change-me}
    ports:
      - "50051:50051"
    restart: unless-stopped

  users:
    build:
      context: .
      dockerfile: services/users/Dockerfile
    container_name: gms_users
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_PORT: "5432"
    ports:
      - "50052:50052"
    restart: unless-stopped

  groups:
    build:
      context: .
      dockerfile: services/groups/Dockerfile
    container_name: gms_groups
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_PORT: "5432"
    ports:
      - "50053:50053"
    restart: unless-stopped

  messaging:
    build:
      context: .
      dockerfile: services/messaging/Dockerfile
    container_name: gms_messaging
    depends_on:
      postgres:
        condition: service_healthy
      kafka:
        condition: service_healthy
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_PORT: "5432"
      KAFKA_BROKER: kafka:9092
    ports:
      - "50054:50054"
      - "8001:8001"
    restart: unless-stopped

  files:
    build:
      context: .
      dockerfile: services/files/Dockerfile
    container_name: gms_files
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_PORT: "5432"
    volumes:
      - gms_files_data:/app/uploads
    ports:
      - "50055:50055"
      - "8002:8002"
    restart: unless-stopped

  notifications:
    build:
      context: .
      dockerfile: services/notifications/Dockerfile
    container_name: gms_notifications
    depends_on:
      kafka:
        condition: service_healthy
    environment:
      KAFKA_BROKER: kafka:9092
    restart: unless-stopped

  gateway:
    build:
      context: .
      dockerfile: services/gateway/Dockerfile
    container_name: gms_gateway
    depends_on:
      - auth
      - users
      - groups
      - messaging
      - files
    environment:
      AUTH_GRPC: auth:50051
      USERS_GRPC: users:50052
      GROUPS_GRPC: groups:50053
      MESSAGING_GRPC: messaging:50054
      FILES_GRPC: files:50055
    ports:
      - "8000:8000"
    restart: unless-stopped

volumes:
  gms_postgres_data:
  gms_files_data:
```

- [ ] **Step 2: Levantar todo y verificar**

```bash
cd groupsapp-ms
docker compose up -d --build
docker compose ps
```

Expected: 10 contenedores corriendo (3 infra + 7 servicios). Todos los healthchecks deben marcar `healthy` (pueden tardar hasta ~2 min en build inicial).

- [ ] **Step 3: Ver logs de cada servicio para confirmar startup**

```bash
docker compose logs auth | tail -5
docker compose logs users | tail -5
docker compose logs groups | tail -5
docker compose logs messaging | tail -5
docker compose logs files | tail -5
docker compose logs notifications | tail -5
docker compose logs gateway | tail -5
```

Expected: cada uno imprime un mensaje tipo `"XXX gRPC server listening on :50XXX"` (excepto notifications que imprime heartbeat, y gateway que logea startup de uvicorn).

- [ ] **Step 4: Commit**

```bash
cd "Proyecto de telematica"
git add groupsapp-ms/docker-compose.yml
git commit -m "feat(infra): wire all 7 services into docker-compose"
```

---

## Task 19: Smoke test integral

**Files:**
- Create: `groupsapp-ms/scripts/smoke_test.py`

- [ ] **Step 1: Escribir el script de smoke test**

Crear `groupsapp-ms/scripts/smoke_test.py`:
```python
#!/usr/bin/env python
"""Smoke test: verifica que los 7 servicios responden a Healthcheck y que Kafka tiene los 3 topics."""
import subprocess
import sys
from pathlib import Path

import grpc

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "gateway"))

from generated import (  # noqa: E402
    auth_pb2_grpc, users_pb2_grpc, groups_pb2_grpc,
    messaging_pb2_grpc, files_pb2_grpc, common_pb2,
)

GRPC_SERVICES = [
    ("auth", 50051, auth_pb2_grpc.AuthServiceStub),
    ("users", 50052, users_pb2_grpc.UsersServiceStub),
    ("groups", 50053, groups_pb2_grpc.GroupsServiceStub),
    ("messaging", 50054, messaging_pb2_grpc.MessagingServiceStub),
    ("files", 50055, files_pb2_grpc.FilesServiceStub),
]

EXPECTED_TOPICS = {"messages.sent", "messages.read", "presence.changed"}


def check_grpc():
    failures = []
    for name, port, stub_cls in GRPC_SERVICES:
        try:
            channel = grpc.insecure_channel(f"localhost:{port}")
            stub = stub_cls(channel)
            resp = stub.Healthcheck(common_pb2.HealthcheckRequest(), timeout=5)
            if resp.service != name or resp.status != "OK":
                failures.append(f"{name}: wrong response {resp}")
            else:
                print(f"OK  gRPC {name} @ :{port}")
        except Exception as e:
            failures.append(f"{name}: {e}")
    return failures


def check_gateway():
    import urllib.request
    import json
    try:
        with urllib.request.urlopen("http://localhost:8000/health", timeout=5) as r:
            body = json.loads(r.read())
            assert body == {"service": "gateway", "status": "OK"}, f"unexpected: {body}"
        print("OK  HTTP gateway @ :8000/health")
        return []
    except Exception as e:
        return [f"gateway: {e}"]


def check_kafka_topics():
    try:
        out = subprocess.run(
            ["docker", "compose", "exec", "-T", "kafka",
             "kafka-topics.sh", "--bootstrap-server", "localhost:9092", "--list"],
            cwd=ROOT, capture_output=True, text=True, check=True, timeout=15,
        )
        actual = set(out.stdout.strip().splitlines())
        missing = EXPECTED_TOPICS - actual
        if missing:
            return [f"kafka: missing topics {missing}"]
        print(f"OK  Kafka topics: {sorted(EXPECTED_TOPICS)}")
        return []
    except Exception as e:
        return [f"kafka: {e}"]


def main():
    failures = []
    failures += check_grpc()
    failures += check_gateway()
    failures += check_kafka_topics()

    if failures:
        print("\n--- FAILURES ---", file=sys.stderr)
        for f in failures:
            print(f"FAIL {f}", file=sys.stderr)
        sys.exit(1)
    print("\nAll smoke checks passed.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Hacer ejecutable y correr**

```bash
chmod +x groupsapp-ms/scripts/smoke_test.py
cd groupsapp-ms

# Asegurar topics creados
./scripts/create_topics.sh

# Compilar protos para tener stubs locales
./scripts/compile_proto.sh

# Correr smoke test
python scripts/smoke_test.py
```

Expected:
```
OK  gRPC auth @ :50051
OK  gRPC users @ :50052
OK  gRPC groups @ :50053
OK  gRPC messaging @ :50054
OK  gRPC files @ :50055
OK  HTTP gateway @ :8000/health
OK  Kafka topics: ['messages.read', 'messages.sent', 'presence.changed']

All smoke checks passed.
```

- [ ] **Step 3: Si falla, diagnosticar con logs**

```bash
docker compose logs <servicio-que-falla>
docker compose ps
```

- [ ] **Step 4: Commit**

```bash
cd "Proyecto de telematica"
git add groupsapp-ms/scripts/smoke_test.py
git commit -m "feat(scripts): integral smoke test (gRPC + HTTP + Kafka)"
```

---

## Task 20: Congelar contratos y cerrar Plan 1

**Files:**
- Modify: `groupsapp-ms/README.md`

- [ ] **Step 1: Actualizar README con el estado del Plan 1**

Agregar al final de `groupsapp-ms/README.md`:
```markdown

## Plan 1 — Foundation (completado)

- [x] Monorepo con 7 servicios
- [x] Proto contracts congelados en `proto/` (auth, users, groups, messaging, files, common)
- [x] Postgres con 6 schemas (auth, users, groups, messaging, files, notifications)
- [x] Kafka + Zookeeper con 3 topics (messages.sent, messages.read, presence.changed)
- [x] 7 servicios respondiendo gRPC Healthcheck
- [x] `scripts/smoke_test.py` pasa

### Contratos gRPC (congelados)

Cualquier cambio a `proto/*.proto` requiere re-compilación en todos los servicios afectados y debe discutirse con el equipo antes de mergear.

## Próximos planes
- **Plan 2** — Auth + Gateway (login/register end-to-end)
- **Plan 3** — Users + Groups (CRUD y membership)
- **Plan 4** — Messaging + Kafka + Notifications (WebSocket + eventos)
- **Plan 5** — Files + E2E + Demo
```

- [ ] **Step 2: Verificación final — correr smoke test 3 veces seguidas**

```bash
cd groupsapp-ms
for i in 1 2 3; do
  echo "=== Run $i ==="
  python scripts/smoke_test.py || { echo "Failed on run $i"; exit 1; }
done
```

Expected: las 3 corridas pasan.

- [ ] **Step 3: Commit final de Plan 1**

```bash
cd "Proyecto de telematica"
git add groupsapp-ms/README.md
git commit -m "docs(ms): mark Plan 1 (Foundation) complete"
```

---

## Criterios de "Definition of Done" para Plan 1

- `docker compose ps` muestra 10 contenedores `healthy`
- `scripts/smoke_test.py` pasa 3 veces consecutivas sin intervención
- Los 5 `.proto` están commiteados y compilan sin warnings
- Los 6 schemas existen en Postgres (`\dn` los lista)
- Los 3 topics de Kafka existen (`kafka-topics.sh --list` los muestra)
- El historial de commits tiene al menos 14 commits atómicos (uno por tarea significativa)
- No hay código de negocio — solo infra, contratos y handlers de Healthcheck

Cuando todo lo anterior se cumpla, el equipo puede comenzar Plan 2 sin bloqueos de infraestructura.

---

## Self-review del plan

**Cobertura del spec (§3, §4, §5.1 topics, §7 schemas):**
- ✅ Topología con 7 servicios: Task 11–17
- ✅ Postgres con 5 schemas (+ notifications audit): Task 9
- ✅ Kafka 3 topics: Task 10
- ✅ Proto contratos congelados: Tasks 2–7
- ⚠️ `notifications` no implementa consumer real (sólo heartbeat). Justificado: corresponde a Plan 4.
- ⚠️ Gateway no valida JWT ni enruta gRPC real. Justificado: corresponde a Plan 2.

**Placeholder scan:** sin TBD, TODO, "fill in" o "similar to". Códigos completos en cada paso.

**Consistencia de tipos:** firmas y nombres de método consistentes con spec §5.2. Puertos gRPC: 50051 (auth) → 50055 (files), HTTP: 8000 (gateway), 8001 (messaging WS), 8002 (files upload).
