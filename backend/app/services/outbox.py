"""
Transactional Outbox Dispatcher.
Polls committed events from `outbox_events` and delivers them to Redis queues,
guaranteeing at-least-once message delivery and decoupling DB transactions from network messaging.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
import redis
from rq import Queue

from backend.app.config import settings
from backend.app.db.models import OutboxEvent
from backend.app.workers.tasks import execute_analysis_task, execute_ingest_task

logger = logging.getLogger("satquery.services.outbox")


class OutboxDispatcher:
    def __init__(self):
        self.redis_conn: Optional[redis.Redis] = None

    def get_redis(self) -> Optional[redis.Redis]:
        if self.redis_conn is None:
            try:
                r = redis.from_url(settings.REDIS_URL, socket_timeout=2)
                r.ping()
                self.redis_conn = r
            except Exception as e:
                logger.debug(f"Redis not reachable for outbox dispatch: {e}")
                self.redis_conn = None
        return self.redis_conn

    def process_pending_events(self, db: Session, batch_size: int = 50) -> int:
        """
        Polls undelivered outbox events and pushes them to the corresponding RQ queues.
        Returns the number of successfully dispatched events.
        """
        now = datetime.now(timezone.utc)
        events = db.query(OutboxEvent).filter(
            OutboxEvent.delivered_at.is_(None),
            OutboxEvent.delivery_attempts < OutboxEvent.max_attempts,
            (OutboxEvent.next_attempt_at.is_(None) | (OutboxEvent.next_attempt_at <= now))
        ).order_by(OutboxEvent.created_at.asc()).limit(batch_size).all()

        if not events:
            return 0

        r = self.get_redis()
        dispatched_count = 0

        for ev in events:
            ev.delivery_attempts += 1
            ev.last_attempt_at = now

            if r is None:
                # Redis unavailable; backoff
                ev.next_attempt_at = now + timedelta(seconds=min(30 * (2 ** ev.delivery_attempts), 300))
                continue

            try:
                payload = json.loads(ev.payload_json)
                if ev.event_type in ("JOB_CREATED", "JOB_RETRY"):
                    q = Queue(settings.REDIS_QUEUE_ANALYSIS, connection=r)
                    q.enqueue(execute_analysis_task, ev.payload_json)
                elif ev.event_type == "SCENE_INGESTION_REQUESTED":
                    q = Queue(settings.REDIS_QUEUE_INGEST, connection=r)
                    q.enqueue(execute_ingest_task, ev.payload_json)

                ev.delivered_at = datetime.now(timezone.utc)
                dispatched_count += 1
            except Exception as e:
                logger.error(f"Failed to dispatch outbox event {ev.id}: {e}")
                ev.next_attempt_at = now + timedelta(seconds=min(10 * (2 ** ev.delivery_attempts), 300))

        db.commit()
        return dispatched_count


outbox_dispatcher = OutboxDispatcher()
