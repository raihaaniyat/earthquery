"""
Application Settings & Configuration via Pydantic Settings.
Implements typed, validated environment settings adhering to the SatQuery Phase 2 specifications.
"""

from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "SatQuery AI"
    APP_ENV: str = "development"
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    AUTH_MODE: str = "local_bearer"

    # 1. Database Connections
    DATABASE_URL: str = "postgresql+psycopg://satquery_admin:satquery_admin_password@127.0.0.1:5432/satquery"
    CHECKPOINT_DATABASE_DSN: str = "postgresql://satquery_admin:satquery_admin_password@127.0.0.1:5432/satquery"
    DB_ECHO: bool = False

    # 2. Redis & Queues
    REDIS_URL: str = "redis://:satquery_redis_password@127.0.0.1:6379/0"
    REDIS_QUEUE_INGEST: str = "satquery-ingest"
    REDIS_QUEUE_ANALYSIS: str = "satquery-analysis"
    RQ_QUEUE_NAME: str = "satquery-analysis"  # Compatibility

    # 3. Object Storage (S3 / SeaweedFS / MinIO)
    S3_ENDPOINT_INTERNAL: str = "http://127.0.0.1:8333"
    S3_ENDPOINT_PUBLIC: str = "http://127.0.0.1:8333"
    S3_ACCESS_KEY_ID: str = "satquery_s3_admin"
    S3_SECRET_ACCESS_KEY: str = "satquery_s3_secret_key"
    S3_REGION: str = "us-east-1"
    S3_ADDRESSING_STYLE: str = "path"

    # Distinct logical stores
    S3_BUCKET_INPUTS: str = "satquery-inputs"
    S3_BUCKET_DERIVED: str = "satquery-derived"
    S3_BUCKET_MODELS: str = "satquery-models"
    S3_BUCKET_DATASETS: str = "satquery-datasets"
    S3_BUCKET_NAME: str = "satquery-inputs"  # Compatibility

    # 4. Storage & Execution Paths
    SATQUERY_DATA_ROOT: str = "C:/Users/HP/earthquery/data"
    SATQUERY_CACHE_ROOT: str = "C:/Users/HP/earthquery/cache"
    SATQUERY_MODEL_ROOT: str = "C:/Users/HP/earthquery/models"
    SATQUERY_STORAGE_ROOT: str = "C:/Users/HP/earthquery/storage"
    MODELS_DIR: str = "C:/Users/HP/earthquery/models"

    # 5. Conda Python Interpreters & Environments
    SATQUERY_CONDA_EXE: str = "C:/Users/HP/miniconda3/Scripts/conda.exe"
    CORE_ENV: str = "satquery-core"
    CHANGEFORMER_ENV: str = "satquery-changeformer"
    GEOGROUND_ENV: str = "satquery-geoground"
    API_ENV: str = "satquery-api"

    # 6. Concurrency & Resource Budgets
    GPU_CONCURRENCY: int = 1
    CPU_CONCURRENCY: int = 1
    GPU_MIN_FREE_MIB: int = 512             # 512 MiB reserve headroom allows 7.5 GB usable model VRAM
    MAX_QUEUED_GPU_JOBS: int = 10           # Allow up to 10 queued tasks before backpressure
    MAX_VRAM_GB: float = 7.5
    MAX_ACTIVE_PREPROCESS_JOBS: int = 1
    MAX_ACTIVE_DOWNLOADS: int = 1
    MAX_UPLOAD_BYTES: int = 524288000       # 500 MB
    MIN_FREE_DISK_BYTES: int = 10737418240  # 10 GB
    MAX_VQA_TILES: int = 6
    MAX_VQA_TOKENS: int = 512

    # 7. ISRO / NRSC External Providers (BHOONIDHI & Bhuvan)
    BHOONIDHI_USER_ID: Optional[str] = None
    BHOONIDHI_PASSWORD: Optional[str] = None
    BHOONIDHI_API_BASE_URL: str = "https://bhoonidhi.nrsc.gov.in/bhoonidhi-api"
    BHUVAN_API_BASE_URL: str = "https://bhuvan-app1.nrsc.gov.in/api"
    BHUVAN_WMS_BASE_URL: str = "https://bhuvan-vec1.nrsc.gov.in/bhuvan/wms"

    # 8. Security, CORS & Compatibility
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000"
    CUDNN_ENABLED: bool = False
    DEVICE: str = "cuda"


    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

def get_settings() -> Settings:
    return settings
