"""
Database connectivity and GeoAlchemy2 model definitions.
"""

from typing import Optional, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Float, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from geoalchemy2 import Geometry
from backend.app.config import settings

Base = declarative_base()

class GeospatialScene(Base):
    __tablename__ = "geospatial_scenes"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    modality = Column(String(50), nullable=False) # optical, sar, bitemporal
    crs = Column(String(100), nullable=True)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    bands = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # Optional PostGIS geometry footprint
    # geometry = Column(Geometry(geometry_type='POLYGON', srid=4326), nullable=True)

class InferenceJob(Base):
    __tablename__ = "inference_jobs"

    id = Column(String(64), primary_key=True, index=True)
    model_id = Column(String(64), nullable=False)
    task_type = Column(String(64), nullable=False)
    status = Column(String(32), default="QUEUED") # QUEUED, RUNNING, COMPLETED, FAILED
    prompt = Column(Text, nullable=True)
    result_text = Column(Text, nullable=True)
    result_mask_path = Column(String(512), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)

def get_engine():
    return create_engine(
        settings.DATABASE_URL,
        echo=settings.DB_ECHO,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 2}
    )

def check_db_connection() -> Dict[str, Any]:
    """
    Checks PostgreSQL/PostGIS connectivity.
    If database server is offline (e.g. Docker not started), returns informative diagnostic status.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            return {"connected": True, "error": None}
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "recommendation": "PostgreSQL/PostGIS is currently unreachable. Start the container via 'docker compose -f docker/docker-compose.yml up -d' if Docker is installed."
        }
