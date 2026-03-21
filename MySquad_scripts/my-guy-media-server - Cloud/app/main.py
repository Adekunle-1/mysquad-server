import time
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse

from app.config import settings
from app.minio_client import upload_file, delete_file
from app.n8n_client import forward_to_n8n
from app.schemas import TextPayload

app = FastAPI(title="MyGuy Media Server", version="1.0.0")

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}
ALLOWED_AUDIO_TYPES = {"audio/ogg", "audio/mpeg", "audio/mp4", "audio/wav", "audio/wave", "audio/x-wav",  "audio/webm"}


# ─── Health Check ───────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "myguy-media-server"}


# ─── Main Chat Endpoint ──────────────────────────────────────────────────────

@app.post("/chat")
async def chat(
    # Multipart form fields (used for image/audio)
    user_id: Optional[str] = Form(None),
    username: Optional[str] = Form(None),
    phone_no: Optional[str] = Form(None),
    timestamp: Optional[int] = Form(None),
    message_type: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    # ── Detect if this is a media (multipart) or text (JSON) request ──
    # For text messages, all Form fields will be None since the app sends JSON.
    # FastAPI handles JSON body separately via the raw request.
    # We check if file is present to determine media vs text routing.

    if file is not None:
        # ── MEDIA MESSAGE (image or audio) ──
        return await handle_media(
            user_id=user_id,
            username=username,
            phone_no=phone_no,
            timestamp=timestamp,
            message_type=message_type,
            caption=caption,
            file=file,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="No file provided. For text messages use /chat/text endpoint."
        )


@app.post("/chat/text")
async def chat_text(payload: TextPayload):
    """
    Handle text messages — forward directly to n8n without MinIO.
    """
    n8n_payload = {
        "user_id": payload.user_id,
        "username": payload.username,
        "phone_no": payload.phone_no,
        "timestamp": payload.timestamp,
        "message_type": "text",
        "text": {
            "body": payload.text.body
        }
    }

    try:
        response = await forward_to_n8n(n8n_payload)
        return JSONResponse(content=response)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"n8n error: {str(e)}")


# ─── Media Handler ───────────────────────────────────────────────────────────

async def handle_media(
    user_id: str,
    username: str,
    phone_no: str,
    timestamp: int,
    message_type: str,
    caption: Optional[str],
    file: UploadFile,
):
    # ── Validate required fields ──
    if not all([user_id, username, phone_no, timestamp, message_type]):
        raise HTTPException(status_code=400, detail="Missing required fields.")

    if message_type not in ("image", "audio"):
        raise HTTPException(status_code=400, detail="message_type must be 'image' or 'audio'.")

    # ── Validate file type ──
    mime_type = file.content_type
    if message_type == "image" and mime_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported image type: {mime_type}. Allowed: {ALLOWED_IMAGE_TYPES}"
        )
    if message_type == "audio" and mime_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported audio type: {mime_type}. Allowed: {ALLOWED_AUDIO_TYPES}"
        )

    # ── Validate file size ──
    file_bytes = await file.read()
    size_mb = len(file_bytes) / (1024 * 1024)
    max_size = settings.max_image_size_mb if message_type == "image" else settings.max_audio_size_mb
    if size_mb > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {size_mb:.1f}MB. Max allowed: {max_size}MB."
        )

    # ── Upload to MinIO ──
    try:
        file_key = upload_file(file_bytes, mime_type, message_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MinIO upload failed: {str(e)}")

    # ── Build n8n payload ──
    if message_type == "image":
        n8n_payload = {
            "user_id": user_id,
            "username": username,
            "phone_no": phone_no,
            "timestamp": timestamp,
            "message_type": "image",
            "image": {
                "file_key": file_key,
                "mime_type": mime_type,
                "caption": caption or "",
            }
        }
    else:
        n8n_payload = {
            "user_id": user_id,
            "username": username,
            "phone_no": phone_no,
            "timestamp": timestamp,
            "message_type": "audio",
            "audio": {
                "file_key": file_key,
                "mime_type": mime_type,
            }
        }

    # ── Forward to n8n and relay response ──
    try:
        response = await forward_to_n8n(n8n_payload)
    except Exception as e:
        # Delete file from MinIO if n8n fails — no point keeping it
        delete_file(file_key)
        raise HTTPException(status_code=502, detail=f"n8n error: {str(e)}")
    finally:
        # Always attempt cleanup after n8n responds
        delete_file(file_key)

    return JSONResponse(content=response)
