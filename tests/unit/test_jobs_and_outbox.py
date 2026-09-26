"""
Unit tests for Job Lifecycle, Idempotency, Outbox Dispatch, and Lease Recovery.
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.session import Base
from backend.app.db.models import User, Project, AnalysisJob, OutboxEvent, JobEvent
from backend.app.services.jobs import JobService, ConflictError
from backend.app.services.recovery import ReconciliationService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    user = User(id="user-1", email="dev@satquery.local", hashed_password="pw")
    project = Project(id="proj-1", owner_id="user-1", name="Test Project")
    session.add_all([user, project])
    session.commit()

    yield session
    session.close()


def test_job_creation_and_idempotency(db_session):
    canonical_req = {"task": "vqa", "image_id": "img-1", "prompt": "Identify features"}
    idemp_key = "idemp-key-12345"

    # 1. Create Job
    job, created = JobService.create_job(
        db=db_session,
        project_id="proj-1",
        task_type="vqa",
        canonical_request=canonical_req,
        idempotency_key=idemp_key
    )

    assert created is True
    assert job.status == "queued"
    assert job.idempotency_key == idemp_key

    # Check that outbox event was created
    outbox_events = db_session.query(OutboxEvent).filter(OutboxEvent.aggregate_id == job.id).all()
    assert len(outbox_events) == 1
    assert outbox_events[0].event_type == "JOB_CREATED"

    # 2. Resubmit with identical request -> must return existing job
    job2, created2 = JobService.create_job(
        db=db_session,
        project_id="proj-1",
        task_type="vqa",
        canonical_request=canonical_req,
        idempotency_key=idemp_key
    )
    assert created2 is False
    assert job2.id == job.id

    # 3. Resubmit with altered request -> must raise ConflictError
    different_req = {"task": "vqa", "image_id": "img-DIFFERENT", "prompt": "Changed"}
    with pytest.raises(ConflictError):
        JobService.create_job(
            db=db_session,
            project_id="proj-1",
            task_type="vqa",
            canonical_request=different_req,
            idempotency_key=idemp_key
        )


def test_job_claim_and_heartbeat(db_session):
    job, _ = JobService.create_job(
        db=db_session,
        project_id="proj-1",
        task_type="bitemporal_change",
        canonical_request={"pair_id": "pair-1"}
    )

    # Worker 1 claims job
    claimed = JobService.claim_job(db_session, job.id, worker_id="worker-node-1", lease_seconds=60)
    assert claimed is not None
    assert claimed.status == "running"
    assert claimed.lease_holder == "worker-node-1"

    # Worker 2 attempts to claim active job -> must return None
    claimed_again = JobService.claim_job(db_session, job.id, worker_id="worker-node-2", lease_seconds=60)
    assert claimed_again is None

    # Worker 1 sends heartbeat
    hb_ok = JobService.heartbeat(db_session, job.id, worker_id="worker-node-1", lease_seconds=120)
    assert hb_ok is True


def test_job_cancellation(db_session):
    job, _ = JobService.create_job(
        db=db_session,
        project_id="proj-1",
        task_type="vqa",
        canonical_request={"test": "data"}
    )
    # Cancel queued job
    cancelled = JobService.cancel_job(db_session, "proj-1", job.id)
    assert cancelled.status == "cancelled"


def test_reconciliation_recovers_expired_lease(db_session):
    job, _ = JobService.create_job(
        db=db_session,
        project_id="proj-1",
        task_type="vqa",
        canonical_request={"test": "data"}
    )
    # Claim and simulate expired lease in past
    job.status = "running"
    job.lease_holder = "dead-worker"
    job.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    db_session.commit()

    recovered = ReconciliationService.reconcile_expired_leases(db_session, max_retries=3)
    assert recovered == 1

    db_session.refresh(job)
    assert job.status == "retry_wait"
    assert job.current_attempt == 2
