import os
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Header, UploadFile
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/app/uploads"))
FILES_BASE_URL = os.getenv("FILES_BASE_URL", "http://localhost:8002")

app = FastAPI(title="Files Service REST")


def _get_engine():
    from src.db import get_engine
    return get_engine()


@app.on_event("startup")
def _startup():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    engine = _get_engine()
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS files"))
        conn.commit()
    from src.models import metadata
    metadata.create_all(engine)


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    x_user_id: str = Header(...),
):
    file_id = str(uuid.uuid4())
    suffix = Path(file.filename or "file").suffix or ".bin"
    dest = UPLOAD_DIR / f"{file_id}{suffix}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    dest.write_bytes(content)

    url = f"{FILES_BASE_URL}/files/{file_id}{suffix}"
    mime = file.content_type or "application/octet-stream"
    size = len(content)

    engine = _get_engine()
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO files (id, owner_id, url, mime_type, size) VALUES (:id, :owner, :url, :mime, :size)"),
            {"id": file_id, "owner": x_user_id, "url": url, "mime": mime, "size": size},
        )
        conn.commit()

    return {"file_id": file_id, "url": url, "mime_type": mime, "size": size}


app.mount("/files", StaticFiles(directory=str(UPLOAD_DIR), check_dir=False), name="files")
