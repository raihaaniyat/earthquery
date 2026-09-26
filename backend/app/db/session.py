"""
Database Engine and Session Configuration.
Supports PostgreSQL/PostGIS in production and graceful fallbacks for testing and diagnostics.
"""

from typing import Generator, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.ext.compiler import compiles
from geoalchemy2 import Geometry
from geoalchemy2.types import _GISType
import geoalchemy2.admin.dialects.sqlite as sqlite_admin
from sqlalchemy.schema import CreateIndex

# Enable seamless SQLite testing and fallback when SpatiaLite is absent
@compiles(Geometry, "sqlite")
def compile_geometry_sqlite(type_, compiler, **kw):
    return "BLOB"

@compiles(CreateIndex, "sqlite")
def compile_create_index_sqlite(element, compiler, **kw):
    for col in element.element.columns:
        if isinstance(getattr(col, "type", None), Geometry):
            return "-- skipped spatial index on sqlite"
    return compiler.visit_create_index(element, **kw)

sqlite_admin.after_create = lambda *args, **kwargs: None
sqlite_admin.before_create = lambda *args, **kwargs: None
_GISType.bind_expression = lambda self, b: b
_GISType.column_expression = lambda self, col: col

from backend.app.config import settings


Base = declarative_base()

def get_engine():
    """Create and configure SQLAlchemy engine with pre-ping and connection timeouts."""
    connect_args = {}
    if "postgresql" in settings.DATABASE_URL:
        connect_args["connect_timeout"] = 2
    
    return create_engine(
        settings.DATABASE_URL,
        echo=settings.DB_ECHO,
        pool_pre_ping=True,
        connect_args=connect_args
    )

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a request-scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_db_connection() -> Dict[str, Any]:
    """Test connectivity to PostgreSQL/PostGIS."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            has_postgis = False
            try:
                gis_ver = conn.execute(text("SELECT PostGIS_Full_Version()")).scalar()
                has_postgis = True
            except Exception:
                gis_ver = None
            return {
                "connected": True,
                "postgis_enabled": has_postgis,
                "postgis_version": gis_ver,
                "error": None
            }
    except Exception as e:
        return {
            "connected": False,
            "postgis_enabled": False,
            "error": str(e),
            "recommendation": "PostgreSQL/PostGIS is unreachable. Launch containers via 'docker compose -f docker/docker-compose.yml up -d' if Docker is installed."
        }
