from fastapi import FastAPI
from .routes.auth import router as auth_router

app = FastAPI(title="GroupsApp Gateway")

app.include_router(auth_router)


@app.get("/health")
def health():
    return {"service": "gateway", "status": "OK"}
