"""
RQ Background Worker & Redis Job Dispatcher
"""

import sys
from typing import Dict, Any, Optional
import redis
from rq import Queue, Worker
from backend.app.config import settings

def get_redis_connection() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL, socket_timeout=2)

def check_redis_connection() -> Dict[str, Any]:
    try:
        r = get_redis_connection()
        r.ping()
        return {"connected": True, "error": None}
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "recommendation": "Redis service is unreachable. Start Redis container or service to enable asynchronous worker queues."
        }

def get_queue() -> Optional[Queue]:
    try:
        r = get_redis_connection()
        r.ping()
        return Queue(settings.RQ_QUEUE_NAME, connection=r)
    except Exception:
        return None

def start_worker():
    """
    Starts an RQ worker listening on satquery_tasks.
    Run this via: python -m backend.app.worker
    """
    r = get_redis_connection()
    print(f"Starting SatQuery RQ Worker listening on: '{settings.RQ_QUEUE_NAME}'...")
    worker = Worker([settings.RQ_QUEUE_NAME], connection=r)
    worker.work()

if __name__ == "__main__":
    start_worker()
