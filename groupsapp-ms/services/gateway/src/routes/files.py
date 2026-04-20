import os
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
import grpc
import httpx

from generated import files_pb2
from ..clients import get_files_stub
from ..deps import get_current_user

router = APIRouter(prefix="/api/files", tags=["files"])

FILES_HTTP_URL = os.getenv("FILES_HTTP", "http://files:8002")


@router.get("/{file_id}")
def get_file_metadata(file_id: str, current_user: dict = Depends(get_current_user)):
    stub = get_files_stub()
    try:
        meta = stub.GetFileMetadata(files_pb2.GetFileMetadataRequest(file_id=file_id))
        return {
            "id": meta.id,
            "owner_id": meta.owner_id,
            "url": meta.url,
            "mime_type": meta.mime_type,
            "size": meta.size,
        }
    except grpc.RpcError as exc:
        if exc.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="File not found")
        raise HTTPException(status_code=503, detail="Files service unavailable")


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    content = await file.read()
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{FILES_HTTP_URL}/upload",
                files={"file": (file.filename, content, file.content_type)},
                headers={"x-user-id": current_user["user_id"]},
                timeout=30.0,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail="Upload failed")
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Files service unavailable")
    return resp.json()
