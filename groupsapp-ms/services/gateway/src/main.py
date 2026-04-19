from fastapi import FastAPI
from .routes.auth import router as auth_router
from .routes.users import router as users_router

app = FastAPI(title="GroupsApp Gateway")

app.include_router(auth_router)
app.include_router(users_router)


@app.get("/health")
def health():
    return {"service": "gateway", "status": "OK"}
