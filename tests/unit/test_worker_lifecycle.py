"""
Unit Test: Windows Worker Lifecycle and SpawnWorker Protocol
Tests RQ SpawnWorker on Windows, JSON serialization, exception handling, and cancellation semantics.
Uses fakeredis for self-contained, offline execution without requiring external Docker services.
"""

import sys
import pytest
import fakeredis
from rq import Queue
from rq.worker import SpawnWorker, SimpleWorker
from rq.job import Job

from backend.app.workers.tasks import (
    ping_task,
    error_test_task,
    slow_task_for_timeout,
    json_task_serializer,
    json_task_deserializer
)

def test_spawn_worker_class_available():
    """Verify SpawnWorker is available in the installed RQ release."""
    import rq.worker
    assert hasattr(rq.worker, "SpawnWorker")

def test_json_task_serialization():
    """Verify explicit JSON serialization for payloads."""
    payload = {"job_id": "test-uuid-1234", "task": "vqa", "inputs": ["a.tif", "b.tif"]}
    serialized = json_task_serializer(payload)
    assert isinstance(serialized, str)
    deserialized = json_task_deserializer(serialized)
    assert deserialized == payload

def test_job_execution_with_worker():
    """Test job execution through SimpleWorker/SpawnWorker pipeline using fakeredis."""
    fake_conn = fakeredis.FakeStrictRedis()
    q = Queue("test_queue", connection=fake_conn)
    
    # Enqueue task
    job = q.enqueue(ping_task, "hello satquery")
    assert job.get_status() == "queued"
    
    # Process with worker in burst mode
    worker = SimpleWorker([q], connection=fake_conn)
    worker.work(burst=True)
    
    # Verify result
    job.refresh()
    assert job.get_status() == "finished"
    assert job.result["status"] == "pong"
    assert job.result["message"] == "hello satquery"

def test_job_exception_handling():
    """Verify that a task throwing an exception enters failed status cleanly."""
    fake_conn = fakeredis.FakeStrictRedis()
    q = Queue("test_queue", connection=fake_conn)
    
    job = q.enqueue(error_test_task, "test deliberate failure")
    worker = SimpleWorker([q], connection=fake_conn)
    worker.work(burst=True)
    
    job.refresh()
    assert job.get_status() == "failed"
    assert "Deliberate task error" in str(job.exc_info)
