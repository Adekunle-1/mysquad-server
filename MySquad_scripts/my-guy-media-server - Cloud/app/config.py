from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    minio_endpoint: str
    minio_root_user: str
    minio_root_password: str
    minio_bucket: str = "myguy-media"
    n8n_webhook_url: str
    port: int = 5672
    max_image_size_mb: int = 10
    max_audio_size_mb: int = 25

    class Config:
        env_file = ".env"


settings = Settings()
