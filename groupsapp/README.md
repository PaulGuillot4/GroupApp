# GroupsApp Backend

Aplicación monolítica de mensajería instantánea (estilo WhatsApp/Telegram) construida con **Django REST Framework** para la API e historial, y **Django Channels** para mensajería en tiempo real mediante WebSockets.

## 🚀 Cómo correr el proyecto localmente

El proyecto está dockerizado para que sea muy fácil de levantar sin necesidad de instalar dependencias locales (solo necesitas Docker).

### Prerrequisitos
- [Docker](https://docs.docker.com/get-docker/) instalado y ejecutándose.

### Pasos

1. **Clonar el repositorio y entrar a la carpeta:**
   ```bash
   git clone <url-del-repo>
   cd groupsapp
   ```

2. **Levantar los contenedores (Base de datos + Servidor web):**
   ```bash
   docker compose up -d --build
   ```
   Esto descargará las imágenes necesarias, instalará las dependencias de Python y levantará la base de datos PostgreSQL en el puerto `5432` y el servidor Daphne en el puerto `8000`. Además, ejecutará las migraciones automáticamente.

3. **Verificar que el servidor está corriendo:**
   Abre tu navegador o Postman en:
   ```text
   http://localhost:8000/api/auth/register
   ```

4. **Crear un superusuario (opcional para acceder al panel de admin):**
   ```bash
   docker compose exec app python manage.py createsuperuser
   ```

5. **Ver logs en tiempo real (útil para debugear):**
   ```bash
   docker logs -f groupsapp
   ```

6. **Detener el proyecto:**
   ```bash
   docker compose stop
   ```
   Si deseas borrar todo incluyendo la base de datos, usa `docker compose down -v`.

---

## 🔌 Estructura de Endpoints de Prueba

Todo está protegido por JWT (excepto login/register).

1. **Registrarse:** `POST http://localhost:8000/api/auth/register`
   - Body JSON: `{"username": "tu_usuario", "email": "correo@test.com", "password": "pass", "password_confirm": "pass"}`
2. **Iniciar Sesión:** `POST http://localhost:8000/api/auth/login`
   - Body JSON: `{"email": "correo@test.com", "password": "pass"}`
   - Guarda el `access_token` que te devuelve.
3. **Peticiones REST:** Añade el header `Authorization: Bearer <access_token>`.
4. **Conexión WebSocket:** Conéctate a `ws://localhost:8000/ws/chat/?token=<access_token>`.
