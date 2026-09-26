"""
Windows RQ SpawnWorker Runner for SatQuery AI.
Usage: python -m backend.app.workers.runner --queues satquery-ingest satquery-analysis
"""

import sys
import argparse
import logging
from redis import Redis
from rq.worker import SimpleWorker
from backend.app.config import get_settings, settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(process)d) %(name)s: %(message)s"
)
logger = logging.getLogger("satquery.worker.runner")

def main():
    parser = argparse.ArgumentParser(description="Run SatQuery Worker on Windows")
    parser.add_argument("--queues", nargs="+", default=["satquery-ingest", "satquery-analysis"], help="Queue names to listen on")
    parser.add_argument("--name", type=str, default=None, help="Worker name")
    args = parser.parse_args()

    s = get_settings()
    logger.info(f"Connecting worker to Redis at {s.REDIS_URL}...")
    
    try:
        redis_conn = Redis.from_url(s.REDIS_URL)
        redis_conn.ping()
        logger.info(f"Redis connection established successfully.")
    except Exception as e:
        logger.error(f"Cannot connect to Redis at {s.REDIS_URL}: {e}")
        sys.exit(1)

    if args.name:
        try:
            key = f"rq:worker:{args.name}"
            if redis_conn.exists(key):
                logger.info(f"Purging stale registration for '{args.name}' from Redis...")
                redis_conn.delete(key)
                redis_conn.srem("rq:workers", args.name)
                for q_name in args.queues:
                    redis_conn.srem(f"rq:workers:{q_name}", args.name)
        except Exception as e:
            logger.warning(f"Could not clean stale worker key: {e}")

    logger.info(f"Starting SimpleWorker (Windows-native) listening on queues: {args.queues}...")
    worker = SimpleWorker(args.queues, connection=redis_conn, name=args.name)
    worker.work()

if __name__ == "__main__":
    main()
