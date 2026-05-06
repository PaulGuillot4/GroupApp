import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routes.auth import router as auth_router
from .routes.users import router as users_router
from .routes.groups import router as groups_router
from .routes.messages import router as messages_router
from .routes.files import router as files_router, media_router
from .routes.frontend import router as frontend_router
from .routes.ws_proxy import router as ws_router

app = FastAPI(title="GroupsApp Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve /static/* from services/gateway/static/
_static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../static")
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# Route order matters: frontend and ws before api routes
app.include_router(frontend_router)
app.include_router(ws_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(groups_router)
app.include_router(messages_router)
app.include_router(files_router)
app.include_router(media_router)


@app.get("/health")
def health():
    return {"service": "gateway", "status": "OK"}
