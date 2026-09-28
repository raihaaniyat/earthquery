"""
SatQuery Database Package
Exports SQLAlchemy models, session factory, engine, and connection health utilities.
"""

from backend.app.db.session import Base, SessionLocal, get_db, get_engine, engine, check_db_connection
from backend.app.db.models import (
    User, ApiToken, Project, ProjectMember, Scene, Asset, SceneQuality,
    ScenePair, DatasetVersion, ModelVersion, AnalysisJob, JobInput,
    ExecutionStep, ExecutionStepAsset, Finding, FindingEvidence, Report,
    OutboxEvent, JobEvent, ExternalDataSource, ExternalMapLayer, ExternalContextRecord,
    Conversation, ConversationMessage, ConversationTurn, ConversationDataset, ConversationResult
)

__all__ = [
    "Base",
    "SessionLocal",
    "get_db",
    "get_engine",
    "engine",
    "check_db_connection",
    "User",
    "ApiToken",
    "Project",
    "ProjectMember",
    "Scene",
    "Asset",
    "SceneQuality",
    "ScenePair",
    "DatasetVersion",
    "ModelVersion",
    "AnalysisJob",
    "JobInput",
    "ExecutionStep",
    "ExecutionStepAsset",
    "Finding",
    "FindingEvidence",
    "Report",
    "OutboxEvent",
    "JobEvent",
    "ExternalDataSource",
    "ExternalMapLayer",
    "ExternalContextRecord",
    "Conversation",
    "ConversationMessage",
    "ConversationTurn",
    "ConversationDataset",
    "ConversationResult",
]

