from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes.auth import router as auth_router
from .routes.users import router as users_router
from .routes.groups import router as groups_router
from .routes.messages import router as messages_router
from .routes.files import router as files_router, media_router
from .routes.frontend import router as frontend_router

app = FastAPI(title="GroupsApp Gateway")

# CORS — allow frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(frontend_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(groups_router)
app.include_router(messages_router)
app.include_router(files_router)
app.include_router(media_router)


@app.get("/health")
def health():
    return {"service": "gateway", "status": "OK"}
