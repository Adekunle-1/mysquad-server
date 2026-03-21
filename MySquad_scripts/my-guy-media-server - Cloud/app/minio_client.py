import uuid
import mimetypes
from io import BytesIO

from minio import Minio
from minio.error import S3Error

from app.config import settings


def get_minio_client() -> Minio:
    # Strip protocol from endpoint for Minio SDK
    endpoint = settings.minio_endpoint.replace("https://", "").replace("http://", "")
    secure = settings.minio_endpoint.startswith("https://")

    return Minio(
        endpoint,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        secure=secure,
    )


def upload_file(file_bytes: bytes, mime_type: str, message_type: str) -> str:
    """
    Upload a file to MinIO and return the file_key.
    message_type: 'image' or 'audio'
    """
    client = get_minio_client()
    bucket = settings.minio_bucket

    # Ensure bucket exists
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)

    # Determine folder and extension
    extension = mimetypes.guess_extension(mime_type) or (
        ".jpg" if message_type == "image" else ".ogg"
    )
    # Fix common mime extension quirks
    extension_map = {
        ".jpe": ".jpg",
        ".jpeg": ".jpg",
        ".mpga": ".mp3",
    }
    extension = extension_map.get(extension, extension)

    folder = "images" if message_type == "image" else "audio"
    file_key = f"{settings.minio_bucket}/{folder}/{uuid.uuid4()}{extension}"

    # Upload
    client.put_object(
        bucket_name=bucket,
        object_name=f"{folder}/{file_key.split('/', 2)[-1]}",
        data=BytesIO(file_bytes),
        length=len(file_bytes),
        content_type=mime_type,
    )

    return file_key


def delete_file(file_key: str) -> None:
    """
    Delete a file from MinIO by file_key.
    file_key format: myguy-media/images/uuid.jpg
    """
    client = get_minio_client()
    bucket = settings.minio_bucket

    # Extract object name from file_key (strip bucket prefix)
    # file_key: "myguy-media/images/uuid.jpg" → object_name: "images/uuid.jpg"
    parts = file_key.split("/", 1)
    object_name = parts[1] if len(parts) > 1 else file_key

    try:
        client.remove_object(bucket, object_name)
    except S3Error as e:
        # Log but don't raise — deletion failure shouldn't break the response
        print(f"[MinIO] Failed to delete {file_key}: {e}")
