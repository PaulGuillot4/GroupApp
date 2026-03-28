# GroupsApp

Aplicación de mensajería instantánea en tiempo real (estilo WhatsApp) construida con **Django REST Framework** + **Django Channels** (WebSockets).

## 🚀 Inicio Rápido (3 comandos)

```bash
git clone <url-del-repo> && cd groupsapp
cp .env.example .env            # Ajustar credenciales si es necesario
docker compose up -d --build    # Levanta DB + Servidor
```

El servidor estará disponible en **http://localhost:8000**.

## 📋 Prerrequisitos

- [Docker](https://docs.docker.com/get-docker/) ≥ 20.x
- [Docker Compose](https://docs.docker.com/compose/) v2+

## 🏗️ Arquitectura

```
groupsapp/
├── apps/
│   ├── core/               # Módulo compartido (responses, exceptions)
│   ├── authentication/     # JWT auth (login, register, logout, refresh)
│   ├── users/              # Perfil y búsqueda de usuarios
│   ├── groups/             # Grupos, canales y membresías
│   ├── chat_messages/      # Mensajes REST + WebSocket consumer
│   ├── files/              # Subida de archivos validada
│   └── frontend/           # Templates Django (UI)
├── config/                 # Settings, URLs, ASGI/WSGI
├── templates/              # HTML (base, auth, chat)
├── static/                 # CSS y JavaScript del frontend
├── docker-compose.yml      # Orquestación de servicios
├── Dockerfile              # Imagen del servidor
└── CONTEXT.md              # Decisiones técnicas documentadas
```

## 🔌 API Endpoints

Todo protegido por JWT excepto login/register.

### Autenticación
| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/api/auth/register` | Crear cuenta |
| `POST` | `/api/auth/login` | Iniciar sesión |
| `POST` | `/api/auth/logout` | Cerrar sesión |
| `POST` | `/api/auth/refresh` | Renovar token |

### Usuarios
| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/users/me/` | Perfil del usuario autenticado |
| `GET` | `/api/users/search/?q=` | Buscar usuarios |

### Grupos
| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET/POST` | `/api/groups/` | Listar/Crear grupos |
| `GET/PUT/DELETE` | `/api/groups/:id/` | Detalle del grupo |
| `POST` | `/api/groups/:id/join/` | Unirse a grupo abierto |
| `POST` | `/api/groups/:id/leave/` | Salir del grupo |
| `GET/POST` | `/api/groups/:id/members/` | Listar/Agregar miembros |
| `DELETE` | `/api/groups/:id/members/:userId/` | Remover miembro |
| `PUT` | `/api/groups/:id/members/:userId/role/` | Cambiar rol |
| `GET/POST` | `/api/groups/:id/channels/` | Listar/Crear canales |

### Mensajes
| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/messages/conversations/` | Lista unificada de chats |
| `GET` | `/api/messages/group/:id/` | Historial de grupo |
| `GET` | `/api/messages/channel/:id/` | Historial de canal |
| `GET` | `/api/messages/private/:userId/` | Historial privado |

### Archivos
| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/api/files/upload/` | Subir archivo (multipart) |

### WebSocket
```
ws://localhost:8000/ws/chat/?token=<access_token>
```

## 🔧 Comandos Útiles

```bash
# Crear superusuario
docker compose exec app python manage.py createsuperuser

# Ver logs en tiempo real
docker logs -f groupsapp

# Acceder al shell de Django
docker compose exec app python manage.py shell

# Detener servicios
docker compose stop

# Detener y borrar todo (incluyendo DB)
docker compose down -v
```

## 🔐 Variables de Entorno

Ver [`.env.example`](.env.example) para la lista completa. Las principales:

| Variable | Descripción | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Clave secreta de Django | **Obligatorio en producción** |
| `DEBUG` | Modo debug | `True` |
| `POSTGRES_*` | Credenciales de PostgreSQL | ver `.env.example` |
| `MAX_IMAGE_UPLOAD_SIZE` | Límite de imágenes (bytes) | `10485760` (10MB) |
| `LOG_LEVEL` | Nivel de logging | `INFO` |

## 📝 Decisiones Técnicas

Ver [`CONTEXT.md`](CONTEXT.md) para la documentación detallada de decisiones arquitectónicas.
