#!/usr/bin/env python3
"""
RQ Worker for processing background tasks

Usage:
    python worker.py [--scheduler]

Options:
    --scheduler    Start the campaign scheduler instead of RQ worker

This will start a worker that listens for tasks in campaign queues.
"""

import sys
from rq import Worker
from queue_config import get_redis_connection
from routes.utils.postgres_connection import get_db
from logger_config import worker_logger


def start_rq_worker():
    """Start the RQ worker for processing campaign tasks"""
    redis_conn = get_redis_connection()

    # RQ worker only handles setup tasks now - execution is handled by scheduler
    queues = [
        "campaign_get_all_followers",
    ]

    worker = Worker(queues, connection=redis_conn)
    worker_logger.info(
        f"RQ Worker started. Listening for tasks on queues: {', '.join(queues)}"
    )
    worker_logger.info("Press Ctrl+C to exit")
    worker.work()


def start_scheduler():
    """Start the campaign scheduler"""
    from campaign_scheduler import start_campaign_scheduler

    start_campaign_scheduler()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--scheduler":
        worker_logger.info("Starting Campaign Scheduler...")
        start_scheduler()
    else:
        worker_logger.info("Starting RQ Worker...")
        start_rq_worker()
