from fastapi import FastAPI

app = FastAPI(title="GroupsApp Gateway")

@app.get("/health")
def health():
    return {"service": "gateway", "status": "OK"}
